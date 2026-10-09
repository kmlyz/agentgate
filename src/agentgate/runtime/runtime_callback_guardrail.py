"""Google ADK 2.0 Runtime Guardrail Callback Bridge.

Intercepts LLM tool execution attempts at runtime, enforces strict Pydantic v2
schemas (extra='forbid'), blocks unauthorized side-effects, and enqueues safe
proposals into the universal ApprovalGate state machine.
"""

from typing import Any

from pydantic import ValidationError

from agentgate.guardrails.adapters.git.adapter import GitGuardrailAdapter
from agentgate.guardrails.adapters.git.schemas import (
    BranchProposal,
    CommitProposal,
    PullRequestProposal,
)
from agentgate.guardrails.core.gate import ApprovalGate
from agentgate.guardrails.core.models import (
    BaseProposal,
    ProposalRecord,
    ProposalStatus,
    ProposalValidationResult,
)

# Standard mappings for recognized proposal tools to their Pydantic schemas
DEFAULT_PROPOSAL_TOOL_MAP: dict[str, type[BaseProposal]] = {
    "propose_commit": CommitProposal,
    "propose_git_commit": CommitProposal,
    "propose_branch": BranchProposal,
    "propose_create_branch": BranchProposal,
    "propose_git_branch": BranchProposal,
    "propose_pr": PullRequestProposal,
    "propose_pull_request": PullRequestProposal,
    "propose_git_pr": PullRequestProposal,
}

# Mutation tools that must NEVER execute without prior Human-in-the-Loop approval
DEFAULT_MUTATION_TOOLS: set[str] = {
    "commit",
    "git_commit",
    "execute_commit",
    "create_branch",
    "git_branch",
    "execute_create_branch",
    "create_pr",
    "git_pr",
    "execute_create_pr",
    "execute_approved_proposal",
}


def _resolve_tool_name(tool: Any) -> str:
    """Deterministically extracts tool identifier from tool object or name string."""
    if isinstance(tool, str):
        return tool
    if hasattr(tool, "name") and isinstance(tool.name, str):
        return tool.name
    if hasattr(tool, "__name__") and isinstance(tool.__name__, str):
        return tool.__name__
    return str(tool)


