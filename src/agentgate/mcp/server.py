"""Deterministic Guardrails Gateway MCPServer.

Exposes strictly typed proposal and approval tools to prevent probabilistic models
from directly issuing arbitrary or malformed mutations across branching, commits,
pull requests, and multi-stage workflows.
Decoupled into universal core state machine, domain adapters, and reasoning engines.
"""

import argparse
import os
import sys
from typing import Any

from mcp.server.mcpserver import MCPServer
from pydantic import ValidationError

from agentgate.guardrails.adapters.git import (
    BranchProposal,
    BranchType,
    CommitProposal,
    CommitType,
    GitGuardrailAdapter,
    PullRequestProposal,
)
from agentgate.guardrails.adapters.sql import (
    GuardrailAdapterSql,
    MigrationProposalSql,
    RollbackProposalSql,
    SqlDialect,
    SqlOperationType,
)
from agentgate.guardrails.core import (
    ApprovalGate,
    ProposalStatus,
)
from agentgate.reasoning import (
    BaseReasoningEngine,
    GeminiReasoningEngine,
    ReasoningError,
)
from blueprints.verified_github_agent.agent import TaskSpecification

# Initialize MCPServer (MCP SDK v2)
mcp = MCPServer(
    name="agentgate-guardrails",
    instructions="Deterministic Guardrail MCP Server enforcing Conventional Commits, git guardrails, and HITL approval.",
)

# Global in-memory approval gate instance and domain adapters
approval_gate = ApprovalGate()
git_adapter = GitGuardrailAdapter()
sql_adapter = GuardrailAdapterSql()

# Active reasoning engine (configurable for test injection)
_reasoning_engine: BaseReasoningEngine | None = None


def get_reasoning_engine() -> BaseReasoningEngine:
    """Return the active reasoning engine, lazily defaulting to GeminiReasoningEngine."""
    global _reasoning_engine
    if _reasoning_engine is None:
        _reasoning_engine = GeminiReasoningEngine()
    return _reasoning_engine


def set_reasoning_engine(engine: BaseReasoningEngine | None) -> None:
    """Set or override active reasoning engine (primarily for testing and mock injection)."""
    global _reasoning_engine
    _reasoning_engine = engine


@mcp.tool()
def propose_branch(
    branch_type: BranchType,
    branch_name: str,
    base_branch: str = "main",
    ticket_id: str | None = None,
) -> str:
    """Propose a git branch conforming strictly to standardized prefix and naming rules.

    This tool DOES NOT create the branch directly. It validates fields against strict deterministic
    rules and enqueues the proposal for human-in-the-loop approval (PENDING_APPROVAL).

    Args:
        branch_type: Category prefix (feat, fix, chore, docs, refactor, test, perf).
        branch_name: Branch slug without prefix (lowercase alphanumeric and hyphens, max 30 chars).
        base_branch: Target base branch to branch off from (default 'main').
        ticket_id: Optional tracking ticket identifier (e.g. CORE-123).
    """
    raw_payload: dict[str, Any] = {
        "branch_type": branch_type.value if hasattr(branch_type, "value") else str(branch_type),
        "branch_name": branch_name,
        "base_branch": base_branch,
    }
    if ticket_id:
        raw_payload["ticket_id"] = ticket_id

    validation = git_adapter.validate_branch_payload(raw_payload)
    if not validation.is_valid:
        error_details = "\n - ".join(validation.errors)
        return (
            f"REJECTED BY DETERMINISTIC GUARDRAIL:\n"
            f"The proposal violated schema constraints:\n - {error_details}\n"
            f"Please correct the parameters and propose again."
        )

    try:
        proposal = BranchProposal(
            branch_type=branch_type,
            branch_name=branch_name,
            base_branch=base_branch,
            ticket_id=ticket_id,
        )
        record = approval_gate.submit_proposal(proposal)
        return (
            f"PROPOSAL SUBMITTED SUCCESSFULLY\n"
            f"Proposal ID: {record.proposal_id}\n"
            f"Rendered Message: '{record.rendered_message}'\n"
            f"Target Branch: {proposal.full_branch_name}\n"
            f"Status: PENDING_APPROVAL\n"
            f"Note: This branch cannot be created until human approval is granted."
        )
    except ValidationError as exc:
        return f"INTERNAL ERROR: {exc}"


