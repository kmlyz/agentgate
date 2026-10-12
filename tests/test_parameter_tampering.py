"""Tests verifying prevention of parameter tampering and confused deputy attacks."""

import pytest

from agentgate.guardrails.adapters.git import CommitProposal, CommitType
from agentgate.guardrails.core import ApprovalGate, TokenSecurityGate


def test_token_fails_on_payload_tampering() -> None:
    """Ensure that modifying proposal payload parameters invalidates the cryptographic approval token."""
    gate = ApprovalGate(storage_path=None)

    # 1. Propose original payload
    original_proposal = CommitProposal(
        branch="main",
        commit_type=CommitType.FEAT,
        scope="auth",
        short_summary="add authentication middleware",
    )
    record = gate.submit_proposal(original_proposal)
    record = gate.approve(record.proposal_id)

    assert record.approval_token is not None

    # 2. Simulate attacker tampering with proposal payload inside the record
    tampered_proposal = CommitProposal(
        branch="main",
        commit_type=CommitType.FEAT,
        scope="auth",
        short_summary="malicious backdoor injection",
    )
    tampered_digest = TokenSecurityGate.compute_payload_digest(tampered_proposal)

    # 3. Attempting to verify token with tampered payload digest must fail
    is_valid, reason = TokenSecurityGate.verify_approval_token(
        token=record.approval_token,
        expected_proposal_id=record.proposal_id,
        expected_payload_sha256=tampered_digest,
        expected_state_fingerprint=record.state_fingerprint or "",
    )

    assert not is_valid
    assert reason is not None
    assert "E_PAYLOAD_TAMPERED" in reason
    assert "Payload hash mismatch" in reason


def test_mark_executed_blocks_when_payload_is_tampered() -> None:
    """Ensure mark_executed fails with ValueError if proposal is modified prior to execution."""
    gate = ApprovalGate(storage_path=None)

    original_proposal = CommitProposal(
        branch="main",
        commit_type=CommitType.FEAT,
        scope="auth",
        short_summary="add authentication middleware",
    )
    record = gate.submit_proposal(original_proposal)
    gate.approve(record.proposal_id)

    # Tamper with record proposal in-memory
    record.proposal = CommitProposal(
        branch="main",
        commit_type=CommitType.FEAT,
        scope="auth",
        short_summary="injected malicious commit message",
    )

    with pytest.raises(ValueError, match="E_PAYLOAD_TAMPERED"):
        gate.mark_executed(record.proposal_id)
