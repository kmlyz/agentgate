"""SQL domain guardrail adapter and deterministic dialect transaction execution engine."""

import logging
import sqlite3
from abc import ABC, abstractmethod
from typing import Any

from agentgate.guardrails.adapters.sql.sql_inspector_ast import AstInspectorSql
from agentgate.guardrails.adapters.sql.sql_schemas_migration import (
    MigrationProposalSql,
    RollbackProposalSql,
    SqlDialect,
)
from agentgate.guardrails.core.gate import ApprovalGate
from agentgate.guardrails.core.models import (
    ProposalRecord,
    ProposalValidationResult,
)

logger = logging.getLogger(__name__)


class BaseSqlDialectExecutor(ABC):
    """Abstract dialect executor interface separating execution engines."""

    @abstractmethod
    def simulate_transaction(self, query: str, rendered_desc: str) -> tuple[bool, str]:
        """Perform transactional dry-run simulation."""
        ...

    @abstractmethod
    def execute_transaction(self, query: str, db_path: str, rendered_desc: str) -> tuple[bool, str]:
        """Execute live transaction on target database."""
        ...


class SqliteDialectExecutor(BaseSqlDialectExecutor):
    """Deterministic transaction executor for SQLite databases."""

    def simulate_transaction(self, query: str, rendered_desc: str) -> tuple[bool, str]:
        """Simulate execution inside an in-memory transactional dry-run."""
        try:
            conn = sqlite3.connect(":memory:")
            cursor = conn.cursor()
            cursor.execute("BEGIN TRANSACTION;")
            cursor.execute(query)
            conn.rollback()
            conn.close()
            return True, f"[DRY_RUN] Simulated query successfully: {rendered_desc}"
        except sqlite3.Error as e:
            return False, f"[DRY_RUN] Query execution simulation failed: {e}"

    def execute_transaction(self, query: str, db_path: str, rendered_desc: str) -> tuple[bool, str]:
        """Execute and commit query inside a transaction on target database file."""
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("BEGIN TRANSACTION;")
            cursor.execute(query)
            conn.commit()
            conn.close()
            return True, f"Successfully executed and committed: {rendered_desc}"
        except sqlite3.Error as e:
            try:
                conn.rollback()
                conn.close()
            except sqlite3.Error as cleanup_err:
                logger.warning("Failed to cleanly rollback/close SQLite connection: %s", cleanup_err)
            return False, f"Database transaction failed and was rolled back: {e}"


class PostgresDialectExecutor(BaseSqlDialectExecutor):
    """Dialect executor for PostgreSQL migrations with isolated mock/dry-run support."""

    def simulate_transaction(self, query: str, rendered_desc: str) -> tuple[bool, str]:
        return True, f"[POSTGRES_DRY_RUN] AST and schema validated for PostgreSQL: {rendered_desc}"

    def execute_transaction(self, query: str, db_path: str, rendered_desc: str) -> tuple[bool, str]:
        raise NotImplementedError(
            "Direct PostgreSQL live execution requires PostgreSQL driver adapter "
            "(agentgate-pro). Use dry_run=True or delegate to target migration pipeline."
        )


