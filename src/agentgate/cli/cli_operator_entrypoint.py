"""AgentGate Operator CLI Entrypoint.

Provides operator commands for natural language workflow planning, proposal inspection,
Human-in-the-Loop approval/rejection, and polymorphic deterministic execution.
"""

import contextlib
import os
from pathlib import Path
from typing import Any

import click
from pydantic import ValidationError

from agentgate.audit import (
    DEFAULT_LEDGER_STORAGE_PATH,
    LedgerEngineAudit,
)
from agentgate.guardrails.adapters.git import (
    BranchProposal,
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
    SqlTaskSpecification,
)
from agentgate.guardrails.core import ApprovalGate, ProposalStatus
from agentgate.guardrails.core.gate import DEFAULT_STORAGE_PATH
from agentgate.reasoning import (
    BaseReasoningEngine,
    GeminiReasoningEngine,
    MockReasoningEngine,
    ReasoningError,
)
from blueprints.verified_github_agent.agent import TaskSpecification

# Global hook for test mock injection
_cli_reasoning_engine: BaseReasoningEngine | None = None


def set_cli_reasoning_engine(engine: BaseReasoningEngine | None) -> None:
    """Inject a custom reasoning engine (primarily for testing and mock injection)."""
    global _cli_reasoning_engine
    _cli_reasoning_engine = engine


def resolve_proposal_instance(proposal: Any) -> Any:
    """Resolve raw dictionary or proposal object into concrete typed proposal."""
    if isinstance(
        proposal,
        (
            BranchProposal,
            CommitProposal,
            PullRequestProposal,
            MigrationProposalSql,
            RollbackProposalSql,
        ),
    ):
        return proposal
    if isinstance(proposal, dict):
        if "head_branch" in proposal or "title_type" in proposal:
            with contextlib.suppress(ValidationError):
                return PullRequestProposal.model_validate(proposal)
        if "branch_name" in proposal or "full_branch_name" in proposal:
            with contextlib.suppress(ValidationError):
                return BranchProposal.model_validate(proposal)
        if "commit_type" in proposal or "short_summary" in proposal:
            with contextlib.suppress(ValidationError):
                return CommitProposal.model_validate(proposal)
        if "migration_sql" in proposal:
            with contextlib.suppress(ValidationError):
                return MigrationProposalSql.model_validate(proposal)
        if "target_migration_id" in proposal:
            with contextlib.suppress(ValidationError):
                return RollbackProposalSql.model_validate(proposal)
    return proposal


def _create_mock_spec_fallback(
    prompt: str,
    base_branch: str = "main",
    ticket_id: str | None = None,
) -> dict[str, Any]:
    """Generate a deterministic fallback specification when running with mock engine."""
    import re

    # Extract ticket ID if present in prompt
    ticket_match = re.search(r"\b([A-Z0-9]+-[0-9]+)\b", prompt)
    resolved_ticket = ticket_id or (ticket_match.group(1) if ticket_match else "CORE-101")

    # Determine branch type
    prompt_lower = prompt.lower()
    branch_type = "feat"
    for candidate in ("fix", "chore", "docs", "refactor", "test", "perf"):
        if candidate in prompt_lower:
            branch_type = candidate
            break

    # Determine slug and scope
    words = [re.sub(r"[^a-z0-9\-]", "", w) for w in prompt_lower.split() if w]
    meaningful = [w for w in words if w and w not in (branch_type, "implement", "add", "the", "for", "in")]
    slug = "-".join(meaningful[:3])[:28] or "task-operation"
    if not slug[0].isalnum():
        slug = f"op-{slug}"
    scope = meaningful[0][:15] if meaningful else "core"

    summary = f"implement {slug.replace('-', ' ')}"[:48].strip().removesuffix(".")

    return {
        "branch_type": branch_type,
        "branch_name": slug,
        "scope": scope,
        "summary": summary,
        "base_branch": base_branch,
        "ticket_id": resolved_ticket,
    }


@click.group(name="agentgate")
@click.version_option(version="0.1.0", prog_name="AgentGate")
def cli() -> None:
    """AgentGate: Deterministic Guardrails and HITL Operations."""


