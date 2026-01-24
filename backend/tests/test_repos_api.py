"""Repository management API tests for multi-repo mode."""

import subprocess
import pytest
from httpx import ASGITransport, AsyncClient

from oya.main import app
from oya.api.deps import get_settings, _reset_db_instance
from oya.state import reset_app_state


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    """Set up OYA_DATA_DIR for tests."""
    oya_dir = tmp_path / ".oya"
    oya_dir.mkdir()
    monkeypatch.setenv("OYA_DATA_DIR", str(oya_dir))
    # Ensure WORKSPACE_PATH is not set (multi-repo mode)
    monkeypatch.delenv("WORKSPACE_PATH", raising=False)

    # Clear caches
    from oya.config import load_settings

    load_settings.cache_clear()
    get_settings.cache_clear()
    _reset_db_instance()

    yield oya_dir

    _reset_db_instance()


@pytest.fixture
def source_repo(tmp_path):
    """Create a source git repo to clone from."""
    repo_path = tmp_path / "source-repo"
    repo_path.mkdir()
    subprocess.run(["git", "init"], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=repo_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"], cwd=repo_path, check=True, capture_output=True
    )

    # Create directory structure with files
    (repo_path / "src").mkdir()
    (repo_path / "src" / "utils").mkdir()
    (repo_path / "docs").mkdir()

    (repo_path / "README.md").write_text("# Test Repo")
    (repo_path / "src" / "main.py").write_text("print('hello')")
    (repo_path / "src" / "utils" / "helpers.py").write_text("def helper(): pass")
    (repo_path / "docs" / "guide.md").write_text("# Guide")

    subprocess.run(["git", "add", "."], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"], cwd=repo_path, check=True, capture_output=True
    )
    return repo_path


@pytest.fixture(autouse=True)
def reset_state():
    """Reset app state before each test."""
    reset_app_state()
    yield
    reset_app_state()


