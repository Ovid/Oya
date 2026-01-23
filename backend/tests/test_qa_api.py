"""Q&A API endpoint tests."""

import subprocess
import pytest
from unittest.mock import AsyncMock, MagicMock
from httpx import ASGITransport, AsyncClient

from oya.main import app
from oya.api.deps import get_settings, _reset_db_instance
from oya.api.routers.qa import get_qa_service
from oya.qa.service import QAService
import oya.qa.service as service_module


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    """Create workspace with git repo."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    subprocess.run(["git", "init"], cwd=workspace, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"], cwd=workspace, capture_output=True
    )
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
            Citation(
                path="docs/auth.md", title="Authentication", lines=None, url="/files/docs_auth-md"
            ),
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

    async def mock_stream(request):
        """Mock streaming response."""
        yield 'data: {"type": "status", "message": "Searching"}\n\n'
        yield 'data: {"type": "answer_chunk", "content": "Test answer"}\n\n'
        yield 'data: {"type": "done"}\n\n'

    service = AsyncMock()
    service.ask.return_value = mock_response
    service.ask_stream = mock_stream
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
            assert (
                "limited" in data["disclaimer"].lower()
                or "speculative" in data["disclaimer"].lower()
            )
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
            "metadatas": [
                [
                    {"path": "a.md", "title": "A", "type": "file"},
                    {"path": "c.md", "title": "C", "type": "file"},
                ]
            ],
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


@pytest.mark.asyncio
async def test_ask_stream_returns_sse(workspace, mock_qa_service):
    """Streaming endpoint returns SSE content type."""
    app.dependency_overrides[get_qa_service] = lambda: mock_qa_service
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/qa/ask/stream",
                json={"question": "test"},
            )
            assert response.headers["content-type"].startswith("text/event-stream")
    finally:
        app.dependency_overrides.clear()


class TestQARequestSchema:
    """Tests for QARequest schema validation."""

    def test_qa_request_has_quick_mode_field(self):
        """QARequest schema has quick_mode field with correct default."""
        from oya.qa.schemas import QARequest

        # Field should exist and have default value
        request = QARequest(question="test")
        assert hasattr(request, "quick_mode")
        assert request.quick_mode is False  # default

        # Field should accept True
        request = QARequest(question="test", quick_mode=True)
        assert request.quick_mode is True

    def test_qa_request_has_temperature_field(self):
        """QARequest schema has temperature field with validation."""
        from oya.qa.schemas import QARequest
        from pydantic import ValidationError

        # Field should exist and have None default
        request = QARequest(question="test")
        assert hasattr(request, "temperature")
        assert request.temperature is None

        # Field should accept valid values
        request = QARequest(question="test", temperature=0.5)
        assert request.temperature == 0.5

        # Field should reject invalid values
        with pytest.raises(ValidationError):
            QARequest(question="test", temperature=1.5)  # > 1.0

        with pytest.raises(ValidationError):
            QARequest(question="test", temperature=-0.1)  # < 0.0

    @pytest.mark.asyncio
    async def test_ask_accepts_quick_mode_and_temperature(self, workspace, mock_qa_service):
        """QARequest accepts quick_mode and temperature parameters via API."""
        app.dependency_overrides[get_qa_service] = lambda: mock_qa_service
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.post(
                    "/api/qa/ask",
                    json={
                        "question": "What is this?",
                        "quick_mode": True,
                        "temperature": 0.3,
                    },
                )
            # Should not fail with validation error
            assert response.status_code in (200, 500)  # 500 if no wiki, but not 422
        finally:
            app.dependency_overrides.clear()


class TestCGRAGStreamingBatching:
    """Tests for CGRAG streaming - answer delivered in done event (no token streaming)."""

    @pytest.mark.asyncio
    async def test_cgrag_no_token_events(self):
        """CGRAG mode does not emit token events - answer is in done event."""
        import json
        from oya.qa.schemas import QARequest
        from oya.qa.cgrag import CGRAGResult

        # Create a long answer with many words
        long_answer = " ".join([f"word{i}" for i in range(100)])  # 100 words

        # Mock dependencies
        vectorstore = MagicMock()
        vectorstore.query.return_value = {"ids": [[]], "documents": [[]], "metadatas": [[]]}

        db = MagicMock()
        db.execute.return_value.fetchall.return_value = []

        llm = AsyncMock()

        # Create service
        service = QAService(vectorstore=vectorstore, db=db, llm=llm)

        # Mock run_cgrag_loop to return our long answer
        original_run_cgrag_loop = service_module.run_cgrag_loop

        async def mock_cgrag_loop(*args, **kwargs):
            return CGRAGResult(answer=long_answer, passes_used=1)

        service_module.run_cgrag_loop = mock_cgrag_loop

        try:
            # Collect all streamed events
            request = QARequest(question="test", quick_mode=False)
            events = []
            async for event in service.ask_stream(request):
                events.append(event)

            # No token events should be emitted
            token_events = [e for e in events if e.startswith("event: token")]
            assert len(token_events) == 0, (
                f"Expected no token events, got {len(token_events)}. "
                "Answer should be delivered in done event, not streamed."
            )

            # Verify done event contains the full answer
            done_events = [e for e in events if e.startswith("event: done")]
            assert len(done_events) == 1, "Expected exactly one 'done' event"

            # Parse done event and verify answer
            done_event = done_events[0]
            for line in done_event.strip().split("\n"):
                if line.startswith("data: "):
                    data = json.loads(line[6:])
                    assert "answer" in data, "Done event must contain 'answer' field"
                    assert data["answer"] == long_answer, (
                        f"Answer in done event doesn't match. "
                        f"Expected {len(long_answer)} chars, got {len(data['answer'])} chars"
                    )
        finally:
            service_module.run_cgrag_loop = original_run_cgrag_loop

    @pytest.mark.asyncio
    async def test_cgrag_preserves_long_response_in_done_event(self):
        """CGRAG preserves the entire response in the done event without truncation."""
        import json
        from oya.qa.schemas import QARequest
        from oya.qa.cgrag import CGRAGResult

        # Create a very long answer (simulating the truncation bug scenario)
        # ~800 words like the real architectural flaws response
        paragraphs = []
        for i in range(5):
            paragraph = f"{i + 1}) Point number {i + 1}: " + " ".join(
                [f"explanation{j}" for j in range(150)]
            )
            paragraphs.append(paragraph)
        long_answer = "\n\n".join(paragraphs)

        # Mock dependencies
        vectorstore = MagicMock()
        vectorstore.query.return_value = {"ids": [[]], "documents": [[]], "metadatas": [[]]}

        db = MagicMock()
        db.execute.return_value.fetchall.return_value = []

        llm = AsyncMock()

        service = QAService(vectorstore=vectorstore, db=db, llm=llm)

        original_run_cgrag_loop = service_module.run_cgrag_loop

        async def mock_cgrag_loop(*args, **kwargs):
            return CGRAGResult(answer=long_answer, passes_used=1)

        service_module.run_cgrag_loop = mock_cgrag_loop

        try:
            request = QARequest(question="test", quick_mode=False)
            events = []
            async for event in service.ask_stream(request):
                events.append(event)

            # Extract answer from done event
            done_events = [e for e in events if e.startswith("event: done")]
            assert len(done_events) == 1, "Expected exactly one 'done' event"

            answer_from_done = None
            for line in done_events[0].strip().split("\n"):
                if line.startswith("data: "):
                    data = json.loads(line[6:])
                    answer_from_done = data.get("answer")

            # The full answer must be preserved exactly
            assert answer_from_done == long_answer, (
                f"Response truncated! Expected {len(long_answer)} chars, "
                f"got {len(answer_from_done) if answer_from_done else 0} chars. "
            )
        finally:
            service_module.run_cgrag_loop = original_run_cgrag_loop

    @pytest.mark.asyncio
    async def test_cgrag_done_event_structure(self):
        """The 'done' event has proper structure with answer field."""
        import json
        from oya.qa.schemas import QARequest
        from oya.qa.cgrag import CGRAGResult

        answer = "This is a test answer with multiple words."

        vectorstore = MagicMock()
        vectorstore.query.return_value = {"ids": [[]], "documents": [[]], "metadatas": [[]]}

        db = MagicMock()
        db.execute.return_value.fetchall.return_value = []

        llm = AsyncMock()

        service = QAService(vectorstore=vectorstore, db=db, llm=llm)

        original_run_cgrag_loop = service_module.run_cgrag_loop

        async def mock_cgrag_loop(*args, **kwargs):
            return CGRAGResult(answer=answer, passes_used=1)

        service_module.run_cgrag_loop = mock_cgrag_loop

        try:
            request = QARequest(question="test", quick_mode=False)
            events = []
            async for event in service.ask_stream(request):
                events.append(event)

            # Extract event types
            event_types = []
            for event in events:
                if event.startswith("event: "):
                    event_type = event.split("\n")[0].replace("event: ", "")
                    event_types.append(event_type)

            # Verify no token events
            assert "token" not in event_types, "No token events should be emitted"

            # Verify done event is present and has required fields
            assert "done" in event_types, "Done event must be present"

            done_events = [e for e in events if e.startswith("event: done")]
            for line in done_events[0].strip().split("\n"):
                if line.startswith("data: "):
                    data = json.loads(line[6:])
                    assert "answer" in data, "Done event must contain 'answer' field"
                    assert "citations" in data, "Done event must contain 'citations' field"
                    assert "confidence" in data, "Done event must contain 'confidence' field"
                    assert data["answer"] == answer, "Answer must match expected value"
        finally:
            service_module.run_cgrag_loop = original_run_cgrag_loop