@cli.command("plan")
@click.argument("prompt", type=str)
@click.option(
    "--engine",
    type=click.Choice(["gemini", "mock"], case_sensitive=False),
    default="gemini",
    help="Reasoning engine to extract TaskSpecification (default: gemini).",
)
@click.option(
    "--base-branch",
    type=str,
    default="main",
    help="Target base branch to fork from and merge into (default: main).",
)
@click.option(
    "--ticket-id",
    type=str,
    default=None,
    help="Optional issue tracking ticket identifier (e.g. CORE-123).",
)
@click.option(
    "--storage-path",
    type=click.Path(),
    default=str(DEFAULT_STORAGE_PATH),
    help="Path to guardrail proposals store file.",
)
def plan_command(
    prompt: str,
    engine: str,
    base_branch: str,
    ticket_id: str | None,
    storage_path: str,
) -> None:
    """Extract a task specification from natural language and stage 3-stage proposals."""
    if _cli_reasoning_engine is not None:
        active_engine = _cli_reasoning_engine
    elif engine.lower() == "mock":
        mock_data = _create_mock_spec_fallback(prompt, base_branch=base_branch, ticket_id=ticket_id)
        active_engine = MockReasoningEngine(default_response=mock_data)
    else:
        active_engine = GeminiReasoningEngine()

    click.echo(f"Planning task using reasoning engine: {active_engine.__class__.__name__}...")
    try:
        task_spec = active_engine.extract_structured(
            prompt=prompt,
            schema=TaskSpecification,
            system_instruction=(
                "You are an expert software engineer extracting task specifications for git workflows. "
                "Convert the user requirement into a structured TaskSpecification adhering strictly to schema rules: "
                "branch_type must be one of feat, fix, chore, docs, refactor, test, perf. "
                "branch_name must be lowercase alphanumeric and hyphens (max 30 chars). "
                "scope must be lowercase alphanumeric, hyphens or underscores (max 15 chars). "
                "summary must be imperative mood starting with lowercase, max 50 chars, no ending period, no banned phrases."
            ),
        )
    except ReasoningError as exc:
        click.secho(f"Error: Reasoning failed: {exc}", fg="red", err=True)
        raise click.Abort()

    updates: dict[str, Any] = {}
    if ticket_id is not None and not task_spec.ticket_id:
        updates["ticket_id"] = ticket_id
    if base_branch != "main" and task_spec.base_branch == "main":
        updates["base_branch"] = base_branch
    if updates:
        task_spec = task_spec.model_copy(update=updates)

    gate = ApprovalGate(storage_path=storage_path)

    # Stage 1: Branch
    branch_prop = BranchProposal(
        branch_type=task_spec.branch_type,
        branch_name=task_spec.branch_name,
        base_branch=task_spec.base_branch,
        ticket_id=task_spec.ticket_id,
    )
    rec_branch = gate.submit_proposal(branch_prop)

    # Stage 2: Commit
    commit_type = CommitType(task_spec.branch_type.value)
    commit_prop = CommitProposal(
        branch=branch_prop.full_branch_name,
        commit_type=commit_type,
        scope=task_spec.scope,
        short_summary=task_spec.summary,
        ticket_id=task_spec.ticket_id,
    )
    rec_commit = gate.submit_proposal(commit_prop)

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
    rec_pr = gate.submit_proposal(pr_prop)

    click.secho("\nWORKFLOW PROPOSALS STAGED SUCCESSFULLY", fg="green", bold=True)
    click.echo(f"Task: {task_spec.branch_type.value}({task_spec.scope}): {task_spec.summary}")
    click.echo("-" * 80)
    click.echo(f"[1] BRANCH: [{rec_branch.proposal_id}] -> {rec_branch.rendered_message}")
    click.echo(f"[2] COMMIT: [{rec_commit.proposal_id}] -> {rec_commit.rendered_message}")
    click.echo(f"[3] PR:     [{rec_pr.proposal_id}] -> {rec_pr.rendered_message}")
    click.echo("-" * 80)
    click.secho("Status: ALL STAGES PENDING_APPROVAL", fg="yellow", bold=True)
    click.echo("Operator approval is required before execution.")
    click.echo(f"Run 'gate approve {rec_branch.proposal_id}' to authorize Stage 1.")


