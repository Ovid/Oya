"""Tests for the repos v2 API endpoints (multi-repo management)."""

import subprocess
from pathlib import Path

import pytest
from httpx import AsyncClient, ASGITransport

from oya.main import app
from oya.db.repo_registry import RepoRegistry
from oya.config import load_settings
from oya.api.deps import get_settings, _reset_db_instance


def _clear_active_repo(oya_dir):
    """Helper to clear the active repo setting from the registry."""
    registry = RepoRegistry(oya_dir / "repos.db")
    try:
        registry.delete_setting("active_repo_id")
    finally:
        registry.close()


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    """Set up OYA_DATA_DIR for tests."""
    oya_dir = tmp_path / ".oya"
    oya_dir.mkdir()
    monkeypatch.setenv("OYA_DATA_DIR", str(oya_dir))

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


@pytest.fixture
def source_repo(tmp_path):
    """Create a test git repository to clone from."""
    repo_dir = tmp_path / "source-repo"
    repo_dir.mkdir()
    subprocess.run(["git", "init"], cwd=repo_dir, capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=repo_dir,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=repo_dir,
        capture_output=True,
        check=True,
    )
    # Create a file and commit
    (repo_dir / "README.md").write_text("# Test Repo")
    subprocess.run(["git", "add", "."], cwd=repo_dir, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=repo_dir,
        capture_output=True,
        check=True,
    )
    return repo_dir


@pytest.mark.asyncio
async def test_create_repo_from_local_path(data_dir, source_repo):
    """POST /api/v2/repos with local path creates and clones repo."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v2/repos",
            json={"url": str(source_repo), "display_name": "My Test Repo"},
        )

    assert response.status_code == 201
    data = response.json()
    assert data["id"] is not None
    assert data["origin_url"] == str(source_repo)
    assert data["source_type"] == "local"
    assert data["display_name"] == "My Test Repo"
    assert data["status"] == "ready"
    # Verify the repo was actually cloned
    cloned_path = Path(data["local_path"])
    assert cloned_path.exists()
    assert (cloned_path / ".git").exists()
    assert (cloned_path / "README.md").exists()


@pytest.mark.asyncio
async def test_create_repo_duplicate_error(data_dir, source_repo):
    """Adding same repo twice returns 409 Conflict."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # First creation should succeed
        response1 = await client.post(
            "/api/v2/repos",
            json={"url": str(source_repo), "display_name": "First Add"},
        )
        assert response1.status_code == 201

        # Second creation with same URL should fail
        response2 = await client.post(
            "/api/v2/repos",
            json={"url": str(source_repo), "display_name": "Second Add"},
        )
        assert response2.status_code == 409
        assert "already exists" in response2.json()["detail"].lower()


@pytest.mark.asyncio
async def test_get_repo_by_id(data_dir, source_repo):
    """GET /api/v2/repos/{repo_id} returns the repo."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Create a repo first
        create_response = await client.post(
            "/api/v2/repos",
            json={"url": str(source_repo), "display_name": "Get Test Repo"},
        )
        assert create_response.status_code == 201
        repo_id = create_response.json()["id"]

        # Now get the repo by ID
        response = await client.get(f"/api/v2/repos/{repo_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == repo_id
    assert data["display_name"] == "Get Test Repo"
    assert data["origin_url"] == str(source_repo)
    assert data["status"] == "ready"


@pytest.mark.asyncio
async def test_get_repo_not_found(data_dir):
    """GET /api/v2/repos/{repo_id} returns 404 for non-existent repo."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v2/repos/999")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_delete_repo(data_dir, source_repo):
    """DELETE /api/v2/repos/{repo_id} deletes the repo and its files."""
    from pathlib import Path

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Create a repo first
        create_response = await client.post(
            "/api/v2/repos",
            json={"url": str(source_repo), "display_name": "Delete Test Repo"},
        )
        assert create_response.status_code == 201
        repo_id = create_response.json()["id"]
        local_path = create_response.json()["local_path"]

        # Verify files exist
        assert Path(local_path).exists()

        # Delete the repo
        delete_response = await client.delete(f"/api/v2/repos/{repo_id}")
        assert delete_response.status_code == 204

        # Verify repo is gone from registry
        get_response = await client.get(f"/api/v2/repos/{repo_id}")
        assert get_response.status_code == 404

        # Verify files are deleted
        assert not Path(local_path).exists()