@mcp.tool()
def propose_commit(
    branch: str,
    commit_type: CommitType,
    scope: str,
    short_summary: str,
    ticket_id: str | None = None,
) -> str:
    """Propose a git commit conforming strictly to Conventional Commits.

    This tool DOES NOT commit directly. It validates fields against strict deterministic
    rules and enqueues the proposal for human-in-the-loop approval (PENDING_APPROVAL).

    Args:
        branch: Target Git branch (e.g. main, feature/auth).
        commit_type: Allowed type (feat, fix, chore, docs, refactor, test, perf).
        scope: Target scope in lowercase without spaces (max 15 characters).
        short_summary: Brief imperative summary (starts lowercase, no period, max 50 chars).
        ticket_id: Optional tracking identifier (e.g. CORE-123).
    """
    raw_payload: dict[str, Any] = {
        "branch": branch,
        "commit_type": commit_type,
        "scope": scope,
        "short_summary": short_summary,
    }
    if ticket_id:
        raw_payload["ticket_id"] = ticket_id

    validation = git_adapter.validate_payload(raw_payload)
    if not validation.is_valid:
        error_details = "\n - ".join(validation.errors)
        return (
            f"REJECTED BY DETERMINISTIC GUARDRAIL:\n"
            f"The proposal violated schema constraints:\n - {error_details}\n"
            f"Please correct the parameters and propose again."
        )

    try:
        proposal = git_adapter.parse_proposal(raw_payload)
        record = approval_gate.submit_proposal(proposal)
        return (
            f"PROPOSAL SUBMITTED SUCCESSFULLY\n"
            f"Proposal ID: {record.proposal_id}\n"
            f"Rendered Message: '{record.rendered_message}'\n"
            f"Target Branch: {record.proposal.branch}\n"
            f"Status: PENDING_APPROVAL\n"
            f"Note: This commit cannot be pushed until human approval is granted."
        )
    except ValidationError as exc:
        return f"INTERNAL ERROR: {exc}"


@mcp.tool()
def propose_pr(
    title_type: CommitType,
    title_scope: str,
    title_summary: str,
    head_branch: str,
    base_branch: str = "main",
    ticket_id: str | None = None,
    body: str | None = None,
) -> str:
    """Propose a GitHub Pull Request with standardized Conventional title and target mapping.

    This tool DOES NOT create the PR directly. It validates fields against strict deterministic
    rules and enqueues the proposal for human-in-the-loop approval (PENDING_APPROVAL).

    Args:
        title_type: Semantic category for PR title (feat, fix, chore, docs, refactor, test, perf).
        title_scope: Module or component scope (lowercase, max 15 chars, no whitespace).
        title_summary: Summary in imperative mood, lowercase start, max 50 chars, no trailing period.
        head_branch: Source feature or fix branch containing changes.
        base_branch: Target base branch to merge into (default 'main').
        ticket_id: Optional tracking ticket identifier (e.g. CORE-123).
        body: Optional structured pull request description body (max 500 chars).
    """
    raw_payload: dict[str, Any] = {
        "title_type": title_type.value if hasattr(title_type, "value") else str(title_type),
        "title_scope": title_scope,
        "title_summary": title_summary,
        "head_branch": head_branch,
        "base_branch": base_branch,
    }
    if ticket_id:
        raw_payload["ticket_id"] = ticket_id
    if body:
        raw_payload["body"] = body

    validation = git_adapter.validate_pr_payload(raw_payload)
    if not validation.is_valid:
        error_details = "\n - ".join(validation.errors)
        return (
            f"REJECTED BY DETERMINISTIC GUARDRAIL:\n"
            f"The proposal violated schema constraints:\n - {error_details}\n"
            f"Please correct the parameters and propose again."
        )

    try:
        proposal = PullRequestProposal(
            title_type=title_type,
            title_scope=title_scope,
            title_summary=title_summary,
            head_branch=head_branch,
            base_branch=base_branch,
            ticket_id=ticket_id,
            body=body,
        )
        record = approval_gate.submit_proposal(proposal)
        return (
            f"PROPOSAL SUBMITTED SUCCESSFULLY\n"
            f"Proposal ID: {record.proposal_id}\n"
            f"Rendered Message: '{record.rendered_message}'\n"
            f"PR Mapping: {head_branch} -> {base_branch}\n"
            f"Status: PENDING_APPROVAL\n"
            f"Note: This pull request cannot be created until human approval is granted."
        )
    except ValidationError as exc:
        return f"INTERNAL ERROR: {exc}"