@cli.group("proposals")
def proposals_group() -> None:
    """Manage and inspect staged proposals."""


@proposals_group.command("list")
@click.option(
    "--all",
    "show_all",
    is_flag=True,
    help="Show all proposals including executed, approved, and rejected.",
)
@click.option(
    "--storage-path",
    type=click.Path(),
    default=str(DEFAULT_STORAGE_PATH),
    help="Path to guardrail proposals store file.",
)
def list_proposals_command(show_all: bool, storage_path: str) -> None:
    """List staged proposals with polymorphic formatting."""
    gate = ApprovalGate(storage_path=storage_path)
    records = list(gate._registry.values()) if show_all else gate.list_pending()
    if not records:
        msg = "No proposals found." if show_all else "No pending proposals awaiting approval."
        click.echo(msg)
        return

    click.secho(f"Staged Proposals ({len(records)} total):", bold=True)
    click.echo("-" * 80)
    for rec in records:
        prop = resolve_proposal_instance(rec.proposal)
        if isinstance(prop, BranchProposal):
            kind = "[BRANCH]"
            target = prop.full_branch_name
        elif isinstance(prop, CommitProposal):
            kind = "[COMMIT]"
            target = prop.branch
        elif isinstance(prop, PullRequestProposal):
            kind = "[PR]"
            target = f"{prop.head_branch} -> {prop.base_branch}"
        elif isinstance(prop, MigrationProposalSql):
            kind = "[SQL_MIG]"
            target = f"{prop.operation_type.value}:{prop.target_table}"
        elif isinstance(prop, RollbackProposalSql):
            kind = "[SQL_ROLL]"
            target = f"table:{prop.target_table}"
        else:
            kind = "[PROPOSAL]"
            target = getattr(prop, "branch", getattr(prop, "full_branch_name", "unknown"))

        status_color = "yellow" if rec.status == ProposalStatus.PENDING_APPROVAL else (
            "green" if rec.status in (ProposalStatus.APPROVED, ProposalStatus.EXECUTED) else "red"
        )
        status_label = click.style(rec.status.value.upper(), fg=status_color, bold=True)
        click.echo(f"  {kind:<8} [{rec.proposal_id}] Status: {status_label} | Target: {target}")
        click.echo(f"           Message: {rec.rendered_message}")
    click.echo("-" * 80)


cli.add_command(list_proposals_command, name="list")


@cli.command("approve")
@click.argument("proposal_id", type=str)
@click.option(
    "--storage-path",
    type=click.Path(),
    default=str(DEFAULT_STORAGE_PATH),
    help="Path to guardrail proposals store file.",
)
def approve_command(proposal_id: str, storage_path: str) -> None:
    """Approve a pending proposal (Human-in-the-Loop authorization)."""
    gate = ApprovalGate(storage_path=storage_path)
    try:
        record = gate.approve(proposal_id)
        click.secho(f"[OK] Proposal '{record.proposal_id}' APPROVED.", fg="green", bold=True)
        click.echo(f"  Action:    {record.rendered_message}")
        click.echo(f"  Next step: Run 'gate execute {record.proposal_id}' to execute.")
    except KeyError:
        click.secho(f"Error: Proposal ID '{proposal_id}' was not found.", fg="red", err=True)
        raise click.Abort()
    except ValueError as exc:
        click.secho(f"Error: Cannot approve proposal: {exc}", fg="red", err=True)
        raise click.Abort()


@cli.command("reject")
@click.argument("proposal_id", type=str)
@click.option(
    "--reason",
    type=str,
    default="Rejected by operator",
    help="Operator rejection explanation.",
)
@click.option(
    "--storage-path",
    type=click.Path(),
    default=str(DEFAULT_STORAGE_PATH),
    help="Path to guardrail proposals store file.",
)
def reject_command(proposal_id: str, reason: str, storage_path: str) -> None:
    """Reject a pending proposal."""
    gate = ApprovalGate(storage_path=storage_path)
    try:
        record = gate.reject(proposal_id, reason=reason)
        click.secho(f"[REJECTED] Proposal '{record.proposal_id}' REJECTED.", fg="yellow", bold=True)
        click.echo(f"  Reason: {record.rejection_reason}")
    except KeyError:
        click.secho(f"Error: Proposal ID '{proposal_id}' was not found.", fg="red", err=True)
        raise click.Abort()
    except ValueError as exc:
        click.secho(f"Error: Cannot reject proposal: {exc}", fg="red", err=True)
        raise click.Abort()


