"""API dependency tests."""

import subprocess

import pytest
from fastapi import HTTPException

from oya.api.deps import (
    get_db,
    get_settings,
    get_repo,
    get_active_repo,
    require_active_repo,
    _reset_db_instance,
)
from oya.db.repo_registry import RepoRegistry


def test_get_settings_returns_settings(tmp_path, monkeypatch):
    """get_settings returns Settings instance."""
    # Setup workspace path
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.setenv("WORKSPACE_PATH", str(workspace))

    # Clear any cached settings
    from oya.config import load_settings

    load_settings.cache_clear()
    get_settings.cache_clear()

    settings = get_settings()
    assert hasattr(settings, "workspace_path")
    assert hasattr(settings, "active_provider")


# =============================================================================
# Active Repo Context Tests
# =============================================================================


def _clear_active_repo(oya_dir):
    """Helper to clear the active repo setting from the registry."""
    registry = RepoRegistry(oya_dir / "repos.db")
    try:
        registry.delete_setting("active_repo_id")
    finally:
        registry.close()


def _set_active_repo(oya_dir, repo_id):
    """Helper to set the active repo in the registry."""
    registry = RepoRegistry(oya_dir / "repos.db")
    try:
        registry.set_setting("active_repo_id", str(repo_id))
    finally:
        registry.close()


@pytest.fixture
def multi_repo_setup(tmp_path, monkeypatch):
    """Set up OYA_DATA_DIR and a source repo for multi-repo tests."""
    from oya.config import load_settings
    from oya.repo.git_operations import clone_repo
    from oya.repo.repo_paths import RepoPaths

    # Reset db instance
    _reset_db_instance()

    # Set up data dir
    oya_dir = tmp_path / ".oya"
    oya_dir.mkdir()
    monkeypatch.setenv("OYA_DATA_DIR", str(oya_dir))

    # Still need WORKSPACE_PATH for load_settings
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.setenv("WORKSPACE_PATH", str(workspace))

    load_settings.cache_clear()
    get_settings.cache_clear()

    # Create a source repo to clone
    source_repo = tmp_path / "source-repo"
    source_repo.mkdir()
    subprocess.run(["git", "init"], cwd=source_repo, capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=source_repo,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=source_repo,
        capture_output=True,
        check=True,
    )
    (source_repo / "README.md").write_text("# Test")
    subprocess.run(["git", "add", "."], cwd=source_repo, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial"],
        cwd=source_repo,
        capture_output=True,
        check=True,
    )

    # Clone and register the repo
    local_path = "local/test-repo"
    paths = RepoPaths(oya_dir, local_path)
    paths.create_structure()
    clone_repo(str(source_repo), paths.source)

    registry = RepoRegistry(oya_dir / "repos.db")
    repo_id = registry.add(
        origin_url=str(source_repo),
        source_type="local",
        local_path=local_path,
        display_name="Test Repo",
    )
    registry.update(repo_id, status="ready")
    registry.close()

    yield {"oya_dir": oya_dir, "repo_id": repo_id, "local_path": local_path, "paths": paths}

    # Cleanup
    _clear_active_repo(oya_dir)
    _reset_db_instance()


def test_get_active_repo_returns_none_when_no_active(multi_repo_setup):
    """get_active_repo returns None when no repo is active."""
    _clear_active_repo(multi_repo_setup["oya_dir"])
    result = get_active_repo()
    assert result is None


def test_get_active_repo_returns_active_repo(multi_repo_setup):
    """get_active_repo returns the active repo record."""
    repo_id = multi_repo_setup["repo_id"]
    oya_dir = multi_repo_setup["oya_dir"]

    # Activate the repo via registry
    _set_active_repo(oya_dir, repo_id)

    result = get_active_repo()
    assert result is not None
    assert result.id == repo_id
    assert result.display_name == "Test Repo"


def test_require_active_repo_raises_when_no_active(multi_repo_setup):
    """require_active_repo raises HTTPException when no repo is active."""
    _clear_active_repo(multi_repo_setup["oya_dir"])

    with pytest.raises(HTTPException) as exc_info:
        require_active_repo()

    assert exc_info.value.status_code == 400
    assert "No repository is active" in exc_info.value.detail


def test_require_active_repo_returns_repo_when_active(multi_repo_setup):
    """require_active_repo returns the repo when one is active."""
    repo_id = multi_repo_setup["repo_id"]
    _set_active_repo(multi_repo_setup["oya_dir"], repo_id)

    result = require_active_repo()
    assert result.id == repo_id


def test_get_db_uses_active_repo_database(multi_repo_setup):
    """get_db returns database for active repo when one is active."""
    from oya.db.connection import Database

    repo_id = multi_repo_setup["repo_id"]
    paths = multi_repo_setup["paths"]

    # Activate the repo via registry
    _set_active_repo(multi_repo_setup["oya_dir"], repo_id)

    db = get_db()
    assert isinstance(db, Database)

    # The db should be at the active repo's path
    assert paths.db_path.exists()


def test_get_repo_uses_active_repo_source(multi_repo_setup):
    """get_repo returns GitRepo for active repo's source directory."""
    from oya.repo.git_repo import GitRepo

    repo_id = multi_repo_setup["repo_id"]
    paths = multi_repo_setup["paths"]

    _set_active_repo(multi_repo_setup["oya_dir"], repo_id)

    repo = get_repo()
    assert isinstance(repo, GitRepo)
    # The repo path should be the active repo's source
    assert repo.path == paths.source
