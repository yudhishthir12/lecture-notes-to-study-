"""LLM Service integration using the official google-genai SDK.

Provides abstract interface LLMService, concrete GeminiProvider with retry logic,
exponential backoff, rate limit handling, token tracking, and structured Pydantic output.
"""

from __future__ import annotations

import json
import logging
import threading
from abc import ABC, abstractmethod
from typing import Any, Type, Union

import httpx
from google import genai
from google.genai import errors, types
from pydantic import BaseModel
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import settings

logger = logging.getLogger(__name__)


class LLMServiceError(Exception):
    """Base exception for LLM service invocation failures."""

    pass


class LLMConfigurationError(LLMServiceError):
    """Raised when the LLM service is invoked without proper credentials."""

    pass


class LLMRateLimitError(LLMServiceError):
    """Raised when rate limits (HTTP 429) are encountered."""

    pass


class LLMTimeoutError(LLMServiceError):
    """Raised when an LLM generation call exceeds the timeout threshold."""

    pass


class LLMMalformedResponseError(LLMServiceError):
    """Raised when the model response cannot be parsed or validated against the schema."""

    pass


class LLMService(ABC):
    """Abstract dependency-injection interface for LLM operations."""

    @abstractmethod
    def generate(
        self,
        prompt: str,
        system_prompt: str,
        response_schema: Type[BaseModel] | None = None,
    ) -> Union[str, dict[str, Any]]:
        """Generate text or structured JSON from the model.

        Args:
            prompt: User message / content to process.
            system_prompt: System directive instructions.
            response_schema: Optional Pydantic model class for structured JSON output.

        Returns:
            String response if response_schema is None, or dictionary if response_schema is provided.
        """
        pass

    @abstractmethod
    def is_configured(self) -> bool:
        """Check whether the service has valid API credentials configured."""
        pass

    @abstractmethod
    def get_token_usage(self) -> dict[str, int]:
        """Return cumulative token usage metrics."""
        pass

    @abstractmethod
    def reset_token_usage(self) -> None:
        """Reset cumulative token counters."""
        pass


_UNSET = object()


