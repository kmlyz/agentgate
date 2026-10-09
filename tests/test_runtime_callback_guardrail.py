"""Integration tests for Google ADK Runtime Guardrail Tool Callback."""

import asyncio

import pytest

from agentgate.guardrails.core.gate import ApprovalGate
from agentgate.guardrails.core.models import ProposalStatus
from agentgate.runtime import (
    RuntimeGuardrailToolCallback,
    intercept_runtime_callback_tool,
    validate_runtime_callback_payload,
)


@pytest.fixture
def callback_instance() -> RuntimeGuardrailToolCallback:
    """Provides an isolated RuntimeGuardrailToolCallback instance with in-memory storage."""
    gate = ApprovalGate(storage_path=None)
    return RuntimeGuardrailToolCallback(approval_gate=gate)


class TestRuntimeCallbackProposalFlow:
    """Tests proposal interception, validation, and staging in ApprovalGate."""

    def test_valid_commit_proposal_staged_as_pending_approval(
        self, callback_instance: RuntimeGuardrailToolCallback
    ):
        payload = {
            "branch": "main",
            "commit_type": "feat",
            "scope": "runtime",
            "short_summary": "add adk guardrail callback",
            "ticket_id": "ADK-101",
        }
        result = callback_instance.intercept_runtime_tool_call(
            "propose_commit", payload
        )

        assert isinstance(result, dict)
        assert result["status"] == "pending_approval"
        assert "proposal_id" in result
        assert result["tool_name"] == "propose_commit"

        # Verify gate registry state
        record = callback_instance.approval_gate.get_record(result["proposal_id"])
        assert record is not None
        assert record.status == ProposalStatus.PENDING_APPROVAL
        assert (
            record.rendered_message
            == "feat(runtime): add adk guardrail callback [ADK-101]"
        )

    def test_valid_branch_and_pr_proposals_staged(
        self, callback_instance: RuntimeGuardrailToolCallback
    ):
        # Branch proposal
        branch_payload = {
            "branch_type": "feat",
            "branch_name": "adk-bridge",
            "base_branch": "main",
            "ticket_id": "ADK-200",
        }
        res_branch = callback_instance.intercept_runtime_tool_call(
            "propose_branch", branch_payload
        )
        assert res_branch["status"] == "pending_approval"
        rec_branch = callback_instance.approval_gate.get_record(
            res_branch["proposal_id"]
        )
        assert rec_branch.status == ProposalStatus.PENDING_APPROVAL
        assert (
            "git checkout -b feat/adk-bridge-adk-200 main"
            in rec_branch.rendered_message
        )

        # PR proposal
        pr_payload = {
            "title_type": "feat",
            "title_scope": "runtime",
            "title_summary": "introduce adk runtime bridge",
            "head_branch": "feat/adk-bridge-adk-200",
            "base_branch": "main",
            "ticket_id": "ADK-200",
        }
        res_pr = callback_instance.intercept_runtime_tool_call("propose_pr", pr_payload)
        assert res_pr["status"] == "pending_approval"
        rec_pr = callback_instance.approval_gate.get_record(res_pr["proposal_id"])
        assert rec_pr.status == ProposalStatus.PENDING_APPROVAL
        assert (
            "feat(runtime): introduce adk runtime bridge [ADK-200]"
            in rec_pr.rendered_message
        )


class TestRuntimeCallbackSecurityAndInjections:
    """Tests security invariants: extra-field injection blocking and rule violations."""

    def test_extra_fields_injection_blocked_by_pydantic_forbid(
        self, callback_instance: RuntimeGuardrailToolCallback
    ):
        malicious_payload = {
            "branch": "main",
            "commit_type": "feat",
            "scope": "core",
            "short_summary": "valid summary text",
            "unauthorized_field": "injected_command",
            "another_leak": 12345,
        }
        result = callback_instance.intercept_runtime_tool_call(
            "propose_commit", malicious_payload
        )

        assert isinstance(result, dict)
        assert result["status"] == "rejected"
        assert result["error"] == "REJECTED BY DETERMINISTIC GUARDRAIL"
        assert len(result["details"]) > 0
        assert any("extra" in d.lower() for d in result["details"])

        # Ensure nothing was staged in ApprovalGate
        assert len(callback_instance.approval_gate.list_pending()) == 0

    def test_banned_phrases_rejected(
        self, callback_instance: RuntimeGuardrailToolCallback
    ):
        banned_payload = {
            "branch": "main",
            "commit_type": "fix",
            "scope": "auth",
            "short_summary": "fix login (ai generated)",
        }
        result = callback_instance.intercept_runtime_tool_call(
            "propose_commit", banned_payload
        )

        assert result["status"] == "rejected"
        assert any("banned phrasing" in d.lower() for d in result["details"])
        assert len(callback_instance.approval_gate.list_pending()) == 0