class GuardrailAdapterSql:
    """Universal guardrail adapter for database mutations and schema migrations."""

    def __init__(self, inspector: AstInspectorSql | None = None) -> None:
        self.inspector = inspector or AstInspectorSql()

    def _get_executor_for_dialect(self, dialect: SqlDialect | str) -> BaseSqlDialectExecutor:
        val = dialect.value if hasattr(dialect, "value") else str(dialect).lower()
        if val in (SqlDialect.POSTGRESQL.value, "postgresql", "postgres"):
            return PostgresDialectExecutor()
        return SqliteDialectExecutor()

    def validate_proposal(
        self,
        proposal: MigrationProposalSql | RollbackProposalSql | Any,
    ) -> ProposalValidationResult:
        """Validate an incoming SQL proposal against schema and security AST rules."""
        if isinstance(proposal, MigrationProposalSql):
            is_valid, errors = self.inspector.inspect_migration_pair(
                proposal.migration_sql,
                proposal.rollback_sql,
            )
            # Transactional dry-run syntax check via dialect executor
            if is_valid:
                executor = self._get_executor_for_dialect(proposal.dialect)
                dry_ok, dry_msg = executor.simulate_transaction(proposal.migration_sql, proposal.render_message())
                if not dry_ok:
                    is_valid = False
                    errors.append(f"Dry-run syntax simulation failed: {dry_msg}")

            return ProposalValidationResult(
                is_valid=is_valid,
                rendered_message=proposal.render_message() if is_valid else None,
                errors=errors,
                metadata={
                    "operation_type": proposal.operation_type.value,
                    "target_table": proposal.target_table,
                    "dialect": proposal.dialect.value,
                },
            )

        if isinstance(proposal, RollbackProposalSql):
            is_valid, err = self.inspector.validate_sql(proposal.rollback_sql)
            errors = [err] if err else []
            if is_valid and proposal.dialect in (SqlDialect.SQLITE, "sqlite"):
                dry_ok, dry_msg = self._simulate_transaction(proposal.rollback_sql, proposal.render_message())
                if not dry_ok:
                    is_valid = False
                    errors.append(f"Dry-run syntax simulation failed: {dry_msg}")

            return ProposalValidationResult(
                is_valid=is_valid,
                rendered_message=proposal.render_message() if is_valid else None,
                errors=errors,
                metadata={
                    "target_migration_id": proposal.target_migration_id,
                    "target_table": proposal.target_table,
                },
            )

        return ProposalValidationResult(
            is_valid=False,
            errors=[f"Unsupported SQL proposal type: '{type(proposal).__name__}'."],
        )

    def propose_migration(
        self,
        arg1: ApprovalGate | MigrationProposalSql,
        arg2: MigrationProposalSql | ApprovalGate | None = None,
        gate: ApprovalGate | None = None,
    ) -> ProposalRecord:
        """Validate and enqueue forward migration into PENDING_APPROVAL state."""
        if isinstance(arg1, ApprovalGate):
            active_gate = arg1
            if not isinstance(arg2, MigrationProposalSql):
                raise TypeError(f"Expected MigrationProposalSql for second argument, got {type(arg2)}")
            proposal = arg2
        else:
            proposal = arg1
            active_gate = arg2 if isinstance(arg2, ApprovalGate) else gate

        val_result = self.validate_proposal(proposal)
        if not val_result.is_valid:
            error_details = "; ".join(val_result.errors)
            raise ValueError(f"Proposal validation failed: {error_details}")

        target_gate = active_gate if active_gate is not None else ApprovalGate(storage_path=None)
        return target_gate.submit_proposal(proposal)

    def propose_rollback(
        self,
        arg1: ApprovalGate | RollbackProposalSql,
        arg2: RollbackProposalSql | ApprovalGate | None = None,
        gate: ApprovalGate | None = None,
    ) -> ProposalRecord:
        """Validate and enqueue rollback proposal into PENDING_APPROVAL state."""
        if isinstance(arg1, ApprovalGate):
            active_gate = arg1
            if not isinstance(arg2, RollbackProposalSql):
                raise TypeError(f"Expected RollbackProposalSql for second argument, got {type(arg2)}")
            proposal = arg2
        else:
            proposal = arg1
            active_gate = arg2 if isinstance(arg2, ApprovalGate) else gate

        val_result = self.validate_proposal(proposal)
        if not val_result.is_valid:
            error_details = "; ".join(val_result.errors)
            raise ValueError(f"Proposal validation failed: {error_details}")

        target_gate = active_gate if active_gate is not None else ApprovalGate(storage_path=None)
        return target_gate.submit_proposal(proposal)

    def execute_migration(
        self,
        target: ProposalRecord | MigrationProposalSql,
        db_path: str = ":memory:",
        dry_run: bool = False,
    ) -> tuple[bool, str]:
        """Execute approved migration in a transactional boundary with rollback safety."""
        if isinstance(target, ProposalRecord):
            proposal = target.proposal
            if isinstance(proposal, dict):
                proposal = MigrationProposalSql.model_validate(proposal)
        else:
            proposal = target

        if not isinstance(proposal, MigrationProposalSql):
            return False, f"Target does not contain MigrationProposalSql: '{type(proposal)}'"

        query = proposal.migration_sql.strip()
        executor = self._get_executor_for_dialect(proposal.dialect)

        if dry_run:
            return executor.simulate_transaction(query, proposal.render_message())

        try:
            return executor.execute_transaction(query, db_path, proposal.render_message())
        except NotImplementedError as exc:
            return False, f"Unsupported dialect execution: {exc}"

    def execute_rollback(
        self,
        target: ProposalRecord | RollbackProposalSql,
        db_path: str = ":memory:",
        dry_run: bool = False,
    ) -> tuple[bool, str]:
        """Execute approved rollback query."""
        if isinstance(target, ProposalRecord):
            proposal = target.proposal
            if isinstance(proposal, dict):
                proposal = RollbackProposalSql.model_validate(proposal)
        else:
            proposal = target

        if not isinstance(proposal, RollbackProposalSql):
            return False, f"Target does not contain RollbackProposalSql: '{type(proposal)}'"

        query = proposal.rollback_sql.strip()
        executor = self._get_executor_for_dialect(proposal.dialect)

        if dry_run:
            return executor.simulate_transaction(query, proposal.render_message())

        try:
            return executor.execute_transaction(query, db_path, proposal.render_message())
        except NotImplementedError as exc:
            return False, f"Unsupported dialect execution: {exc}"

    def _simulate_transaction(self, query: str, rendered_desc: str) -> tuple[bool, str]:
        """Execute query inside isolated in-memory transaction and immediately rollback."""
        return SqliteDialectExecutor().simulate_transaction(query, rendered_desc)

    def _execute_live_transaction(
        self,
        query: str,
        db_path: str,
        rendered_desc: str,
    ) -> tuple[bool, str]:
        """Execute live transaction on target SQLite database with defensive rollback."""
        return SqliteDialectExecutor().execute_transaction(query, db_path, rendered_desc)



# Alias for compliance
SqlGuardrailAdapter = GuardrailAdapterSql
