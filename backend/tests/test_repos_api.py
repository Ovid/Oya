"""Repository management API tests."""

import subprocess
import pytest
from httpx import ASGITransport, AsyncClient

from oya.main import app
from oya.api.deps import get_settings, _reset_db_instance


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    """Create workspace with git repo."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    subprocess.run(["git", "init"], cwd=workspace, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=workspace, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=workspace, capture_output=True)

    # Create a file and commit
    (workspace / "README.md").write_text("# Test Repo")
    subprocess.run(["git", "add", "."], cwd=workspace, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=workspace, capture_output=True)

    monkeypatch.setenv("WORKSPACE_PATH", str(workspace))

    # Clear caches
    from oya.config import load_settings
    load_settings.cache_clear()
    get_settings.cache_clear()
    _reset_db_instance()

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


async def test_get_repo_status_returns_info(client, workspace):
    """GET /api/repos/status returns repository info."""
    response = await client.get("/api/repos/status")

    assert response.status_code == 200
    data = response.json()
    assert "path" in data
    assert "head_commit" in data
    assert "initialized" in data
    assert data["initialized"] is True


async def test_post_repos_init_starts_generation(client, workspace):
    """POST /api/repos/init starts wiki generation job."""
    response = await client.post("/api/repos/init")

    assert response.status_code == 202
    data = response.json()
    assert "job_id" in data
    assert data["job_id"] is not None


async def test_get_repo_status_not_initialized(client, tmp_path, monkeypatch):
    """GET /api/repos/status returns not initialized for non-git dir."""
    non_git = tmp_path / "non_git"
    non_git.mkdir()
    monkeypatch.setenv("WORKSPACE_PATH", str(non_git))

    from oya.config import load_settings
    load_settings.cache_clear()
    get_settings.cache_clear()
    _reset_db_instance()

    response = await client.get("/api/repos/status")

    assert response.status_code == 200
    data = response.json()
    assert data["initialized"] is False
