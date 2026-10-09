"""Tests for SQL Migration Guardrail Adapter, AST Inspector, and polymorphic execution."""

import os
import sqlite3
from pathlib import Path

import pytest
from click.testing import CliRunner
from pydantic import ValidationError

from agentgate.cli.cli_operator_entrypoint import cli
from agentgate.guardrails.adapters.sql import (
    AstInspectorSql,
    GuardrailAdapterSql,
    MigrationProposalSql,
    RollbackProposalSql,
    SqlDialect,
    SqlOperationType,
    SqlTaskSpecification,
)
from agentgate.guardrails.core import ApprovalGate, ProposalStatus
from agentgate.mcp.server import (
    approval_gate,
    approve_proposal,
    execute_approved_proposal,
    list_pending_proposals,
    propose_sql_migration,
)


class TestSqlSchemas:
    """Validate strict Pydantic v2 schemas and extra='forbid' constraint."""

    def test_migration_proposal_valid(self) -> None:
        prop = MigrationProposalSql(
            dialect=SqlDialect.SQLITE,
            operation_type=SqlOperationType.CREATE_TABLE,
            target_table="users",
            migration_sql="CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT NOT NULL);",
            rollback_sql="-- rollback marker",
            description="Create users table with email",
        )
        assert prop.dialect == SqlDialect.SQLITE
        assert prop.target_table == "users"
        assert prop.operation_type == SqlOperationType.CREATE_TABLE

    def test_migration_proposal_extra_fields_forbidden(self) -> None:
        with pytest.raises(ValidationError):
            MigrationProposalSql(
                dialect=SqlDialect.SQLITE,
                operation_type=SqlOperationType.CREATE_TABLE,
                target_table="users",
                migration_sql="CREATE TABLE users (id INT);",
                rollback_sql="-- rollback",
                description="Create users",
                unauthorized_extra_field="malicious_payload",
            )

    def test_rollback_proposal_valid(self) -> None:
        rollback = RollbackProposalSql(
            dialect=SqlDialect.SQLITE,
            target_table="users",
            rollback_sql="DELETE FROM users WHERE id = 100;",
            target_migration_id="prop_1234abcd",
            reason="Rollback inserted record safely",
        )
        assert rollback.target_migration_id == "prop_1234abcd"
        assert rollback.dialect == SqlDialect.SQLITE

    def test_rollback_proposal_extra_forbidden(self) -> None:
        with pytest.raises(ValidationError):
            RollbackProposalSql(
                dialect=SqlDialect.SQLITE,
                target_table="users",
                rollback_sql="DELETE FROM users WHERE id = 1;",
                target_migration_id="prop_1234abcd",
                reason="Revert migration",
                unexpected_field=123,
            )

    def test_sql_task_specification(self) -> None:
        spec = SqlTaskSpecification(
            dialect=SqlDialect.SQLITE,
            operation_type=SqlOperationType.ADD_COLUMN,
            target_table="accounts",
            migration_sql="ALTER TABLE accounts ADD COLUMN balance REAL DEFAULT 0.0;",
            rollback_sql="-- sqlite table recreate required",
            description="Add balance column",
        )
        assert spec.operation_type == SqlOperationType.ADD_COLUMN
        assert spec.target_table == "accounts"


