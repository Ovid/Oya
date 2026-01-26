import pytest
from unittest.mock import AsyncMock, MagicMock
from oya.qa.classifier import QueryClassifier, QueryMode


@pytest.fixture
def mock_llm_client():
    """Create mock LLM client."""
    client = MagicMock()
    client.complete = AsyncMock()
    return client


@pytest.mark.asyncio
async def test_classifies_diagnostic_query(mock_llm_client):
    """Should classify error-related queries as diagnostic."""
    mock_llm_client.complete.return_value = MagicMock(
        content='{"mode": "DIAGNOSTIC", "reasoning": "Contains exception type", "scope": null}'
    )

    classifier = QueryClassifier(mock_llm_client)
    result = await classifier.classify("Why am I getting ValueError when calling process()?")

    assert result.mode == QueryMode.DIAGNOSTIC
    assert result.reasoning == "Contains exception type"


@pytest.mark.asyncio
async def test_classifies_exploratory_query(mock_llm_client):
    """Should classify trace queries as exploratory."""
    mock_llm_client.complete.return_value = MagicMock(
        content='{"mode": "EXPLORATORY", "reasoning": "Asks to trace flow", "scope": "auth"}'
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
    mock_llm_client.complete.return_value = MagicMock(
        content='{"mode": "ANALYTICAL", "reasoning": "Asks about flaws", "scope": "frontend"}'
    )

    classifier = QueryClassifier(mock_llm_client)
    result = await classifier.classify("What are the architectural flaws in the frontend code?")

    assert result.mode == QueryMode.ANALYTICAL
    assert result.scope == "frontend"


@pytest.mark.asyncio
async def test_classifies_conceptual_query(mock_llm_client):
    """Should classify general questions as conceptual."""
    mock_llm_client.complete.return_value = MagicMock(
        content='{"mode": "CONCEPTUAL", "reasoning": "General explanation request", "scope": null}'
    )

    classifier = QueryClassifier(mock_llm_client)
    result = await classifier.classify("How does the caching system work?")

    assert result.mode == QueryMode.CONCEPTUAL


@pytest.mark.asyncio
async def test_handles_malformed_llm_response(mock_llm_client):
    """Should default to conceptual on malformed response."""
    mock_llm_client.complete.return_value = MagicMock(content="not valid json")

    classifier = QueryClassifier(mock_llm_client)
    result = await classifier.classify("Some query")

    assert result.mode == QueryMode.CONCEPTUAL