@cli.command("execute")
@click.argument("proposal_id", type=str)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Simulate execution without performing actual Git mutation.",
)
@click.option(
    "--repo-path",
    type=str,
    default=".",
    help="Path to repository (default: current directory).",
)
@click.option(
    "--storage-path",
    type=click.Path(),
    default=str(DEFAULT_STORAGE_PATH),
    help="Path to guardrail proposals store file.",
)
@click.option(
    "--db-path",
    type=str,
    default=None,
    help="Target SQLite database file path for SQL migrations.",
)
def execute_command(
    proposal_id: str,
    dry_run: bool,
    repo_path: str,
    storage_path: str,
    db_path: str | None,
) -> None:
    """Execute an APPROVED proposal deterministically."""
    gate = ApprovalGate(storage_path=storage_path)
    record = gate.get_record(proposal_id)
    if not record:
        click.secho(f"Error: Proposal ID '{proposal_id}' was not found.", fg="red", err=True)
        raise click.Abort()

    if record.status != ProposalStatus.APPROVED:
        click.secho(
            f"Execution Blocked: Proposal '{proposal_id}' is in status '{record.status.value.upper()}'. "
            f"Prior human approval is strictly required. Run 'gate approve {proposal_id}' first.",
            fg="red",
            err=True,
        )
        raise click.Abort()

    adapter = GitGuardrailAdapter()
    proposal = resolve_proposal_instance(record.proposal)

    if isinstance(proposal, BranchProposal):
        success, output = adapter.execute_create_branch(record, repo_path=repo_path, dry_run=dry_run)
        action_name = "BRANCH CREATION"
    elif isinstance(proposal, CommitProposal):
        success, output = adapter.execute_commit(record, repo_path=repo_path, dry_run=dry_run)
        action_name = "COMMIT"
    elif isinstance(proposal, PullRequestProposal):
        success, output = adapter.execute_create_pr(record, repo_path=repo_path, dry_run=dry_run)
        action_name = "PULL REQUEST"
    elif isinstance(proposal, MigrationProposalSql):
        sql_adapter = GuardrailAdapterSql()
        target_db = db_path or os.getenv("AGENTGATE_SQL_DB_PATH", ":memory:")
        success, output = sql_adapter.execute_migration(record, db_path=target_db, dry_run=dry_run)
        action_name = "SQL MIGRATION"
    elif isinstance(proposal, RollbackProposalSql):
        sql_adapter = GuardrailAdapterSql()
        target_db = db_path or os.getenv("AGENTGATE_SQL_DB_PATH", ":memory:")
        success, output = sql_adapter.execute_rollback(record, db_path=target_db, dry_run=dry_run)
        action_name = "SQL ROLLBACK"
    else:
        click.secho(f"Error: Unsupported proposal type '{type(proposal).__name__}'.", fg="red", err=True)
        raise click.Abort()

    if not success:
        click.secho(f"Error: {action_name} failed:\n{output}", fg="red", err=True)
        raise click.Abort()

    # Strictly mark executed only after successful Git execution
    gate.mark_executed(proposal_id)
    click.secho(f"[EXECUTED] {action_name} executed successfully.", fg="green", bold=True)
    click.echo(f"  Proposal ID: {record.proposal_id}")
    click.echo(f"  Action:      {record.rendered_message}")
    if output:
        click.echo(f"  Details:     {output}")


@cli.group("mcp")
def mcp_group() -> None:
    """Manage and serve the Model Context Protocol (MCP) Gateway."""


