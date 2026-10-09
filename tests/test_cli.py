"""Comprehensive unit and integration test suite for AgentGate Operator CLI.

Tests command line argument parsing, natural language workflow planning,
polymorphic proposal listing, HITL approval/rejection lifecycle,
and deterministic execution routing using Click CliRunner.
"""

from pathlib import Path

import pytest
from click.testing import CliRunner

from agentgate.cli.cli_operator_entrypoint import (
    cli,
    set_cli_reasoning_engine,
)
from agentgate.guardrails.core import ApprovalGate, ProposalStatus
from agentgate.reasoning import MockReasoningEngine, ReasoningError


@pytest.fixture(autouse=True)
def reset_cli_state():
    """Ensure clean CLI mock state before and after each test."""
    set_cli_reasoning_engine(None)
    yield
    set_cli_reasoning_engine(None)


@pytest.fixture
def cli_runner() -> CliRunner:
    """Fixture providing Click CLI test runner."""
    return CliRunner()


@pytest.fixture
def temp_storage(tmp_path: Path) -> Path:
    """Fixture providing an isolated temporary storage JSON path."""
    return tmp_path / "proposals.json"


# ============================================================================
# 1. Command: agentgate plan
# ============================================================================


def test_cli_plan_command_with_mock_engine(cli_runner: CliRunner, temp_storage: Path):
    result = cli_runner.invoke(
        cli,
        [
            "plan",
            "AUTH-101: implement oauth2 token rotation in auth module",
            "--engine",
            "mock",
            "--storage-path",
            str(temp_storage),
        ],
    )
    assert result.exit_code == 0, f"CLI command failed with: {result.output}"
    assert "WORKFLOW PROPOSALS STAGED SUCCESSFULLY" in result.output
    assert "[1] BRANCH:" in result.output
    assert "[2] COMMIT:" in result.output
    assert "[3] PR:" in result.output
    assert "Status: ALL STAGES PENDING_APPROVAL" in result.output

    # Verify that proposals were atomically written to the temporary storage
    gate = ApprovalGate(storage_path=temp_storage)
    pending = gate.list_pending()
    assert len(pending) == 3


def test_cli_plan_command_with_injected_reasoning_engine(cli_runner: CliRunner, temp_storage: Path):
    custom_spec = {
        "branch_type": "refactor",
        "branch_name": "clean-gate",
        "scope": "gate",
        "summary": "refactor gate state transitions",
        "ticket_id": "GATE-50",
        "base_branch": "main",
    }
    set_cli_reasoning_engine(MockReasoningEngine(default_response=custom_spec))

    result = cli_runner.invoke(
        cli,
        [
            "plan",
            "refactor gate state machine",
            "--storage-path",
            str(temp_storage),
        ],
    )
    assert result.exit_code == 0
    assert "refactor(gate): refactor gate state transitions" in result.output

    gate = ApprovalGate(storage_path=temp_storage)
    pending = gate.list_pending()
    assert len(pending) == 3
    assert any("refactor/clean-gate" in rec.rendered_message for rec in pending)


def test_cli_plan_reasoning_failure_handling(cli_runner: CliRunner, temp_storage: Path):
    set_cli_reasoning_engine(MockReasoningEngine(raise_error=ReasoningError("Model connection timeout")))

    result = cli_runner.invoke(
        cli,
        [
            "plan",
            "add feature",
            "--storage-path",
            str(temp_storage),
        ],
    )
    assert result.exit_code != 0
    assert "Error: Reasoning failed: Model connection timeout" in result.output


# ============================================================================
# 2. Command: agentgate proposals list
# ============================================================================


def test_cli_proposals_list_empty(cli_runner: CliRunner, temp_storage: Path):
    result = cli_runner.invoke(cli, ["proposals", "list", "--storage-path", str(temp_storage)])
    assert result.exit_code == 0
    assert "No pending proposals awaiting approval." in result.output


def test_cli_proposals_list_polymorphic(cli_runner: CliRunner, temp_storage: Path):
    # Stage proposals first using plan
    cli_runner.invoke(
        cli,
        [
            "plan",
            "CORE-42: add telemetry handler",
            "--engine",
            "mock",
            "--storage-path",
            str(temp_storage),
        ],
    )

    result = cli_runner.invoke(cli, ["proposals", "list", "--storage-path", str(temp_storage)])
    assert result.exit_code == 0
    assert "Staged Proposals (3 total):" in result.output
    assert "[BRANCH]" in result.output
    assert "[COMMIT]" in result.output
    assert "[PR]" in result.output
    assert "PENDING_APPROVAL" in result.output


# ============================================================================
# 3. Commands: agentgate approve & reject
# ============================================================================


