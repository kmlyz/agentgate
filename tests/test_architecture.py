import pytest

from agentgate.guardrails.adapters.git import (
    CommitType,
    GitGuardrailAdapter,
)
from agentgate.guardrails.core import (
    ApprovalGate,
    BaseGuardrailAdapter,
    BaseProposal,
    ProposalStatus,
)


class DummyDomainProposal(BaseProposal):
    name: str

    def render_message(self) -> str:
        return f"dummy: {self.name}"


def test_core_approval_gate_is_domain_agnostic():
    """Verify that ApprovalGate works with any BaseProposal, completely decoupled from Git."""
    gate = ApprovalGate()
    dummy = DummyDomainProposal(name="sample-action")

    record = gate.submit_proposal(dummy)
    assert record.status == ProposalStatus.PENDING_APPROVAL
    assert record.rendered_message == "dummy: sample-action"

    # Execution blocked without approval
    with pytest.raises(ValueError, match="without prior APPROVAL"):
        gate.mark_executed(record.proposal_id)

    # Approve and execute
    gate.approve(record.proposal_id)
    executed = gate.mark_executed(record.proposal_id)
    assert executed.status == ProposalStatus.EXECUTED


def test_git_adapter_implements_base_interface():
    """Verify GitGuardrailAdapter conforms to BaseGuardrailAdapter contract."""
    adapter = GitGuardrailAdapter()
    assert isinstance(adapter, BaseGuardrailAdapter)
    assert adapter.domain == "git"

    # Valid payload
    res = adapter.validate_payload(
        {
            "branch": "main",
            "commit_type": CommitType.FEAT,
            "scope": "refactor",
            "short_summary": "split core and adapters",
        }
    )
    assert res.is_valid
    assert res.rendered_message == "feat(refactor): split core and adapters"
    assert res.metadata["domain"] == "git"


def test_backward_compatibility_imports():
    """Ensure legacy module paths still resolve properly."""
    from agentgate.guardrails.engine import (
        ApprovalGate as LegacyGate,
    )
    from agentgate.guardrails.engine import (
        ProposalValidator as LegacyValidator,
    )
    from agentgate.guardrails.schemas import CommitProposal as LegacyProposal

    gate = LegacyGate()
    assert isinstance(gate, ApprovalGate)

    prop = LegacyProposal(
        branch="main",
        commit_type=CommitType.CHORE,
        scope="ci",
        short_summary="maintain legacy imports",
    )
    assert isinstance(prop, BaseProposal)

    val_res = LegacyValidator.validate_proposal_dict(
        {
            "branch": "main",
            "commit_type": "chore",
            "scope": "ci",
            "short_summary": "maintain legacy imports",
        }
    )
    assert val_res.is_valid
