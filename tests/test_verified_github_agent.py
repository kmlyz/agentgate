"""Tests for Verified GitHub Agent Blueprint and extended Git guardrails."""

import pytest
from pydantic import ValidationError

from agentgate.guardrails.adapters.git import (
    BranchProposal,
    BranchType,
    CommitProposal,
    CommitType,
    GitGuardrailAdapter,
    PullRequestProposal,
)
from agentgate.guardrails.core import ApprovalGate, ProposalStatus
from blueprints.verified_github_agent import (
    TaskSpecification,
    VerifiedGitHubAgent,
)


class TestBranchProposalValidation:
    """Tests for BranchProposal schema rules and constraints."""

    def test_valid_branch_proposal(self):
        proposal = BranchProposal(
            branch_type=BranchType.FEAT,
            branch_name="oauth2-refresh",
            base_branch="main",
            ticket_id="AUTH-101",
        )
        assert proposal.full_branch_name == "feat/oauth2-refresh-auth-101"
        assert proposal.render_message() == "git checkout -b feat/oauth2-refresh-auth-101 main"

    def test_valid_branch_proposal_without_ticket(self):
        proposal = BranchProposal(
            branch_type=BranchType.FIX,
            branch_name="null-pointer",
        )
        assert proposal.full_branch_name == "fix/null-pointer"
        assert proposal.render_message() == "git checkout -b fix/null-pointer main"

    def test_invalid_branch_slug_characters(self):
        with pytest.raises(ValidationError):
            BranchProposal(
                branch_type=BranchType.FEAT,
                branch_name="INVALID_UPPERCASE",
            )

    def test_branch_proposal_forbids_extra_fields(self):
        with pytest.raises(ValidationError) as exc_info:
            BranchProposal(
                branch_type=BranchType.CHORE,
                branch_name="deps-update",
                unauthorized_extra_field="malicious_injection",
            )
        assert any(e["type"] == "extra_forbidden" for e in exc_info.value.errors())


class TestPullRequestProposalValidation:
    """Tests for PullRequestProposal schema rules and constraints."""

    def test_valid_pull_request_proposal(self):
        proposal = PullRequestProposal(
            title_type=CommitType.FEAT,
            title_scope="auth",
            title_summary="add jwt verification middleware",
            head_branch="feat/auth-jwt",
            base_branch="main",
            ticket_id="AUTH-200",
            body="Implements HMAC and RSA token verification.",
        )
        assert proposal.render_title() == "feat(auth): add jwt verification middleware [AUTH-200]"
        assert "feat/auth-jwt -> main" in proposal.render_message()

    def test_pr_summary_banned_phrases(self):
        with pytest.raises(ValidationError, match="banned phrasing"):
            PullRequestProposal(
                title_type=CommitType.FIX,
                title_scope="ui",
                title_summary="fix button (ai generated)",
                head_branch="fix/ui-button",
            )

    def test_pr_summary_period_prohibited(self):
        with pytest.raises(ValidationError, match="cannot end with a period"):
            PullRequestProposal(
                title_type=CommitType.REFACTOR,
                title_scope="core",
                title_summary="simplify gate state machine.",
                head_branch="refactor/gate",
            )

    def test_pr_summary_lowercase_required(self):
        with pytest.raises(ValidationError, match="must start with a lowercase letter"):
            PullRequestProposal(
                title_type=CommitType.TEST,
                title_scope="unit",
                title_summary="Add mock tests",
                head_branch="test/unit-mock",
            )

    def test_pr_proposal_forbids_extra_fields(self):
        with pytest.raises(ValidationError) as exc_info:
            PullRequestProposal(
                title_type=CommitType.CHORE,
                title_scope="ci",
                title_summary="update github actions",
                head_branch="chore/ci",
                arbitrary_field="leak",
            )
        assert any(e["type"] == "extra_forbidden" for e in exc_info.value.errors())


