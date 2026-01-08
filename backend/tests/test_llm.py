# backend/tests/test_llm.py
"""LLM client tests."""

from unittest.mock import AsyncMock, patch

import pytest

from oya.llm import LLMClient


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