@pytest.fixture
async def client():
    """Create async test client."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client


async def _create_and_activate_repo(client, source_repo, display_name="Test Repo"):
    """Helper to create a repo and activate it."""
    # Create the repo
    create_response = await client.post(
        "/api/v2/repos", json={"url": str(source_repo), "display_name": display_name}
    )
    assert create_response.status_code == 201
    repo_id = create_response.json()["id"]

    # Activate it
    activate_response = await client.post(f"/api/v2/repos/{repo_id}/activate")
    assert activate_response.status_code == 200

    return repo_id


# ============================================================================
# Indexable Items Endpoint Tests
# ============================================================================


async def test_get_indexable_items_requires_active_repo(client, data_dir):
    """GET /api/repos/indexable returns 400 when no repo is active."""
    response = await client.get("/api/repos/indexable")

    assert response.status_code == 400
    data = response.json()
    assert "No repository is active" in data["detail"]


async def test_get_indexable_items_returns_correct_schema(client, data_dir, source_repo):
    """GET /api/repos/indexable returns categorized directories and files."""
    await _create_and_activate_repo(client, source_repo)

    response = await client.get("/api/repos/indexable")

    assert response.status_code == 200
    data = response.json()

    # Check schema has three categories
    assert "included" in data
    assert "excluded_by_oyaignore" in data
    assert "excluded_by_rule" in data

    # Check each category has directories and files
    for category in ["included", "excluded_by_oyaignore", "excluded_by_rule"]:
        assert "directories" in data[category]
        assert "files" in data[category]
        assert isinstance(data[category]["directories"], list)
        assert isinstance(data[category]["files"], list)


async def test_get_indexable_items_returns_expected_content(client, data_dir, source_repo):
    """GET /api/repos/indexable returns expected directories and files."""
    await _create_and_activate_repo(client, source_repo)

    response = await client.get("/api/repos/indexable")

    assert response.status_code == 200
    data = response.json()

    # Check expected directories are present in included category
    assert "src" in data["included"]["directories"]
    assert "src/utils" in data["included"]["directories"]
    assert "docs" in data["included"]["directories"]

    # Check expected files are present in included category
    assert "README.md" in data["included"]["files"]
    assert "src/main.py" in data["included"]["files"]
    assert "src/utils/helpers.py" in data["included"]["files"]
    assert "docs/guide.md" in data["included"]["files"]


# ============================================================================
# Oyaignore Update Endpoint Tests
# ============================================================================


async def test_post_oyaignore_requires_active_repo(client, data_dir):
    """POST /api/repos/oyaignore returns 400 when no repo is active."""
    response = await client.post(
        "/api/repos/oyaignore", json={"directories": ["docs"], "files": ["README.md"]}
    )

    assert response.status_code == 400
    data = response.json()
    assert "No repository is active" in data["detail"]


async def test_post_oyaignore_creates_file(client, data_dir, source_repo):
    """POST /api/repos/oyaignore creates .oyaignore file."""
    repo_id = await _create_and_activate_repo(client, source_repo)

    response = await client.post(
        "/api/repos/oyaignore", json={"directories": ["docs"], "files": ["README.md"]}
    )

    assert response.status_code == 200

    # Verify the file was created in the meta directory
    from oya.config import load_settings
    from oya.repo.repo_paths import RepoPaths
    from oya.db.repo_registry import RepoRegistry

    settings = load_settings()
    registry = RepoRegistry(settings.repos_db_path)
    repo = registry.get(repo_id)
    registry.close()

    paths = RepoPaths(settings.data_dir, repo.local_path)
    oyaignore_path = paths.oyaignore

    assert oyaignore_path.exists()
    content = oyaignore_path.read_text()
    assert "docs/" in content  # Directory should have trailing slash
    assert "README.md" in content


async def test_post_oyaignore_adds_trailing_slash_to_directories(client, data_dir, source_repo):
    """POST /api/repos/oyaignore adds trailing slash to directory patterns."""
    repo_id = await _create_and_activate_repo(client, source_repo)

    response = await client.post(
        "/api/repos/oyaignore", json={"directories": ["src", "docs"], "files": []}
    )

    assert response.status_code == 200

    # Verify the content
    from oya.config import load_settings
    from oya.repo.repo_paths import RepoPaths
    from oya.db.repo_registry import RepoRegistry

    settings = load_settings()
    registry = RepoRegistry(settings.repos_db_path)
    repo = registry.get(repo_id)
    registry.close()

    paths = RepoPaths(settings.data_dir, repo.local_path)
    content = paths.oyaignore.read_text()

    assert "src/" in content
    assert "docs/" in content


async def test_post_oyaignore_returns_correct_response_schema(client, data_dir, source_repo):
    """POST /api/repos/oyaignore returns correct response schema."""
    await _create_and_activate_repo(client, source_repo)

    response = await client.post(
        "/api/repos/oyaignore",
        json={"directories": ["docs", "src"], "files": ["README.md", "LICENSE"]},
    )

    assert response.status_code == 200
    data = response.json()

    # Check response schema
    assert "added_directories" in data
    assert "added_files" in data
    assert "total_added" in data

    # Check types
    assert isinstance(data["added_directories"], list)
    assert isinstance(data["added_files"], list)
    assert isinstance(data["total_added"], int)

    # Check values
    assert "docs/" in data["added_directories"]
    assert "src/" in data["added_directories"]
    assert "README.md" in data["added_files"]
    assert data["total_added"] >= 3  # At least docs, src, README.md


# ============================================================================
# Init Repo (Generation) Endpoint Tests
# ============================================================================


async def test_post_repos_init_requires_active_repo(client, data_dir):
    """POST /api/repos/init returns 400 when no repo is active."""
    response = await client.post("/api/repos/init")

    assert response.status_code == 400
    data = response.json()
    assert "No repository is active" in data["detail"]


async def test_post_repos_init_starts_generation(client, data_dir, source_repo, monkeypatch):
    """POST /api/repos/init starts wiki generation job."""
    await _create_and_activate_repo(client, source_repo)

    # Mock the background task to prevent it from running after test cleanup
    from unittest.mock import AsyncMock
    from oya.api.routers import repos

    mock_run_generation = AsyncMock()
    monkeypatch.setattr(repos, "_run_generation", mock_run_generation)

    response = await client.post("/api/repos/init")

    assert response.status_code == 202
    data = response.json()
    assert "job_id" in data
    assert data["job_id"] is not None

    # Verify the background task was scheduled (mock was called)
    assert mock_run_generation.call_count == 1
