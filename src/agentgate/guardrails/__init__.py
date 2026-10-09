"""Deterministic guardrails and schema validation module.

Exposes both universal core components and domain-specific adapters.
"""

from agentgate.guardrails.adapters.git.adapter import (
    GitGuardrailAdapter,
    GitProposalValidator,
)
from agentgate.guardrails.adapters.git.schemas import CommitProposal, CommitType
from agentgate.guardrails.core.gate import ApprovalGate
from agentgate.guardrails.core.models import (
    BaseProposal,
    ProposalRecord,
    ProposalStatus,
    ProposalValidationResult,
)

# Backward compatibility alias
ProposalValidator = GitProposalValidator

__all__ = [
    "ApprovalGate",
    "BaseProposal",
    "CommitProposal",
    "CommitType",
    "GitGuardrailAdapter",
    "GitProposalValidator",
    "ProposalRecord",
    "ProposalStatus",
    "ProposalValidationResult",
    "ProposalValidator",
]
