# backend/src/oya/llm/client.py
"""LiteLLM-based LLM client."""

import json
import time
from datetime import datetime, timezone
from pathlib import Path

from litellm import acompletion

from oya.config.llm import DEFAULT_TEMPERATURE, JSON_TEMPERATURE, MAX_TOKENS
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

        try:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception:
            # Don't let logging failures break the application
            pass

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
        temperature: float = DEFAULT_TEMPERATURE,
        max_tokens: int = MAX_TOKENS,
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
            result = response.choices[0].message.content
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            self._log_query(
                system_prompt, prompt, temperature, max_tokens,
                response=result, duration_ms=duration_ms, error=None
            )
            return result
        except AuthenticationError as e:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            self._log_query(
                system_prompt, prompt, temperature, max_tokens,
                response=None, duration_ms=duration_ms, error=str(e)
            )
            raise LLMAuthenticationError(f"Authentication failed: {e}") from e
        except RateLimitError as e:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            self._log_query(
                system_prompt, prompt, temperature, max_tokens,
                response=None, duration_ms=duration_ms, error=str(e)
            )
            raise LLMRateLimitError(f"Rate limit exceeded: {e}") from e
        except APIConnectionError as e:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            self._log_query(
                system_prompt, prompt, temperature, max_tokens,
                response=None, duration_ms=duration_ms, error=str(e)
            )
            raise LLMConnectionError(f"Connection failed: {e}") from e
        except APIError as e:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            self._log_query(
                system_prompt, prompt, temperature, max_tokens,
                response=None, duration_ms=duration_ms, error=str(e)
            )
            raise LLMError(f"LLM API error: {e}") from e

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
        full_system = (system_prompt or "") + "\n\nRespond with valid JSON only."
        return await self.generate(
            prompt,
            system_prompt=full_system.strip(),
            temperature=JSON_TEMPERATURE,
        )