class RuntimeGuardrailToolCallback:
    """ADK 2.0 runtime guardrail interceptor and approval gatekeeper.

    Designed for seamless use with Google ADK `before_tool_callback`.
    Returning a dictionary instructs ADK to skip tool execution and feed
    the dictionary directly back to the model as the deterministic outcome.
    Returning None allows benign / read-only tools to execute normally.
    """

    def __init__(
        self,
        approval_gate: ApprovalGate | None = None,
        git_adapter: GitGuardrailAdapter | None = None,
        proposal_tool_map: dict[str, type[BaseProposal]] | None = None,
        protected_mutation_tools: set[str] | None = None,
    ) -> None:
        self.approval_gate = approval_gate or ApprovalGate()
        self.git_adapter = git_adapter or GitGuardrailAdapter()
        self.proposal_tool_map = (
            dict(proposal_tool_map)
            if proposal_tool_map is not None
            else dict(DEFAULT_PROPOSAL_TOOL_MAP)
        )
        self.protected_mutation_tools = (
            set(protected_mutation_tools)
            if protected_mutation_tools is not None
            else set(DEFAULT_MUTATION_TOOLS)
        )

    def validate_runtime_tool_payload(
        self, tool_name: str, payload: dict[str, Any]
    ) -> ProposalValidationResult:
        """Validate input payload against the registered Pydantic proposal schema."""
        schema = self.proposal_tool_map.get(tool_name)
        if not schema:
            return ProposalValidationResult(
                is_valid=False,
                errors=[
                    f"Tool '{tool_name}' has no registered guardrail proposal schema."
                ],
            )

        try:
            instance = schema.model_validate(payload)
            rendered = (
                instance.render_message()
                if hasattr(instance, "render_message")
                else str(instance)
            )
            return ProposalValidationResult(
                is_valid=True,
                rendered_message=rendered,
                errors=[],
                metadata={"tool_name": tool_name},
            )
        except ValidationError as exc:
            error_details = []
            for err in exc.errors():
                loc = ".".join(str(item) for item in err.get("loc", []))
                msg = err.get("msg", "Validation error")
                error_details.append(f"Field '{loc}': {msg}")
            return ProposalValidationResult(
                is_valid=False,
                rendered_message=None,
                errors=error_details,
                metadata={"tool_name": tool_name},
            )

    def intercept_runtime_tool_call(
        self, tool: Any, args: dict[str, Any], context: Any = None
    ) -> dict[str, Any] | None:
        """Intercept and evaluate tool calls synchronously or within ADK hooks."""
        tool_name = _resolve_tool_name(tool)

        # 1. Check if tool is a recognized proposal generator
        if tool_name in self.proposal_tool_map:
            schema = self.proposal_tool_map[tool_name]
            validation = self.validate_runtime_tool_payload(tool_name, args)

            if not validation.is_valid:
                return {
                    "status": "rejected",
                    "error": "REJECTED BY DETERMINISTIC GUARDRAIL",
                    "details": validation.errors,
                    "tool_name": tool_name,
                }

            # Valid payload -> Instantiate and submit to ApprovalGate
            proposal = schema.model_validate(args)
            record: ProposalRecord = self.approval_gate.submit_proposal(proposal)

            # Return dict to ADK so the tool is safely skipped and staged
            return {
                "status": "pending_approval",
                "proposal_id": record.proposal_id,
                "rendered_message": record.rendered_message,
                "tool_name": tool_name,
                "message": (
                    f"PROPOSAL SUBMITTED: Proposal ID '{record.proposal_id}' staged "
                    f"in ApprovalGate (Status: PENDING_APPROVAL). Awaiting human operator approval."
                ),
            }

        # 2. Check if tool is a protected mutation attempting execution
        if tool_name in self.protected_mutation_tools:
            proposal_id = args.get("proposal_id")
            if not proposal_id:
                return {
                    "status": "blocked",
                    "error": (
                        f"EXECUTION_BLOCKED: Tool '{tool_name}' performs destructive mutations "
                        f"and cannot be invoked directly without an approved 'proposal_id'."
                    ),
                    "tool_name": tool_name,
                }

            record = self.approval_gate.get_record(proposal_id)
            if not record:
                return {
                    "status": "blocked",
                    "error": f"EXECUTION_BLOCKED: Proposal ID '{proposal_id}' not found.",
                    "tool_name": tool_name,
                }

            if record.status != ProposalStatus.APPROVED:
                return {
                    "status": "blocked",
                    "error": (
                        f"EXECUTION_BLOCKED: Proposal '{proposal_id}' status is '{record.status.value}'. "
                        f"Human approval (APPROVED) is strictly required before execution."
                    ),
                    "proposal_id": proposal_id,
                    "status_current": record.status.value,
                    "tool_name": tool_name,
                }

            # Proposal is officially APPROVED -> Mark executed and run deterministically
            self.approval_gate.mark_executed(proposal_id)
            repo_path = args.get("repo_path", ".")
            dry_run = args.get("dry_run", False)

            success, output = self._execute_proposal_payload(
                record, repo_path=repo_path, dry_run=dry_run
            )
            return {
                "status": "executed" if success else "failed",
                "proposal_id": record.proposal_id,
                "rendered_message": record.rendered_message,
                "output": output,
                "tool_name": tool_name,
            }

        # 3. Unprotected / read-only tool -> Allow normal execution
        return None

    async def before_tool_callback(
        self, tool: Any, args: dict[str, Any], tool_context: Any = None
    ) -> dict[str, Any] | None:
        """ADK 2.0 asynchronous before_tool_callback standard implementation."""
        return self.intercept_runtime_tool_call(tool, args, tool_context)

    def _execute_proposal_payload(
        self, record: ProposalRecord, repo_path: str = ".", dry_run: bool = False
    ) -> tuple[bool, str]:
        """Dispatch approved proposal to domain adapter deterministically."""
        prop = record.proposal
        if isinstance(prop, CommitProposal):
            return self.git_adapter.execute_commit(
                record, repo_path=repo_path, dry_run=dry_run
            )
        if isinstance(prop, BranchProposal):
            return self.git_adapter.execute_create_branch(
                record, repo_path=repo_path, dry_run=dry_run
            )
        if isinstance(prop, PullRequestProposal):
            return self.git_adapter.execute_create_pr(
                record, repo_path=repo_path, dry_run=dry_run
            )
        return True, f"Proposal '{record.proposal_id}' executed deterministically."


# Module-level convenience functions conforming to hierarchical naming
_default_runtime_callback = RuntimeGuardrailToolCallback()


def intercept_runtime_callback_tool(
    tool: Any,
    args: dict[str, Any],
    context: Any = None,
    callback: RuntimeGuardrailToolCallback | None = None,
) -> dict[str, Any] | None:
    """Standalone helper function to intercept tool calls using runtime guardrail."""
    cb = callback or _default_runtime_callback
    return cb.intercept_runtime_tool_call(tool, args, context)


def validate_runtime_callback_payload(
    tool_name: str,
    payload: dict[str, Any],
    callback: RuntimeGuardrailToolCallback | None = None,
) -> ProposalValidationResult:
    """Standalone helper function to validate payload against registered schemas."""
    cb = callback or _default_runtime_callback
    return cb.validate_runtime_tool_payload(tool_name, payload)