class TestAstInspectorSql:
    """Validate deterministic AST inspection and blocking of destructive SQL."""

    @pytest.fixture
    def inspector(self) -> AstInspectorSql:
        return AstInspectorSql()

    @pytest.mark.parametrize(
        "destructive_sql",
        [
            "DROP TABLE users;",
            "drop table if exists users",
            "DROP DATABASE production;",
            "DROP SCHEMA public CASCADE;",
            "DROP VIEW active_users;",
            "TRUNCATE TABLE audit_logs;",
            "truncate logs",
            "ALTER TABLE users DROP COLUMN email;",
            "ALTER TABLE users DROP email;",
            "ATTACH DATABASE 'evil.db' AS evil;",
            "GRANT ALL PRIVILEGES ON users TO attacker;",
            "REVOKE ALL ON users FROM admin;",
            "SHUTDOWN;",
        ],
    )
    def test_inspector_blocks_destructive_ddl(
        self, inspector: AstInspectorSql, destructive_sql: str
    ) -> None:
        is_safe, reason = inspector.validate_sql(destructive_sql)
        assert not is_safe
        assert reason is not None
        assert any(term in reason.lower() for term in ["prohibited", "blocked", "destructive"])

    @pytest.mark.parametrize(
        "unconstrained_dml",
        [
            "DELETE FROM users;",
            "DELETE FROM users",
            "DELETE FROM users WHERE 1=1;",
            "DELETE FROM users WHERE true;",
            "DELETE FROM users WHERE '1' = '1';",
            "UPDATE users SET is_active = 0;",
            "UPDATE users SET is_active = 0 WHERE 1=1;",
            "UPDATE users SET is_active = 0 WHERE true;",
        ],
    )
    def test_inspector_blocks_unconstrained_dml(
        self, inspector: AstInspectorSql, unconstrained_dml: str
    ) -> None:
        is_safe, reason = inspector.validate_sql(unconstrained_dml)
        assert not is_safe
        assert reason is not None
        assert "unconstrained" in reason.lower() or "prohibited" in reason.lower()

    def test_inspector_blocks_multi_statement_injection(
        self, inspector: AstInspectorSql
    ) -> None:
        injected = "CREATE TABLE dummy (id INT); DROP TABLE users;"
        is_safe, reason = inspector.validate_sql(injected)
        assert not is_safe
        assert reason is not None
        assert "multi-statement" in reason.lower()

    def test_inspector_handles_comments_and_blocks_hidden_destructions(
        self, inspector: AstInspectorSql
    ) -> None:
        comment_hidden_1 = "/* safe comment */ DROP TABLE users;"
        is_safe, reason = inspector.validate_sql(comment_hidden_1)
        assert not is_safe
        assert reason is not None

        comment_hidden_2 = "-- harmless note\nTRUNCATE TABLE users;"
        is_safe, reason = inspector.validate_sql(comment_hidden_2)
        assert not is_safe
        assert reason is not None

    @pytest.mark.parametrize(
        "valid_sql",
        [
            "CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT NOT NULL);",
            "ALTER TABLE items ADD COLUMN price REAL DEFAULT 0.0;",
            "CREATE INDEX idx_items_name ON items(name);",
            "INSERT INTO items (name, price) VALUES ('Book', 12.5);",
            "UPDATE items SET price = 15.0 WHERE id = 1;",
            "DELETE FROM items WHERE id = 1;",
        ],
    )
    def test_inspector_accepts_valid_safe_sql(
        self, inspector: AstInspectorSql, valid_sql: str
    ) -> None:
        is_safe, reason = inspector.validate_sql(valid_sql)
        assert is_safe
        assert reason is None

    @pytest.mark.parametrize(
        "sql_with_semicolons",
        [
            "INSERT INTO logs (level, msg) VALUES ('INFO', 'Batch complete; status=200; records=42');",
            "INSERT INTO logs (msg) VALUES ('It''s ok; proceed; code=1');",
            'INSERT INTO logs ("msg") VALUES (\'error; retry; delay=5s\');',
            "/* Note: migration step; do not delete; */ INSERT INTO settings (val) VALUES ('key;val'); -- trailing; comment",
            "UPDATE config SET conn_str = 'host=db;port=5432;ssl=true' WHERE id = 1;",
        ],
    )
    def test_inspector_preserves_semicolons_in_literals_and_comments(
        self, inspector: AstInspectorSql, sql_with_semicolons: str
    ) -> None:
        is_safe, reason = inspector.validate_sql(sql_with_semicolons)
        assert is_safe, f"Expected safe but got: {reason}"
        assert reason is None

    def test_inspector_splits_statements_lexically(self) -> None:
        raw = "SELECT 1; SELECT 'a;b'; -- comment; \n SELECT 3;"
        stmts = AstInspectorSql.split_statements(raw)
        assert len(stmts) == 3
        assert stmts[0] == "SELECT 1"
        assert stmts[1] == "SELECT 'a;b'"
        assert stmts[2] == "SELECT 3"



