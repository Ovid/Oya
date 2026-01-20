# backend/src/oya/llm/client.py
"""LiteLLM-based LLM client."""

import json
import time
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from pathlib import Path

from litellm import acompletion

from oya.config import load_settings
from litellm.exceptions import (
    APIConnectionError,
    APIError,
    AuthenticationError,
    RateLimitError,
)


class LLMError(Exception):
    """Base exception for LLM client errors."""

    pass


class LLMConnectionError(LLMError):
    """Raised when unable to connect to the LLM provider."""

    pass


class LLMAuthenticationError(LLMError):
    """Raised when authentication with the LLM provider fails."""

    pass


class LLMRateLimitError(LLMError):
    """Raised when rate limited by the LLM provider."""

    pass


class LLMClient:
    """Unified LLM client supporting multiple providers via LiteLLM."""

    def __init__(
        self,
        provider: str,
        model: str,
        api_key: str | None = None,
        endpoint: str | None = None,
        log_path: Path | None = None,
    ):
        """Initialize LLM client.

        Args:
            provider: LLM provider (openai, anthropic, google, ollama).
            model: Model name.
            api_key: Optional API key (uses env var if not provided).
            endpoint: Optional custom endpoint (for Ollama).
            log_path: Optional path to JSONL log file for query logging.
        """
        self.provider = provider
        self.model = model
        self.api_key = api_key
        self.endpoint = endpoint
        self.log_path = log_path

    def _log_query(
        self,
        system_prompt: str | None,
        prompt: str,
        temperature: float,
        max_tokens: int,
        response: str | None,
        duration_ms: int,
        error: str | None,
        error_details: dict | None = None,
    ) -> None:
        """Log a query to the JSONL log file.

        Args:
            system_prompt: System prompt used.
            prompt: User prompt.
            temperature: Temperature setting.
            max_tokens: Max tokens setting.
            response: Response text (None if error).
            duration_ms: Request duration in milliseconds.
            error: Error message (None if success).
            error_details: Optional dict with status_code, headers, etc.
        """
        if not self.log_path:
            return

        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "provider": self.provider,
            "model": self.model,
            "request": {
                "system_prompt": system_prompt,
                "prompt": prompt,
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
            "response": response,
            "duration_ms": duration_ms,
            "error": error,
        }

        if error_details:
            entry["error_details"] = error_details

        try:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception:
            # Don't let logging failures break the application
            pass

    def _extract_error_details(self, e: Exception) -> dict | None:
        """Extract HTTP details from LiteLLM exceptions.

        Args:
            e: The exception to extract details from.

        Returns:
            Dict with status_code, headers, and body if available.
        """
        details: dict = {}

        # LiteLLM exceptions often have these attributes
        if hasattr(e, "status_code"):
            details["status_code"] = e.status_code

        if hasattr(e, "response") and e.response is not None:
            resp = e.response
            # httpx Response object
            if hasattr(resp, "status_code"):
                details["status_code"] = resp.status_code
            if hasattr(resp, "headers"):
                # Convert headers to dict, filtering to useful ones
                try:
                    headers = dict(resp.headers)
                    # Keep only relevant headers for debugging
                    relevant_headers = {
                        k: v
                        for k, v in headers.items()
                        if k.lower()
                        in (
                            "x-ratelimit-limit-requests",
                            "x-ratelimit-limit-tokens",
                            "x-ratelimit-remaining-requests",
                            "x-ratelimit-remaining-tokens",
                            "x-ratelimit-reset-requests",
                            "x-ratelimit-reset-tokens",
                            "retry-after",
                            "x-request-id",
                            "openai-organization",
                            "openai-processing-ms",
                            "openai-version",
                            "cf-ray",
                        )
                    }
                    if relevant_headers:
                        details["response_headers"] = relevant_headers
                except Exception:
                    pass

        # Some exceptions have llm_provider info
        if hasattr(e, "llm_provider"):
            details["llm_provider"] = e.llm_provider

        # Message often contains useful info
        if hasattr(e, "message"):
            details["message"] = str(e.message)

        return details if details else None

    def _get_model_string(self) -> str:
        """Get LiteLLM model string.

        Returns:
            Model string in provider/model format.
        """
        if self.provider == "openai":
            return self.model  # OpenAI is default
        elif self.provider == "ollama":
            return f"ollama/{self.model}"
        else:
            return f"{self.provider}/{self.model}"

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """Generate completion from prompt.

        Args:
            prompt: User prompt.
            system_prompt: Optional system prompt.
            temperature: Sampling temperature.
            max_tokens: Maximum response tokens.

        Returns:
            Generated text response.
        """
        if temperature is None or max_tokens is None:
            try:
                settings = load_settings()
                if temperature is None:
                    temperature = settings.llm.default_temperature
                if max_tokens is None:
                    max_tokens = settings.llm.max_tokens
            except (ValueError, OSError):
                # Settings not available (e.g., WORKSPACE_PATH not set in tests)
                if temperature is None:
                    temperature = 0.7  # Default from CONFIG_SCHEMA
                if max_tokens is None:
                    max_tokens = 8192  # Default from CONFIG_SCHEMA

        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({"role": "user", "content": prompt})

        kwargs = {
            "model": self._get_model_string(),
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if self.api_key:
            kwargs["api_key"] = self.api_key

        if self.endpoint and self.provider == "ollama":
            kwargs["api_base"] = self.endpoint

        start_time = time.perf_counter()
        try:
            response = await acompletion(**kwargs)
            result: str = str(response.choices[0].message.content or "")
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            self._log_query(
                system_prompt,
                prompt,
                temperature,
                max_tokens,
                response=result,
                duration_ms=duration_ms,
                error=None,
            )
            return result
        except AuthenticationError as e:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            self._log_query(
                system_prompt,
                prompt,
                temperature,
                max_tokens,
                response=None,
                duration_ms=duration_ms,
                error=str(e),
                error_details=self._extract_error_details(e),
            )
            raise LLMAuthenticationError(f"Authentication failed: {e}") from e
        except RateLimitError as e:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            self._log_query(
                system_prompt,
                prompt,
                temperature,
                max_tokens,
                response=None,
                duration_ms=duration_ms,
                error=str(e),
                error_details=self._extract_error_details(e),
            )
            raise LLMRateLimitError(f"Rate limit exceeded: {e}") from e
        except APIConnectionError as e:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            self._log_query(
                system_prompt,
                prompt,
                temperature,
                max_tokens,
                response=None,
                duration_ms=duration_ms,
                error=str(e),
                error_details=self._extract_error_details(e),
            )
            raise LLMConnectionError(f"Connection failed: {e}") from e
        except APIError as e:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            self._log_query(
                system_prompt,
                prompt,
                temperature,
                max_tokens,
                response=None,
                duration_ms=duration_ms,
                error=str(e),
                error_details=self._extract_error_details(e),
            )
            raise LLMError(f"LLM API error: {e}") from e

    async def generate_stream(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncGenerator[str, None]:
        """Generate completion with streaming tokens.

        Args:
            prompt: User prompt.
            system_prompt: Optional system prompt.
            temperature: Sampling temperature.
            max_tokens: Maximum response tokens.

        Yields:
            Individual tokens as they are generated.
        """
        if temperature is None or max_tokens is None:
            try:
                settings = load_settings()
                if temperature is None:
                    temperature = settings.llm.default_temperature
                if max_tokens is None:
                    max_tokens = settings.llm.max_tokens
            except (ValueError, OSError):
                # Settings not available (e.g., WORKSPACE_PATH not set in tests)
                if temperature is None:
                    temperature = 0.7  # Default from CONFIG_SCHEMA
                if max_tokens is None:
                    max_tokens = 8192  # Default from CONFIG_SCHEMA

        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({"role": "user", "content": prompt})

        kwargs = {
            "model": self._get_model_string(),
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }

        if self.api_key:
            kwargs["api_key"] = self.api_key

        if self.endpoint and self.provider == "ollama":
            kwargs["api_base"] = self.endpoint

        start_time = time.perf_counter()
        accumulated_tokens: list[str] = []
        error_msg: str | None = None
        error_details: dict | None = None

        try:
            response = await acompletion(**kwargs)
            async for chunk in response:
                content = chunk.choices[0].delta.content
                if content:
                    accumulated_tokens.append(content)
                    yield content
        except AuthenticationError as e:
            error_msg = str(e)
            error_details = self._extract_error_details(e)
            raise LLMAuthenticationError(f"Authentication failed: {e}") from e
        except RateLimitError as e:
            error_msg = str(e)
            error_details = self._extract_error_details(e)
            raise LLMRateLimitError(f"Rate limit exceeded: {e}") from e
        except APIConnectionError as e:
            error_msg = str(e)
            error_details = self._extract_error_details(e)
            raise LLMConnectionError(f"Connection failed: {e}") from e
        except APIError as e:
            error_msg = str(e)
            error_details = self._extract_error_details(e)
            raise LLMError(f"LLM API error: {e}") from e
        finally:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            self._log_query(
                system_prompt,
                prompt,
                temperature,
                max_tokens,
                response="".join(accumulated_tokens) if accumulated_tokens else None,
                duration_ms=duration_ms,
                error=error_msg,
                error_details=error_details,
            )

    async def generate_with_json(
        self,
        prompt: str,
        system_prompt: str | None = None,
    ) -> str:
        """Generate completion expecting JSON response.

        Args:
            prompt: User prompt.
            system_prompt: Optional system prompt.

        Returns:
            Generated JSON string.
        """
        try:
            settings = load_settings()
            json_temperature = settings.llm.json_temperature
        except (ValueError, OSError):
            # Settings not available (e.g., WORKSPACE_PATH not set in tests)
            json_temperature = 0.3  # Default from CONFIG_SCHEMA
        full_system = (system_prompt or "") + "\n\nRespond with valid JSON only."
        return await self.generate(
            prompt,
            system_prompt=full_system.strip(),
            temperature=json_temperature,
        )
