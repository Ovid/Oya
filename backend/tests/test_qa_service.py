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
        "metadatas": [[
            {"type": "wiki", "path": "overview.md", "title": "Overview"},
            {"type": "code", "path": "src/main.py", "title": "main.py"},
            {"type": "note", "path": "notes/fix.md", "title": "Fix note"},
        ]],
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

        result = await service.search(request.question)

        # Should have called both vectorstore and db
        mock_vectorstore.query.assert_called_once()
        mock_db.execute.assert_called_once()

        # Results should be deduplicated and combined
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_hybrid_search_prioritizes_notes(
        self, mock_vectorstore, mock_db, mock_llm
    ):
        """Notes are prioritized over wiki/code in search results."""
        service = QAService(mock_vectorstore, mock_db, mock_llm)

        result = await service.search("How does X work?")

        # Notes should appear first (lower index = higher priority)
        note_indices = [
            i for i, r in enumerate(result) if r.get("type") == "note"
        ]
        wiki_indices = [
            i for i, r in enumerate(result) if r.get("type") == "wiki"
        ]

        if note_indices and wiki_indices:
            assert min(note_indices) < max(wiki_indices)


class TestQAServiceEvidenceEvaluation:
    """Tests for evidence gating functionality."""

    @pytest.mark.asyncio
    async def test_gated_mode_requires_sufficient_evidence(
        self, mock_vectorstore, mock_db, mock_llm
    ):
        """Gated mode requires sufficient evidence to generate answer."""
        service = QAService(mock_vectorstore, mock_db, mock_llm)
        request = QARequest(
            question="How does authentication work?",
            mode=QAMode.GATED,
        )

        response = await service.ask(request)

        assert response.evidence_sufficient is True
        assert response.answer is not None

    @pytest.mark.asyncio
    async def test_gated_mode_rejects_insufficient_evidence(
        self, mock_vectorstore, mock_db, mock_llm
    ):
        """Gated mode returns no answer when evidence is insufficient."""
        # Empty results = no evidence
        mock_vectorstore.query.return_value = {
            "ids": [[]],
            "documents": [[]],
            "metadatas": [[]],
            "distances": [[]],
        }
        mock_db.execute.return_value.fetchall.return_value = []

        service = QAService(mock_vectorstore, mock_db, mock_llm)
        request = QARequest(
            question="What is the meaning of life?",
            mode=QAMode.GATED,
        )

        response = await service.ask(request)

        assert response.evidence_sufficient is False
        assert response.answer == ""
        assert "insufficient evidence" in response.disclaimer.lower()
        # LLM should not be called
        mock_llm.generate.assert_not_called()

    @pytest.mark.asyncio
    async def test_loose_mode_always_answers(
        self, mock_vectorstore, mock_db, mock_llm
    ):
        """Loose mode generates answer even with limited evidence."""
        # Empty results
        mock_vectorstore.query.return_value = {
            "ids": [[]],
            "documents": [[]],
            "metadatas": [[]],
            "distances": [[]],
        }
        mock_db.execute.return_value.fetchall.return_value = []

        service = QAService(mock_vectorstore, mock_db, mock_llm)
        request = QARequest(
            question="How does authentication work?",
            mode=QAMode.LOOSE,
        )

        response = await service.ask(request)

        # Should still answer in loose mode
        mock_llm.generate.assert_called_once()
        assert "speculative" in response.disclaimer.lower() or "limited evidence" in response.disclaimer.lower()


class TestQAServiceAnswerGeneration:
    """Tests for LLM answer generation."""

    @pytest.mark.asyncio
    async def test_generates_answer_with_context(
        self, mock_vectorstore, mock_db, mock_llm
    ):
        """Answer is generated using search results as context."""
        service = QAService(mock_vectorstore, mock_db, mock_llm)
        request = QARequest(question="How does the main function work?")

        response = await service.ask(request)

        # LLM should be called with context
        call_args = mock_llm.generate.call_args
        prompt = call_args.kwargs.get("prompt") or call_args.args[0]

        # Prompt should include search results
        assert "content 1" in prompt or "fts result" in prompt

    @pytest.mark.asyncio
    async def test_extracts_citations_from_answer(
        self, mock_vectorstore, mock_db, mock_llm
    ):
        """Citations are extracted from LLM response."""
        service = QAService(mock_vectorstore, mock_db, mock_llm)
        request = QARequest(question="Where is the main entry point?")

        response = await service.ask(request)

        assert len(response.citations) > 0
        assert any(c.path == "src/main.py" for c in response.citations)

    @pytest.mark.asyncio
    async def test_includes_mandatory_disclaimer(
        self, mock_vectorstore, mock_db, mock_llm
    ):
        """Response always includes AI-generated disclaimer."""
        service = QAService(mock_vectorstore, mock_db, mock_llm)
        request = QARequest(question="How does X work?")

        response = await service.ask(request)

        assert response.disclaimer is not None
        assert len(response.disclaimer) > 0
        assert "ai" in response.disclaimer.lower() or "generated" in response.disclaimer.lower()


class TestQAServiceContextFiltering:
    """Tests for context-based filtering."""

    @pytest.mark.asyncio
    async def test_filters_by_page_context(
        self, mock_vectorstore, mock_db, mock_llm
    ):
        """Search can be filtered by current page context."""
        service = QAService(mock_vectorstore, mock_db, mock_llm)
        request = QARequest(
            question="What does this module do?",
            context={"page_type": "file", "slug": "src-main-py"},
        )

        await service.ask(request)

        # Vectorstore should be called with where filter
        call_args = mock_vectorstore.query.call_args
        # Context should influence the search
        assert call_args is not None


def test_qa_request_no_mode_or_context():
    """QARequest only has question field."""
    from oya.qa.schemas import QARequest
    request = QARequest(question="How does auth work?")
    assert request.question == "How does auth work?"
    # Verify mode and context don't exist
    assert not hasattr(request, 'mode')
    assert not hasattr(request, 'context')


def test_qa_response_has_confidence_and_search_quality():
    """QAResponse uses confidence instead of evidence_sufficient."""
    from oya.qa.schemas import QAResponse, ConfidenceLevel, SearchQuality, Citation
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
    assert not hasattr(response, 'evidence_sufficient')


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
    from oya.qa.schemas import Citation
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
