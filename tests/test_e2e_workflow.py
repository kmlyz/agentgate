"""End-to-End (E2E) Full Lifecycle Integration Tests for AgentGate.

Validates the complete workflow lifecycle from natural language prompt,
deterministic reasoning extraction, persistent proposal staging, HITL approval gate,
to polymorphic Git execution and audit tracking across multiple CLI invocations.
"""

import re
from pathlib import Path

import pytest
from click.testing import CliRunner

from agentgate.cli.cli_operator_entrypoint import (
    cli,
    set_cli_reasoning_engine,
)
from agentgate.guardrails.adapters.git import BranchType
from agentgate.guardrails.core import ApprovalGate, ProposalStatus
from agentgate.reasoning import MockReasoningEngine
from blueprints.verified_github_agent.agent import TaskSpecification


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
# 1. Full Lifecycle Happy Path
# ============================================================================


def test_e2e_full_lifecycle_happy_path(cli_runner: CliRunner, temp_storage: Path):
    """E2E Test: Natural language prompt -> Staging -> Gate Block -> Approve -> Execute -> Audit.

    Verifies the entire lifecycle of a 3-stage workflow (Branch, Commit, PR)
    across isolated CLI calls with atomic disk state persistence.
    """
    prompt = "feat(checkout): implement payment gateway integration for PAY-101"

    # Step 1: Natural language planning & proposal staging
    res_plan = cli_runner.invoke(
        cli,
        [
            "plan",
            prompt,
            "--engine",
            "mock",
            "--storage-path",
            str(temp_storage),
        ],
    )
    assert res_plan.exit_code == 0, f"Plan failed: {res_plan.output}"
    assert "WORKFLOW PROPOSALS STAGED SUCCESSFULLY" in res_plan.output
    assert "Status: ALL STAGES PENDING_APPROVAL" in res_plan.output

    # Extract proposal IDs using regex
    branch_match = re.search(r"\[1\] BRANCH:\s+\[(prop_[a-f0-9]+)\]", res_plan.output)
    commit_match = re.search(r"\[2\] COMMIT:\s+\[(prop_[a-f0-9]+)\]", res_plan.output)
    pr_match = re.search(r"\[3\] PR:\s+\[(prop_[a-f0-9]+)\]", res_plan.output)

    assert branch_match, "Branch proposal ID not found in plan output"
    assert commit_match, "Commit proposal ID not found in plan output"
    assert pr_match, "PR proposal ID not found in plan output"

    branch_id = branch_match.group(1)
    commit_id = commit_match.group(1)
    pr_id = pr_match.group(1)

    # Step 2: Verify all proposals are staged as PENDING_APPROVAL
    res_list = cli_runner.invoke(cli, ["proposals", "list", "--storage-path", str(temp_storage)])
    assert res_list.exit_code == 0
    assert "Staged Proposals (3 total):" in res_list.output
    assert f"[{branch_id}] Status: PENDING_APPROVAL" in res_list.output
    assert f"[{commit_id}] Status: PENDING_APPROVAL" in res_list.output
    assert f"[{pr_id}] Status: PENDING_APPROVAL" in res_list.output

    # Step 3: Defensive HITL Gate check: Execution MUST be blocked before human approval
    res_blocked = cli_runner.invoke(
        cli,
        ["execute", branch_id, "--storage-path", str(temp_storage)],
    )
    assert res_blocked.exit_code == 1
    assert f"Execution Blocked: Proposal '{branch_id}' is in status 'PENDING_APPROVAL'" in res_blocked.output
    assert "Prior human approval is strictly required." in res_blocked.output

    # Step 4: Human-in-the-Loop Approval for all stages
    for pid in (branch_id, commit_id, pr_id):
        res_app = cli_runner.invoke(cli, ["approve", pid, "--storage-path", str(temp_storage)])
        assert res_app.exit_code == 0
        assert f"Proposal '{pid}' APPROVED." in res_app.output

    # Step 5: Sequential Polymorphic Deterministic Execution (Dry-Run Mode)
    # Stage 1: Branch
    res_exec_branch = cli_runner.invoke(
        cli,
        ["execute", branch_id, "--dry-run", "--storage-path", str(temp_storage)],
    )
    assert res_exec_branch.exit_code == 0
    assert "[EXECUTED] BRANCH CREATION executed successfully." in res_exec_branch.output

    # Stage 2: Commit
    res_exec_commit = cli_runner.invoke(
        cli,
        ["execute", commit_id, "--dry-run", "--storage-path", str(temp_storage)],
    )
    assert res_exec_commit.exit_code == 0
    assert "[EXECUTED] COMMIT executed successfully." in res_exec_commit.output

    # Stage 3: Pull Request
    res_exec_pr = cli_runner.invoke(
        cli,
        ["execute", pr_id, "--dry-run", "--storage-path", str(temp_storage)],
    )
    assert res_exec_pr.exit_code == 0
    assert "[EXECUTED] PULL REQUEST executed successfully." in res_exec_pr.output

    # Step 6: Verify final persistent state and audit log
    # Default list should now show 0 pending proposals
    res_list_pending = cli_runner.invoke(
        cli,
        ["proposals", "list", "--storage-path", str(temp_storage)],
    )
    assert res_list_pending.exit_code == 0
    assert "No pending proposals awaiting approval." in res_list_pending.output

    # Full audit list (--all) should show all 3 proposals with EXECUTED status
    res_list_all = cli_runner.invoke(
        cli,
        ["proposals", "list", "--all", "--storage-path", str(temp_storage)],
    )
    assert res_list_all.exit_code == 0
    assert "Staged Proposals (3 total):" in res_list_all.output
    assert f"[{branch_id}] Status: EXECUTED" in res_list_all.output
    assert f"[{commit_id}] Status: EXECUTED" in res_list_all.output
    assert f"[{pr_id}] Status: EXECUTED" in res_list_all.output