class TestGitGuardrailAdapterExtensions:
    """Tests for extended GitGuardrailAdapter branch and PR capabilities."""

    def test_validate_branch_payload(self):
        adapter = GitGuardrailAdapter()
        res_valid = adapter.validate_branch_payload({
            "branch_type": "feat",
            "branch_name": "payment-stripe",
            "base_branch": "main",
        })
        assert res_valid.is_valid
        assert res_valid.metadata["branch"] == "feat/payment-stripe"

        res_invalid = adapter.validate_branch_payload({
            "branch_type": "invalid_type",
            "branch_name": "payment-stripe",
        })
        assert not res_valid.is_valid is False
        assert not res_invalid.is_valid

    def test_validate_pr_payload(self):
        adapter = GitGuardrailAdapter()
        res_valid = adapter.validate_pr_payload({
            "title_type": "feat",
            "title_scope": "stripe",
            "title_summary": "integrate webhook handler",
            "head_branch": "feat/stripe",
            "base_branch": "main",
        })
        assert res_valid.is_valid

        res_invalid = adapter.validate_pr_payload({
            "title_type": "feat",
            "title_scope": "stripe",
            "title_summary": "Integrate webhook handler.",  # Uppercase + period
            "head_branch": "feat/stripe",
        })
        assert not res_invalid.is_valid

    def test_execute_dry_run_branch_and_pr(self):
        gate = ApprovalGate()
        adapter = GitGuardrailAdapter()

        branch_prop = BranchProposal(
            branch_type=BranchType.FEAT,
            branch_name="dry-run-branch",
        )
        rec_branch = gate.submit_proposal(branch_prop)
        success, out_branch = adapter.execute_create_branch(rec_branch, dry_run=True)
        assert success
        assert "[DRY_RUN] Branch created: feat/dry-run-branch" in out_branch

        pr_prop = PullRequestProposal(
            title_type=CommitType.FEAT,
            title_scope="core",
            title_summary="dry run pull request",
            head_branch="feat/dry-run-branch",
        )
        rec_pr = gate.submit_proposal(pr_prop)
        success, out_pr = adapter.execute_create_pr(rec_pr, dry_run=True)
        assert success
        assert "[DRY_RUN] Pull Request created" in out_pr


class TestVerifiedGitHubAgentLifecycle:
    """Tests for the complete VerifiedGitHubAgent workflow lifecycle."""

    def test_agent_plans_and_executes_workflow_deterministically(self):
        gate = ApprovalGate()
        agent = VerifiedGitHubAgent(approval_gate=gate)

        task = TaskSpecification(
            branch_type=BranchType.FEAT,
            branch_name="auth-session",
            scope="session",
            summary="implement redis session store",
            ticket_id="SESS-42",
            base_branch="main",
        )

        proposals = agent.plan_workflow(task)
        assert len(proposals) == 3

        # All proposals start in PENDING_APPROVAL
        for prop in proposals:
            assert prop.status == ProposalStatus.PENDING_APPROVAL

        branch_rec, commit_rec, pr_rec = proposals
        assert isinstance(branch_rec.proposal, BranchProposal)
        assert isinstance(commit_rec.proposal, CommitProposal)
        assert isinstance(pr_rec.proposal, PullRequestProposal)

        # Execution blocked without approval
        with pytest.raises(ValueError, match="strictly required before execution"):
            agent.execute_proposal(branch_rec.proposal_id, dry_run=True)

        # Approve and execute Stage 1 (Branch)
        gate.approve(branch_rec.proposal_id)
        success, out = agent.execute_proposal(branch_rec.proposal_id, dry_run=True)
        assert success
        assert "[DRY_RUN]" in out
        assert gate.get_record(branch_rec.proposal_id).status == ProposalStatus.EXECUTED

        # Approve and execute Stage 2 (Commit)
        gate.approve(commit_rec.proposal_id)
        success, out = agent.execute_proposal(commit_rec.proposal_id, dry_run=True)
        assert success
        assert "[DRY_RUN]" in out
        assert gate.get_record(commit_rec.proposal_id).status == ProposalStatus.EXECUTED

        # Reject Stage 3 (PR)
        gate.reject(pr_rec.proposal_id, reason="Needs more test coverage")
        with pytest.raises(ValueError, match="strictly required before execution"):
            agent.execute_proposal(pr_rec.proposal_id, dry_run=True)

        # Summary check
        summary = agent.get_workflow_summary()
        assert summary["branch"]["status"] == "executed"
        assert summary["commit"]["status"] == "executed"
        assert summary["pr"]["status"] == "rejected"
