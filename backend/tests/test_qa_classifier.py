import pytest
from unittest.mock import AsyncMock, MagicMock
from oya.qa.classifier import QueryClassifier, QueryMode


@pytest.fixture
def mock_llm_client():
    """Create mock LLM client."""
    client = MagicMock()
    client.generate = AsyncMock()
    return client


@pytest.mark.asyncio
async def test_classifies_diagnostic_query(mock_llm_client):
    """Should classify error-related queries as diagnostic."""
    mock_llm_client.generate.return_value = (
        '{"mode": "DIAGNOSTIC", "reasoning": "Contains exception type", "scope": null}'
    )

    classifier = QueryClassifier(mock_llm_client)
    result = await classifier.classify("Why am I getting ValueError when calling process()?")

    assert result.mode == QueryMode.DIAGNOSTIC
    assert result.reasoning == "Contains exception type"

    # Verify correct method and parameters were used
    mock_llm_client.generate.assert_called_once()
    call_kwargs = mock_llm_client.generate.call_args.kwargs
    assert "prompt" in call_kwargs
    assert "system_prompt" in call_kwargs
    assert call_kwargs["temperature"] == 0.0
    assert call_kwargs["max_tokens"] == 200


@pytest.mark.asyncio
async def test_classifies_exploratory_query(mock_llm_client):
    """Should classify trace queries as exploratory."""
    mock_llm_client.generate.return_value = (
        '{"mode": "EXPLORATORY", "reasoning": "Asks to trace flow", "scope": "auth"}'
    )

    classifier = QueryClassifier(mock_llm_client)
    result = await classifier.classify(
        "Trace the authentication flow from login to session creation"
    )

    assert result.mode == QueryMode.EXPLORATORY
    assert result.scope == "auth"


@pytest.mark.asyncio
async def test_classifies_analytical_query(mock_llm_client):
    """Should classify architecture questions as analytical."""
    mock_llm_client.generate.return_value = (
        '{"mode": "ANALYTICAL", "reasoning": "Asks about flaws", "scope": "frontend"}'
    )

    classifier = QueryClassifier(mock_llm_client)
    result = await classifier.classify("What are the architectural flaws in the frontend code?")

    assert result.mode == QueryMode.ANALYTICAL
    assert result.scope == "frontend"


@pytest.mark.asyncio
async def test_classifies_conceptual_query(mock_llm_client):
    """Should classify general questions as conceptual."""
    mock_llm_client.generate.return_value = (
        '{"mode": "CONCEPTUAL", "reasoning": "General explanation request", "scope": null}'
    )

    classifier = QueryClassifier(mock_llm_client)
    result = await classifier.classify("How does the caching system work?")

    assert result.mode == QueryMode.CONCEPTUAL


@pytest.mark.asyncio
async def test_handles_malformed_llm_response(mock_llm_client):
    """Should default to conceptual on malformed response."""
    mock_llm_client.generate.return_value = "not valid json"

    classifier = QueryClassifier(mock_llm_client)
    result = await classifier.classify("Some query")

    assert result.mode == QueryMode.CONCEPTUAL
    assert "parsing error" in result.reasoning.lower()


@pytest.mark.asyncio
async def test_handles_missing_mode_key(mock_llm_client):
    """Should default to conceptual when mode key is missing."""
    mock_llm_client.generate.return_value = '{"reasoning": "Some reasoning", "scope": null}'

    classifier = QueryClassifier(mock_llm_client)
    result = await classifier.classify("Some query")

    assert result.mode == QueryMode.CONCEPTUAL
    assert "parsing error" in result.reasoning.lower()


@pytest.mark.asyncio
async def test_handles_invalid_mode_value(mock_llm_client):
    """Should default to conceptual when mode value is invalid."""
    mock_llm_client.generate.return_value = (
        '{"mode": "INVALID_MODE", "reasoning": "Some reasoning", "scope": null}'
    )

    classifier = QueryClassifier(mock_llm_client)
    result = await classifier.classify("Some query")

    assert result.mode == QueryMode.CONCEPTUAL
    assert "parsing error" in result.reasoning.lower()
