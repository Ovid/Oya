"""Q&A service tests."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from oya.qa.service import QAService
from oya.qa.schemas import (
    QARequest,
    QAResponse,
    Citation,
    ConfidenceLevel,
    SearchQuality,
)


@pytest.fixture
def mock_vectorstore():
    """Mock VectorStore for testing."""
    store = MagicMock()
    store.query.return_value = {
        "ids": [["doc1", "doc2", "doc3"]],
        "documents": [["content 1", "content 2", "content 3"]],
        "metadatas": [
            [
                {"type": "wiki", "path": "overview.md", "title": "Overview"},
                {"type": "code", "path": "src/main.py", "title": "main.py"},
                {"type": "note", "path": "notes/fix.md", "title": "Fix note"},
            ]
        ],
        "distances": [[0.2, 0.4, 0.6]],
    }
    return store


@pytest.fixture
def mock_db():
    """Mock Database for testing."""
    db = MagicMock()
    cursor = MagicMock()
    cursor.fetchall.return_value = [
        {"content": "fts result 1", "path": "docs/api.md", "title": "API Docs", "type": "wiki"},
        {"content": "fts result 2", "path": "src/utils.py", "title": "utils.py", "type": "code"},
    ]
    db.execute.return_value = cursor
    return db


@pytest.fixture
def mock_llm():
    """Mock LLMClient for testing."""
    llm = AsyncMock()
    llm.generate.return_value = """Based on the codebase, here's the answer:

The main entry point is in `src/main.py` which initializes the application.

