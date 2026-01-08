# backend/tests/test_llm.py
"""LLM client tests."""

from unittest.mock import AsyncMock, patch

import pytest
from litellm.exceptions import AuthenticationError, RateLimitError

from oya.llm import (
    LLMAuthenticationError,
    LLMClient,
    LLMRateLimitError,
)


@pytest.fixture
def mock_completion():
    """Mock litellm completion response."""
    with patch("oya.llm.client.acompletion") as mock:
        mock.return_value = AsyncMock(
            choices=[
                AsyncMock(
                    message=AsyncMock(content="Test response")
                )
            ]
        )
        yield mock


async def test_llm_client_generates_response(mock_completion):
    """LLM client generates response from prompt."""
    client = LLMClient(provider="openai", model="gpt-4o")

    response = await client.generate("Test prompt")

    assert response == "Test response"
    mock_completion.assert_called_once()


async def test_llm_client_uses_configured_model(mock_completion):
    """LLM client uses configured provider and model."""
    client = LLMClient(provider="anthropic", model="claude-3-sonnet")

    await client.generate("Test")

    call_args = mock_completion.call_args
    assert call_args.kwargs["model"] == "anthropic/claude-3-sonnet"


async def test_llm_client_passes_system_prompt(mock_completion):
    """LLM client includes system prompt in messages."""
    client = LLMClient(provider="openai", model="gpt-4o")

    await client.generate(
        "User message",
        system_prompt="You are a helpful assistant",
    )

    call_args = mock_completion.call_args
    messages = call_args.kwargs["messages"]
    assert messages[0]["role"] == "system"
    assert messages[0]["content"] == "You are a helpful assistant"
    assert messages[1]["role"] == "user"
    assert messages[1]["content"] == "User message"


async def test_llm_client_ollama_provider_model_string(mock_completion):
    """LLM client formats ollama provider with ollama/ prefix."""
    client = LLMClient(provider="ollama", model="llama3")

    await client.generate("Test")

    call_args = mock_completion.call_args
    assert call_args.kwargs["model"] == "ollama/llama3"


async def test_llm_client_generate_with_json_adds_instruction(mock_completion):
    """generate_with_json adds JSON instruction to system prompt."""
    client = LLMClient(provider="openai", model="gpt-4o")

    await client.generate_with_json(
        "Generate user data",
        system_prompt="You are a data generator",
    )

    call_args = mock_completion.call_args
    messages = call_args.kwargs["messages"]
    assert messages[0]["role"] == "system"
    assert "Respond with valid JSON only" in messages[0]["content"]
    assert "You are a data generator" in messages[0]["content"]


async def test_llm_client_generate_with_json_uses_lower_temperature(mock_completion):
    """generate_with_json uses lower temperature for structured output."""
    client = LLMClient(provider="openai", model="gpt-4o")

    await client.generate_with_json("Generate data")

    call_args = mock_completion.call_args
    assert call_args.kwargs["temperature"] == 0.3


async def test_llm_client_raises_authentication_error():
    """LLM client raises LLMAuthenticationError on auth failure."""
    with patch("oya.llm.client.acompletion") as mock:
        mock.side_effect = AuthenticationError(
            message="Invalid API key",
            llm_provider="openai",
            model="gpt-4o",
        )
        client = LLMClient(provider="openai", model="gpt-4o")

        with pytest.raises(LLMAuthenticationError) as exc_info:
            await client.generate("Test")

        assert "Authentication failed" in str(exc_info.value)


async def test_llm_client_raises_rate_limit_error():
    """LLM client raises LLMRateLimitError on rate limit."""
    with patch("oya.llm.client.acompletion") as mock:
        mock.side_effect = RateLimitError(
            message="Rate limit exceeded",
            llm_provider="openai",
            model="gpt-4o",
        )
        client = LLMClient(provider="openai", model="gpt-4o")

        with pytest.raises(LLMRateLimitError) as exc_info:
            await client.generate("Test")

        assert "Rate limit exceeded" in str(exc_info.value)
