"""Verified GitHub Agent Blueprint implementation.

Orchestrates development workflows with deterministic guardrails and Human-in-the-Loop
approval gates across git branching, conventional commits, and pull requests.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from agentgate.guardrails.adapters.git.adapter import GitGuardrailAdapter
from agentgate.guardrails.adapters.git.schemas import (
    BANNED_PHRASES,
    BranchProposal,
    BranchType,
    CommitProposal,
    CommitType,
    PullRequestProposal,
)
from agentgate.guardrails.core.gate import ApprovalGate
from agentgate.guardrails.core.models import ProposalRecord, ProposalStatus
from agentgate.reasoning import BaseReasoningEngine, ReasoningError


class TaskSpecification(BaseModel):
    """Structured specification of a development task.

    Designed with strict typing to be cleanly driven by upstream LLMs or APIs
    without allowing free-form prompt injection or arbitrary parameters.
    """

    model_config = ConfigDict(extra="forbid")

    branch_type: BranchType = Field(
        ...,
        description="Branch and commit category (feat, fix, chore, docs, refactor, test, perf).",
    )
    branch_name: str = Field(
        ...,
        description="Branch slug without prefix (lowercase alphanumeric and hyphens, max 30 chars).",
        pattern=r"^[a-z0-9][a-z0-9\-]{0,29}$",
    )
    scope: str = Field(
        ...,
        description="Target module or component scope (max 15 chars, lowercase, no whitespace).",
        pattern=r"^[a-z0-9_\-]{1,15}$",
    )
    summary: str = Field(
        ...,
        description="Brief summary in imperative mood, lowercase start, max 50 chars, no trailing period.",
    )
    base_branch: str = Field(
        default="main",
        description="Base branch to fork from and merge into.",
        pattern=r"^[a-zA-Z0-9_\-\.\/]+$",
    )
    ticket_id: str | None = Field(
        default=None,
        description="Optional tracking ticket identifier (e.g. CORE-123).",
        pattern=r"^[A-Z0-9]+-[0-9]+$",
    )
    pr_body: str | None = Field(
        default=None,
        description="Optional structured PR description body.",
        max_length=500,
    )

    @field_validator("summary")
    @classmethod
    def validate_summary(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("summary cannot be empty.")
        if len(trimmed) > 50:
            raise ValueError(f"summary exceeds 50 characters (current: {len(trimmed)}).")
        if trimmed.endswith("."):
            raise ValueError("summary cannot end with a period ('.').")
        if not trimmed[0].islower():
            raise ValueError("summary must start with a lowercase letter.")

        lowered = trimmed.lower()
        for banned in BANNED_PHRASES:
            if banned in lowered:
                raise ValueError(f"summary contains banned phrasing: '{banned}'.")

        return trimmed


class VerifiedGitHubAgent:
    """Production-grade agent orchestrating verified Git and GitHub lifecycle.

    Transforms a structured TaskSpecification into a 3-stage proposal pipeline:
      Stage 1: BranchProposal -> PENDING_APPROVAL
      Stage 2: CommitProposal -> PENDING_APPROVAL
      Stage 3: PullRequestProposal -> PENDING_APPROVAL

    Execution strictly enforces ApprovalGate human-in-the-loop authorization.
    """

    def __init__(
        self,
        approval_gate: ApprovalGate | None = None,
        git_adapter: GitGuardrailAdapter | None = None,
        reasoning_engine: BaseReasoningEngine | None = None,
    ) -> None:
        self.approval_gate = approval_gate or ApprovalGate()
        self.git_adapter = git_adapter or GitGuardrailAdapter()
        self.reasoning_engine = reasoning_engine
        self.staged_proposals: dict[str, ProposalRecord] = {}

    def plan_from_natural_language(
        self,
        prompt: str,
        base_branch: str = "main",
        ticket_id: str | None = None,
    ) -> tuple[TaskSpecification, list[ProposalRecord]]:
        """Extract a structured TaskSpecification from natural language and stage approval workflow.

        Uses the configured reasoning_engine with strict schema enforcement to generate
        a TaskSpecification, then submits the 3-stage proposal sequence to ApprovalGate.
        """
        if self.reasoning_engine is None:
            raise ReasoningError(
                "Cannot plan from natural language: No reasoning_engine configured for VerifiedGitHubAgent."
            )

        system_instruction = (
            "You are an expert software engineer extracting task specifications for git workflows. "
            "Convert the user requirement into a structured TaskSpecification adhering strictly to schema rules: "
            "branch_type must be one of feat, fix, chore, docs, refactor, test, perf. "
            "branch_name must be lowercase alphanumeric and hyphens (max 30 chars). "
            "scope must be lowercase alphanumeric, hyphens or underscores (max 15 chars). "
            "summary must be imperative mood starting with lowercase, max 50 chars, no ending period, no banned phrases."
        )

        task_spec = self.reasoning_engine.extract_structured(
            prompt=prompt,
            schema=TaskSpecification,
            system_instruction=system_instruction,
        )

        updates: dict[str, Any] = {}
        if ticket_id is not None and not task_spec.ticket_id:
            updates["ticket_id"] = ticket_id
        if base_branch != "main" and task_spec.base_branch == "main":
            updates["base_branch"] = base_branch
        if updates:
            task_spec = task_spec.model_copy(update=updates)

        proposals = self.plan_workflow(task_spec)
        return task_spec, proposals

    async def aplan_from_natural_language(
        self,
        prompt: str,
        base_branch: str = "main",
        ticket_id: str | None = None,
    ) -> tuple[TaskSpecification, list[ProposalRecord]]:
        """Asynchronously extract a structured TaskSpecification and stage approval workflow."""
        if self.reasoning_engine is None:
            raise ReasoningError(
                "Cannot plan from natural language: No reasoning_engine configured for VerifiedGitHubAgent."
            )

        system_instruction = (
            "You are an expert software engineer extracting task specifications for git workflows. "
            "Convert the user requirement into a structured TaskSpecification adhering strictly to schema rules."
        )

        task_spec = await self.reasoning_engine.aextract_structured(
            prompt=prompt,
            schema=TaskSpecification,
            system_instruction=system_instruction,
        )

        updates: dict[str, Any] = {}
        if ticket_id is not None and not task_spec.ticket_id:
            updates["ticket_id"] = ticket_id
        if base_branch != "main" and task_spec.base_branch == "main":
            updates["base_branch"] = base_branch
        if updates:
            task_spec = task_spec.model_copy(update=updates)

        proposals = self.plan_workflow(task_spec)
        return task_spec, proposals

    def plan_workflow(self, task: TaskSpecification) -> list[ProposalRecord]:
        """Create and stage all required proposals in PENDING_APPROVAL state."""
        # Stage 1: Branch Proposal
        branch_prop = BranchProposal(
            branch_type=task.branch_type,
            branch_name=task.branch_name,
            base_branch=task.base_branch,
            ticket_id=task.ticket_id,
        )
        rec_branch = self.approval_gate.submit_proposal(branch_prop)
        self.staged_proposals["branch"] = rec_branch

        # Stage 2: Commit Proposal
        commit_type = CommitType(task.branch_type.value)
        commit_prop = CommitProposal(
            branch=branch_prop.full_branch_name,
            commit_type=commit_type,
            scope=task.scope,
            short_summary=task.summary,
            ticket_id=task.ticket_id,
        )
        rec_commit = self.approval_gate.submit_proposal(commit_prop)
        self.staged_proposals["commit"] = rec_commit

        # Stage 3: Pull Request Proposal
        pr_prop = PullRequestProposal(
            title_type=commit_type,
            title_scope=task.scope,
            title_summary=task.summary,
            head_branch=branch_prop.full_branch_name,
            base_branch=task.base_branch,
            body=task.pr_body,
            ticket_id=task.ticket_id,
        )
        rec_pr = self.approval_gate.submit_proposal(pr_prop)
        self.staged_proposals["pr"] = rec_pr

        return [rec_branch, rec_commit, rec_pr]

    def execute_proposal(
        self,
        proposal_id: str,
        repo_path: str = ".",
        dry_run: bool = False,
    ) -> tuple[bool, str]:
        """Execute a single proposal deterministically after human approval."""
        record = self.approval_gate.get_record(proposal_id)
        if not record:
            raise KeyError(f"Proposal '{proposal_id}' not found in registry.")

        if record.status != ProposalStatus.APPROVED:
            raise ValueError(
                f"Execution blocked: Proposal '{proposal_id}' is in status '{record.status}'. "
                f"Approval is strictly required before execution."
            )

        proposal = record.proposal
        if isinstance(proposal, BranchProposal):
            success, output = self.git_adapter.execute_create_branch(
                record, repo_path=repo_path, dry_run=dry_run
            )
        elif isinstance(proposal, CommitProposal):
            success, output = self.git_adapter.execute_commit(
                record, repo_path=repo_path, dry_run=dry_run
            )
        elif isinstance(proposal, PullRequestProposal):
            success, output = self.git_adapter.execute_create_pr(
                record, repo_path=repo_path, dry_run=dry_run
            )
        else:
            raise TypeError(f"Unsupported proposal type: {type(proposal).__name__}")

        if success:
            self.approval_gate.mark_executed(proposal_id)
        return success, output

    def get_staged_proposals(self) -> dict[str, ProposalRecord]:
        """Return the dictionary of staged proposal records."""
        return dict(self.staged_proposals)

    def get_workflow_summary(self) -> dict[str, Any]:
        """Return high-level summary of current workflow stages."""
        summary: dict[str, Any] = {}
        for stage, rec in self.staged_proposals.items():
            summary[stage] = {
                "proposal_id": rec.proposal_id,
                "status": rec.status.value,
                "rendered_message": rec.rendered_message,
            }
        return summary


# Expose Google ADK root_agent instance for Google ADK CLI loader compatibility
from blueprints.verified_github_agent.github_agent_runtime import root_agent

__all__ = [
    "TaskSpecification",
    "VerifiedGitHubAgent",
    "root_agent",
]

