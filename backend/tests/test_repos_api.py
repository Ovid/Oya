"""Repository management API tests."""

import subprocess
import pytest
from httpx import ASGITransport, AsyncClient

from oya.main import app
from oya.api.deps import get_settings, _reset_db_instance, _reset_vectorstore_instance


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


# ============================================================================
# Workspace Switch Endpoint Tests (Task 6.1)
# Requirements: 4.6, 4.7, 4.11
# ============================================================================


@pytest.fixture
def workspace_base(tmp_path, monkeypatch):
    """Create a base directory with multiple workspaces for testing."""
    base = tmp_path / "base"
    base.mkdir()
    
    # Create first workspace with git repo
    workspace1 = base / "workspace1"
    workspace1.mkdir()
    subprocess.run(["git", "init"], cwd=workspace1, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=workspace1, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=workspace1, capture_output=True)
    (workspace1 / "README.md").write_text("# Workspace 1")
    subprocess.run(["git", "add", "."], cwd=workspace1, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=workspace1, capture_output=True)
    
    # Create second workspace with git repo
    workspace2 = base / "workspace2"
    workspace2.mkdir()
    subprocess.run(["git", "init"], cwd=workspace2, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=workspace2, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=workspace2, capture_output=True)
    (workspace2 / "README.md").write_text("# Workspace 2")
    subprocess.run(["git", "add", "."], cwd=workspace2, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=workspace2, capture_output=True)
    
    # Create a regular file (not a directory)
    (base / "not_a_dir.txt").write_text("I am a file")
    
    # Set environment variables
    monkeypatch.setenv("WORKSPACE_PATH", str(workspace1))
    monkeypatch.setenv("WORKSPACE_BASE_PATH", str(base))
    
    # Clear caches
    from oya.config import load_settings
    load_settings.cache_clear()
    get_settings.cache_clear()
    _reset_db_instance()
    _reset_vectorstore_instance()
    
    yield {
        "base": base,
        "workspace1": workspace1,
        "workspace2": workspace2,
        "file_path": base / "not_a_dir.txt",
    }
    
    _reset_db_instance()
    _reset_vectorstore_instance()


async def test_switch_workspace_success(client, workspace_base):
    """POST /api/repos/workspace with valid path returns 200 with status.
    
    Requirements: 4.1, 4.2, 4.8
    """
    response = await client.post(
        "/api/repos/workspace",
        json={"path": str(workspace_base["workspace2"])}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "message" in data
    assert data["status"]["path"] == str(workspace_base["workspace2"])


async def test_switch_workspace_nonexistent_path_returns_400(client, workspace_base):
    """POST /api/repos/workspace with non-existent path returns 400.
    
    Requirements: 4.6
    """
    nonexistent = workspace_base["base"] / "does_not_exist"
    response = await client.post(
        "/api/repos/workspace",
        json={"path": str(nonexistent)}
    )
    
    assert response.status_code == 400
    data = response.json()
    assert "detail" in data


async def test_switch_workspace_file_path_returns_400(client, workspace_base):
    """POST /api/repos/workspace with file path (not directory) returns 400.
    
    Requirements: 4.7
    """
    response = await client.post(
        "/api/repos/workspace",
        json={"path": str(workspace_base["file_path"])}
    )
    
    assert response.status_code == 400
    data = response.json()
    assert "detail" in data


async def test_switch_workspace_outside_base_returns_403(client, workspace_base, tmp_path):
    """POST /api/repos/workspace with path outside base returns 403.
    
    Requirements: 4.11
    """
    # Create a directory outside the base path
    outside = tmp_path / "outside_base"
    outside.mkdir()
    
    response = await client.post(
        "/api/repos/workspace",
        json={"path": str(outside)}
    )
    
    assert response.status_code == 403
    data = response.json()
    assert "detail" in data
