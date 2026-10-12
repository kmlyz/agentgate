"""Tests verifying immunity against synthetic self-approval vulnerabilities in runtime callbacks."""

import pytest

from agentgate.guardrails.core import ApprovalGate
from agentgate.runtime import RuntimeGuardrailToolCallback


@pytest.fixture
def callback() -> RuntimeGuardrailToolCallback:
    """Isolated callback instance with in-memory gate."""
    gate = ApprovalGate(storage_path=None)
    return RuntimeGuardrailToolCallback(approval_gate=gate)


@pytest.mark.parametrize(
    "forbidden_tool",
    [
        "approve_proposal",
        "reject_proposal",
        "gate_approve",
        "gate_reject",
    ],
)
def test_runtime_callback_blocks_self_approval_primitives_with_eperm(
    callback: RuntimeGuardrailToolCallback,
    forbidden_tool: str,
) -> None:
    """Ensure autonomous agents cannot invoke approval tools via before_tool_callback."""
    res = callback.intercept_runtime_tool_call(forbidden_tool, {"proposal_id": "prop_test_123"})
    assert isinstance(res, dict)
    assert res["status"] == "blocked"
    assert "E_PERM" in res["error"]
    assert "isolated approval endpoint out-of-band" in res["error"]


def test_staged_proposal_receipt_contract(callback: RuntimeGuardrailToolCallback) -> None:
    """Verify staged receipt contains staged_receipt_id, state_fingerprint, and branch lock message."""
    payload = {
        "branch": "main",
        "commit_type": "feat",
        "scope": "security",
        "short_summary": "harden approval gates",
    }
    res = callback.intercept_runtime_tool_call("propose_commit", payload)

    assert res is not None
    assert res["status"] == "pending_approval"
    assert "staged_receipt_id" in res
    assert res["staged_receipt_id"].startswith("rcpt_")
    assert "state_fingerprint" in res
    assert res["state_fingerprint"] is not None
    assert "Execution of this branch is locked" in res["message"]
