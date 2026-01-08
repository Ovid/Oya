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
    from oya.qa.schemas import QAResponse, Citation

    mock_response = QAResponse(
        answer="The authentication system uses JWT tokens.",
        citations=[
            Citation(path="src/auth.py", title="auth.py", lines="10-20"),
            Citation(path="docs/auth.md", title="Authentication", lines=None),
        ],
        evidence_sufficient=True,
        disclaimer="AI-generated; may contain errors.",
    )

    service = AsyncMock()
    service.ask.return_value = mock_response
    return service


class TestQAEndpoint:
    """Tests for POST /api/qa/ask endpoint."""

    @pytest.mark.asyncio
    async def test_ask_returns_answer(self, workspace, mock_qa_service):
        """POST /api/qa/ask returns answer with citations."""
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
            assert "evidence_sufficient" in data
            assert "disclaimer" in data
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
    async def test_ask_with_gated_mode(self, workspace, mock_qa_service):
        """POST /api/qa/ask supports gated mode."""
        app.dependency_overrides[get_qa_service] = lambda: mock_qa_service
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.post(
                    "/api/qa/ask",
                    json={
                        "question": "How does auth work?",
                        "mode": "gated",
                    },
                )

            assert response.status_code == 200
            mock_qa_service.ask.assert_called_once()
            call_args = mock_qa_service.ask.call_args[0][0]
            assert call_args.mode.value == "gated"
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_ask_with_loose_mode(self, workspace, mock_qa_service):
        """POST /api/qa/ask supports loose mode."""
        app.dependency_overrides[get_qa_service] = lambda: mock_qa_service
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.post(
                    "/api/qa/ask",
                    json={
                        "question": "How does auth work?",
                        "mode": "loose",
                    },
                )

            assert response.status_code == 200
            call_args = mock_qa_service.ask.call_args[0][0]
            assert call_args.mode.value == "loose"
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_ask_with_context(self, workspace, mock_qa_service):
        """POST /api/qa/ask supports page context."""
        app.dependency_overrides[get_qa_service] = lambda: mock_qa_service
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.post(
                    "/api/qa/ask",
                    json={
                        "question": "What does this function do?",
                        "context": {"page_type": "file", "slug": "src-main-py"},
                    },
                )

            assert response.status_code == 200
            call_args = mock_qa_service.ask.call_args[0][0]
            assert call_args.context is not None
            assert call_args.context["page_type"] == "file"
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_ask_insufficient_evidence_response(self, workspace):
        """POST /api/qa/ask returns proper response for insufficient evidence."""
        from oya.qa.schemas import QAResponse

        mock_service = AsyncMock()
        mock_service.ask.return_value = QAResponse(
            answer="",
            citations=[],
            evidence_sufficient=False,
            disclaimer="Unable to answer: insufficient evidence in the codebase.",
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
            assert data["evidence_sufficient"] is False
            assert data["answer"] == ""
            assert "insufficient" in data["disclaimer"].lower()
        finally:
            app.dependency_overrides.clear()
