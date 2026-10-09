import pytest

from agentgate.guardrails.engine import (
    ApprovalGate,
    ProposalStatus,
    ProposalValidator,
)
from agentgate.guardrails.schemas import CommitProposal, CommitType


def test_valid_commit_proposal_rendering():
    proposal = CommitProposal(
        branch="main",
        commit_type=CommitType.FEAT,
        scope="auth",
        short_summary="add refresh token handler",
    )
    rendered = proposal.render_message()
    assert rendered == "feat(auth): add refresh token handler"


def test_valid_commit_proposal_with_ticket():
    proposal = CommitProposal(
        branch="feature/login",
        commit_type=CommitType.FIX,
        scope="api",
        short_summary="resolve timeout issue",
        ticket_id="CORE-404",
    )
    rendered = proposal.render_message()
    assert rendered == "fix(api): resolve timeout issue [CORE-404]"


@pytest.mark.parametrize(
    "banned_summary",
    [
        "fix login page (ai generated)",
        "model updated token generator",
        "automated update",
        "otomatik guncelleme",
        "auto-generated migration file",
    ],
)
def test_banned_phrases_rejected(banned_summary: str):
    res = ProposalValidator.validate_proposal_dict(
        {
            "branch": "main",
            "commit_type": "fix",
            "scope": "auth",
            "short_summary": banned_summary,
        }
    )
    assert not res.is_valid
    assert any("banned phrasing" in err for err in res.errors)


def test_summary_must_start_with_lowercase():
    res = ProposalValidator.validate_proposal_dict(
        {
            "branch": "main",
            "commit_type": "fix",
            "scope": "auth",
            "short_summary": "Fix login button",
        }
    )
    assert not res.is_valid
    assert any("must start with a lowercase" in err for err in res.errors)


def test_summary_cannot_end_with_period():
    res = ProposalValidator.validate_proposal_dict(
        {
            "branch": "main",
            "commit_type": "fix",
            "scope": "auth",
            "short_summary": "fix login button.",
        }
    )
    assert not res.is_valid
    assert any("cannot end with a period" in err for err in res.errors)


def test_summary_max_length_exceeded():
    long_summary = "a" * 51
    res = ProposalValidator.validate_proposal_dict(
        {
            "branch": "main",
            "commit_type": "fix",
            "scope": "auth",
            "short_summary": long_summary,
        }
    )
    assert not res.is_valid
    assert any("exceeds 50 characters" in err for err in res.errors)


def test_invalid_scope_format():
    res = ProposalValidator.validate_proposal_dict(
        {
            "branch": "main",
            "commit_type": "fix",
            "scope": "Auth Scope With Spaces",
            "short_summary": "fix login button",
        }
    )
    assert not res.is_valid


def test_forbid_extra_free_form_fields():
    """Ensure arbitrary fields like 'message' or 'free_text' are rejected at schema level."""
    res = ProposalValidator.validate_proposal_dict(
        {
            "branch": "main",
            "commit_type": "fix",
            "scope": "auth",
            "short_summary": "fix login button",
            "message": "Hey please commit this file",  # Disallowed extra field!
        }
    )
    assert not res.is_valid
    assert any("extra" in err.lower() for err in res.errors)


def test_approval_gate_lifecycle():
    gate = ApprovalGate()
    proposal = CommitProposal(
        branch="main",
        commit_type=CommitType.CHORE,
        scope="ci",
        short_summary="update workflow triggers",
    )

    # 1. Submit proposal
    record = gate.submit_proposal(proposal)
    assert record.status == ProposalStatus.PENDING_APPROVAL
    prop_id = record.proposal_id

    # 2. Cannot execute directly without approval
    with pytest.raises(ValueError, match="without prior APPROVAL"):
        gate.mark_executed(prop_id)

    # 3. Approve proposal
    approved_record = gate.approve(prop_id)
    assert approved_record.status == ProposalStatus.APPROVED

    # 4. Execute proposal
    executed_record = gate.mark_executed(prop_id)
    assert executed_record.status == ProposalStatus.EXECUTED


def test_approval_gate_rejection():
    gate = ApprovalGate()
    proposal = CommitProposal(
        branch="main",
        commit_type=CommitType.REFACTOR,
        scope="db",
        short_summary="simplify connection pool",
    )
    record = gate.submit_proposal(proposal)
    prop_id = record.proposal_id

    rejected_record = gate.reject(prop_id, reason="Branch is currently locked")
    assert rejected_record.status == ProposalStatus.REJECTED
    assert rejected_record.rejection_reason == "Branch is currently locked"


def test_polymorphic_proposal_hydration():
    gate = ApprovalGate()
    data = {
        "branch": "main",
        "commit_type": "feat",
        "scope": "core",
        "short_summary": "add polymorphic hydration",
    }
    proposal = CommitProposal.model_validate(data)
    record = gate.submit_proposal(proposal)
    assert record.status == ProposalStatus.PENDING_APPROVAL
    assert isinstance(record.proposal, CommitProposal)


def test_proposal_record_raw_dict_hydration():
    from agentgate.guardrails.core.models import ProposalRecord

    rec = ProposalRecord(
        proposal_id="prop_test_hydrate",
        proposal={
            "branch": "main",
            "commit_type": "fix",
            "scope": "core",
            "short_summary": "fix raw hydration",
        },
        rendered_message="fix(core): fix raw hydration",
    )
    assert isinstance(rec.proposal, CommitProposal)

