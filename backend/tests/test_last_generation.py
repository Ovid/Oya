"""Tests for last_generation field in RepoStatus."""

import subprocess
import pytest
from httpx import ASGITransport, AsyncClient

from oya.main import app
from oya.api.deps import get_db, get_settings, _reset_db_instance
from oya.config import load_settings


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
    load_settings.cache_clear()
    get_settings.cache_clear()
    _reset_db_instance()

    yield workspace

    _reset_db_instance()
    load_settings.cache_clear()
    get_settings.cache_clear()


@pytest.fixture
async def client():
    """Create async test client."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client


class TestLastGenerationInRepoStatus:
    """Test that RepoStatus includes last_generation datetime."""

    async def test_repo_status_includes_last_generation_when_completed(
        self, client, workspace
    ) -> None:
        """RepoStatus should include last_generation from most recent completed generation."""
        # Get database and insert a completed generation
        db = get_db()
        db.execute(
            """
            INSERT INTO generations (id, type, status, started_at, completed_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("test-job-1", "full", "completed", "2026-01-10T10:00:00", "2026-01-10T10:30:00"),
        )
        db.commit()

        # Make request to get repo status
        response = await client.get("/api/repos/status")

        assert response.status_code == 200
        data = response.json()

        # Should have last_generation field with the completed_at time
        assert "last_generation" in data
        assert data["last_generation"] is not None
        assert "2026-01-10" in data["last_generation"]

    async def test_repo_status_last_generation_is_null_when_no_completed_jobs(
        self, client, workspace
    ) -> None:
        """RepoStatus should have null last_generation when no completed generations exist."""
        # Make request to get repo status (no generations inserted)
        response = await client.get("/api/repos/status")

        assert response.status_code == 200
        data = response.json()

        # Should have last_generation field but it should be null
        assert "last_generation" in data
        assert data["last_generation"] is None

    async def test_repo_status_uses_most_recent_completed_generation(
        self, client, workspace
    ) -> None:
        """RepoStatus should use the most recent completed generation, not failed or pending."""
        # Get database and insert multiple generations
        db = get_db()
        # Older completed generation
        db.execute(
            """
            INSERT INTO generations (id, type, status, started_at, completed_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("job-1", "full", "completed", "2026-01-09T10:00:00", "2026-01-09T10:30:00"),
        )
        # Newer completed generation (should be returned)
        db.execute(
            """
            INSERT INTO generations (id, type, status, started_at, completed_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("job-2", "full", "completed", "2026-01-10T14:00:00", "2026-01-10T14:45:00"),
        )
        # Failed generation (should be ignored)
        db.execute(
            """
            INSERT INTO generations (id, type, status, started_at, completed_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("job-3", "full", "failed", "2026-01-10T16:00:00", "2026-01-10T16:05:00"),
        )
        # Pending generation (should be ignored)
        db.execute(
            """
            INSERT INTO generations (id, type, status, started_at)
            VALUES (?, ?, ?, ?)
            """,
            ("job-4", "full", "pending", "2026-01-10T17:00:00"),
        )
        db.commit()

        # Make request to get repo status
        response = await client.get("/api/repos/status")

        assert response.status_code == 200
        data = response.json()

        # Should have the most recent completed generation (job-2)
        assert data["last_generation"] is not None
        assert "2026-01-10T14:45:00" in data["last_generation"]
