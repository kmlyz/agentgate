"""Deterministic SQL security inspection and AST syntax validation via sqlglot.

Enforces absolute prohibition against destructive DDL (DROP, TRUNCATE),
destructive column drops (ALTER TABLE ... DROP COLUMN), indirect execution
(CALL, EXECUTE IMMEDIATE), and unconstrained DML (DELETE/UPDATE without valid WHERE clauses).
"""

import re
from typing import Any, ClassVar

import sqlglot
from sqlglot import exp


class AstInspectorSql:
    """Deterministic security analyzer blocking destructive, tautological, and unconstrained SQL operations."""

    # Explicitly banned statement patterns (defense-in-depth lexical layer)
    BANNED_DDL_PATTERNS: ClassVar[list[tuple[re.Pattern[str], str]]] = [
        (
            re.compile(r"\bDROP\s+(TABLE|DATABASE|SCHEMA|VIEW)\b", re.IGNORECASE),
            "Destructive DDL 'DROP' operation is prohibited by guardrail constitution.",
        ),
        (
            re.compile(r"\bTRUNCATE(\s+TABLE)?\b", re.IGNORECASE),
            "Destructive DDL 'TRUNCATE' operation is prohibited by guardrail constitution.",
        ),
        (
            re.compile(r"\bALTER\s+TABLE\s+[^\s]+\s+DROP\s+(COLUMN\s+)?[^\s]+", re.IGNORECASE),
            "Destructive DDL 'ALTER TABLE ... DROP COLUMN' leads to irreversible data loss and is blocked.",
        ),
        (
            re.compile(r"\bATTACH(\s+DATABASE)?\b", re.IGNORECASE),
            "Database attachment or external file manipulation is prohibited.",
        ),
        (
            re.compile(r"\b(GRANT|REVOKE|SHUTDOWN)\b", re.IGNORECASE),
            "Privilege or administrative mutations are prohibited.",
        ),
    ]

    # Unconstrained DML patterns (Missing or trivial WHERE clause)
    DML_UNCONSTRAINED_PATTERNS: ClassVar[list[tuple[re.Pattern[str], str]]] = [
        (
            re.compile(r"^\s*DELETE\s+FROM\s+[a-zA-Z0-9_.]+\s*(;)?$", re.IGNORECASE),
            "Unconstrained 'DELETE FROM' without WHERE clause is prohibited.",
        ),
        (
            re.compile(
                r"\bDELETE\s+FROM\s+[a-zA-Z0-9_.]+\s+WHERE\s+(1\s*=\s*1|true|'1'\s*=\s*'1')(?:;|\s|$)",
                re.IGNORECASE,
            ),
            "Trivial unconstrained WHERE clause (e.g. 1=1, true) on DELETE is prohibited.",
        ),
        (
            re.compile(
                r"\bUPDATE\s+[a-zA-Z0-9_.]+\s+SET\s+[\s\S]+\s+WHERE\s+(1\s*=\s*1|true|'1'\s*=\s*'1')(?:;|\s|$)",
                re.IGNORECASE,
            ),
            "Trivial unconstrained WHERE clause (e.g. 1=1, true) on UPDATE is prohibited.",
        ),
    ]

    # Multiple statement injection detector
    MULTI_STATEMENT_PATTERN = re.compile(r";\s*\S+")

    @staticmethod
    def _is_single_tautology(node: Any) -> bool:
        """Check if an individual AST condition node resolves to a trivial boolean true / tautology."""
        while isinstance(node, exp.Paren):
            node = node.this

        if isinstance(node, exp.Boolean) and node.this is True:
            return True
        if isinstance(node, exp.Literal) and str(node.this).lower() in ("1", "true"):
            return True
        if isinstance(node, exp.EQ):
            left, right = node.this, node.expression
            if isinstance(left, exp.Literal) and isinstance(right, exp.Literal):
                return str(left.this).lower() == str(right.this).lower()
            if hasattr(left, "sql") and hasattr(right, "sql"):
                left_sql = left.sql().strip()
                right_sql = right.sql().strip()
                if left_sql and left_sql == right_sql:
                    return True
        return False

    @classmethod
    def _is_tautology(cls, node: Any) -> bool:
        """Recursively inspect condition tree for top-level tautologies or unconstrained OR branches."""
        if not node:
            return True
        while isinstance(node, exp.Paren):
            node = node.this

        if cls._is_single_tautology(node):
            return True
        if isinstance(node, exp.Or):
            return cls._is_tautology(node.this) or cls._is_tautology(node.expression)
        return False

    @staticmethod
    def split_statements(sql: str) -> list[str]:
        """Split SQL into executable statements using an O(N) lexical state machine.

        Correctly ignores semicolons inside single quotes, double quotes, and comments.
        """
        statements: list[str] = []
        current: list[str] = []
        state = "DEFAULT"
        i = 0
        n = len(sql)

        while i < n:
            ch = sql[i]
            next_ch = sql[i + 1] if i + 1 < n else ""

            if state == "DEFAULT":
                if ch == "'":
                    state = "SINGLE_QUOTE"
                    current.append(ch)
                elif ch == '"':
                    state = "DOUBLE_QUOTE"
                    current.append(ch)
                elif ch == "-" and next_ch == "-":
                    state = "LINE_COMMENT"
                    i += 1
                elif ch == "/" and next_ch == "*":
                    state = "BLOCK_COMMENT"
                    i += 1
                elif ch == ";":
                    stmt = "".join(current).strip()
                    if stmt:
                        statements.append(stmt)
                    current = []
                else:
                    current.append(ch)
            elif state == "SINGLE_QUOTE":
                current.append(ch)
                if ch == "'":
                    if next_ch == "'":
                        current.append(next_ch)
                        i += 1
                    elif (i > 0 and sql[i - 1] != "\\") or i == 0:
                        state = "DEFAULT"
            elif state == "DOUBLE_QUOTE":
                current.append(ch)
                if ch == '"':
                    if next_ch == '"':
                        current.append(next_ch)
                        i += 1
                    elif (i > 0 and sql[i - 1] != "\\") or i == 0:
                        state = "DEFAULT"
            elif state == "LINE_COMMENT" and ch == "\n":
                state = "DEFAULT"
                current.append("\n")
            elif state == "BLOCK_COMMENT" and ch == "*" and next_ch == "/":
                state = "DEFAULT"
                i += 1
                current.append(" ")

            i += 1

        tail = "".join(current).strip()
        if tail:
            statements.append(tail)

        return statements

    def inspect_query_ast(self, sql: str, dialect: str = "postgres") -> list[str]:
        """Deep semantic AST inspection using sqlglot, returning all safety violations."""
        if not sql or not sql.strip():
            return ["SQL statement cannot be empty."]

        violations: list[str] = []

        try:
            expressions = [
                e
                for e in sqlglot.parse(sql, read=dialect)
                if e is not None and not isinstance(e, exp.Semicolon)
            ]
        except (sqlglot.errors.SqlglotError, ValueError, TypeError):
            try:
                # Fallback to generic dialect parsing
                expressions = [
                    e
                    for e in sqlglot.parse(sql)
                    if e is not None and not isinstance(e, exp.Semicolon)
                ]
            except (sqlglot.errors.SqlglotError, ValueError, TypeError) as exc:
                return [f"SQL_SYNTAX_ERROR: Failed to parse query AST: {exc}"]

        # Multi-statement injection detection
        if len(expressions) > 1:
            violations.append(
                "Multi-statement execution is prohibited. Each migration proposal must be atomic (single statement)."
            )

        truncate_types = tuple(t for t in (getattr(exp, "TruncateTable", None),) if t is not None)

        for expr in expressions:
            for node in expr.walk():
                # Destructive DDL (DROP / TRUNCATE)
                node_key = (getattr(node, "key", None) or "").upper()
                if isinstance(node, exp.Drop) or (truncate_types and isinstance(node, truncate_types)) or node_key in {"TRUNCATE", "TRUNCATETABLE"}:
                    violations.append(
                        f"Destructive DDL '{node_key or 'DROP'}' operation is prohibited by guardrail constitution."
                    )
                # Schema alteration dropping columns
                elif isinstance(node, exp.Alter):
                    if any(isinstance(child, exp.Drop) for child in node.walk()):
                        violations.append(
                            "Destructive DDL 'ALTER TABLE ... DROP COLUMN' leads to irreversible data loss and is blocked."
                        )
                # Indirect execution (CALL / EXECUTE)
                elif isinstance(node, exp.Command):
                    cmd_text = (node.this or "").upper()
                    if any(k in cmd_text for k in ("CALL", "EXECUTE", "EXEC", "SHUTDOWN", "GRANT", "REVOKE", "ATTACH")):
                        violations.append(
                            "Privilege, administrative, or indirect execution mutations are prohibited."
                        )
                elif isinstance(node, exp.Anonymous) and node.name and node.name.upper() in {"CALL", "EXECUTE", "EXEC"}:
                    violations.append("Indirect execution (CALL/EXECUTE) prohibited.")
                # Unconstrained DELETE / UPDATE
                elif isinstance(node, exp.Delete):
                    where = node.find(exp.Where)
                    if not where:
                        violations.append("Unconstrained 'DELETE FROM' without WHERE clause is prohibited.")
                    elif self._is_tautology(where.this):
                        violations.append("Trivial unconstrained WHERE clause (e.g. 1=1, true) on DELETE is prohibited.")
                elif isinstance(node, exp.Update):
                    where = node.find(exp.Where)
                    if not where:
                        violations.append("Unconstrained 'UPDATE' without WHERE clause is prohibited.")
                    elif self._is_tautology(where.this):
                        violations.append("Trivial unconstrained WHERE clause (e.g. 1=1, true) on UPDATE is prohibited.")
                # System catalog mutations
                elif isinstance(node, exp.Table):
                    tbl_name = (node.name or "").lower()
                    if tbl_name in {"sqlite_master", "sqlite_temp_master", "pg_catalog", "information_schema"}:
                        violations.append("Direct mutation of database system catalog tables is prohibited.")

        return violations

    def validate_sql(self, sql: str, dialect: str = "postgres") -> tuple[bool, str | None]:
        """Validate single SQL statement against deterministic safety rules and AST semantics.

        Returns:
            Tuple of (is_safe, error_reason).
        """
        if not sql or not sql.strip():
            return False, "SQL statement cannot be empty."

        statements = self.split_statements(sql)
        if not statements:
            return True, None

        # Block multiple chained statements via lexical analysis
        if len(statements) > 1:
            return (
                False,
                "Multi-statement execution is prohibited. Each migration proposal must be atomic (single statement).",
            )

        clean_sql = statements[0]

        # 1. Check banned DDL patterns (Lexical fast-path)
        for pattern, reason in self.BANNED_DDL_PATTERNS:
            if pattern.search(clean_sql):
                return False, reason

        # 2. Check unconstrained DML (Lexical fast-path)
        upper_sql = clean_sql.upper()
        if upper_sql.startswith("DELETE FROM ") and " WHERE " not in upper_sql:
            return False, "Unconstrained 'DELETE FROM' without WHERE clause is prohibited."

        if upper_sql.startswith("UPDATE ") and " WHERE " not in upper_sql:
            return False, "Unconstrained 'UPDATE' without WHERE clause is prohibited."

        for pattern, reason in self.DML_UNCONSTRAINED_PATTERNS:
            if pattern.search(clean_sql):
                return False, reason

        # Check system table manipulation
        if re.search(r"\b(sqlite_master|sqlite_temp_master|pg_catalog|information_schema)\b", clean_sql, re.IGNORECASE):
            return False, "Direct mutation of database system catalog tables is prohibited."

        # 3. Deep AST Inspection via sqlglot
        ast_violations = self.inspect_query_ast(clean_sql, dialect=dialect)
        if ast_violations:
            return False, ast_violations[0]

        return True, None

    def inspect_migration_pair(
        self,
        migration_sql: str,
        rollback_sql: str,
        dialect: str = "postgres",
    ) -> tuple[bool, list[str]]:
        """Validate both forward migration and compensatory rollback SQL queries."""
        errors: list[str] = []

        is_valid_mig, mig_err = self.validate_sql(migration_sql, dialect=dialect)
        if not is_valid_mig and mig_err:
            errors.append(f"Migration query error: {mig_err}")

        is_valid_roll, roll_err = self.validate_sql(rollback_sql, dialect=dialect)
        if not is_valid_roll and roll_err:
            errors.append(f"Rollback query error: {roll_err}")

        return len(errors) == 0, errors

    def _strip_comments(self, sql: str) -> str:
        """Strip SQL line comments and block comments preserving string literals."""
        stmts = self.split_statements(sql)
        return stmts[0] if stmts else ""


# Alias for compliance
SqlAstSecurityInspector = AstInspectorSql
