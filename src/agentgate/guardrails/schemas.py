"""Universal and domain schemas including discriminated ProposalUnion."""

from typing import Annotated

from pydantic import Discriminator

from agentgate.guardrails.adapters.git.schemas import (
    BANNED_PHRASES,
    BranchProposal,
    BranchType,
    CommitProposal,
    CommitType,
    PullRequestProposal,
)
from agentgate.guardrails.adapters.sql.sql_schemas_migration import (
    MigrationProposalSql,
    RollbackProposalSql,
    SqlDialect,
    SqlOperationType,
    SqlTaskSpecification,
)
from agentgate.guardrails.core.models import (
    BaseProposal,
    ProposalRecord,
    ProposalStatus,
    ProposalValidationResult,
    discriminate_proposal,
    hydrate_proposal,
)

ProposalUnion = Annotated[
    (
        BranchProposal
        | CommitProposal
        | PullRequestProposal
        | MigrationProposalSql
        | RollbackProposalSql
    ),
    Discriminator(discriminate_proposal),
]


__all__ = [
    "BANNED_PHRASES",
    "BaseProposal",
    "BranchProposal",
    "BranchType",
    "CommitProposal",
    "CommitType",
    "MigrationProposalSql",
    "ProposalRecord",
    "ProposalStatus",
    "ProposalUnion",
    "ProposalValidationResult",
    "PullRequestProposal",
    "RollbackProposalSql",
    "SqlDialect",
    "SqlOperationType",
    "SqlTaskSpecification",
    "discriminate_proposal",
    "hydrate_proposal",
]

