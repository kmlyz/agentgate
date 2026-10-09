"""Vendor-agnostic reasoning abstractions and contracts.

Defines the abstract interface for LLM-backed structured output engines
and dedicated reasoning exception types.
"""

from abc import ABC, abstractmethod
from typing import TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class ReasoningError(Exception):
    """Raised when reasoning engine fails, API returns an error, or schema validation fails."""


class BaseReasoningEngine(ABC):
    """Vendor-agnostic abstract engine for extracting strictly typed Pydantic models."""

    @abstractmethod
    def extract_structured(
        self,
        prompt: str,
        schema: type[T],
        system_instruction: str | None = None,
    ) -> T:
        """Extract a strictly typed Pydantic model from a natural language prompt.

        Args:
            prompt: User requirement or task description in natural language.
            schema: Target Pydantic model class defining the required schema.
            system_instruction: Optional guiding instructions for the model.

        Returns:
            An instance of schema populated with deterministic, validated data.

        Raises:
            ReasoningError: If the provider fails, returns empty output, or
                the generated content does not conform to schema constraints.
        """
        ...

    @abstractmethod
    async def aextract_structured(
        self,
        prompt: str,
        schema: type[T],
        system_instruction: str | None = None,
    ) -> T:
        """Asynchronously extract a strictly typed Pydantic model.

        Args:
            prompt: User requirement or task description in natural language.
            schema: Target Pydantic model class defining the required schema.
            system_instruction: Optional guiding instructions for the model.

        Returns:
            An instance of schema populated with deterministic, validated data.

        Raises:
            ReasoningError: If the provider fails, returns empty output, or
                the generated content does not conform to schema constraints.
        """
        ...
