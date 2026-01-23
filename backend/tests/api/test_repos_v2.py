"""Tests for the repos v2 API endpoints (multi-repo management)."""

import pytest
from httpx import AsyncClient, ASGITransport

from oya.main import app
from oya.db.repo_registry import RepoRegistry
from oya.config import load_settings
from oya.api.deps import get_settings, _reset_db_instance


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    """Set up OYA_DATA_DIR for tests."""
    oya_dir = tmp_path / ".oya"
    oya_dir.mkdir()
    monkeypatch.setenv("OYA_DATA_DIR", str(oya_dir))
    # Still need WORKSPACE_PATH for load_settings to work
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.setenv("WORKSPACE_PATH", str(workspace))

    # Clear caches
    load_settings.cache_clear()
    get_settings.cache_clear()
    _reset_db_instance()

    yield oya_dir

    _reset_db_instance()


@pytest.mark.asyncio
async def test_list_repos_empty(data_dir):
    """List repos returns empty list when no repos exist."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v2/repos")

    assert response.status_code == 200
    data = response.json()
    assert data["repos"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_list_repos_with_repos(data_dir):
    """List repos returns all repos."""
    # Add some repos directly to the registry
    registry = RepoRegistry(data_dir / "repos.db")
    registry.add("https://github.com/a/b", "github", "github.com/a/b", "Repo A")
    registry.add("https://github.com/c/d", "github", "github.com/c/d", "Repo B")
    registry.close()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v2/repos")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["repos"]) == 2
    assert data["repos"][0]["display_name"] == "Repo A"