[CITATIONS]
- src/main.py:10-20
- overview.md
"""
    return llm


class TestQAServiceHybridSearch:
    """Tests for hybrid search functionality."""

    @pytest.mark.asyncio
    async def test_hybrid_search_combines_semantic_and_fts(
        self, mock_vectorstore, mock_db, mock_llm
    ):
        """Hybrid search combines semantic and full-text results."""
        service = QAService(mock_vectorstore, mock_db, mock_llm)
        request = QARequest(question="How does authentication work?")

        results, semantic_ok, fts_ok = await service.search(request.question)

        # Should have called both vectorstore and db
        mock_vectorstore.query.assert_called_once()
        mock_db.execute.assert_called_once()

        # Results should be deduplicated and combined
        assert len(results) > 0
        # Both search methods should have succeeded
        assert semantic_ok is True
        assert fts_ok is True

    @pytest.mark.asyncio
    async def test_hybrid_search_prioritizes_notes(self, mock_vectorstore, mock_db, mock_llm):
        """Notes are prioritized over wiki/code in search results."""
        service = QAService(mock_vectorstore, mock_db, mock_llm)

        results, _, _ = await service.search("How does X work?")

        # Notes should appear first (lower index = higher priority)
        note_indices = [i for i, r in enumerate(results) if r.get("type") == "note"]
        wiki_indices = [i for i, r in enumerate(results) if r.get("type") == "wiki"]

        if note_indices and wiki_indices:
            assert min(note_indices) < max(wiki_indices)


class TestQAServiceAnswerGeneration:
    """Tests for LLM answer generation."""

    @pytest.mark.asyncio
    async def test_generates_answer_with_context(self, mock_vectorstore, mock_db, mock_llm):
        """Answer is generated using search results as context."""
        service = QAService(mock_vectorstore, mock_db, mock_llm)
        request = QARequest(question="How does the main function work?")

        await service.ask(request)

        # LLM should be called with context
        call_args = mock_llm.generate.call_args
        prompt = call_args.kwargs.get("prompt") or call_args.args[0]

        # Prompt should include search results
        assert "content 1" in prompt or "fts result" in prompt

    @pytest.mark.asyncio
    async def test_extracts_citations_from_answer(self, mock_vectorstore, mock_db, mock_llm):
        """Citations are extracted from LLM response."""
        service = QAService(mock_vectorstore, mock_db, mock_llm)
        request = QARequest(question="Where is the main entry point?")

        response = await service.ask(request)

        assert len(response.citations) > 0
        assert any(c.path == "src/main.py" for c in response.citations)

    @pytest.mark.asyncio
    async def test_includes_mandatory_disclaimer(self, mock_vectorstore, mock_db, mock_llm):
        """Response always includes confidence-based disclaimer."""
        service = QAService(mock_vectorstore, mock_db, mock_llm)
        request = QARequest(question="How does X work?")

        response = await service.ask(request)

        assert response.disclaimer is not None
        assert len(response.disclaimer) > 0
        # Disclaimers now describe confidence level
        assert any(
            word in response.disclaimer.lower()
            for word in ["evidence", "codebase", "verify", "speculative"]
        )


def test_qa_request_no_mode_or_context():
    """QARequest only has question field."""
    from oya.qa.schemas import QARequest

    request = QARequest(question="How does auth work?")
    assert request.question == "How does auth work?"
    # Verify mode and context don't exist
    assert not hasattr(request, "mode")
    assert not hasattr(request, "context")


def test_qa_response_has_confidence_and_search_quality():
    """QAResponse uses confidence instead of evidence_sufficient."""
    from oya.qa.schemas import ConfidenceLevel, SearchQuality

    response = QAResponse(
        answer="Auth uses JWT tokens.",
        citations=[],
        confidence=ConfidenceLevel.HIGH,
        disclaimer="Based on strong evidence.",
        search_quality=SearchQuality(
            semantic_searched=True,
            fts_searched=True,
            results_found=5,
            results_used=3,
        ),
    )
    assert response.confidence == ConfidenceLevel.HIGH
    assert response.search_quality.results_used == 3
    assert not hasattr(response, "evidence_sufficient")


def test_confidence_level_values():
    """ConfidenceLevel enum has expected values."""
    assert ConfidenceLevel.HIGH == "high"
    assert ConfidenceLevel.MEDIUM == "medium"
    assert ConfidenceLevel.LOW == "low"


def test_search_quality_schema():
    """SearchQuality tracks search execution metrics."""
    quality = SearchQuality(
        semantic_searched=True,
        fts_searched=False,
        results_found=10,
        results_used=5,
    )
    assert quality.semantic_searched is True
    assert quality.fts_searched is False
    assert quality.results_found == 10
    assert quality.results_used == 5


def test_citation_has_url_field():
    """Citation includes url for frontend routing."""
    citation = Citation(
        path="files/src_main-py.md",
        title="Main Module",
        lines="10-20",
        url="/files/src_main-py",
    )
    assert citation.url == "/files/src_main-py"


class TestConfidenceCalculation:
    """Tests for confidence level calculation."""

    def test_calculate_confidence_high(self):
        """HIGH confidence requires 3+ strong matches and best < 0.3."""
        from oya.qa.service import QAService
        from oya.qa.schemas import ConfidenceLevel

        # Mock service (we only need the method)
        service = QAService.__new__(QAService)

        results = [
            {"distance": 0.2},  # strong
            {"distance": 0.3},  # strong
            {"distance": 0.4},  # strong
            {"distance": 0.7},
        ]
        assert service._calculate_confidence(results) == ConfidenceLevel.HIGH

    def test_calculate_confidence_medium(self):
        """MEDIUM confidence requires 1+ decent match and best < 0.6."""
        from oya.qa.service import QAService
        from oya.qa.schemas import ConfidenceLevel

        service = QAService.__new__(QAService)

        results = [
            {"distance": 0.4},  # decent
            {"distance": 0.7},
            {"distance": 0.8},
        ]
        assert service._calculate_confidence(results) == ConfidenceLevel.MEDIUM

    def test_calculate_confidence_low(self):
        """LOW confidence when no good matches."""
        from oya.qa.service import QAService
        from oya.qa.schemas import ConfidenceLevel

        service = QAService.__new__(QAService)

        results = [
            {"distance": 0.7},
            {"distance": 0.9},
        ]
        assert service._calculate_confidence(results) == ConfidenceLevel.LOW

    def test_calculate_confidence_empty(self):
        """LOW confidence with no results."""
        from oya.qa.service import QAService
        from oya.qa.schemas import ConfidenceLevel

        service = QAService.__new__(QAService)
        assert service._calculate_confidence([]) == ConfidenceLevel.LOW


class TestPathToUrl:
    """Tests for _path_to_url helper method."""

    def test_path_to_url_files(self):
        """File paths convert to /files/slug route."""
        from oya.qa.service import QAService

        service = QAService.__new__(QAService)

        assert service._path_to_url("files/src_main-py.md") == "/files/src_main-py"

    def test_path_to_url_directories(self):
        """Directory paths convert to /directories/slug route."""
        from oya.qa.service import QAService

        service = QAService.__new__(QAService)

        assert service._path_to_url("directories/backend_src.md") == "/directories/backend_src"

    def test_path_to_url_overview(self):
        """Overview converts to root route."""
        from oya.qa.service import QAService

        service = QAService.__new__(QAService)

        assert service._path_to_url("overview.md") == "/"

    def test_path_to_url_architecture(self):
        """Architecture converts to /architecture route."""
        from oya.qa.service import QAService

        service = QAService.__new__(QAService)

        assert service._path_to_url("architecture.md") == "/architecture"


class TestStructuredCitationExtraction:
    """Tests for structured citation extraction."""

    def test_extract_structured_citations(self):
        """Extract citations from structured JSON output."""
        from oya.qa.service import QAService

        service = QAService.__new__(QAService)

        response = """<answer>
