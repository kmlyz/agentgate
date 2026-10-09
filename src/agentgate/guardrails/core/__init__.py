"""Universal Guardrails Core package."""

from agentgate.guardrails.core.adapter import BaseGuardrailAdapter
from agentgate.guardrails.core.gate import ApprovalGate
from agentgate.guardrails.core.models import (
    BaseProposal,
    ProposalRecord,
    ProposalStatus,
    ProposalValidationResult,
)

__all__ = [
    "ApprovalGate",
    "BaseGuardrailAdapter",
    "BaseProposal",
    "ProposalRecord",
    "ProposalStatus",
    "ProposalValidationResult",
]