class TestRuntimeCallbackMutationControl:
    """Tests blocking of unauthorized executions and enforcing Human-in-the-Loop approval."""

    def test_direct_execution_blocked_without_proposal_id(
        self, callback_instance: RuntimeGuardrailToolCallback
    ):
        result = callback_instance.intercept_runtime_tool_call(
            "execute_approved_proposal", {}
        )
        assert result["status"] == "blocked"
        assert (
            "cannot be invoked directly without an approved 'proposal_id'"
            in result["error"]
        )

    def test_execution_blocked_while_pending_approval(
        self, callback_instance: RuntimeGuardrailToolCallback
    ):
        # 1. Stage a proposal
        payload = {
            "branch": "main",
            "commit_type": "chore",
            "scope": "deps",
            "short_summary": "update dependencies",
        }
        res_submit = callback_instance.intercept_runtime_tool_call(
            "propose_commit", payload
        )
        prop_id = res_submit["proposal_id"]

        # 2. Try executing without operator approval
        res_exec = callback_instance.intercept_runtime_tool_call(
            "execute_approved_proposal", {"proposal_id": prop_id}
        )
        assert res_exec["status"] == "blocked"
        assert "status is 'pending_approval'" in res_exec["error"]

    def test_approved_proposal_executes_successfully(
        self, callback_instance: RuntimeGuardrailToolCallback
    ):
        # 1. Stage proposal
        payload = {
            "branch": "main",
            "commit_type": "docs",
            "scope": "readme",
            "short_summary": "update adk callback documentation",
        }
        res_submit = callback_instance.intercept_runtime_tool_call(
            "propose_commit", payload
        )
        prop_id = res_submit["proposal_id"]

        # 2. Operator explicitly approves
        callback_instance.approval_gate.approve(prop_id)

        # 3. Execution succeeds deterministically
        res_exec = callback_instance.intercept_runtime_tool_call(
            "execute_approved_proposal", {"proposal_id": prop_id, "dry_run": True}
        )
        assert res_exec["status"] == "executed"
        assert "[DRY_RUN]" in res_exec["output"]

        # 4. State transitioned to EXECUTED
        record = callback_instance.approval_gate.get_record(prop_id)
        assert record.status == ProposalStatus.EXECUTED


class TestADKProtocolCompatibility:
    """Tests adherence to Google ADK before_tool_callback async contract."""

    def test_async_before_tool_callback(
        self, callback_instance: RuntimeGuardrailToolCallback
    ):
        payload = {
            "branch": "develop",
            "commit_type": "test",
            "scope": "runtime",
            "short_summary": "add async callback test",
        }
        # Call async before_tool_callback
        result = asyncio.run(
            callback_instance.before_tool_callback("propose_commit", payload, None)
        )
        assert isinstance(result, dict)
        assert result["status"] == "pending_approval"

    def test_unprotected_read_only_tool_passes_through(
        self, callback_instance: RuntimeGuardrailToolCallback
    ):
        # Tools not in proposal or mutation map must return None so ADK runs them
        result = callback_instance.intercept_runtime_tool_call(
            "read_code_file", {"filepath": "src/main.py"}
        )
        assert result is None

    def test_module_level_helpers(
        self, callback_instance: RuntimeGuardrailToolCallback
    ):
        validation = validate_runtime_callback_payload(
            "propose_commit",
            {
                "branch": "main",
                "commit_type": "feat",
                "scope": "helper",
                "short_summary": "test helper function",
            },
            callback=callback_instance,
        )
        assert validation.is_valid

        intercept_res = intercept_runtime_callback_tool(
            "propose_commit",
            {
                "branch": "main",
                "commit_type": "feat",
                "scope": "helper",
                "short_summary": "test helper function",
            },
            callback=callback_instance,
        )
        assert intercept_res["status"] == "pending_approval"