# ============================================================================
# 2. Operator Rejection Lifecycle
# ============================================================================


def test_e2e_operator_rejection_lifecycle(cli_runner: CliRunner, temp_storage: Path):
    """E2E Test: Partial approval and rejection handling.

    Verifies that rejected proposals cannot be executed and keep their rejection reasons.
    """
    prompt = "chore(deps): bump pydantic dependency for SEC-999"

    # Stage workflow
    res_plan = cli_runner.invoke(
        cli,
        ["plan", prompt, "--engine", "mock", "--storage-path", str(temp_storage)],
    )
    assert res_plan.exit_code == 0

    branch_match = re.search(r"\[1\] BRANCH:\s+\[(prop_[a-f0-9]+)\]", res_plan.output)
    commit_match = re.search(r"\[2\] COMMIT:\s+\[(prop_[a-f0-9]+)\]", res_plan.output)
    assert branch_match and commit_match

    branch_id = branch_match.group(1)
    commit_id = commit_match.group(1)

    # Approve Branch
    res_app = cli_runner.invoke(cli, ["approve", branch_id, "--storage-path", str(temp_storage)])
    assert res_app.exit_code == 0

    # Reject Commit with specific reason
    rejection_reason = "Dependency bump requires prior security vulnerability assessment"
    res_rej = cli_runner.invoke(
        cli,
        [
            "reject",
            commit_id,
            "--reason",
            rejection_reason,
            "--storage-path",
            str(temp_storage),
        ],
    )
    assert res_rej.exit_code == 0
    assert f"Proposal '{commit_id}' REJECTED." in res_rej.output
    assert rejection_reason in res_rej.output

    # Attempt to execute rejected proposal -> MUST be blocked
    res_exec_rej = cli_runner.invoke(
        cli,
        ["execute", commit_id, "--dry-run", "--storage-path", str(temp_storage)],
    )
    assert res_exec_rej.exit_code == 1
    assert "Execution Blocked:" in res_exec_rej.output
    assert "REJECTED" in res_exec_rej.output

    # Authorized Branch executes cleanly
    res_exec_br = cli_runner.invoke(
        cli,
        ["execute", branch_id, "--dry-run", "--storage-path", str(temp_storage)],
    )
    assert res_exec_br.exit_code == 0
    assert "[EXECUTED] BRANCH CREATION executed successfully." in res_exec_br.output

    # Check persistence audit
    gate = ApprovalGate(storage_path=temp_storage)
    record = gate.get_record(commit_id)
    assert record is not None
    assert record.status == ProposalStatus.REJECTED
    assert record.rejection_reason == rejection_reason


# ============================================================================
# 3. Custom Reasoning Engine Injection
# ============================================================================


def test_e2e_custom_reasoning_engine_injection(cli_runner: CliRunner, temp_storage: Path):
    """E2E Test: Injection of custom reasoning model and target branch customization."""
    custom_spec = TaskSpecification(
        branch_type=BranchType.FEAT,
        branch_name="custom-billing-engine",
        scope="billing",
        summary="integrate stripe webhook dispatcher",
        base_branch="develop",
        ticket_id="BILL-404",
    )
    custom_engine = MockReasoningEngine(default_response=custom_spec)
    set_cli_reasoning_engine(custom_engine)

    res_plan = cli_runner.invoke(
        cli,
        [
            "plan",
            "Natural language input that will be handled by custom engine",
            "--storage-path",
            str(temp_storage),
        ],
    )
    assert res_plan.exit_code == 0
    assert "git checkout -b feat/custom-billing-engine-bill-404 develop" in res_plan.output
    assert "feat(billing): integrate stripe webhook dispatcher [BILL-404]" in res_plan.output
    assert "(feat/custom-billing-engine-bill-404 -> develop)" in res_plan.output

    # Extract branch ID and approve
    branch_match = re.search(r"\[1\] BRANCH:\s+\[(prop_[a-f0-9]+)\]", res_plan.output)
    assert branch_match
    branch_id = branch_match.group(1)

    cli_runner.invoke(cli, ["approve", branch_id, "--storage-path", str(temp_storage)])
    res_exec = cli_runner.invoke(
        cli,
        ["execute", branch_id, "--dry-run", "--storage-path", str(temp_storage)],
    )
    assert res_exec.exit_code == 0
    assert "[EXECUTED] BRANCH CREATION executed successfully." in res_exec.output
    assert "feat/custom-billing-engine-bill-404" in res_exec.output


# ============================================================================
# 4. Corrupted Storage Resilience
# ============================================================================


def test_e2e_corrupted_storage_resilience(cli_runner: CliRunner, tmp_path: Path):
    """E2E Test: Resilience against corrupted or malformed storage files."""
    broken_file = tmp_path / "corrupted_registry.json"
    broken_file.write_text("{ this is malformed JSON content that cannot be parsed", encoding="utf-8")

    # List proposals on corrupted file should safely fallback to empty state without crash
    res_list = cli_runner.invoke(
        cli,
        ["proposals", "list", "--storage-path", str(broken_file)],
    )
    assert res_list.exit_code == 0
    assert "No pending proposals awaiting approval." in res_list.output

    # Attempt to approve on corrupted/empty state returns controlled not-found error
    res_app = cli_runner.invoke(
        cli,
        ["approve", "prop_nonexistent", "--storage-path", str(broken_file)],
    )
    assert res_app.exit_code == 1
    assert "Error: Proposal ID 'prop_nonexistent' was not found." in res_app.output
