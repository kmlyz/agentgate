"""Google GenAI Gemini reasoning engine implementation.

Provides structured schema generation via Google GenAI SDK (google-genai)
using Gemini 3.8 Flash and strict Pydantic v2 validation.
"""

import os
from typing import TypeVar

from google import genai
from google.genai import types
from pydantic import BaseModel, ValidationError

from agentgate.reasoning.base import BaseReasoningEngine, ReasoningError

T = TypeVar("T", bound=BaseModel)

DEFAULT_GEMINI_MODEL: str = "gemini-3.8-flash"


class GeminiReasoningEngine(BaseReasoningEngine):
    """Reasoning engine backed by Google Gemini models for structured output generation."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = DEFAULT_GEMINI_MODEL,
        client: genai.Client | None = None,
    ) -> None:
        """Initialize GeminiReasoningEngine.

        Args:
            api_key: Optional Gemini API key. Defaults to $env:GEMINI_API_KEY.
            model: Target Gemini model identifier (default: gemini-3.8-flash).
            client: Optional pre-configured genai.Client instance (useful for mocking).
        """
        self.model = model
        if client is not None:
            self.client = client
        else:
            resolved_key = api_key or os.getenv("GEMINI_API_KEY")
            try:
                if resolved_key:
                    self.client = genai.Client(api_key=resolved_key)
                else:
                    self.client = genai.Client()
            except Exception as exc:
                raise ReasoningError(f"Failed to initialize Gemini client: {exc}") from exc

    def extract_structured(
        self,
        prompt: str,
        schema: type[T],
        system_instruction: str | None = None,
    ) -> T:
        """Synchronously extract structured data conforming to target schema using Gemini."""
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=schema,
            system_instruction=system_instruction,
        )
        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=config,
            )
        except Exception as exc:
            raise ReasoningError(f"Gemini API content generation failed: {exc}") from exc

        if not response or not response.text:
            raise ReasoningError("Gemini API returned an empty response or null text content.")

        try:
            return schema.model_validate_json(response.text)
        except ValidationError as val_err:
            raise ReasoningError(
                f"Validation error against schema '{schema.__name__}': {val_err}"
            ) from val_err
        except Exception as exc:
            raise ReasoningError(
                f"Failed to parse structured JSON from Gemini response: {exc}"
            ) from exc

    async def aextract_structured(
        self,
        prompt: str,
        schema: type[T],
        system_instruction: str | None = None,
    ) -> T:
        """Asynchronously extract structured data conforming to target schema using Gemini."""
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=schema,
            system_instruction=system_instruction,
        )
        try:
            response = await self.client.aio.models.generate_content(
                model=self.model,
                contents=prompt,
                config=config,
            )
        except Exception as exc:
            raise ReasoningError(f"Gemini API async content generation failed: {exc}") from exc

        if not response or not response.text:
            raise ReasoningError("Gemini API returned an empty response or null text content.")

        try:
            return schema.model_validate_json(response.text)
        except ValidationError as val_err:
            raise ReasoningError(
                f"Validation error against schema '{schema.__name__}': {val_err}"
            ) from val_err
        except Exception as exc:
            raise ReasoningError(
                f"Failed to parse structured JSON from Gemini response: {exc}"
            ) from exc
