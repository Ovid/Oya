"""Tests for analytical retrieval."""

import pytest
from unittest.mock import MagicMock

from oya.db.code_index import CodeIndexEntry
from oya.qa.retrieval.analytical import AnalyticalRetriever, extract_scope


def test_extract_scope():
    """Should extract scope from analytical queries."""
    assert extract_scope("What are the architectural flaws in the frontend?") == "frontend"
    assert extract_scope("Analyze the backend API structure") == "backend"
    assert extract_scope("What's wrong with the caching layer?") == "caching"


@pytest.fixture
def mock_code_index():
    """Create mock code index query."""
    index = MagicMock()
    index.find_by_file.return_value = []
    return index


@pytest.fixture
def mock_issues_store():
    """Create mock issues store."""
    store = MagicMock()
    store.query_issues.return_value = []
    return store


@pytest.mark.asyncio
async def test_analytical_retriever_computes_metrics(mock_code_index, mock_issues_store):
    """Should compute structural metrics for scope."""
    # Function with high fan-out (potential god function)
    god_func = CodeIndexEntry(
        id=1,
        file_path="frontend/src/App.tsx",
        symbol_name="handleEverything",
        symbol_type="function",
        line_start=10,
        line_end=200,
        signature="function handleEverything()",
        docstring=None,
        calls=["a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "k", "l", "m", "n", "o", "p"],
        called_by=[],
        raises=[],
        mutates=["state"],
        error_strings=[],
        source_hash="abc",
    )
    mock_code_index.find_by_file.return_value = [god_func]

    retriever = AnalyticalRetriever(mock_code_index, mock_issues_store)
    results = await retriever.retrieve("What are the flaws in the frontend?", budget=2000)

    assert len(results) > 0
    # Should flag high fan-out function
    assert any("fan-out" in r.relevance.lower() or "god" in r.relevance.lower() for r in results)


@pytest.mark.asyncio
async def test_analytical_retriever_finds_hotspots(mock_code_index, mock_issues_store):
    """Should identify hotspots (high fan-in functions)."""
    # Function with high fan-in (called by many)
    hotspot = CodeIndexEntry(
        id=2,
        file_path="backend/src/utils.py",
        symbol_name="validate",
        symbol_type="function",
        line_start=5,
        line_end=20,
        signature="def validate(data)",
        docstring=None,
        calls=[],
        called_by=[
            "a",
            "b",
            "c",
            "d",
            "e",
            "f",
            "g",
            "h",
            "i",
            "j",
            "k",
            "l",
            "m",
            "n",
            "o",
            "p",
            "q",
            "r",
            "s",
            "t",
            "u",
        ],
        raises=[],
        mutates=[],
        error_strings=[],
        source_hash="def",
    )
    mock_code_index.find_by_file.return_value = [hotspot]

    retriever = AnalyticalRetriever(mock_code_index, mock_issues_store)
    results = await retriever.retrieve("What are the flaws in the backend?", budget=2000)

    assert len(results) > 0
    # Should flag high fan-in function
    assert any("fan-in" in r.relevance.lower() or "hotspot" in r.relevance.lower() for r in results)


@pytest.mark.asyncio
async def test_analytical_retriever_includes_issues(mock_code_index, mock_issues_store):
    """Should include pre-computed issues from issues store."""
    mock_code_index.find_by_file.return_value = []
    mock_issues_store.query_issues.return_value = [
        {
            "file_path": "frontend/src/App.tsx",
            "category": "complexity",
            "title": "High cyclomatic complexity",
            "content": "Function has too many branches",
        }
    ]

    retriever = AnalyticalRetriever(mock_code_index, mock_issues_store)
    results = await retriever.retrieve("What are the flaws in the frontend?", budget=2000)

    assert len(results) > 0
    assert any("issues_store" in r.source for r in results)


@pytest.mark.asyncio
async def test_analytical_retriever_no_scope(mock_code_index, mock_issues_store):
    """Should handle queries with no clear scope."""
    retriever = AnalyticalRetriever(mock_code_index, mock_issues_store)
    results = await retriever.retrieve("What's the time?", budget=2000)

    # Should return empty when no scope can be extracted
    assert results == []
