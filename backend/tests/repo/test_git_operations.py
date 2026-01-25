"""Tests for git clone/pull operations."""

import subprocess

import pytest

from oya.repo.git_operations import (
    GitCloneError,
    GitPullError,
    GitSyncError,
    clone_repo,
    get_remote_url,
    pull_repo,
)


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
        ["git", "config", "user.name", "Test"],
        cwd=repo_path,
        check=True,
        capture_output=True,
    )
    (repo_path / "README.md").write_text("# Test Repo")
    subprocess.run(["git", "add", "."], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=repo_path,
        check=True,
        capture_output=True,
    )
    return repo_path


def test_clone_repo_success(tmp_path, source_repo):
    """Can clone a local repo."""
    dest = tmp_path / "dest"
    clone_repo(str(source_repo), dest)
    assert (dest / "README.md").exists()
    assert (dest / ".git").exists()


def test_clone_repo_invalid_url(tmp_path):
    """Clone raises GitCloneError for invalid URL."""
    dest = tmp_path / "dest"
    with pytest.raises(GitCloneError) as exc_info:
        clone_repo("/nonexistent/path/that/does/not/exist", dest)
    assert "not found" in str(exc_info.value).lower() or "clone" in str(exc_info.value).lower()


def test_clone_repo_dest_already_exists(tmp_path, source_repo):
    """Clone raises GitCloneError if destination already exists."""
    dest = tmp_path / "dest"
    dest.mkdir()
    (dest / "some_file.txt").write_text("existing content")

    with pytest.raises(GitCloneError) as exc_info:
        clone_repo(str(source_repo), dest)
    assert "already exists" in str(exc_info.value).lower()


def test_pull_repo_success(tmp_path, source_repo):
    """Can pull updates from origin."""
    dest = tmp_path / "dest"
    clone_repo(str(source_repo), dest)

    # Add a commit to source
    (source_repo / "new_file.txt").write_text("new content")
    subprocess.run(["git", "add", "."], cwd=source_repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Add new file"],
        cwd=source_repo,
        check=True,
        capture_output=True,
    )

    # Pull should get the new file
    pull_repo(dest)
    assert (dest / "new_file.txt").exists()


def test_pull_repo_not_a_git_repo(tmp_path):
    """Pull raises GitPullError for non-git directory."""
    non_repo = tmp_path / "not-a-repo"
    non_repo.mkdir()

    with pytest.raises(GitPullError):
        pull_repo(non_repo)


def test_get_remote_url(tmp_path, source_repo):
    """Can get the remote URL of a cloned repo."""
    dest = tmp_path / "dest"
    clone_repo(str(source_repo), dest)
    url = get_remote_url(dest)
    assert str(source_repo) in url


def test_get_remote_url_no_origin(tmp_path):
    """Raises ValueError for repo without origin remote."""
    repo_path = tmp_path / "no-origin-repo"
    repo_path.mkdir()
    subprocess.run(["git", "init"], cwd=repo_path, check=True, capture_output=True)

    with pytest.raises(ValueError) as exc_info:
        get_remote_url(repo_path)
    assert "origin" in str(exc_info.value).lower()


def test_git_sync_error_has_message_and_original_error():
    """GitSyncError stores message and optional original error."""
    error = GitSyncError("User message", original_error="Raw stderr")
    assert error.message == "User message"
    assert error.original_error == "Raw stderr"
    assert str(error) == "User message"
