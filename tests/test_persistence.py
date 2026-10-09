from pathlib import Path

from agentgate.guardrails.adapters.git.schemas import CommitProposal, CommitType
from agentgate.guardrails.core import ApprovalGate, ProposalStatus


def test_approval_gate_disk_persistence(tmp_path: Path):
    test_storage = tmp_path / "proposals.json"

    # Process 1: Proposal is created and persisted to disk
    gate1 = ApprovalGate(storage_path=test_storage)
    proposal = CommitProposal(
        branch="main",
        commit_type=CommitType.FEAT,
        scope="auth",
        short_summary="add session persistence",
    )
    rec1 = gate1.submit_proposal(proposal)
    prop_id = rec1.proposal_id

    assert test_storage.exists()

    # Process 2: Clean session initialized and reloaded from disk
    gate2 = ApprovalGate(storage_path=test_storage)
    loaded_rec = gate2.get_record(prop_id)
    assert loaded_rec is not None
    assert loaded_rec.status == ProposalStatus.PENDING_APPROVAL
    assert loaded_rec.rendered_message == "feat(auth): add session persistence"

    # Process 2: Approves proposal and updates disk state
    gate2.approve(prop_id)

    # Process 3: Another session observes approved state and executes
    gate3 = ApprovalGate(storage_path=test_storage)
    rec3 = gate3.get_record(prop_id)
    assert rec3 is not None
    assert rec3.status == ProposalStatus.APPROVED

    gate3.mark_executed(prop_id)

    # Process 4: Verifies executed state
    gate4 = ApprovalGate(storage_path=test_storage)
    rec4 = gate4.get_record(prop_id)
    assert rec4 is not None
    assert rec4.status == ProposalStatus.EXECUTED

    # Cleanup
    gate4.clear()
    assert not test_storage.exists()


def test_persistence_hydrates_concrete_proposal_instances(tmp_path: Path):
    test_storage = tmp_path / "hydration.json"
    gate1 = ApprovalGate(storage_path=test_storage)
    proposal = CommitProposal(
        branch="main",
        commit_type=CommitType.FIX,
        scope="core",
        short_summary="fix hydration from disk",
    )
    rec1 = gate1.submit_proposal(proposal)

    gate2 = ApprovalGate(storage_path=test_storage)
    rec2 = gate2.get_record(rec1.proposal_id)
    assert rec2 is not None
    assert isinstance(rec2.proposal, CommitProposal)
    assert rec2.proposal.branch == "main"