@pytest.mark.asyncio
async def test_delete_repo_not_found(data_dir):
    """DELETE /api/v2/repos/{repo_id} returns 404 for non-existent repo."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.delete("/api/v2/repos/999")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_repo_generating_conflict(data_dir):
    """DELETE /api/v2/repos/{repo_id} returns 409 if repo is generating."""
    # Add a repo directly to registry with 'generating' status
    registry = RepoRegistry(data_dir / "repos.db")
    repo_id = registry.add("https://github.com/x/y", "github", "github.com/x/y", "Generating Repo")
    registry.update(repo_id, status="generating")
    registry.close()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.delete(f"/api/v2/repos/{repo_id}")

    assert response.status_code == 409
    assert "generating" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_delete_active_repo_clears_active_selection(data_dir, source_repo):
    """DELETE /api/v2/repos/{repo_id} clears active selection if deleting active repo."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Create and activate a repo
        create_response = await client.post(
            "/api/v2/repos",
            json={"url": str(source_repo), "display_name": "Delete Active Test"},
        )
        assert create_response.status_code == 201
        repo_id = create_response.json()["id"]

        await client.post(f"/api/v2/repos/{repo_id}/activate")

        # Verify it's active
        active_response = await client.get("/api/v2/repos/active")
        assert active_response.json()["active_repo"]["id"] == repo_id

        # Delete the active repo
        delete_response = await client.delete(f"/api/v2/repos/{repo_id}")
        assert delete_response.status_code == 204

        # Verify active selection is cleared
        active_response = await client.get("/api/v2/repos/active")
        assert active_response.json()["active_repo"] is None

    # Also verify it's cleared in the database
    registry = RepoRegistry(data_dir / "repos.db")
    try:
        stored_id = registry.get_setting("active_repo_id")
        assert stored_id is None
    finally:
        registry.close()


@pytest.mark.asyncio
async def test_activate_repo(data_dir, source_repo):
    """POST /api/v2/repos/{repo_id}/activate sets the active repo."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Create a repo first
        create_response = await client.post(
            "/api/v2/repos",
            json={"url": str(source_repo), "display_name": "Activate Test Repo"},
        )
        assert create_response.status_code == 201
        repo_id = create_response.json()["id"]

        # Activate the repo
        activate_response = await client.post(f"/api/v2/repos/{repo_id}/activate")

    assert activate_response.status_code == 200
    data = activate_response.json()
    assert data["active_repo_id"] == repo_id

    # Verify active repo was persisted to database
    registry = RepoRegistry(data_dir / "repos.db")
    try:
        stored_id = registry.get_setting("active_repo_id")
        assert stored_id == str(repo_id)
    finally:
        registry.close()


@pytest.mark.asyncio
async def test_activate_repo_not_found(data_dir):
    """POST /api/v2/repos/{repo_id}/activate returns 404 for non-existent repo."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v2/repos/999/activate")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_get_active_repo_none(data_dir):
    """GET /api/v2/repos/active returns None when no repo is active."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v2/repos/active")

    assert response.status_code == 200
    data = response.json()
    assert data["active_repo"] is None


@pytest.mark.asyncio
async def test_activate_switches_active_repo(data_dir, source_repo, tmp_path):
    """Activating a different repo switches the active repo."""
    # Create a second source repo
    second_repo = tmp_path / "second-repo"
    second_repo.mkdir()
    subprocess.run(["git", "init"], cwd=second_repo, capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=second_repo,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=second_repo,
        capture_output=True,
        check=True,
    )
    (second_repo / "README.md").write_text("# Second Repo")
    subprocess.run(["git", "add", "."], cwd=second_repo, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=second_repo,
        capture_output=True,
        check=True,
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Create first repo and activate it
        resp1 = await client.post(
            "/api/v2/repos",
            json={"url": str(source_repo), "display_name": "First Repo"},
        )
        repo1_id = resp1.json()["id"]
        await client.post(f"/api/v2/repos/{repo1_id}/activate")

        # Create second repo and activate it
        resp2 = await client.post(
            "/api/v2/repos",
            json={"url": str(second_repo), "display_name": "Second Repo"},
        )
        repo2_id = resp2.json()["id"]
        await client.post(f"/api/v2/repos/{repo2_id}/activate")

        # Verify active repo switched to second
        active_resp = await client.get("/api/v2/repos/active")

    assert active_resp.status_code == 200
    assert active_resp.json()["active_repo"]["id"] == repo2_id
    assert active_resp.json()["active_repo"]["display_name"] == "Second Repo"


@pytest.mark.asyncio
async def test_get_active_repo(data_dir, source_repo):
    """GET /api/v2/repos/active returns the active repo after activation."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Create a repo
        create_response = await client.post(
            "/api/v2/repos",
            json={"url": str(source_repo), "display_name": "Active Repo Test"},
        )
        assert create_response.status_code == 201
        repo_id = create_response.json()["id"]

        # Activate it
        activate_response = await client.post(f"/api/v2/repos/{repo_id}/activate")
        assert activate_response.status_code == 200

        # Get active repo
        response = await client.get("/api/v2/repos/active")

    assert response.status_code == 200
    data = response.json()
    assert data["active_repo"] is not None
    assert data["active_repo"]["id"] == repo_id
    assert data["active_repo"]["display_name"] == "Active Repo Test"