The auth module handles JWT tokens.
</answer>

<citations>
[
  {"path": "files/auth-py.md", "relevant_text": "JWT token generation"},
  {"path": "files/config-py.md", "relevant_text": "auth settings"}
]
</citations>"""

        results = [
            {"path": "files/auth-py.md", "title": "Auth Module"},
            {"path": "files/config-py.md", "title": "Config"},
            {"path": "files/other.md", "title": "Other"},
        ]

        citations = service._extract_citations(response, results)
        assert len(citations) == 2
        assert citations[0].path == "files/auth-py.md"
        assert citations[0].url == "/files/auth-py"

    def test_extract_answer_from_structured(self):
        """Extract answer from structured output."""
        from oya.qa.service import QAService

        service = QAService.__new__(QAService)

        response = """<answer>
The auth module handles JWT tokens.
</answer>

<citations>
[{"path": "files/auth-py.md"}]
</citations>"""

        answer = service._extract_answer(response)
        assert answer == "The auth module handles JWT tokens."
        assert "<citations>" not in answer

    def test_fallback_to_legacy_citations(self):
        """Falls back to legacy format when no structured citations."""
        from oya.qa.service import QAService

        service = QAService.__new__(QAService)

        response = """Here is the answer.

[CITATIONS]
- files/auth-py.md:10-20
- files/config-py.md
"""

        results = [
            {"path": "files/auth-py.md", "title": "Auth Module"},
            {"path": "files/config-py.md", "title": "Config"},
        ]

        citations = service._extract_citations(response, results)
        assert len(citations) == 2
        assert citations[0].lines == "10-20"

    def test_fallback_citations_from_results(self):
        """Uses fallback citations when no explicit citations found."""
        from oya.qa.service import QAService

        service = QAService.__new__(QAService)

        response = "Just a plain answer with no citations."

        results = [
            {"path": "files/a.md", "title": "A"},
            {"path": "files/b.md", "title": "B"},
            {"path": "files/c.md", "title": "C"},
        ]

        citations = service._extract_citations(response, results)
        assert len(citations) == 3


class TestDeduplicateResults:
    """Tests for content deduplication."""

    def test_removes_duplicate_content(self):
        """Deduplication removes near-duplicate content."""
        from oya.qa.service import QAService

        service = QAService.__new__(QAService)

        results = [
            {"path": "file1.md", "content": "This is the same content here."},
            {"path": "file2.md", "content": "This is the same content here."},  # Duplicate
            {"path": "file3.md", "content": "This is different content."},
        ]

        deduped = service._deduplicate_results(results)
        assert len(deduped) == 2
        assert deduped[0]["path"] == "file1.md"
        assert deduped[1]["path"] == "file3.md"

    def test_preserves_order(self):
        """Deduplication preserves order of first occurrence."""
        from oya.qa.service import QAService

        service = QAService.__new__(QAService)

        results = [
            {"path": "a.md", "content": "Unique A content."},
            {"path": "b.md", "content": "Unique B content."},
            {"path": "c.md", "content": "Unique C content."},
        ]

        deduped = service._deduplicate_results(results)
        assert len(deduped) == 3
        assert [r["path"] for r in deduped] == ["a.md", "b.md", "c.md"]

    def test_empty_results(self):
        """Empty results return empty list."""
        from oya.qa.service import QAService

        service = QAService.__new__(QAService)

        assert service._deduplicate_results([]) == []


class TestTruncateAtSentence:
    """Tests for sentence-boundary truncation."""

    def test_short_text_unchanged(self):
        """Short text passes through unchanged."""
        from oya.qa.service import QAService

        service = QAService.__new__(QAService)

        text = "This is a short sentence."
        result = service._truncate_at_sentence(text, max_tokens=100)
        assert result == text

    def test_preserves_sentence_boundary(self):
        """Long text truncates at sentence boundary."""
        from oya.qa.service import QAService

        service = QAService.__new__(QAService)

        text = "First sentence. Second sentence. Third sentence that is very long."
        # 10 tokens ~= 40 chars, should fit "First sentence. Second sentence."
        result = service._truncate_at_sentence(text, max_tokens=10)
        assert result.endswith(".")
        # Should have truncated before "Third"
        assert "Third" not in result

    def test_empty_text(self):
        """Empty text returns empty string."""
        from oya.qa.service import QAService

        service = QAService.__new__(QAService)

        result = service._truncate_at_sentence("", max_tokens=100)
        assert result == ""

    def test_single_very_long_sentence(self):
        """Single long sentence gets character-truncated."""
        from oya.qa.service import QAService

        service = QAService.__new__(QAService)

        text = "This is one very long sentence with no periods " * 50
        result = service._truncate_at_sentence(text, max_tokens=10)
        # Should be truncated and end with "..."
        assert len(result) < len(text)
        assert result.endswith("...")


class TestQAServiceGraphAugmented:
    """Tests for graph-augmented Q&A."""

    @pytest.mark.asyncio
    async def test_qa_with_graph_expands_context(self, mock_vectorstore, mock_db, mock_llm):
        """When graph is provided, Q&A expands context using graph traversal."""
        import networkx as nx

        # Create a simple graph
        graph = nx.DiGraph()
        graph.add_node(
            "auth/handler.py::login",
            name="login",
            type="function",
            file_path="auth/handler.py",
            line_start=10,
            line_end=30,
        )
        graph.add_node(
            "auth/verify.py::verify",
            name="verify",
            type="function",
            file_path="auth/verify.py",
            line_start=5,
            line_end=20,
        )
        graph.add_edge(
            "auth/handler.py::login",
            "auth/verify.py::verify",
            type="calls",
            confidence=0.9,
            line=15,
        )

        service = QAService(mock_vectorstore, mock_db, mock_llm, graph=graph)
        request = QARequest(question="How does login work?")

        await service.ask(request)

        # LLM should be called with expanded context
        call_args = mock_llm.generate.call_args
        prompt = call_args.kwargs.get("prompt") or call_args.args[0]

        # Should include graph context (mermaid or code relationships)
        assert "login" in prompt.lower() or "flowchart" in prompt.lower()

    @pytest.mark.asyncio
    async def test_qa_falls_back_without_graph(self, mock_vectorstore, mock_db, mock_llm):
        """Without graph, Q&A uses normal vector retrieval."""
        service = QAService(mock_vectorstore, mock_db, mock_llm, graph=None)
        request = QARequest(question="How does X work?")

        response = await service.ask(request)

        # Should still work and return response
        assert response.answer is not None
        assert response.confidence is not None

    @pytest.mark.asyncio
    async def test_qa_graph_can_be_disabled(self, mock_vectorstore, mock_db, mock_llm):
        """Graph expansion can be disabled via parameter."""
        import networkx as nx

        graph = nx.DiGraph()
        graph.add_node(
            "test::func",
            name="func",
            type="function",
            file_path="test.py",
            line_start=1,
            line_end=10,
        )

        service = QAService(mock_vectorstore, mock_db, mock_llm, graph=graph)
        request = QARequest(question="Test question", use_graph=False)

        await service.ask(request)

        # Should work without graph expansion
        mock_llm.generate.assert_called_once()


class TestQAServiceIssues:
    """Tests for issue-aware Q&A."""

    def test_is_issue_query_detects_keywords(self):
        """_is_issue_query detects issue-related questions."""
        from unittest.mock import Mock
        from oya.qa.service import QAService

        mock_vectorstore = Mock()
        mock_db = Mock()
        mock_llm = Mock()

        service = QAService(mock_vectorstore, mock_db, mock_llm)

        assert service._is_issue_query("Are there any security issues?")
        assert service._is_issue_query("What bugs exist in the code?")
        assert service._is_issue_query("Show me code quality problems")
        assert service._is_issue_query("What's wrong with the authentication?")

        assert not service._is_issue_query("How does the API work?")
        assert not service._is_issue_query("Explain the database schema")

    def test_is_issue_query_case_insensitive(self):
        """_is_issue_query is case-insensitive."""
        from unittest.mock import Mock
        from oya.qa.service import QAService

        mock_vectorstore = Mock()
        mock_db = Mock()
        mock_llm = Mock()

        service = QAService(mock_vectorstore, mock_db, mock_llm)

        assert service._is_issue_query("Are there any SECURITY ISSUES?")
        assert service._is_issue_query("What BUGS exist?")
        assert service._is_issue_query("TECHNICAL DEBT in the codebase")

    @pytest.mark.asyncio
    async def test_ask_with_issues_queries_issues_store(self):
        """Issue queries use IssuesStore when available."""
        from unittest.mock import Mock, AsyncMock
        from oya.qa.service import QAService

        mock_vectorstore = Mock()
        mock_db = Mock()
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = """<answer>
Found 2 security issues.
</answer>
<citations>
[{"path": "files/auth-py.md", "relevant_text": "security issue"}]
</citations>"""

        mock_issues_store = Mock()
        mock_issues_store.query_issues.return_value = [
            {
                "id": "auth.py::hardcoded-secret::0",
                "file_path": "auth.py",
                "category": "security",
                "severity": "problem",
                "title": "Hardcoded secret",
                "content": "Hardcoded secret\n\nAPI key is hardcoded in source.",
            },
            {
                "id": "db.py::sql-injection::0",
                "file_path": "db.py",
                "category": "security",
                "severity": "problem",
                "title": "SQL injection risk",
                "content": "SQL injection risk\n\nUser input is not sanitized.",
            },
        ]

        service = QAService(mock_vectorstore, mock_db, mock_llm, mock_issues_store)

        from oya.qa.schemas import QARequest

        request = QARequest(question="What security issues exist?")
        response = await service.ask(request)

        # Should have queried the issues store
        mock_issues_store.query_issues.assert_called_once()

        # Should have generated an answer
        assert response.answer is not None
        assert len(response.answer) > 0

    @pytest.mark.asyncio
    async def test_ask_with_issues_falls_back_when_no_issues(self):
        """Falls back to normal search when no issues found."""
        from unittest.mock import Mock, AsyncMock
        from oya.qa.service import QAService

        mock_vectorstore = Mock()
        mock_vectorstore.query.return_value = {
            "ids": [["doc1"]],
            "documents": [["content 1"]],
            "metadatas": [[{"type": "wiki", "path": "overview.md", "title": "Overview"}]],
            "distances": [[0.2]],
        }

        mock_db = Mock()
        cursor = Mock()
        cursor.fetchall.return_value = []
        mock_db.execute.return_value = cursor

        mock_llm = AsyncMock()
        mock_llm.generate.return_value = """<answer>
