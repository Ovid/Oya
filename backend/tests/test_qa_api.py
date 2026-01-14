"""Q&A API endpoint tests."""

import subprocess
import pytest
from unittest.mock import AsyncMock
from httpx import ASGITransport, AsyncClient

from oya.main import app
from oya.api.deps import get_settings, _reset_db_instance
from oya.api.routers.qa import get_qa_service


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
