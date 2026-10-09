"""Deterministic mock reasoning engine for testing and offline environments.

Provides controllable structured outputs and error injection without network calls.
"""

from collections.abc import Callable
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from agentgate.reasoning.base import BaseReasoningEngine, ReasoningError

T = TypeVar("T", bound=BaseModel)


class MockReasoningEngine(BaseReasoningEngine):
    """Deterministic mock reasoning engine for CI/CD pipelines and unit testing."""

    def __init__(
        self,
        default_response: (
            BaseModel
            | dict[str, Any]
            | str
            | Callable[[str, type[Any]], BaseModel | dict[str, Any] | str]
            | None
        ) = None,
        raise_error: Exception | None = None,
    ) -> None:
        """Initialize MockReasoningEngine.

        Args:
            default_response: Model instance, dict, JSON string, or callable handler.
            raise_error: Optional exception to raise upon invocation.
        """
        self.default_response = default_response
        self.raise_error = raise_error
        self.call_history: list[dict[str, Any]] = []

    def set_response(
        self,
        response: (
            BaseModel
            | dict[str, Any]
            | str
            | Callable[[str, type[Any]], BaseModel | dict[str, Any] | str]
            | None
        ),
    ) -> None:
        """Set or update the active mock response."""
        self.default_response = response

    def set_error(self, error: Exception | None) -> None:
        """Set or clear the mock error to simulate failure scenarios."""
        self.raise_error = error

    def extract_structured(
        self,
        prompt: str,
        schema: type[T],
        system_instruction: str | None = None,
    ) -> T:
        """Extract structured model deterministically from mock data."""
        self.call_history.append(
            {
                "prompt": prompt,
                "schema": schema,
                "system_instruction": system_instruction,
            }
        )

        if self.raise_error is not None:
            if isinstance(self.raise_error, ReasoningError):
                raise self.raise_error
            raise ReasoningError(f"Simulated mock failure: {self.raise_error}") from self.raise_error

        if self.default_response is None:
            raise ReasoningError("MockReasoningEngine has no response configured.")

        candidate = self.default_response
        if callable(candidate):
            try:
                candidate = candidate(prompt, schema)
            except Exception as exc:
                raise ReasoningError(f"Mock response callback raised an error: {exc}") from exc

        if isinstance(candidate, schema):
            return candidate

        if isinstance(candidate, BaseModel):
            try:
                return schema.model_validate(candidate.model_dump())
            except ValidationError as val_err:
                raise ReasoningError(
                    f"Mock model response failed schema validation: {val_err}"
                ) from val_err

        if isinstance(candidate, dict):
            try:
                return schema.model_validate(candidate)
            except ValidationError as val_err:
                raise ReasoningError(
                    f"Mock dict response failed schema validation: {val_err}"
                ) from val_err

        if isinstance(candidate, str):
            try:
                return schema.model_validate_json(candidate)
            except ValidationError as val_err:
                raise ReasoningError(
                    f"Mock JSON string response failed schema validation: {val_err}"
                ) from val_err

        raise ReasoningError(f"Unsupported mock response type: {type(candidate).__name__}")

    async def aextract_structured(
        self,
        prompt: str,
        schema: type[T],
        system_instruction: str | None = None,
    ) -> T:
        """Asynchronously extract structured model deterministically."""
        return self.extract_structured(prompt, schema, system_instruction)