No issues found, here is normal answer.
</answer>
<citations>
[{"path": "overview.md", "relevant_text": "overview"}]
</citations>"""

        mock_issues_store = Mock()
        mock_issues_store.query_issues.return_value = []  # No issues

        service = QAService(mock_vectorstore, mock_db, mock_llm, mock_issues_store)

        from oya.qa.schemas import QARequest

        request = QARequest(question="What bugs exist?")
        await service.ask(request)

        # Should have tried issues store first
        mock_issues_store.query_issues.assert_called_once()

        # Should have fallen back to normal search
        mock_vectorstore.query.assert_called_once()

    @pytest.mark.asyncio
    async def test_ask_without_issues_store_uses_normal_flow(self):
        """Issue queries use normal flow when no IssuesStore provided."""
        from unittest.mock import Mock, AsyncMock
        from oya.qa.service import QAService

        mock_vectorstore = Mock()
        mock_vectorstore.query.return_value = {
            "ids": [["doc1"]],
            "documents": [["content 1"]],
            "metadatas": [[{"type": "wiki", "path": "overview.md", "title": "Overview"}]],
            "distances": [[0.2]],
        }

        mock_db = Mock()
        cursor = Mock()
        cursor.fetchall.return_value = []
        mock_db.execute.return_value = cursor

        mock_llm = AsyncMock()
        mock_llm.generate.return_value = """<answer>
