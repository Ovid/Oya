"""Tests for RepoPaths utility class."""

import pytest

from oya.repo.repo_paths import RepoPaths


def test_repo_paths_from_local_path(tmp_path):
    """RepoPaths computes correct paths for a repo."""
    data_dir = tmp_path / ".oya"
    local_path = "github.com/Ovid/Oya"

    paths = RepoPaths(data_dir, local_path)

    assert paths.root == data_dir / "wikis" / "github.com" / "Ovid" / "Oya"
    assert paths.source == paths.root / "source"
    assert paths.meta == paths.root / "meta"
    assert paths.oyawiki == paths.meta / ".oyawiki"
    assert paths.oyaignore == paths.meta / ".oyaignore"
    assert paths.oya_logs == paths.meta / ".oya-logs"


def test_repo_paths_create_structure(tmp_path):
    """Can create the directory structure."""
    data_dir = tmp_path / ".oya"
    paths = RepoPaths(data_dir, "github.com/Ovid/Oya")

    paths.create_structure()

    assert paths.root.exists()
    assert paths.meta.exists()
    # source/ is created by git clone, not by us


def test_repo_paths_delete_all(tmp_path):
    """Can delete the entire repo directory."""
    data_dir = tmp_path / ".oya"
    paths = RepoPaths(data_dir, "github.com/Ovid/Oya")
    paths.create_structure()

    # Create some files
    (paths.meta / "test.txt").write_text("test")

    paths.delete_all()

    assert not paths.root.exists()


def test_repo_paths_oyawiki_subdirs(tmp_path):
    """RepoPaths provides .oyawiki subdirectory paths."""
    data_dir = tmp_path / ".oya"
    paths = RepoPaths(data_dir, "local/some/path")

    assert paths.wiki_dir == paths.oyawiki / "wiki"
    assert paths.notes_dir == paths.oyawiki / "notes"
    assert paths.meta_dir == paths.oyawiki / "meta"
    assert paths.db_path == paths.meta_dir / "oya.db"
    assert paths.chroma_dir == paths.meta_dir / "chroma"


def test_repo_paths_exists(tmp_path):
    """exists() returns True only when root directory exists."""
    data_dir = tmp_path / ".oya"
    paths = RepoPaths(data_dir, "github.com/test/repo")

    assert not paths.exists()

    paths.create_structure()

    assert paths.exists()


def test_repo_paths_has_source(tmp_path):
    """has_source() returns True only when source/.git exists."""
    data_dir = tmp_path / ".oya"
    paths = RepoPaths(data_dir, "github.com/test/repo")
    paths.create_structure()

    assert not paths.has_source()

    # Create source directory without .git
    paths.source.mkdir(parents=True, exist_ok=True)
    assert not paths.has_source()

    # Create .git directory
    (paths.source / ".git").mkdir()
    assert paths.has_source()


def test_repo_paths_has_wiki(tmp_path):
    """has_wiki() returns True only when wiki_dir exists with content."""
    data_dir = tmp_path / ".oya"
    paths = RepoPaths(data_dir, "github.com/test/repo")
    paths.create_structure()

    assert not paths.has_wiki()

    # Create a wiki file
    (paths.wiki_dir / "overview.md").write_text("# Overview")
    assert paths.has_wiki()


def test_repo_paths_create_structure_creates_all_subdirs(tmp_path):
    """create_structure() creates all expected subdirectories."""
    data_dir = tmp_path / ".oya"
    paths = RepoPaths(data_dir, "github.com/test/repo")

    paths.create_structure()

    # All meta directories should exist
    assert paths.meta.exists()
    assert paths.wiki_dir.exists()
    assert paths.notes_dir.exists()
    assert paths.meta_dir.exists()
    assert paths.config_dir.exists()
    assert paths.index_dir.exists()
    assert paths.cache_dir.exists()
    assert paths.oya_logs.exists()

    # Source should NOT be created (git clone creates it)
    assert not paths.source.exists()


def test_repo_paths_delete_all_nonexistent(tmp_path):
    """delete_all() is safe to call on non-existent paths."""
    data_dir = tmp_path / ".oya"
    paths = RepoPaths(data_dir, "github.com/test/repo")

    # Should not raise
    paths.delete_all()

    assert not paths.root.exists()


# =============================================================================
# Path Traversal Security Tests
# =============================================================================


def test_repo_paths_rejects_dotdot_in_local_path(tmp_path):
    """RepoPaths rejects local_path containing '..' (path traversal)."""
    data_dir = tmp_path / ".oya"

    with pytest.raises(ValueError, match="Invalid local_path"):
        RepoPaths(data_dir, "github.com/user/../../../etc")


def test_repo_paths_rejects_leading_slash(tmp_path):
    """RepoPaths rejects local_path starting with '/'."""
    data_dir = tmp_path / ".oya"

    with pytest.raises(ValueError, match="Invalid local_path"):
        RepoPaths(data_dir, "/etc/passwd")


def test_repo_paths_rejects_dotdot_in_repo_name(tmp_path):
    """RepoPaths rejects '..' embedded in repo name."""
    data_dir = tmp_path / ".oya"

    with pytest.raises(ValueError, match="Invalid local_path"):
        RepoPaths(data_dir, "github.com/owner/repo..name")


def test_repo_paths_allows_dots_in_valid_names(tmp_path):
    """RepoPaths allows single dots in valid path components."""
    data_dir = tmp_path / ".oya"

    # Valid: single dots are fine (like file.txt)
    paths = RepoPaths(data_dir, "github.com/owner/repo.name")
    assert paths.root == data_dir / "wikis" / "github.com" / "owner" / "repo.name"

    # Valid: .dotfile style names
    paths = RepoPaths(data_dir, "github.com/owner/.dotfiles")
    assert paths.root == data_dir / "wikis" / "github.com" / "owner" / ".dotfiles"
