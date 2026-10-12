"""Tests verifying token lifecycle, TTL expiration, and atomic single-use anti-replay enforcement."""

import time

import pytest

from agentgate.guardrails.adapters.git import CommitProposal, CommitType
from agentgate.guardrails.core import ApprovalGate, TokenSecurityGate


def test_token_fails_when_expired_ttl() -> None:
    """Ensure expired approval token fails verification."""
    gate = ApprovalGate(storage_path=None)

    proposal = CommitProposal(
        branch="main",
        commit_type=CommitType.FEAT,
        scope="auth",
        short_summary="token expiry verification",
    )
    record = gate.submit_proposal(proposal)

    # Approve with 1 second TTL
    record = gate.approve(record.proposal_id, ttl_seconds=1.0)
    assert record.approval_token is not None

    # Simulate time passing beyond expiration
    simulated_future_time = time.time() + 10.0

    is_valid, reason = TokenSecurityGate.verify_approval_token(
        token=record.approval_token,
        expected_proposal_id=record.proposal_id,
        expected_payload_sha256=record.payload_sha256 or "",
        expected_state_fingerprint=record.state_fingerprint or "",
        current_time=simulated_future_time,
    )

    assert not is_valid
    assert reason is not None
    assert "E_TOKEN_EXPIRED" in reason


def test_token_replay_rejected_on_second_execution() -> None:
    """Ensure consuming an approval token once permanently blocks re-execution (anti-replay)."""
    gate = ApprovalGate(storage_path=None)

    proposal = CommitProposal(
        branch="main",
        commit_type=CommitType.FEAT,
        scope="auth",
        short_summary="single use token verification",
    )
    record = gate.submit_proposal(proposal)
    gate.approve(record.proposal_id)

    # First execution succeeds
    gate.mark_executed(record.proposal_id)
    assert record.consumed_at is not None

    # Second execution must raise replay error
    with pytest.raises(ValueError, match="E_TOKEN_REPLAY"):
        gate.mark_executed(record.proposal_id)