Normal answer.
</answer>
<citations>
[{"path": "overview.md", "relevant_text": "overview"}]
</citations>"""

        # No issues_store provided
        service = QAService(mock_vectorstore, mock_db, mock_llm)

        from oya.qa.schemas import QARequest

        request = QARequest(question="What bugs exist?")
        await service.ask(request)

        # Should use normal search flow
        mock_vectorstore.query.assert_called_once()

    @pytest.mark.asyncio
    async def test_ask_with_issues_handles_llm_error(self):
        """Error during LLM generation returns error response."""
        from unittest.mock import AsyncMock, Mock
        from oya.qa.service import QAService
        from oya.qa.schemas import QARequest, ConfidenceLevel

        mock_vectorstore = Mock()
        mock_db = Mock()
        mock_llm = AsyncMock()
        mock_llm.generate.side_effect = Exception("LLM unavailable")

        mock_issues_store = Mock()
        mock_issues_store.query_issues.return_value = [
            {
                "file_path": "test.py",
                "category": "security",
                "severity": "problem",
                "title": "Test issue",
                "content": "Test content",
            }
        ]

        service = QAService(mock_vectorstore, mock_db, mock_llm, mock_issues_store)
        response = await service.ask(QARequest(question="What security issues exist?"))

        assert "Error:" in response.answer
        assert response.confidence == ConfidenceLevel.LOW