class GeminiProvider(LLMService):
    """Google Gemini provider implementing LLMService via google-genai SDK."""

    def __init__(
        self,
        api_key: Any = _UNSET,
        model_name: str | None = None,
        timeout_seconds: float = 180.0,
    ) -> None:
        """Initialize the GeminiProvider.

        Args:
            api_key: Optional Gemini API key override (defaults to settings.GEMINI_API_KEY).
            model_name: Optional model override (defaults to settings.GEMINI_MODEL).
            timeout_seconds: Generation timeout in seconds (default 180s).
        """
        if api_key is not _UNSET:
            self.api_key = api_key if (api_key and str(api_key).strip()) else None
        else:
            self.api_key = settings.GEMINI_API_KEY
        self.model_name = model_name or settings.GEMINI_MODEL
        self.timeout_seconds = timeout_seconds

        self._client: genai.Client | None = None
        self.cumulative_token_usage: dict[str, int] = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }
        self.last_token_usage: dict[str, int] = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }

    def is_configured(self) -> bool:
        """Return True if an API key is set and non-empty."""
        return bool(self.api_key and self.api_key.strip())

    def _get_client(self) -> genai.Client:
        """Obtain or lazily instantiate the genai.Client."""
        if not self.is_configured():
            raise LLMConfigurationError(
                "Gemini API key is not configured. Please set the GEMINI_API_KEY environment variable."
            )
        if self._client is None:
            self._client = genai.Client(
                api_key=self.api_key,
                http_options=types.HttpOptions(
                    timeout=180000,
                    client_args={"transport": httpx.HTTPTransport(local_address="0.0.0.0")},
                ),
            )
        return self._client

    def get_token_usage(self) -> dict[str, int]:
        """Return the cumulative token usage dict."""
        return dict(self.cumulative_token_usage)

    def reset_token_usage(self) -> None:
        """Reset token tracking metrics."""
        self.cumulative_token_usage = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }
        self.last_token_usage = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }

    def _track_usage(self, response: Any) -> None:
        """Record token counts from response usage_metadata."""
        usage = getattr(response, "usage_metadata", None)
        if usage:
            prompt_tok = getattr(usage, "prompt_token_count", 0) or 0
            candidate_tok = getattr(usage, "candidates_token_count", 0) or 0
            total_tok = getattr(usage, "total_token_count", 0) or (prompt_tok + candidate_tok)

            self.last_token_usage = {
                "prompt_tokens": prompt_tok,
                "completion_tokens": candidate_tok,
                "total_tokens": total_tok,
            }
            self.cumulative_token_usage["prompt_tokens"] += prompt_tok
            self.cumulative_token_usage["completion_tokens"] += candidate_tok
            self.cumulative_token_usage["total_tokens"] += total_tok

            logger.debug(
                "Gemini token usage: prompt=%d, completion=%d, total=%d",
                prompt_tok,
                candidate_tok,
                total_tok,
            )

    # Process-wide cap on concurrent in-flight Gemini requests.
    _REQUEST_SEMAPHORE = threading.Semaphore(max(1, settings.GEMINI_MAX_CONCURRENT_REQUESTS))

    def _model_candidates(self) -> list[str]:
        """Return the ordered models to try: primary first, then the fallback."""
        models = [self.model_name]
        fallback = (settings.GEMINI_FALLBACK_MODEL or "").strip()
        if fallback and fallback != self.model_name:
            models.append(fallback)
        return models

    @retry(
        stop=stop_after_attempt(max(1, settings.GEMINI_MAX_RETRIES)),
        wait=wait_exponential(
            multiplier=max(0.0, settings.GEMINI_RETRY_BASE_DELAY),
            min=max(0.0, settings.GEMINI_RETRY_BASE_DELAY),
            max=30,
        ),
        retry=retry_if_exception_type(
            (
                errors.ServerError,
                errors.APIError,
                httpx.TimeoutException,
                httpx.NetworkError,
                json.JSONDecodeError,
                LLMRateLimitError,
                LLMTimeoutError,
                LLMMalformedResponseError,
            )
        ),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    def _generate_with_model(
        self,
        model_name: str,
        prompt: str,
        system_prompt: str,
        response_schema: Type[BaseModel] | None = None,
    ) -> Any:
        """Call Gemini for a single model with exponential-backoff retry.

        Retries on rate limits (429), timeouts, server errors, and malformed
        responses. Concurrency is bounded by GEMINI_MAX_CONCURRENT_REQUESTS.
        """
        client = self._get_client()

        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            response_mime_type="application/json" if response_schema is not None else None,
            response_schema=None,
        )

        with self._REQUEST_SEMAPHORE:
            try:
                return client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=config,
                )
            except errors.ClientError as exc:
                # Check for HTTP 429 / RESOURCE_EXHAUSTED
                exc_str = str(exc)
                if "429" in exc_str or "RESOURCE_EXHAUSTED" in exc_str:
                    logger.warning("Gemini rate limit encountered: %s", exc)
                    raise LLMRateLimitError(f"Gemini API rate limit exceeded: {exc}") from exc
                raise LLMServiceError(f"Gemini client error: {exc}") from exc
            except errors.ServerError as exc:
                logger.warning("Gemini server error: %s", exc)
                raise
            except (httpx.TimeoutException, TimeoutError) as exc:
                logger.warning("Gemini request timed out: %s", exc)
                raise LLMTimeoutError(
                    f"Gemini request timed out after {self.timeout_seconds}s"
                ) from exc
            except Exception as exc:
                logger.error("Unexpected error during Gemini API call: %s", exc)
                raise LLMServiceError(f"Gemini call failed: {exc}") from exc

    def _execute_generate(
        self,
        prompt: str,
        system_prompt: str,
        response_schema: Type[BaseModel] | None = None,
    ) -> Any:
        """Generate with the primary model, then the fallback model on failure.

        Each model is attempted GEMINI_MAX_RETRIES times (with exponential
        backoff) before moving on to the next candidate.
        """
        candidates = self._model_candidates()
        last_error: Exception | None = None

        for index, model_name in enumerate(candidates):
            try:
                return self._generate_with_model(
                    model_name, prompt, system_prompt, response_schema
                )
            except LLMConfigurationError:
                raise
            except LLMServiceError as exc:
                last_error = exc
                if index < len(candidates) - 1:
                    logger.warning(
                        "Gemini model %s failed (%s); falling back to %s",
                        model_name,
                        exc,
                        candidates[index + 1],
                    )

        if last_error is not None:
            raise last_error
        raise LLMServiceError("Gemini generation failed for all configured models.")

    def generate(
        self,
        prompt: str,
        system_prompt: str,
        response_schema: Type[BaseModel] | None = None,
    ) -> Union[str, dict[str, Any]]:
        """Generate content from Gemini, with automatic JSON schema validation and retry.

        Args:
            prompt: Input text prompt.
            system_prompt: System role instructions.
            response_schema: Optional Pydantic model for structured output.

        Returns:
            dict if response_schema is provided, str otherwise.

        Raises:
            LLMConfigurationError: If API key is missing.
            LLMServiceError: If generation repeatedly fails.
        """
        response = self._execute_generate(prompt, system_prompt, response_schema)
        self._track_usage(response)

        raw_text = getattr(response, "text", "") or ""

        if response_schema is not None:
            return self._parse_json_response(raw_text, response_schema)

        return raw_text

    def _parse_json_response(
        self,
        raw_text: str,
        response_schema: Type[BaseModel],
    ) -> dict[str, Any]:
        """Safely parse and clean JSON output, handling markdown fences and schema parsing."""
        cleaned = raw_text.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            logger.warning(
                "Failed to decode model response as JSON: %s. Raw: %s", exc, raw_text[:200]
            )
            raise LLMMalformedResponseError(f"Model returned invalid JSON: {exc}") from exc

        # Optional validation using the Pydantic schema to ensure data compliance
        try:
            if isinstance(parsed, dict):
                response_schema.model_validate(parsed)
            elif isinstance(parsed, list):
                # When schema might be a list container
                pass
        except Exception as val_exc:
            logger.warning("Schema validation warning on parsed JSON: %s", val_exc)
            # Re-raise so tenacity can retry if schema is severely violated
            raise LLMMalformedResponseError(
                f"Model response did not match schema {response_schema.__name__}: {val_exc}"
            ) from val_exc

        return parsed


# Singleton instance container
_llm_service_instance: LLMService | None = None


def get_llm_service(api_key: str | None = None, model_name: str | None = None) -> LLMService:
    """Factory function providing configured LLMService instance.

    Args:
        api_key: Optional explicit API key override.
        model_name: Optional explicit model override.

    Returns:
        GeminiProvider instance.
    """
    global _llm_service_instance
    if api_key or model_name:
        return GeminiProvider(api_key=api_key, model_name=model_name)

    if _llm_service_instance is None:
        _llm_service_instance = GeminiProvider()
    return _llm_service_instance
