"""Tests for the logs API endpoints."""

from pathlib import Path

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

    load_settings.cache_clear()
    get_settings.cache_clear()
    _reset_db_instance()

    yield oya_dir

    _reset_db_instance()


def _create_repo_with_logs(data_dir: Path, log_content: str) -> int:
    """Helper to create a repo and populate its logs."""
    registry = RepoRegistry(data_dir / "repos.db")
    repo_id = registry.add(
        "https://github.com/test/repo", "github", "github.com/test/repo", "Test Repo"
    )
    registry.set_setting("active_repo_id", str(repo_id))
    registry.close()

    # Create the log directory and file
    log_dir = data_dir / "wikis" / "github.com" / "test" / "repo" / "meta" / ".oya-logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    (log_dir / "llm-queries.jsonl").write_text(log_content)

    return repo_id


def _create_repo_without_logs(data_dir: Path) -> int:
    """Helper to create a repo without logs."""
    registry = RepoRegistry(data_dir / "repos.db")
    repo_id = registry.add(
        "https://github.com/test/repo", "github", "github.com/test/repo", "Test Repo"
    )
    registry.set_setting("active_repo_id", str(repo_id))
    registry.close()

    # Create the meta directory structure but no log file
    meta_dir = data_dir / "wikis" / "github.com" / "test" / "repo" / "meta"
    meta_dir.mkdir(parents=True, exist_ok=True)

    return repo_id


@pytest.mark.asyncio
async def test_get_logs_returns_content(data_dir):
    """GET /api/v2/repos/{repo_id}/logs/llm-queries returns log content."""
    log_content = '{"timestamp": "2024-01-01", "model": "gpt-4"}\n{"timestamp": "2024-01-02", "model": "gpt-4"}\n'
    repo_id = _create_repo_with_logs(data_dir, log_content)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/api/v2/repos/{repo_id}/logs/llm-queries")

    assert response.status_code == 200
    data = response.json()
    assert data["content"] == log_content
    assert data["entry_count"] == 2


@pytest.mark.asyncio
async def test_get_logs_not_found_when_no_file(data_dir):
    """GET /api/v2/repos/{repo_id}/logs/llm-queries returns 404 when no log file exists."""
    repo_id = _create_repo_without_logs(data_dir)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/api/v2/repos/{repo_id}/logs/llm-queries")

    assert response.status_code == 404
    assert "no logs" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_get_logs_repo_not_found(data_dir):
    """GET /api/v2/repos/{repo_id}/logs/llm-queries returns 404 for non-existent repo."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v2/repos/999/logs/llm-queries")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_delete_logs_removes_file(data_dir):
    """DELETE /api/v2/repos/{repo_id}/logs/llm-queries removes the log file."""
    log_content = '{"timestamp": "2024-01-01"}\n'
    repo_id = _create_repo_with_logs(data_dir, log_content)
    log_path = (
        data_dir
        / "wikis"
        / "github.com"
        / "test"
        / "repo"
        / "meta"
        / ".oya-logs"
        / "llm-queries.jsonl"
    )

    assert log_path.exists()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.delete(f"/api/v2/repos/{repo_id}/logs/llm-queries")

    assert response.status_code == 200
    assert "deleted" in response.json()["message"].lower()
    assert not log_path.exists()


@pytest.mark.asyncio
async def test_delete_logs_not_found_when_no_file(data_dir):
    """DELETE /api/v2/repos/{repo_id}/logs/llm-queries returns 404 when no log file exists."""
    repo_id = _create_repo_without_logs(data_dir)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.delete(f"/api/v2/repos/{repo_id}/logs/llm-queries")

    assert response.status_code == 404
    assert "no logs" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_delete_logs_repo_not_found(data_dir):
    """DELETE /api/v2/repos/{repo_id}/logs/llm-queries returns 404 for non-existent repo."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.delete("/api/v2/repos/999/logs/llm-queries")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()