class TestGuardrailAdapterSql:
    """Validate GuardrailAdapterSql propose, validation, dry-run, and transactional execution."""

    @pytest.fixture
    def adapter(self) -> GuardrailAdapterSql:
        return GuardrailAdapterSql()

    @pytest.fixture
    def gate(self, tmp_path: Path) -> ApprovalGate:
        storage = tmp_path / "proposals.json"
        return ApprovalGate(storage_path=storage)

    def test_validate_proposal_blocks_destructive(
        self, adapter: GuardrailAdapterSql
    ) -> None:
        prop = MigrationProposalSql(
            dialect=SqlDialect.SQLITE,
            operation_type=SqlOperationType.CREATE_TABLE,
            target_table="users",
            migration_sql="DROP TABLE users;",
            rollback_sql="CREATE TABLE users (id INT);",
            description="Destructive attempt",
        )
        result = adapter.validate_proposal(prop)
        assert not result.is_valid
        assert len(result.errors) > 0
        assert "prohibited" in result.errors[0].lower()

    def test_validate_proposal_dry_run_syntax_error(
        self, adapter: GuardrailAdapterSql
    ) -> None:
        prop = MigrationProposalSql(
            dialect=SqlDialect.SQLITE,
            operation_type=SqlOperationType.CREATE_TABLE,
            target_table="users",
            migration_sql="CREATE TABEL invalid_syntax (id INT);",  # Intentional typo TABEL
            rollback_sql="-- rollback placeholder",
            description="Syntax error migration",
        )
        result = adapter.validate_proposal(prop)
        assert not result.is_valid
        assert any("dry-run syntax simulation failed" in err.lower() for err in result.errors)

    def test_propose_migration_and_gate_staging(
        self, adapter: GuardrailAdapterSql, gate: ApprovalGate
    ) -> None:
        prop = MigrationProposalSql(
            dialect=SqlDialect.SQLITE,
            operation_type=SqlOperationType.CREATE_TABLE,
            target_table="products",
            migration_sql="CREATE TABLE products (id INTEGER PRIMARY KEY, sku TEXT);",
            rollback_sql="-- rollback note",
            description="Create products table",
        )
        record = adapter.propose_migration(prop, gate=gate)
        assert record.status == ProposalStatus.PENDING_APPROVAL
        assert record.proposal_id.startswith("prop_")
        assert record.proposal.target_table == "products"

    def test_transactional_live_execution_and_rollback(
        self, adapter: GuardrailAdapterSql, tmp_path: Path
    ) -> None:
        db_file = tmp_path / "production.db"
        # 1. Execute initial table creation
        prop_create = MigrationProposalSql(
            dialect=SqlDialect.SQLITE,
            operation_type=SqlOperationType.CREATE_TABLE,
            target_table="metrics",
            migration_sql="CREATE TABLE metrics (id INTEGER PRIMARY KEY, score REAL);",
            rollback_sql="-- drop not permitted",
            description="Create metrics table",
        )
        ok, msg = adapter.execute_migration(prop_create, db_path=str(db_file), dry_run=False)
        assert ok
        assert "Successfully executed and committed" in msg

        # Verify table exists in SQLite database
        conn = sqlite3.connect(str(db_file))
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='metrics';")
        assert cursor.fetchone() is not None

        # 2. Execute an insert
        prop_insert = MigrationProposalSql(
            dialect=SqlDialect.SQLITE,
            operation_type=SqlOperationType.INSERT_DATA,
            target_table="metrics",
            migration_sql="INSERT INTO metrics (score) VALUES (98.5);",
            rollback_sql="DELETE FROM metrics WHERE id = 1;",
            description="Seed metrics",
        )
        ok, _ = adapter.execute_migration(prop_insert, db_path=str(db_file), dry_run=False)
        assert ok

        cursor.execute("SELECT COUNT(*) FROM metrics;")
        assert cursor.fetchone()[0] == 1

        # 3. Execute rollback proposal
        rollback_prop = RollbackProposalSql(
            dialect=SqlDialect.SQLITE,
            target_table="metrics",
            rollback_sql="DELETE FROM metrics WHERE id = 1;",
            target_migration_id="prop_1234abcd",
            reason="Rollback seed metrics safely",
        )
        ok, msg = adapter.execute_rollback(rollback_prop, db_path=str(db_file), dry_run=False)
        assert ok

        cursor.execute("SELECT COUNT(*) FROM metrics;")
        assert cursor.fetchone()[0] == 0
        conn.close()

    def test_postgresql_dialect_isolation_dry_run_and_execution(
        self, adapter: GuardrailAdapterSql, gate: ApprovalGate
    ) -> None:
        prop = MigrationProposalSql(
            dialect=SqlDialect.POSTGRESQL,
            operation_type=SqlOperationType.CREATE_TABLE,
            target_table="audit_events",
            migration_sql="CREATE TABLE audit_events (id SERIAL PRIMARY KEY, note TEXT);",
            rollback_sql="-- rollback note",
            description="Create audit events table in PG",
        )
        val = adapter.validate_proposal(prop)
        assert val.is_valid

        record = adapter.propose_migration(prop, gate=gate)
        assert record.status == ProposalStatus.PENDING_APPROVAL

        dry_ok, dry_msg = adapter.execute_migration(record, dry_run=True)
        assert dry_ok
        assert "[POSTGRES_DRY_RUN]" in dry_msg

        gate.approve(record.proposal_id)
        live_ok, live_msg = adapter.execute_migration(record, dry_run=False)
        assert not live_ok
        assert "Unsupported dialect execution" in live_msg
        assert "PostgreSQL live execution requires" in live_msg



