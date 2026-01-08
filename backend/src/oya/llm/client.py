# backend/src/oya/llm/client.py
"""LiteLLM-based LLM client."""

from litellm import acompletion
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
    ):
        """Initialize LLM client.

        Args:
            provider: LLM provider (openai, anthropic, google, ollama).
            model: Model name.
            api_key: Optional API key (uses env var if not provided).
            endpoint: Optional custom endpoint (for Ollama).
        """
        self.provider = provider
        self.model = model
        self.api_key = api_key
        self.endpoint = endpoint

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
        temperature: float = 0.7,
        max_tokens: int = 4096,
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

        try:
            response = await acompletion(**kwargs)
            return response.choices[0].message.content
        except AuthenticationError as e:
            raise LLMAuthenticationError(f"Authentication failed: {e}") from e
        except RateLimitError as e:
            raise LLMRateLimitError(f"Rate limit exceeded: {e}") from e
        except APIConnectionError as e:
            raise LLMConnectionError(f"Connection failed: {e}") from e
        except APIError as e:
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
            temperature=0.3,  # Lower temperature for structured output
        )