def test_cli_approve_and_reject_flow(cli_runner: CliRunner, temp_storage: Path):
    # Stage proposals
    cli_runner.invoke(
        cli,
        [
            "plan",
            "AUTH-200: add jwt validation",
            "--engine",
            "mock",
            "--storage-path",
            str(temp_storage),
        ],
    )

    gate = ApprovalGate(storage_path=temp_storage)
    pending = gate.list_pending()
    prop1_id = pending[0].proposal_id
    prop2_id = pending[1].proposal_id

    # Approve prop1
    app_res = cli_runner.invoke(cli, ["approve", prop1_id, "--storage-path", str(temp_storage)])
    assert app_res.exit_code == 0
    assert f"[OK] Proposal '{prop1_id}' APPROVED." in app_res.output

    # Verify status changed in gate
    gate_reloaded = ApprovalGate(storage_path=temp_storage)
    assert gate_reloaded.get_record(prop1_id).status == ProposalStatus.APPROVED

    # Reject prop2
    rej_res = cli_runner.invoke(
        cli,
        ["reject", prop2_id, "--reason", "Insufficient testing", "--storage-path", str(temp_storage)],
    )
    assert rej_res.exit_code == 0
    assert f"[REJECTED] Proposal '{prop2_id}' REJECTED." in rej_res.output
    assert "Insufficient testing" in rej_res.output

    gate_reloaded_2 = ApprovalGate(storage_path=temp_storage)
    assert gate_reloaded_2.get_record(prop2_id).status == ProposalStatus.REJECTED


def test_cli_approve_non_existent_proposal(cli_runner: CliRunner, temp_storage: Path):
    result = cli_runner.invoke(cli, ["approve", "prop_nonexistent_xyz", "--storage-path", str(temp_storage)])
    assert result.exit_code != 0
    assert "Error: Proposal ID 'prop_nonexistent_xyz' was not found." in result.output


# ============================================================================
# 4. Command: agentgate execute
# ============================================================================


def test_cli_execute_blocked_without_approval(cli_runner: CliRunner, temp_storage: Path):
    # Stage proposal
    cli_runner.invoke(
        cli,
        [
            "plan",
            "BUG-10: fix memory leak",
            "--engine",
            "mock",
            "--storage-path",
            str(temp_storage),
        ],
    )

    gate = ApprovalGate(storage_path=temp_storage)
    prop_id = gate.list_pending()[0].proposal_id

    # Attempt to execute while in PENDING_APPROVAL
    exec_res = cli_runner.invoke(cli, ["execute", prop_id, "--dry-run", "--storage-path", str(temp_storage)])
    assert exec_res.exit_code != 0
    assert "Execution Blocked:" in exec_res.output
    assert "Prior human approval is strictly required" in exec_res.output


def test_cli_execute_approved_proposals_polymorphic(cli_runner: CliRunner, temp_storage: Path):
    # Stage proposals
    cli_runner.invoke(
        cli,
        [
            "plan",
            "SEC-99: add security headers",
            "--engine",
            "mock",
            "--storage-path",
            str(temp_storage),
        ],
    )

    gate = ApprovalGate(storage_path=temp_storage)
    records = gate.list_pending()
    assert len(records) == 3

    branch_id = records[0].proposal_id
    commit_id = records[1].proposal_id
    pr_id = records[2].proposal_id

    # 1. Approve & Execute Branch
    cli_runner.invoke(cli, ["approve", branch_id, "--storage-path", str(temp_storage)])
    exec_b = cli_runner.invoke(cli, ["execute", branch_id, "--dry-run", "--storage-path", str(temp_storage)])
    assert exec_b.exit_code == 0
    assert "[EXECUTED] BRANCH CREATION executed successfully." in exec_b.output
    assert "[DRY_RUN]" in exec_b.output

    # 2. Approve & Execute Commit
    cli_runner.invoke(cli, ["approve", commit_id, "--storage-path", str(temp_storage)])
    exec_c = cli_runner.invoke(cli, ["execute", commit_id, "--dry-run", "--storage-path", str(temp_storage)])
    assert exec_c.exit_code == 0
    assert "[EXECUTED] COMMIT executed successfully." in exec_c.output
    assert "[DRY_RUN]" in exec_c.output

    # 3. Approve & Execute PR
    cli_runner.invoke(cli, ["approve", pr_id, "--storage-path", str(temp_storage)])
    exec_pr = cli_runner.invoke(cli, ["execute", pr_id, "--dry-run", "--storage-path", str(temp_storage)])
    assert exec_pr.exit_code == 0
    assert "[EXECUTED] PULL REQUEST executed successfully." in exec_pr.output
    assert "[DRY_RUN]" in exec_pr.output

    # Verify all records reached EXECUTED state in storage
    gate_final = ApprovalGate(storage_path=temp_storage)
    assert gate_final.get_record(branch_id).status == ProposalStatus.EXECUTED
    assert gate_final.get_record(commit_id).status == ProposalStatus.EXECUTED
    assert gate_final.get_record(pr_id).status == ProposalStatus.EXECUTED


def test_cli_execute_non_existent_proposal(cli_runner: CliRunner, temp_storage: Path):
    result = cli_runner.invoke(cli, ["execute", "prop_nonexistent_xyz", "--dry-run", "--storage-path", str(temp_storage)])
    assert result.exit_code != 0
    assert "Error: Proposal ID 'prop_nonexistent_xyz' was not found." in result.output