class TestMcpSqlIntegration:
    """Validate MCP tools for SQL migration proposals and polymorphic execution."""

    def test_mcp_propose_and_polymorphic_execution(self, tmp_path: Path) -> None:
        # Configure isolated approval gate for MCP test
        storage_file = tmp_path / "mcp_proposals.json"
        approval_gate.storage_path = storage_file
        approval_gate._registry.clear()

        # Step 1: Propose SQL migration
        res = propose_sql_migration(
            dialect="sqlite",
            operation_type="create_table",
            target_table="invoices",
            migration_sql="CREATE TABLE invoices (id INTEGER PRIMARY KEY, amount REAL NOT NULL);",
            rollback_sql="-- rollback placeholder",
            description="Create invoices table",
        )
        assert "PENDING_APPROVAL" in res
        assert "PROPOSAL STAGED FOR APPROVAL" in res

        # Extract proposal ID
        prop_id = None
        for line in res.splitlines():
            if line.startswith("Proposal ID:"):
                prop_id = line.split(":", 1)[1].strip()
                break
        assert prop_id is not None

        # Step 2: Verify in list_pending_proposals
        pending = list_pending_proposals()
        assert "invoices" in pending
        assert prop_id in pending

        # Step 3: Execution before approval is blocked
        db_path = str(tmp_path / "mcp_test.db")
        os.environ["AGENTGATE_SQL_DB_PATH"] = db_path
        try:
            blocked_res = execute_approved_proposal(proposal_id=prop_id)
            assert "EXECUTION BLOCKED" in blocked_res

            # Step 4: Approve and execute polymorphically
            app_res = approve_proposal(prop_id)
            assert "PROPOSAL APPROVED" in app_res

            exec_res = execute_approved_proposal(proposal_id=prop_id)
            assert "EXECUTED" in exec_res
            assert "Successfully executed and committed" in exec_res

            # Verify SQLite mutation
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='invoices';")
            assert cur.fetchone() is not None
            conn.close()
        finally:
            os.environ.pop("AGENTGATE_SQL_DB_PATH", None)


class TestCliSqlIntegration:
    """Validate CLI 'agentgate sql plan' and polymorphic 'agentgate execute' commands."""

    def test_cli_sql_plan_and_execution_lifecycle(self, tmp_path: Path) -> None:
        runner = CliRunner()
        storage_path = str(tmp_path / "cli_guardrail_proposals.json")
        db_path = str(tmp_path / "cli_production.db")

        # 1. Plan SQL migration via mock engine
        res_plan = runner.invoke(
            cli,
            [
                "sql",
                "plan",
                "create users table with id and email",
                "--engine",
                "mock",
                "--storage-path",
                storage_path,
            ],
        )
        assert res_plan.exit_code == 0
        assert "SQL MIGRATION PROPOSAL STAGED" in res_plan.output

        # 2. List proposals
        res_list = runner.invoke(cli, ["proposals", "list", "--storage-path", storage_path])
        assert res_list.exit_code == 0
        assert "users" in res_list.output
        assert "PENDING_APPROVAL" in res_list.output

        # Extract proposal ID
        prop_id = None
        for line in res_list.output.splitlines():
            if "prop_" in line:
                for token in line.split():
                    clean_token = token.strip("[]")
                    if clean_token.startswith("prop_"):
                        prop_id = clean_token
                        break
            if prop_id:
                break
        assert prop_id is not None

        # 3. Approve proposal
        res_app = runner.invoke(
            cli,
            ["approve", prop_id, "--storage-path", storage_path],
        )
        assert res_app.exit_code == 0
        assert "APPROVED" in res_app.output

        # 4. Execute polymorphically via CLI
        res_exec = runner.invoke(
            cli,
            [
                "execute",
                prop_id,
                "--storage-path",
                storage_path,
                "--db-path",
                db_path,
            ],
        )
        assert res_exec.exit_code == 0
        assert "EXECUTED" in res_exec.output
        assert "Successfully executed and committed" in res_exec.output

        # Verify table was created on disk
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users';")
        assert cur.fetchone() is not None
        conn.close()
