"""Backward-compatibility module forwarding to core and adapters.git."""

from agentgate.guardrails.adapters.git.adapter import (
    GitProposalValidator as ProposalValidator,
)
from agentgate.guardrails.core.gate import ApprovalGate
from agentgate.guardrails.core.models import (
    ProposalRecord,
    ProposalStatus,
    ProposalValidationResult,
)

__all__ = [
    "ApprovalGate",
    "ProposalRecord",
    "ProposalStatus",
    "ProposalValidationResult",
    "ProposalValidator",
]
