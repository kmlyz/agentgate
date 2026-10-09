"""Deterministic SQL security inspection and syntax validation.

Enforces absolute prohibition against destructive DDL (DROP, TRUNCATE)
and unconstrained DML (DELETE/UPDATE without WHERE clauses).
"""

import re
from typing import ClassVar


class AstInspectorSql:
    """Deterministic security analyzer blocking destructive and unconstrained SQL operations."""

    # Explicitly banned statement patterns
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
                    elif i > 0 and sql[i - 1] != "\\" or i == 0:
                        state = "DEFAULT"
            elif state == "DOUBLE_QUOTE":
                current.append(ch)
                if ch == '"':
                    if next_ch == '"':
                        current.append(next_ch)
                        i += 1
                    elif i > 0 and sql[i - 1] != "\\" or i == 0:
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

    def validate_sql(self, sql: str) -> tuple[bool, str | None]:
        """Validate single SQL statement against deterministic safety rules.

        Returns:
            Tuple of (is_safe, error_reason).
        """
        if not sql or not sql.strip():
            return False, "SQL statement cannot be empty."

        statements = self.split_statements(sql)
        if not statements:
            return True, None

        # Block multiple chained statements to prevent hidden mutation injection
        if len(statements) > 1:
            return (
                False,
                "Multi-statement execution is prohibited. Each migration proposal must be atomic (single statement).",
            )

        clean_sql = statements[0]

        # Check banned DDL patterns
        for pattern, reason in self.BANNED_DDL_PATTERNS:
            if pattern.search(clean_sql):
                return False, reason

        # Check unconstrained DML
        # Verify if DELETE or UPDATE contains legitimate WHERE clause
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

        return True, None

    def inspect_migration_pair(
        self,
        migration_sql: str,
        rollback_sql: str,
    ) -> tuple[bool, list[str]]:
        """Validate both forward migration and compensatory rollback SQL queries."""
        errors: list[str] = []

        is_valid_mig, mig_err = self.validate_sql(migration_sql)
        if not is_valid_mig and mig_err:
            errors.append(f"Migration query error: {mig_err}")

        is_valid_roll, roll_err = self.validate_sql(rollback_sql)
        if not is_valid_roll and roll_err:
            errors.append(f"Rollback query error: {roll_err}")

        return len(errors) == 0, errors

    def _strip_comments(self, sql: str) -> str:
        """Strip SQL line comments and block comments preserving string literals."""
        stmts = self.split_statements(sql)
        return stmts[0] if stmts else ""


# Alias for compliance
SqlAstSecurityInspector = AstInspectorSql