@mcp.tool()
def propose_workflow(
    prompt: str,
    base_branch: str = "main",
    ticket_id: str | None = None,
) -> str:
    """Extract a task specification from natural language and propose the full 3-stage Git workflow.

    Uses the active reasoning engine to extract a strictly-typed TaskSpecification
    (extra='forbid') and deterministically stages 3 sequential proposals:
      1. BranchProposal (PENDING_APPROVAL)
      2. CommitProposal (PENDING_APPROVAL)
      3. PullRequestProposal (PENDING_APPROVAL)

    Args:
        prompt: Natural language user requirement or ticket description.
        base_branch: Base branch to branch from and target for PR (default 'main').
        ticket_id: Optional issue tracking ticket identifier (e.g. AUTH-101).
    """
    engine = get_reasoning_engine()
    system_instruction = (
        "You are an expert software engineer extracting task specifications for git workflows. "
        "Convert the user requirement into a structured TaskSpecification adhering strictly to schema rules: "
        "branch_type must be one of feat, fix, chore, docs, refactor, test, perf. "
        "branch_name must be lowercase alphanumeric and hyphens (max 30 chars). "
        "scope must be lowercase alphanumeric, hyphens or underscores (max 15 chars). "
        "summary must be imperative mood starting with lowercase, max 50 chars, no ending period, no banned phrases."
    )
    try:
        task_spec = engine.extract_structured(
            prompt=prompt,
            schema=TaskSpecification,
            system_instruction=system_instruction,
        )
    except ReasoningError as err:
        return f"REASONING FAILED: Could not extract valid task specification: {err}"

    updates: dict[str, Any] = {}
    if ticket_id is not None and not task_spec.ticket_id:
        updates["ticket_id"] = ticket_id
    if base_branch != "main" and task_spec.base_branch == "main":
        updates["base_branch"] = base_branch
    if updates:
        task_spec = task_spec.model_copy(update=updates)

    # Stage 1: Branch
    branch_prop = BranchProposal(
        branch_type=task_spec.branch_type,
        branch_name=task_spec.branch_name,
        base_branch=task_spec.base_branch,
        ticket_id=task_spec.ticket_id,
    )
    rec_branch = approval_gate.submit_proposal(branch_prop)

    # Stage 2: Commit
    commit_type = CommitType(task_spec.branch_type.value)
    commit_prop = CommitProposal(
        branch=branch_prop.full_branch_name,
        commit_type=commit_type,
        scope=task_spec.scope,
        short_summary=task_spec.summary,
        ticket_id=task_spec.ticket_id,
    )
    rec_commit = approval_gate.submit_proposal(commit_prop)

    # Stage 3: Pull Request
    pr_prop = PullRequestProposal(
        title_type=commit_type,
        title_scope=task_spec.scope,
        title_summary=task_spec.summary,
        head_branch=branch_prop.full_branch_name,
        base_branch=task_spec.base_branch,
        body=task_spec.pr_body,
        ticket_id=task_spec.ticket_id,
    )
    rec_pr = approval_gate.submit_proposal(pr_prop)

    return (
        f"WORKFLOW PROPOSALS STAGED SUCCESSFULLY\n"
        f"Task: {task_spec.branch_type.value}({task_spec.scope}): {task_spec.summary}\n"
        f"1. Branch Proposal [{rec_branch.proposal_id}]: {rec_branch.rendered_message}\n"
        f"2. Commit Proposal [{rec_commit.proposal_id}]: {rec_commit.rendered_message}\n"
        f"3. PR Proposal     [{rec_pr.proposal_id}]: {rec_pr.rendered_message}\n"
        f"Status: ALL STAGES PENDING_APPROVAL\n"
        f"Operator approval required before deterministic execution."
    )


