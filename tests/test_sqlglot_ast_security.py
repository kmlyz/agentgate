"""Security tests verifying sqlglot AST analysis against comment injection, tautologies, and indirect execution."""

import pytest

from agentgate.guardrails.adapters.sql import AstInspectorSql


@pytest.fixture
def inspector() -> AstInspectorSql:
    return AstInspectorSql()


@pytest.mark.parametrize(
    "tautological_query",
    [
        "DELETE FROM users WHERE 1 = 1;",
        "DELETE FROM users WHERE '1' = '1';",
        "DELETE FROM users WHERE 'a' = 'a';",
        "DELETE FROM users WHERE TRUE;",
        "DELETE FROM users WHERE (1 = 1);",
        "DELETE FROM users WHERE ((TRUE));",
        "DELETE FROM users WHERE id = 1 OR 1 = 1;",
        "UPDATE accounts SET balance = 0 WHERE 1 = 1;",
        "UPDATE accounts SET balance = 0 WHERE TRUE;",
        "UPDATE accounts SET balance = 0 WHERE 'x' = 'x';",
    ],
)
def test_inspector_blocks_tautological_where_clauses(
    inspector: AstInspectorSql,
    tautological_query: str,
) -> None:
    """Ensure that AST tautology detection catches all variations of 1=1 and TRUE filters."""
    is_safe, reason = inspector.validate_sql(tautological_query)
    assert not is_safe
    assert reason is not None
    assert "trivial unconstrained where clause" in reason.lower() or "unconstrained" in reason.lower()


@pytest.mark.parametrize(
    "indirect_or_injection_query",
    [
        "CALL sp_drop_all_tables();",
        "EXEC sp_purge();",
        "EXECUTE IMMEDIATE 'DROP TABLE users';",
        "SELECT 1; --\nDROP TABLE users;",
    ],
)
def test_inspector_blocks_indirect_and_comment_injections(
    inspector: AstInspectorSql,
    indirect_or_injection_query: str,
) -> None:
    """Ensure indirect execution (CALL/EXEC) and comment-hidden chained queries are blocked."""
    is_safe, reason = inspector.validate_sql(indirect_or_injection_query)
    assert not is_safe
    assert reason is not None
    assert any(
        term in reason.lower()
        for term in ["indirect execution", "multi-statement", "prohibited", "privilege"]
    )
