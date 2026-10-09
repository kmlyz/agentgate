"""Base adapter interface for domain-specific guardrail plugins."""

from abc import ABC, abstractmethod
from typing import Any

from agentgate.guardrails.core.models import BaseProposal, ProposalValidationResult


class BaseGuardrailAdapter(ABC):
    """Abstract interface that all domain guardrails must implement."""

    @property
    @abstractmethod
    def domain(self) -> str:
        """Domain identifier (e.g. 'git', 'docker', 'wordpress')."""
        ...

    @abstractmethod
    def validate_payload(self, raw_data: dict[str, Any]) -> ProposalValidationResult:
        """Validate raw input dictionary against domain schema."""
        ...

    @abstractmethod
    def parse_proposal(self, raw_data: dict[str, Any]) -> BaseProposal:
        """Instantiate concrete BaseProposal from validated dictionary."""
        ...