@mcp.tool()
def propose_sql_migration(
    operation_type: str,
    target_table: str,
    migration_sql: str,
    rollback_sql: str,
    description: str,
    dialect: str = "sqlite",
) -> str:
    """Propose a database schema migration or controlled DML query for operator approval.

    Performs strict AST inspection to block destructive DDL (DROP, TRUNCATE) and unconstrained DML.
    """
    try:
        op_type = SqlOperationType(operation_type.lower())
    except ValueError:
        valid_types = [t.value for t in SqlOperationType]
        return f"PROPOSAL REJECTED: Invalid operation_type '{operation_type}'. Must be one of {valid_types}."

    try:
        sql_dialect = SqlDialect(dialect.lower())
    except ValueError:
        valid_dialects = [d.value for d in SqlDialect]
        return f"PROPOSAL REJECTED: Invalid dialect '{dialect}'. Must be one of {valid_dialects}."

    try:
        proposal = MigrationProposalSql(
            dialect=sql_dialect,
            operation_type=op_type,
            target_table=target_table,
            migration_sql=migration_sql,
            rollback_sql=rollback_sql,
            description=description,
        )
    except ValidationError as e:
        return f"PROPOSAL REJECTED: Schema validation error:\n{e}"

    val_result = sql_adapter.validate_proposal(proposal)
    if not val_result.is_valid:
        error_details = "\n - ".join(val_result.errors)
        return (
            f"REJECTED BY DETERMINISTIC GUARDRAIL:\n"
            f"The SQL proposal violated safety constraints:\n - {error_details}\n"
            f"Destructive or unconstrained operations are strictly prohibited."
        )

    record = approval_gate.submit_proposal(proposal)

    return (
        f"SQL MIGRATION PROPOSAL STAGED FOR APPROVAL\n"
        f"Proposal ID: {record.proposal_id}\n"
        f"Status: PENDING_APPROVAL\n"
        f"Action: {record.rendered_message}\n\n"
        f"Run 'approve_proposal(\"{record.proposal_id}\")' to authorize execution."
    )


@mcp.tool()
def list_pending_proposals() -> str:
    """List all proposals currently awaiting operator approval."""
    pending = approval_gate.list_pending()
    if not pending:
        return "No pending proposals awaiting approval."

    lines = ["Pending Proposals:"]
    for p in pending:
        prop = p.proposal
        if isinstance(prop, BranchProposal):
            target = f"Branch: {prop.full_branch_name}"
            prefix = "[BRANCH]"
        elif isinstance(prop, CommitProposal):
            target = f"Branch: {prop.branch}"
            prefix = "[COMMIT]"
        elif isinstance(prop, PullRequestProposal):
            target = f"PR: {prop.head_branch} -> {prop.base_branch}"
            prefix = "[PR]"
        elif isinstance(prop, MigrationProposalSql):
            target = f"Table: {prop.target_table} ({prop.operation_type.value})"
            prefix = "[SQL_MIGRATION]"
        elif isinstance(prop, RollbackProposalSql):
            target = f"Table: {prop.target_table} (Rollback {prop.target_migration_id})"
            prefix = "[SQL_ROLLBACK]"
        else:
            branch = getattr(prop, "branch", getattr(prop, "full_branch_name", "unknown"))
            target = f"Target: {branch}"
            prefix = "[PROPOSAL]"

        lines.append(
            f"- {prefix} [{p.proposal_id}] {target} | Message: '{p.rendered_message}'"
        )
    return "\n".join(lines)


@mcp.tool()
def approve_proposal(proposal_id: str) -> str:
    """Approve a pending proposal (Human-in-the-Loop action).

    Args:
        proposal_id: The unique proposal identifier (e.g. prop_a1b2c3d4).
    """
    try:
        record = approval_gate.approve(proposal_id)
        return (
            f"PROPOSAL APPROVED\n"
            f"Proposal ID: {record.proposal_id}\n"
            f"Approved Message: '{record.rendered_message}'\n"
            f"Status: APPROVED\n"
            f"Ready for deterministic execution."
        )
    except KeyError:
        return f"ERROR: Proposal ID '{proposal_id}' was not found."
    except ValueError as exc:
        return f"ERROR: {exc}"


@mcp.tool()
def reject_proposal(proposal_id: str, reason: str = "Rejected by operator") -> str:
    """Reject a pending proposal.

    Args:
        proposal_id: The unique proposal identifier.
        reason: Optional reason for rejection.
    """
    try:
        record = approval_gate.reject(proposal_id, reason=reason)
        return (
            f"PROPOSAL REJECTED\n"
            f"Proposal ID: {record.proposal_id}\n"
            f"Status: REJECTED\n"
            f"Reason: {record.rejection_reason}"
        )
    except KeyError:
        return f"ERROR: Proposal ID '{proposal_id}' was not found."
    except ValueError as exc:
        return f"ERROR: {exc}"


