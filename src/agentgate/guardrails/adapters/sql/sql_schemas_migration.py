"""Strict Pydantic v2 schemas for SQL migration and rollback proposals."""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from agentgate.guardrails.core.models import BaseProposal


class SqlOperationType(str, Enum):
    """Categorization of allowed and inspected SQL operations."""

    CREATE_TABLE = "create_table"
    ADD_COLUMN = "add_column"
    RENAME_COLUMN = "rename_column"
    CREATE_INDEX = "create_index"
    INSERT_DATA = "insert_data"
    UPDATE_DATA = "update_data"


class SqlDialect(str, Enum):
    """Supported SQL target dialects."""

    SQLITE = "sqlite"
    POSTGRESQL = "postgresql"
    GENERIC = "generic"


class MigrationProposalSql(BaseProposal):
    """Typed proposal representing a forward database schema migration."""

    model_config = ConfigDict(extra="forbid")

    dialect: SqlDialect = SqlDialect.SQLITE
    operation_type: SqlOperationType
    target_table: str = Field(
        pattern=r"^[a-zA-Z_][a-zA-Z0-9_]{0,63}$",
        description="Target table identifier.",
    )
    migration_sql: str = Field(
        min_length=5,
        max_length=4000,
        description="Forward migration DDL or controlled DML query.",
    )
    rollback_sql: str = Field(
        min_length=5,
        max_length=4000,
        description="Compensatory rollback query to undo this migration.",
    )
    description: str = Field(
        min_length=5,
        max_length=200,
        description="Concise description of the migration intent.",
    )

    def render_message(self) -> str:
        """Render standardized proposal description for operator inspection."""
        return (
            f"SQL [{self.operation_type.value.upper()}] on '{self.target_table}': "
            f"{self.description} ({self.migration_sql.strip()})"
        )


class RollbackProposalSql(BaseProposal):
    """Typed proposal representing a compensatory rollback operation."""

    model_config = ConfigDict(extra="forbid")

    dialect: SqlDialect = SqlDialect.SQLITE
    target_table: str = Field(
        pattern=r"^[a-zA-Z_][a-zA-Z0-9_]{0,63}$",
        description="Target table identifier.",
    )
    rollback_sql: str = Field(
        min_length=5,
        max_length=4000,
        description="Compensatory rollback query to execute.",
    )
    target_migration_id: str = Field(
        pattern=r"^prop_[a-f0-9]{8}$",
        description="Proposal ID of the migration being rolled back.",
    )
    reason: str = Field(
        min_length=5,
        max_length=200,
        description="Operator or automated rationale for the rollback.",
    )

    def render_message(self) -> str:
        """Render standardized rollback description."""
        return (
            f"SQL ROLLBACK for '{self.target_migration_id}' on '{self.target_table}': "
            f"{self.reason} ({self.rollback_sql.strip()})"
        )


class SqlTaskSpecification(BaseModel):
    """Structured extraction format for natural language SQL migration requests."""

    model_config = ConfigDict(extra="forbid")

    dialect: SqlDialect = SqlDialect.SQLITE
    operation_type: SqlOperationType
    target_table: str = Field(
        pattern=r"^[a-zA-Z_][a-zA-Z0-9_]{0,63}$",
        description="Target table identifier.",
    )
    migration_sql: str = Field(
        min_length=5,
        max_length=4000,
        description="Forward migration DDL or controlled DML query.",
    )
    rollback_sql: str = Field(
        min_length=5,
        max_length=4000,
        description="Compensatory rollback query.",
    )
    description: str = Field(
        min_length=5,
        max_length=200,
        description="Concise description of the migration intent.",
    )


# Natural naming aliases
SQLMigrationProposal = MigrationProposalSql
SQLRollbackProposal = RollbackProposalSql
SQLOperationType = SqlOperationType
SQLDialect = SqlDialect
SQLTaskSpecification = SqlTaskSpecification

from agentgate.guardrails.core.models import register_proposal_type

register_proposal_type("sql_migration", MigrationProposalSql)
register_proposal_type("sql_rollback", RollbackProposalSql)
