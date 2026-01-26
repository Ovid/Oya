import pytest
from unittest.mock import MagicMock
from oya.qa.retrieval.diagnostic import DiagnosticRetriever, extract_error_anchors


def test_extract_exception_types():
    """Should extract exception types from query."""
    query = "Why am I getting sqlite3.OperationalError: readonly database?"
    anchors = extract_error_anchors(query)

    assert (
        "sqlite3.OperationalError" in anchors.exception_types
        or "OperationalError" in anchors.exception_types
    )


def test_extract_error_messages():
    """Should extract error message patterns."""
    query = 'The API returns "connection refused" when calling the endpoint'
    anchors = extract_error_anchors(query)

    assert "connection refused" in anchors.error_strings


def test_extract_stack_trace_info():
    """Should extract file/function from stack trace patterns."""
    query = """Getting error at:
    File "backend/src/oya/api/deps.py", line 45, in get_db
    """
    anchors = extract_error_anchors(query)

    assert any("deps.py" in p for p in anchors.file_refs)
    assert "get_db" in anchors.function_refs


@pytest.fixture
def mock_code_index():
    """Create mock code index query."""
    index = MagicMock()
    index.find_by_raises.return_value = []
    index.find_by_error_string.return_value = []
    index.get_callers.return_value = []
    return index


@pytest.mark.asyncio
async def test_diagnostic_retriever_uses_error_anchors(mock_code_index):
    """Should query code index with extracted error anchors."""
    from oya.db.code_index import CodeIndexEntry

    mock_entry = CodeIndexEntry(
        id=1,
        file_path="backend/src/oya/api/deps.py",
        symbol_name="get_db",
        symbol_type="function",
        line_start=45,
        line_end=60,
        signature="def get_db(repo) -> Database",
        docstring="Get database connection",
        calls=[],
        called_by=["get_notes_service"],
        raises=["sqlite3.OperationalError"],
        mutates=["_db_instances"],
        error_strings=["readonly database"],
        source_hash="abc",
    )
    mock_code_index.find_by_raises.return_value = [mock_entry]

    retriever = DiagnosticRetriever(mock_code_index)
    query = "Why am I getting sqlite3.OperationalError?"

    results = await retriever.retrieve(query, budget=2000)

    mock_code_index.find_by_raises.assert_called()
    assert len(results) > 0