@mcp_group.command("serve")
@click.option(
    "--transport",
    type=click.Choice(["stdio", "sse", "streamable-http"], case_sensitive=False),
    default="stdio",
    help="Transport protocol (default: stdio).",
)
@click.option(
    "--host",
    type=str,
    default="0.0.0.0",
    help="Bind host for SSE/HTTP (default: 0.0.0.0).",
)
@click.option(
    "--port",
    type=int,
    default=8000,
    help="Bind port for SSE/HTTP (default: 8000).",
)
def mcp_serve(transport: str, host: str, port: int) -> None:
    """Start the Guardrails MCP server."""
    from agentgate.mcp.server import run_server

    run_server(transport=transport, host=host, port=port)


def _create_mock_sql_spec_fallback(prompt: str) -> dict[str, Any]:
    """Generate a deterministic fallback SQL specification when running with mock engine."""
    prompt_lower = prompt.lower()
    table = "users"
    for candidate in ("orders", "accounts", "products", "audit_logs", "payments"):
        if candidate in prompt_lower:
            table = candidate
            break

    if any(k in prompt_lower for k in ("table", "tablo", "create")):
        op_type = SqlOperationType.CREATE_TABLE
        mig_sql = f"CREATE TABLE IF NOT EXISTS {table} (id INTEGER PRIMARY KEY, email TEXT, created_at TIMESTAMP);"
        roll_sql = f"-- Safe rollback requires manual deprecation rename for table {table}"
    elif "index" in prompt_lower:
        op_type = SqlOperationType.CREATE_INDEX
        mig_sql = f"CREATE INDEX idx_{table}_status ON {table} (created_at);"
        roll_sql = f"DROP INDEX idx_{table}_status;"
    else:
        op_type = SqlOperationType.ADD_COLUMN
        mig_sql = f"ALTER TABLE {table} ADD COLUMN last_login_at TIMESTAMP;"
        roll_sql = f"-- Safe column rollback requires table recreate in SQLite for {table}"

    return {
        "dialect": SqlDialect.SQLITE,
        "operation_type": op_type,
        "target_table": table,
        "migration_sql": mig_sql,
        "rollback_sql": roll_sql,
        "description": f"migration for {table} based on prompt: {prompt[:40]}",
    }


@cli.group("sql")
def sql_group() -> None:
    """Manage and stage database schema migrations."""


@sql_group.command("plan")
@click.argument("prompt", type=str)
@click.option(
    "--engine",
    type=click.Choice(["gemini", "mock"], case_sensitive=False),
    default="gemini",
    help="Reasoning engine to extract SqlTaskSpecification (default: gemini).",
)
@click.option(
    "--storage-path",
    type=click.Path(),
    default=str(DEFAULT_STORAGE_PATH),
    help="Target JSON path for persistent proposal storage.",
)
def sql_plan(
    prompt: str,
    engine: str,
    storage_path: str,
) -> None:
    """Extract SQL migration and rollback queries from natural language and stage for approval."""
    gate = ApprovalGate(storage_path=Path(storage_path))
    sql_adapter = GuardrailAdapterSql()

    # Step 1: Extract or mock SqlTaskSpecification
    if _cli_reasoning_engine is not None:
        try:
            task_spec = _cli_reasoning_engine.extract_structured(prompt, SqlTaskSpecification)
        except ReasoningError as exc:
            click.secho(f"Error extracting SQL specification: {exc}", fg="red", err=True)
            raise click.Abort()
    elif engine.lower() == "mock":
        fallback_data = _create_mock_sql_spec_fallback(prompt)
        task_spec = SqlTaskSpecification.model_validate(fallback_data)
    else:
        try:
            reasoning_eng = GeminiReasoningEngine()
            task_spec = reasoning_eng.extract_structured(prompt, SqlTaskSpecification)
        except Exception as exc:  # noqa: BLE001
            click.secho(f"Gemini reasoning failed: {exc}. Retrying with deterministic mock spec.", fg="yellow")
            fallback_data = _create_mock_sql_spec_fallback(prompt)
            task_spec = SqlTaskSpecification.model_validate(fallback_data)

    # Step 2: Formulate MigrationProposalSql
    proposal = MigrationProposalSql(
        dialect=task_spec.dialect,
        operation_type=task_spec.operation_type,
        target_table=task_spec.target_table,
        migration_sql=task_spec.migration_sql,
        rollback_sql=task_spec.rollback_sql,
        description=task_spec.description,
    )

    # Step 3: Propose through GuardrailAdapterSql
    val_result = sql_adapter.validate_proposal(proposal)
    if not val_result.is_valid:
        click.secho("Error: SQL Proposal rejected by guardrail security inspector:", fg="red", err=True)
        for err in val_result.errors:
            click.echo(f"  - {err}")
        raise click.Abort()

    record = gate.submit_proposal(proposal)

    click.secho("\nSQL MIGRATION PROPOSAL STAGED SUCCESSFULLY", fg="green", bold=True)
    click.echo(f"Proposal ID:   [{record.proposal_id}]")
    click.echo(f"Operation:     {proposal.operation_type.value.upper()} on table '{proposal.target_table}'")
    click.echo(f"Migration SQL: {proposal.migration_sql.strip()}")
    click.echo(f"Rollback SQL:  {proposal.rollback_sql.strip()}")
    click.echo("-" * 80)
    click.secho("Status: PENDING_APPROVAL", fg="yellow", bold=True)
    click.echo("Operator approval is required before execution.")
    click.echo(f"Run 'gate approve {record.proposal_id}' to authorize execution.")


