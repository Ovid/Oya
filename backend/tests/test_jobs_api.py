"""Job management API tests."""

import subprocess
import pytest
from httpx import ASGITransport, AsyncClient

from oya.main import app
from oya.api.deps import get_settings, _reset_db_instance, get_db


@pytest.fixture
def workspace_with_db(tmp_path, monkeypatch):
    """Create workspace with database and job."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    subprocess.run(["git", "init"], cwd=workspace, capture_output=True)

    monkeypatch.setenv("WORKSPACE_PATH", str(workspace))

    from oya.config import load_settings
    load_settings.cache_clear()
    get_settings.cache_clear()
    _reset_db_instance()

    # Initialize database with a test job
    db = get_db()
    db.execute(
        """
        INSERT INTO generations (id, type, status, started_at, current_phase, total_phases)
        VALUES ('test-job-123', 'full', 'running', datetime('now'), 'analysis', 6)
        """
    )
    db.commit()

    yield workspace

    _reset_db_instance()


@pytest.fixture
async def client():
    """Create async test client."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client


async def test_get_job_status(client, workspace_with_db):
    """GET /api/jobs/{job_id} returns job status."""
    response = await client.get("/api/jobs/test-job-123")

    assert response.status_code == 200
    data = response.json()
    assert data["job_id"] == "test-job-123"
    assert data["status"] == "running"
    assert data["current_phase"] == "analysis"


async def test_get_nonexistent_job_returns_404(client, workspace_with_db):
    """GET /api/jobs/{nonexistent} returns 404."""
    response = await client.get("/api/jobs/nonexistent-job")

    assert response.status_code == 404


async def test_list_jobs(client, workspace_with_db):
    """GET /api/jobs returns list of jobs."""
    response = await client.get("/api/jobs")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert data[0]["job_id"] == "test-job-123"
