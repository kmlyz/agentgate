"""Tests verifying detection of TOCTOU (Time-of-Check to Time-of-Use) state drift."""

import pytest

from agentgate.guardrails.adapters.git import CommitProposal, CommitType
from agentgate.guardrails.core import ApprovalGate, TokenSecurityGate


def test_token_fails_on_state_drift() -> None:
    """Ensure that modifying environmental state fingerprint invalidates the approval token."""
    gate = ApprovalGate(storage_path=None)

    proposal = CommitProposal(
        branch="main",
        commit_type=CommitType.FEAT,
        scope="core",
        short_summary="implement state fingerprint",
    )
    record = gate.submit_proposal(proposal)
    gate.approve(record.proposal_id)

    assert record.approval_token is not None

    drifted_fingerprint = "f" * 64

    is_valid, reason = TokenSecurityGate.verify_approval_token(
        token=record.approval_token,
        expected_proposal_id=record.proposal_id,
        expected_payload_sha256=record.payload_sha256 or "",
        expected_state_fingerprint=drifted_fingerprint,
    )

    assert not is_valid
    assert reason is not None
    assert "E_STATE_DRIFT" in reason


def test_mark_executed_with_drifted_state_fails() -> None:
    """Ensure mark_executed with verify_environment=True rejects drifted state."""
    gate = ApprovalGate(storage_path=None)

    proposal = CommitProposal(
        branch="main",
        commit_type=CommitType.FEAT,
        scope="core",
        short_summary="implement state fingerprint",
    )
    record = gate.submit_proposal(proposal)
    gate.approve(record.proposal_id)

    # Force record's staged state_fingerprint to an obsolete hash
    record.state_fingerprint = "0" * 64
    # Re-issue token with obsolete hash to test mismatch with live environment
    signed_tok = TokenSecurityGate.issue_approval_token(
        proposal_id=record.proposal_id,
        payload_sha256=record.payload_sha256 or "",
        state_fingerprint="0" * 64,
    )
    record.approval_token = TokenSecurityGate.serialize_token(signed_tok)

    with pytest.raises(ValueError, match="E_STATE_DRIFT"):
        gate.mark_executed(record.proposal_id, verify_environment=True)
