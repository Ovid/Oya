import pytest
from unittest.mock import MagicMock
from oya.db.code_index import CodeIndexEntry
from oya.qa.retrieval.exploratory import ExploratoryRetriever, extract_trace_subject


def test_extract_trace_subject():
    """Should extract the subject being traced."""
    assert extract_trace_subject("Trace the auth flow") == "auth"
    assert extract_trace_subject("How does authentication work step by step?") == "authentication"
    assert extract_trace_subject("Walk through the request handling") == "request"


def test_extract_trace_subject_no_match():
    """Should return None when query doesn't match any pattern."""
    assert extract_trace_subject("What is the meaning of life?") is None
    assert extract_trace_subject("random text here") is None


def test_extract_trace_subject_filters_stop_words():
    """Should filter out stop words and return None."""
    # "the" is a stop word, should be filtered
    assert extract_trace_subject("trace the") is None
    # "code" is also filtered
    assert extract_trace_subject("how does code") is None


def test_extract_trace_subject_empty_input():
    """Should return None for empty string input."""
    assert extract_trace_subject("") is None


@pytest.fixture
def mock_code_index():
    """Create mock code index query."""
    index = MagicMock()
    index.find_by_symbol.return_value = []
    index.get_callees.return_value = []
    return index


@pytest.mark.asyncio
async def test_exploratory_retriever_finds_entry_points(mock_code_index):
    """Should find entry points and trace forward."""
    entry_point = CodeIndexEntry(
        id=1,
        file_path="backend/src/oya/api/routers/auth.py",
        symbol_name="login",
        symbol_type="function",
        line_start=20,
        line_end=45,
        signature="def login(request: LoginRequest) -> Token",
        docstring="Handle user login",
        calls=["validate_credentials", "create_session"],
        called_by=[],
        raises=[],
        mutates=[],
        error_strings=[],
        source_hash="abc",
    )
    mock_code_index.find_by_symbol.return_value = [entry_point]

    retriever = ExploratoryRetriever(mock_code_index)
    results = await retriever.retrieve("Trace the login flow", budget=2500)

    assert len(results) > 0
    assert any("login" in r.content for r in results)