class TestActiveRepoPersistence:
    """Tests for active repo persistence across restarts."""

    @pytest.mark.asyncio
    async def test_activate_repo_persists_to_db(self, data_dir, source_repo):
        """Activating a repo persists the ID to the database."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Create a repo first
            create_response = await client.post(
                "/api/v2/repos",
                json={"url": str(source_repo), "display_name": "Persist Test Repo"},
            )
            assert create_response.status_code == 201
            repo_id = create_response.json()["id"]

            # Activate the repo
            response = await client.post(f"/api/v2/repos/{repo_id}/activate")
            assert response.status_code == 200

        # Verify it's persisted by checking the registry directly
        registry = RepoRegistry(data_dir / "repos.db")
        try:
            stored_id = registry.get_setting("active_repo_id")
            assert stored_id == str(repo_id)
        finally:
            registry.close()

    @pytest.mark.asyncio
    async def test_get_active_repo_reads_from_db(self, data_dir, source_repo):
        """Getting active repo reads from database, not just memory."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Create a repo first
            create_response = await client.post(
                "/api/v2/repos",
                json={"url": str(source_repo), "display_name": "DB Read Test Repo"},
            )
            assert create_response.status_code == 201
            repo_id = create_response.json()["id"]

        # Set the active repo directly in database (simulating restart)
        registry = RepoRegistry(data_dir / "repos.db")
        try:
            registry.set_setting("active_repo_id", str(repo_id))
        finally:
            registry.close()

        # Get active repo through API - should read from DB
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v2/repos/active")
            assert response.status_code == 200
            data = response.json()
            assert data["active_repo"] is not None
            assert data["active_repo"]["id"] == repo_id

    @pytest.mark.asyncio
    async def test_get_active_repo_clears_invalid_id(self, data_dir):
        """Getting active repo clears persisted ID if repo was deleted."""
        # Set a nonexistent repo ID directly in database
        registry = RepoRegistry(data_dir / "repos.db")
        try:
            registry.set_setting("active_repo_id", "99999")
        finally:
            registry.close()

        # Get active repo should return None and clear the invalid ID
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v2/repos/active")
            assert response.status_code == 200
            data = response.json()
            assert data["active_repo"] is None

        # Verify the setting was cleared
        registry = RepoRegistry(data_dir / "repos.db")
        try:
            stored_id = registry.get_setting("active_repo_id")
            assert stored_id is None
        finally:
            registry.close()
