"""SSE streaming tests."""

import pytest
from httpx import ASGITransport, AsyncClient

from oya.main import app
from oya.api.deps import get_db


@pytest.fixture
def workspace_with_job(setup_active_repo):
    """Create workspace with database and running job using active repo fixture."""
    db = get_db()
    db.execute(
        """
        INSERT INTO generations (id, type, status, started_at)
        VALUES ('stream-job-123', 'full', 'completed', datetime('now'))
        """
    )
    db.commit()

    return setup_active_repo


@pytest.fixture
async def client():
    """Create async test client."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client


async def test_sse_stream_endpoint_exists(client, workspace_with_job):
    """GET /api/jobs/{job_id}/stream returns SSE response."""
    response = await client.get("/api/jobs/stream-job-123/stream")

    # For completed jobs, we get a final event immediately
    assert response.status_code == 200
    assert "text/event-stream" in response.headers.get("content-type", "")


async def test_sse_stream_completed_job_sends_complete_event(client, workspace_with_job):
    """Streaming completed job sends complete event."""
    response = await client.get("/api/jobs/stream-job-123/stream")

    assert response.status_code == 200
    content = response.text
    assert "event: complete" in content or "completed" in content


async def test_sse_stream_nonexistent_job_returns_404(client, workspace_with_job):
    """GET /api/jobs/{nonexistent}/stream returns 404."""
    response = await client.get("/api/jobs/nonexistent/stream")

    assert response.status_code == 404
