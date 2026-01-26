import pytest
from unittest.mock import MagicMock
from oya.qa.retrieval.exploratory import ExploratoryRetriever, extract_trace_subject


def test_extract_trace_subject():
    """Should extract the subject being traced."""
    assert extract_trace_subject("Trace the auth flow") == "auth"
    assert extract_trace_subject("How does authentication work step by step?") == "authentication"
    assert extract_trace_subject("Walk through the request handling") == "request"


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
    from oya.db.code_index import CodeIndexEntry

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