@cli.group("audit")
def audit_group() -> None:
    """Inspect and cryptographically verify the immutable audit ledger."""


@audit_group.command("verify")
@click.option(
    "--storage-path",
    type=click.Path(),
    default=str(DEFAULT_LEDGER_STORAGE_PATH),
    help="Path to guardrail audit ledger storage file.",
)
def audit_verify(storage_path: str) -> None:
    """Cryptographically verify the integrity of the audit ledger hash chain."""
    engine = LedgerEngineAudit(storage_path=storage_path)
    total_blocks = len(engine.chain)
    if total_blocks == 0:
        click.secho("Audit Ledger is empty (0 blocks).", fg="yellow")
        return

    is_valid, error_reason = engine.verify_integrity()
    if is_valid:
        click.secho(
            f"[SECURE] Audit Ledger integrity verified: {total_blocks} chained blocks intact.",
            fg="green",
            bold=True,
        )
        first_hash = engine.chain[0].current_hash[:16]
        latest_hash = engine.chain[-1].current_hash[:16]
        click.echo(f"  Genesis Block Hash:  {first_hash}...")
        click.echo(f"  Latest Sealed Block: {latest_hash}...")
    else:
        click.secho(
            f"[TAMPER DETECTED] Cryptographic integrity violation!\n  {error_reason}",
            fg="red",
            bold=True,
            err=True,
        )
        raise click.Abort()


@audit_group.command("trail")
@click.argument("proposal_id", type=str)
@click.option(
    "--storage-path",
    type=click.Path(),
    default=str(DEFAULT_LEDGER_STORAGE_PATH),
    help="Path to guardrail audit ledger storage file.",
)
def audit_trail(proposal_id: str, storage_path: str) -> None:
    """Export and display the complete cryptographic audit trail for a proposal."""
    engine = LedgerEngineAudit(storage_path=storage_path)
    trail = engine.export_audit_trail(proposal_id)
    if not trail:
        click.secho(f"No audit records found for proposal '{proposal_id}'.", fg="yellow")
        return

    click.secho(f"\nAUDIT TRAIL FOR PROPOSAL [{proposal_id}] ({len(trail)} blocks)", fg="cyan", bold=True)
    click.echo("=" * 80)
    for block in trail:
        click.echo(
            f"Block #{block.sequence_number} | Type: {block.entry_type.value.upper()} | "
            f"Domain: {block.domain.upper()}"
        )
        click.echo(f"  Timestamp UTC:  {block.timestamp_utc}")
        click.echo(f"  Operator:       {block.operator_id or 'SYSTEM/AUTOMATED'}")
        click.echo(f"  Payload Digest: {block.payload_digest[:24]}...")
        click.echo(f"  Prev Hash:      {block.prev_hash[:24]}...")
        click.echo(f"  Current Hash:   {block.current_hash[:24]}...")
        click.echo("-" * 80)


def main() -> None:
    """CLI execution entrypoint."""
    cli()


if __name__ == "__main__":
    main()