@mcp.tool()
def execute_approved_proposal(
    proposal_id: str,
    repo_path: str = ".",
    dry_run: bool = False,
) -> str:
    """Execute Git mutation for an APPROVED proposal.

    Fails deterministically if proposal is not yet approved.
    Polymorphic dispatcher routes execution based on proposal type
    (BranchProposal, CommitProposal, PullRequestProposal).

    Args:
        proposal_id: The unique proposal identifier.
        repo_path: Path to target repository directory.
        dry_run: When True, simulates execution without performing mutations.
    """
    record = approval_gate.get_record(proposal_id)
    if not record:
        return f"ERROR: Proposal ID '{proposal_id}' was not found."

    if record.status != ProposalStatus.APPROVED:
        return (
            f"EXECUTION BLOCKED (GATEWAY RESTRICTION): "
            f"Cannot execute proposal '{proposal_id}' without prior APPROVAL (Current status: {record.status.value})."
        )

    proposal = record.proposal
    if isinstance(proposal, BranchProposal):
        success, output = git_adapter.execute_create_branch(record, repo_path=repo_path, dry_run=dry_run)
        action_name = "BRANCH CREATION"
    elif isinstance(proposal, CommitProposal):
        success, output = git_adapter.execute_commit(record, repo_path=repo_path, dry_run=dry_run)
        action_name = "COMMIT"
    elif isinstance(proposal, PullRequestProposal):
        success, output = git_adapter.execute_create_pr(record, repo_path=repo_path, dry_run=dry_run)
        action_name = "PULL REQUEST"
    elif isinstance(proposal, MigrationProposalSql):
        target_db = os.getenv("AGENTGATE_SQL_DB_PATH", ":memory:")
        success, output = sql_adapter.execute_migration(record, db_path=target_db, dry_run=dry_run)
        action_name = "SQL MIGRATION"
    elif isinstance(proposal, RollbackProposalSql):
        target_db = os.getenv("AGENTGATE_SQL_DB_PATH", ":memory:")
        success, output = sql_adapter.execute_rollback(record, db_path=target_db, dry_run=dry_run)
        action_name = "SQL ROLLBACK"
    else:
        return f"EXECUTION BLOCKED: Unsupported proposal type '{type(proposal).__name__}'."

    if not success:
        return f"{action_name} FAILED:\n{output}"

    # Only mark executed once operation has succeeded
    approval_gate.mark_executed(proposal_id)
    return (
        f"{action_name} EXECUTED DETERMINISTICALLY\n"
        f"Proposal ID: {record.proposal_id}\n"
        f"Status: EXECUTED\n"
        f"Executed Message: '{record.rendered_message}'\n"
        f"Output: {output}"
    )


def _enforce_strict_tool_models(server: MCPServer) -> None:
    """Enforce strict Pydantic v2 extra='forbid' on all registered MCP tools."""
    for tool in server._tool_manager.list_tools():
        if hasattr(tool, "fn_metadata") and hasattr(tool.fn_metadata, "arg_model"):
            tool.fn_metadata.arg_model.model_config["extra"] = "forbid"
            tool.fn_metadata.arg_model.model_rebuild(force=True)


_enforce_strict_tool_models(mcp)


def run_server(
    transport: str = "stdio",
    host: str = "0.0.0.0",
    port: int = 8000,
) -> None:
    """Run MCP server with specified transport protocol and network bindings."""
    if transport == "stdio":
        mcp.run(transport="stdio")
    elif transport in ("sse", "streamable-http"):
        mcp.run(transport=transport, host=host, port=port)  # type: ignore[arg-type]
    else:
        raise ValueError(
            f"Unsupported transport '{transport}'. Must be one of: stdio, sse, streamable-http."
        )


def main(argv: list[str] | None = None) -> None:
    """Entry point for Guardrails MCP server supporting CLI flags and environment variables."""
    parser = argparse.ArgumentParser(
        prog="agentgate-mcp",
        description="AgentGate Guardrails MCP Server enforcing Conventional Commits, SQL inspection, and HITL approval.",
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "streamable-http"],
        default=os.getenv("MCP_TRANSPORT", "stdio"),
        help="Transport protocol (default: stdio, or $MCP_TRANSPORT)",
    )
    parser.add_argument(
        "--host",
        default=os.getenv("HOST", "0.0.0.0"),
        help="Bind host for SSE/HTTP (default: 0.0.0.0, or $HOST)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("PORT", "8000")),
        help="Bind port for SSE/HTTP (default: 8000, or $PORT)",
    )
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    run_server(transport=args.transport, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
