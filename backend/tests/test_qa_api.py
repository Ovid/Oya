"""Q&A API endpoint tests."""

import subprocess
import pytest
from unittest.mock import AsyncMock, MagicMock
from httpx import ASGITransport, AsyncClient

from oya.main import app
from oya.api.deps import get_settings, _reset_db_instance
from oya.api.routers.qa import get_qa_service
from oya.qa.service import QAService


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    """Create workspace with git repo."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    subprocess.run(["git", "init"], cwd=workspace, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=workspace, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=workspace, capture_output=True)

    (workspace / "README.md").write_text("# Test Repo")
    subprocess.run(["git", "add", "."], cwd=workspace, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=workspace, capture_output=True)

    monkeypatch.setenv("WORKSPACE_PATH", str(workspace))

    from oya.config import load_settings
    load_settings.cache_clear()
    get_settings.cache_clear()
    _reset_db_instance()

    yield workspace

    _reset_db_instance()


@pytest.fixture
def mock_qa_service():
    """Mock QAService for testing."""
    from oya.qa.schemas import QAResponse, Citation, ConfidenceLevel, SearchQuality

    mock_response = QAResponse(
        answer="The authentication system uses JWT tokens.",
        citations=[
            Citation(path="src/auth.py", title="auth.py", lines="10-20", url="/files/src_auth-py"),
            Citation(path="docs/auth.md", title="Authentication", lines=None, url="/files/docs_auth-md"),
        ],
        confidence=ConfidenceLevel.HIGH,
        disclaimer="Based on strong evidence from the codebase.",
        search_quality=SearchQuality(
            semantic_searched=True,
            fts_searched=True,
            results_found=5,
            results_used=3,
        ),
    )

    service = AsyncMock()
    service.ask.return_value = mock_response
    return service


class TestQAEndpoint:
    """Tests for POST /api/qa/ask endpoint."""

    @pytest.mark.asyncio
    async def test_ask_returns_answer(self, workspace, mock_qa_service):
        """POST /api/qa/ask returns answer with citations and confidence."""
        app.dependency_overrides[get_qa_service] = lambda: mock_qa_service
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.post(
                    "/api/qa/ask",
                    json={"question": "How does authentication work?"},
                )

            assert response.status_code == 200
            data = response.json()
            assert "answer" in data
            assert "citations" in data
            assert "confidence" in data
            assert data["confidence"] in ["high", "medium", "low"]
            assert "disclaimer" in data
            assert "search_quality" in data
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_ask_requires_question(self, workspace):
        """POST /api/qa/ask requires question field."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post("/api/qa/ask", json={})

        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_ask_low_confidence_response(self, workspace):
        """POST /api/qa/ask returns low confidence for poor search results."""
        from oya.qa.schemas import QAResponse, ConfidenceLevel, SearchQuality

        mock_service = AsyncMock()
        mock_service.ask.return_value = QAResponse(
            answer="I found limited information about this topic.",
            citations=[],
            confidence=ConfidenceLevel.LOW,
            disclaimer="Limited evidence found. This answer may be speculative.",
            search_quality=SearchQuality(
                semantic_searched=True,
                fts_searched=True,
                results_found=1,
                results_used=1,
            ),
        )

        app.dependency_overrides[get_qa_service] = lambda: mock_service
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.post(
                    "/api/qa/ask",
                    json={"question": "What is the meaning of life?"},
                )

            assert response.status_code == 200
            data = response.json()
            assert data["confidence"] == "low"
            assert "limited" in data["disclaimer"].lower() or "speculative" in data["disclaimer"].lower()
        finally:
            app.dependency_overrides.clear()


class TestQAServiceSearch:
    """Tests for QAService.search method."""

    @pytest.mark.asyncio
    async def test_search_uses_rrf_ranking(self):
        """Search results are ranked using RRF, not simple deduplication.

        With RRF, a result in BOTH lists should rank higher than one in only
        one list, even if the single-list result has a better individual score.
        """
        # Setup mocks
        mock_vectorstore = MagicMock()
        # Semantic: a.md at rank 0, c.md at rank 1 (b.md not in semantic)
        mock_vectorstore.query.return_value = {
            "ids": [["chunk_a", "chunk_c"]],
            "documents": [["Content A", "Content C"]],
            "metadatas": [[
                {"path": "a.md", "title": "A", "type": "file"},
                {"path": "c.md", "title": "C", "type": "file"},
            ]],
            "distances": [[0.1, 0.2]],
        }

        mock_db = MagicMock()
        # FTS: b.md at rank 0, a.md at rank 1 (c.md not in FTS)
        mock_db.execute.return_value.fetchall.return_value = [
            {"content": "Content B", "title": "B", "path": "b.md", "type": "file", "score": -10},
            {"content": "Content A", "title": "A", "path": "a.md", "type": "file", "score": -5},
        ]

        mock_llm = AsyncMock()

        service = QAService(vectorstore=mock_vectorstore, db=mock_db, llm=mock_llm)
        results, _, _ = await service.search("test query")

        # With RRF:
        # a.md: in both lists (semantic rank 0, FTS rank 1) = high RRF score
        # b.md: only in FTS (rank 0) = medium RRF score
        # c.md: only in semantic (rank 1) = medium RRF score
        #
        # a.md should be ranked highest because it appears in BOTH lists.
        # This is the key property of RRF that distinguishes it from simple dedup.
        # Note: IDs are normalized to paths for cross-source matching
        assert results[0]["path"] == "a.md", (
            f"Expected a.md (in both lists) to rank first, but got {results[0]['path']}"
        )
