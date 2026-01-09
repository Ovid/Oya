"""File filtering tests."""

import tempfile
from pathlib import Path

import pytest

from oya.repo.file_filter import FileFilter


@pytest.fixture
def temp_repo():
    """Create temporary directory with various files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir)

        # Create structure
        (repo_path / "src").mkdir()
        (repo_path / "src" / "main.py").write_text("code")
        (repo_path / "node_modules").mkdir()
        (repo_path / "node_modules" / "pkg").mkdir()
        (repo_path / "node_modules" / "pkg" / "index.js").write_text("module")
        (repo_path / "build").mkdir()
        (repo_path / "build" / "output.js").write_text("built")
        (repo_path / ".git").mkdir()
        (repo_path / ".git" / "config").write_text("git")
        (repo_path / "README.md").write_text("readme")

        yield repo_path


def test_default_excludes_node_modules(temp_repo: Path):
    """Default patterns exclude node_modules."""
    filter = FileFilter(temp_repo)

    files = filter.get_files()

    assert not any("node_modules" in f for f in files)


def test_default_excludes_git(temp_repo: Path):
    """Default patterns exclude .git."""
    filter = FileFilter(temp_repo)

    files = filter.get_files()

    assert not any(".git" in f for f in files)


def test_default_excludes_build(temp_repo: Path):
    """Default patterns exclude build directories."""
    filter = FileFilter(temp_repo)

    files = filter.get_files()

    assert not any("build" in f for f in files)


def test_includes_source_files(temp_repo: Path):
    """Includes regular source files."""
    filter = FileFilter(temp_repo)

    files = filter.get_files()

    assert "src/main.py" in files
    assert "README.md" in files


def test_oyaignore_adds_custom_patterns(temp_repo: Path):
    """Custom .oyaignore patterns are applied."""
    # Create .oyaignore
    (temp_repo / ".oyaignore").write_text("*.md\n")

    filter = FileFilter(temp_repo)
    files = filter.get_files()

    assert "README.md" not in files
    assert "src/main.py" in files


def test_respects_max_file_size(temp_repo: Path):
    """Files over max size are excluded."""
    # Create large file
    (temp_repo / "large.txt").write_text("x" * 1000)

    filter = FileFilter(temp_repo, max_file_size_kb=0.5)  # 0.5 KB
    files = filter.get_files()

    assert "large.txt" not in files


def test_excludes_binary_files(temp_repo: Path):
    """Binary files are excluded."""
    # Create a binary file (with null bytes)
    (temp_repo / "image.bin").write_bytes(b"\x00\x01\x02\x03")

    filter = FileFilter(temp_repo)
    files = filter.get_files()

    assert "image.bin" not in files


def test_oyaignore_directory_with_trailing_slash(temp_repo: Path):
    """Directory patterns with trailing slash are correctly excluded."""
    # Create docs directory with files
    (temp_repo / "docs").mkdir()
    (temp_repo / "docs" / "plan.md").write_text("plan content")
    (temp_repo / "docs" / "design.md").write_text("design content")
    (temp_repo / "docs" / "nested").mkdir()
    (temp_repo / "docs" / "nested" / "deep.md").write_text("deep content")

    # Create .oyaignore with trailing slash pattern
    (temp_repo / ".oyaignore").write_text("docs/\n")

    filter = FileFilter(temp_repo)
    files = filter.get_files()

    # All docs files should be excluded
    assert not any("docs" in f for f in files)
    # But other files should still be included
    assert "src/main.py" in files
    assert "README.md" in files


def test_oyaignore_directory_without_trailing_slash(temp_repo: Path):
    """Directory patterns without trailing slash also work."""
    # Create docs directory with files
    (temp_repo / "docs").mkdir()
    (temp_repo / "docs" / "plan.md").write_text("plan content")

    # Create .oyaignore without trailing slash
    (temp_repo / ".oyaignore").write_text("docs\n")

    filter = FileFilter(temp_repo)
    files = filter.get_files()

    # Docs files should be excluded
    assert not any("docs" in f for f in files)
    assert "src/main.py" in files


def test_path_pattern_with_slash_excludes_subdirectory(temp_repo: Path):
    """Path patterns with / (like .oyawiki/wiki) exclude that specific subdirectory."""
    # Create .oyawiki structure
    (temp_repo / ".oyawiki").mkdir()
    (temp_repo / ".oyawiki" / "wiki").mkdir()
    (temp_repo / ".oyawiki" / "wiki" / "overview.md").write_text("wiki content")
    (temp_repo / ".oyawiki" / "notes").mkdir()
    (temp_repo / ".oyawiki" / "notes" / "correction.md").write_text("user correction")
    (temp_repo / ".oyawiki" / "cache").mkdir()
    (temp_repo / ".oyawiki" / "cache" / "data.json").write_text("{}")

    # Use extra_excludes to test path patterns with /
    filter = FileFilter(
        temp_repo,
        extra_excludes=[".oyawiki/wiki", ".oyawiki/cache"],
    )
    files = filter.get_files()

    # Wiki and cache should be excluded
    assert not any(".oyawiki/wiki" in f for f in files)
    assert not any(".oyawiki/cache" in f for f in files)
    # But notes should be included
    assert ".oyawiki/notes/correction.md" in files


def test_default_excludes_oyawiki_subdirs_but_not_notes(temp_repo: Path):
    """DEFAULT_EXCLUDES excludes .oyawiki subdirs but NOT notes."""
    # Create .oyawiki structure
    (temp_repo / ".oyawiki").mkdir()
    (temp_repo / ".oyawiki" / "wiki").mkdir()
    (temp_repo / ".oyawiki" / "wiki" / "overview.md").write_text("wiki content")
    (temp_repo / ".oyawiki" / "meta").mkdir()
    (temp_repo / ".oyawiki" / "meta" / "metadata.json").write_text("{}")
    (temp_repo / ".oyawiki" / "index").mkdir()
    (temp_repo / ".oyawiki" / "index" / "search.idx").write_text("index")
    (temp_repo / ".oyawiki" / "cache").mkdir()
    (temp_repo / ".oyawiki" / "cache" / "temp.json").write_text("{}")
    (temp_repo / ".oyawiki" / "config").mkdir()
    (temp_repo / ".oyawiki" / "config" / "settings.toml").write_text("config")
    (temp_repo / ".oyawiki" / "notes").mkdir()
    (temp_repo / ".oyawiki" / "notes" / "user_correction.md").write_text("correction")

    filter = FileFilter(temp_repo)
    files = filter.get_files()

    # Generated/ephemeral dirs should be excluded
    assert not any(".oyawiki/wiki" in f for f in files)
    assert not any(".oyawiki/meta" in f for f in files)
    assert not any(".oyawiki/index" in f for f in files)
    assert not any(".oyawiki/cache" in f for f in files)
    assert not any(".oyawiki/config" in f for f in files)
    # But notes should be INCLUDED (user corrections guide analysis)
    assert ".oyawiki/notes/user_correction.md" in files
