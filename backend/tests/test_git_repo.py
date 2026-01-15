"""Git repository wrapper tests."""

import subprocess
import tempfile
from pathlib import Path

import pytest

from oya.repo import GitRepo


@pytest.fixture
def temp_git_repo():
    """Create a temporary git repository with some files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir)

        # Initialize git repo
        subprocess.run(["git", "init"], cwd=repo_path, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"], cwd=repo_path, capture_output=True
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"], cwd=repo_path, capture_output=True
        )

        # Create some files
        (repo_path / "README.md").write_text("# Test Project")
        (repo_path / "src").mkdir()
        (repo_path / "src" / "main.py").write_text("def main(): pass")

        # Commit
        subprocess.run(["git", "add", "."], cwd=repo_path, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"], cwd=repo_path, capture_output=True
        )

        yield repo_path


def test_git_repo_gets_head_commit(temp_git_repo: Path):
    """Can get HEAD commit hash."""
    repo = GitRepo(temp_git_repo)

    commit_hash = repo.get_head_commit()

    assert len(commit_hash) == 40  # Full SHA


def test_git_repo_checks_dirty_status(temp_git_repo: Path):
    """Can detect dirty working directory."""
    repo = GitRepo(temp_git_repo)

    # Clean initially
    assert not repo.is_dirty()

    # Make dirty
    (temp_git_repo / "new_file.txt").write_text("dirty")

    assert repo.is_dirty()


def test_git_repo_gets_branch(temp_git_repo: Path):
    """Can get current branch name."""
    repo = GitRepo(temp_git_repo)

    branch = repo.get_current_branch()

    assert branch in ("main", "master")


def test_git_repo_gets_file_at_commit(temp_git_repo: Path):
    """Can get file content at specific commit."""
    repo = GitRepo(temp_git_repo)
    commit = repo.get_head_commit()

    content = repo.get_file_at_commit("README.md", commit)

    assert content == "# Test Project"


def test_git_repo_lists_files(temp_git_repo: Path):
    """Can list all tracked files."""
    repo = GitRepo(temp_git_repo)

    files = repo.list_files()

    assert "README.md" in files
    assert "src/main.py" in files
