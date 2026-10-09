"""Deterministic and type-safe tools for Verified GitHub Agent.

Enforces zero free-text policy, regex constraints, and Pydantic v2 schemas across
branching, commits, pull requests, and human-authorized execution.
"""

from typing import Any

from agentgate.guardrails.adapters.git.adapter import GitGuardrailAdapter
from agentgate.guardrails.adapters.git.schemas import (
    BranchProposal,
    BranchType,
    CommitProposal,
    CommitType,
    PullRequestProposal,
)
from agentgate.guardrails.core.gate import ApprovalGate
from agentgate.guardrails.core.models import ProposalStatus


def propose_branch(
    branch_type: BranchType,
    branch_name: str,
    base_branch: str = "main",
    ticket_id: str | None = None,
) -> dict[str, Any]:
    """Propose a new git branch according to standardized prefix and naming rules.

    Args:
        branch_type: Category prefix (feat, fix, chore, docs, refactor, test, perf).
        branch_name: Branch slug without prefix (lowercase alphanumeric and hyphens, max 30 chars).
        base_branch: Base branch to branch off from (default 'main').
        ticket_id: Optional tracking ticket identifier (e.g. CORE-123).
    """
    proposal = BranchProposal(
        branch_type=branch_type,
        branch_name=branch_name,
        base_branch=base_branch,
        ticket_id=ticket_id,
    )
    return {
        "status": "pending_approval",
        "action": "propose_branch",
        "full_branch_name": proposal.full_branch_name,
        "rendered_message": proposal.render_message(),
    }


def propose_commit(
    branch: str,
    commit_type: CommitType,
    scope: str,
    short_summary: str,
    ticket_id: str | None = None,
) -> dict[str, Any]:
    """Propose a Conventional Commit message with strict imperative summary checks.

    Args:
        branch: Target branch name for the commit.
        commit_type: Semantic category (feat, fix, chore, docs, refactor, test, perf).
        scope: Target component or module scope (lowercase, max 15 chars, no whitespace).
        short_summary: Summary in imperative mood, lowercase start, max 50 chars, no trailing period.
        ticket_id: Optional issue tracking ticket identifier (e.g. PROJ-101).
    """
    proposal = CommitProposal(
        branch=branch,
        commit_type=commit_type,
        scope=scope,
        short_summary=short_summary,
        ticket_id=ticket_id,
    )
    return {
        "status": "pending_approval",
        "action": "propose_commit",
        "rendered_message": proposal.render_message(),
    }


def propose_pr(
    title_type: CommitType,
    title_scope: str,
    title_summary: str,
    head_branch: str,
    base_branch: str = "main",
    ticket_id: str | None = None,
    body: str | None = None,
) -> dict[str, Any]:
    """Propose a GitHub Pull Request with standardized title and target mapping.

    Args:
        title_type: Semantic category for PR title.
        title_scope: Module or component scope (lowercase, max 15 chars, no whitespace).
        title_summary: Imperative summary, lowercase start, max 50 chars, no trailing period.
        head_branch: Source feature or fix branch containing changes.
        base_branch: Target base branch to merge into (default 'main').
        ticket_id: Optional tracking ticket identifier (e.g. CORE-123).
        body: Optional structured pull request description (max 500 chars).
    """
    proposal = PullRequestProposal(
        title_type=title_type,
        title_scope=title_scope,
        title_summary=title_summary,
        head_branch=head_branch,
        base_branch=base_branch,
        ticket_id=ticket_id,
        body=body,
    )
    return {
        "status": "pending_approval",
        "action": "propose_pr",
        "rendered_message": proposal.render_message(),
    }


def execute_approved_proposal(
    proposal_id: str,
    repo_path: str = ".",
    dry_run: bool = True,
    gate: ApprovalGate | None = None,
    adapter: GitGuardrailAdapter | None = None,
) -> dict[str, Any]:
    """Execute a previously authorized proposal. Fails deterministically if status is not APPROVED.

    Args:
        proposal_id: Unique UUID identifier of the approved proposal.
        repo_path: Local git repository root directory (default '.').
        dry_run: If True, simulates git commands without mutating the repository.
        gate: Optional ApprovalGate instance (defaults to global persistent gate).
        adapter: Optional GitGuardrailAdapter instance.
    """
    active_gate = gate or ApprovalGate()
    active_adapter = adapter or GitGuardrailAdapter()

    record = active_gate.get_record(proposal_id)
    if not record:
        return {
            "status": "failed",
            "error": f"Proposal ID '{proposal_id}' was not found in gate registry.",
            "proposal_id": proposal_id,
        }

    if record.status != ProposalStatus.APPROVED:
        return {
            "status": "blocked",
            "error": (
                f"EXECUTION_BLOCKED: Proposal '{proposal_id}' status is '{record.status.value.upper()}'. "
                f"Human approval (APPROVED) is strictly required before execution."
            ),
            "proposal_id": proposal_id,
            "current_status": record.status.value,
        }

    proposal = record.proposal
    if isinstance(proposal, BranchProposal):
        success, output = active_adapter.execute_create_branch(
            record, repo_path=repo_path, dry_run=dry_run
        )
        action_type = "branch_creation"
    elif isinstance(proposal, CommitProposal):
        success, output = active_adapter.execute_commit(
            record, repo_path=repo_path, dry_run=dry_run
        )
        action_type = "commit"
    elif isinstance(proposal, PullRequestProposal):
        success, output = active_adapter.execute_create_pr(
            record, repo_path=repo_path, dry_run=dry_run
        )
        action_type = "pull_request"
    else:
        return {
            "status": "failed",
            "error": f"Unsupported proposal type for git execution: '{type(proposal).__name__}'.",
            "proposal_id": proposal_id,
        }

    if not success:
        return {
            "status": "failed",
            "action": action_type,
            "proposal_id": proposal_id,
            "output": output,
        }

    active_gate.mark_executed(proposal_id)
    return {
        "status": "executed",
        "action": action_type,
        "proposal_id": proposal_id,
        "output": output,
    }


def list_pending_proposals() -> list[dict[str, Any]]:
    """List all staged proposals currently awaiting Human-in-the-Loop review."""
    active_gate = ApprovalGate()
    records = active_gate.list_pending()
    return [
        {
            "proposal_id": r.proposal_id,
            "status": r.status.value,
            "rendered_message": r.rendered_message,
        }
        for r in records
    ]


class ToolsAgentGithub:
    """Namespace container grouping Verified GitHub Agent ADK tools."""

    propose_branch = staticmethod(propose_branch)
    propose_commit = staticmethod(propose_commit)
    propose_pr = staticmethod(propose_pr)
    execute_approved_proposal = staticmethod(execute_approved_proposal)
    list_pending_proposals = staticmethod(list_pending_proposals)


# Module-level convenience bindings conforming to naming specification
propose_github_agent_branch = propose_branch
propose_github_agent_commit = propose_commit
propose_github_agent_pr = propose_pr
execute_github_agent_approved_proposal = execute_approved_proposal
list_github_agent_pending_proposals = list_pending_proposals

__all__ = [
    "ToolsAgentGithub",
    "execute_approved_proposal",
    "execute_github_agent_approved_proposal",
    "list_github_agent_pending_proposals",
    "list_pending_proposals",
    "propose_branch",
    "propose_commit",
    "propose_github_agent_branch",
    "propose_github_agent_commit",
    "propose_github_agent_pr",
    "propose_pr",
]
