"""File filtering tests."""

import tempfile
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from oya.repo.file_filter import FileFilter, extract_directories_from_files


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


def test_default_excludes_all_dotfiles_and_dotdirs(temp_repo: Path):
    """Default patterns exclude all files and directories starting with a dot."""
    # Create various dotfiles and dotdirs
    (temp_repo / ".hypothesis").mkdir()
    (temp_repo / ".hypothesis" / "constants").mkdir()
    (temp_repo / ".hypothesis" / "constants" / "abc123").write_text("data")
    (temp_repo / ".pytest_cache").mkdir()
    (temp_repo / ".pytest_cache" / "v").mkdir()
    (temp_repo / ".pytest_cache" / "v" / "cache").write_text("cache")
    (temp_repo / ".ruff_cache").mkdir()
    (temp_repo / ".ruff_cache" / "data").write_text("ruff")
    (temp_repo / ".env").write_text("SECRET=value")
    (temp_repo / ".env.local").write_text("LOCAL=value")
    (temp_repo / ".gitignore").write_text("*.pyc")
    (temp_repo / ".editorconfig").write_text("[*]")
    (temp_repo / ".kiro").mkdir()
    (temp_repo / ".kiro" / "settings.json").write_text("{}")
    (temp_repo / ".claude").mkdir()
    (temp_repo / ".claude" / "config.json").write_text("{}")

    filter = FileFilter(temp_repo)
    files = filter.get_files()

    # All dotfiles and dotdirs should be excluded
    dotfiles_found = [f for f in files if f.startswith(".") or "/." in f]
    assert not dotfiles_found, f"Found dotfiles/dotdirs in files: {dotfiles_found}"
    # Regular files should still be included
    assert "src/main.py" in files
    assert "README.md" in files


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
    """Custom .oyawiki/.oyaignore patterns are applied."""
    # Create .oyawiki/.oyaignore (new location)
    (temp_repo / ".oyawiki").mkdir(exist_ok=True)
    (temp_repo / ".oyawiki" / ".oyaignore").write_text("*.md\n")

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

    # Create .oyawiki/.oyaignore with trailing slash pattern (new location)
    (temp_repo / ".oyawiki").mkdir(exist_ok=True)
    (temp_repo / ".oyawiki" / ".oyaignore").write_text("docs/\n")

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

    # Create .oyawiki/.oyaignore without trailing slash (new location)
    (temp_repo / ".oyawiki").mkdir(exist_ok=True)
    (temp_repo / ".oyawiki" / ".oyaignore").write_text("docs\n")

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


# Tests for extract_directories_from_files utility function


def test_default_excludes_minified_js(temp_repo: Path):
    """Default patterns exclude minified JavaScript files."""
    (temp_repo / "app.min.js").write_text("minified code")
    (temp_repo / "app.js").write_text("normal code")

    filter = FileFilter(temp_repo)
    files = filter.get_files()

    assert "app.min.js" not in files
    assert "app.js" in files


def test_default_excludes_bundle_files(temp_repo: Path):
    """Default patterns exclude bundle and chunk files."""
    (temp_repo / "main.bundle.js").write_text("bundled")
    (temp_repo / "vendor.chunk.js").write_text("chunked")

    filter = FileFilter(temp_repo)
    files = filter.get_files()

    assert "main.bundle.js" not in files
    assert "vendor.chunk.js" not in files


def test_default_excludes_lock_files(temp_repo: Path):
    """Default patterns exclude package lock files."""
    (temp_repo / "package-lock.json").write_text("{}")
    (temp_repo / "yarn.lock").write_text("lockfile")
    (temp_repo / "pnpm-lock.yaml").write_text("lockfile")
    (temp_repo / "Cargo.lock").write_text("lockfile")
    (temp_repo / "poetry.lock").write_text("lockfile")
    (temp_repo / "Gemfile.lock").write_text("lockfile")
    (temp_repo / "composer.lock").write_text("{}")

    filter = FileFilter(temp_repo)
    files = filter.get_files()

    assert "package-lock.json" not in files
    assert "yarn.lock" not in files
    assert "pnpm-lock.yaml" not in files
    assert "Cargo.lock" not in files
    assert "poetry.lock" not in files
    assert "Gemfile.lock" not in files
    assert "composer.lock" not in files


def test_default_excludes_source_maps(temp_repo: Path):
    """Default patterns exclude source map files."""
    (temp_repo / "app.js.map").write_text("{}")
    (temp_repo / "styles.css.map").write_text("{}")

    filter = FileFilter(temp_repo)
    files = filter.get_files()

    assert "app.js.map" not in files
    assert "styles.css.map" not in files


# Tests for extract_directories_from_files utility function


def test_extract_directories_from_files_basic():
    """Extract unique parent directories from file paths."""
    files = [
        "src/main.py",
        "src/utils/helpers.py",
        "tests/test_main.py",
    ]

    directories = extract_directories_from_files(files)

    assert "src" in directories
    assert "src/utils" in directories
    assert "tests" in directories


def test_extract_directories_from_files_sorted():
    """Output is sorted alphabetically with root first."""
    files = [
        "zebra/file.py",
        "alpha/file.py",
        "beta/nested/file.py",
    ]

    directories = extract_directories_from_files(files)

    assert directories == sorted(directories)
    assert directories == ["", "alpha", "beta", "beta/nested", "zebra"]


def test_extract_directories_from_files_unique():
    """Directories are unique even when multiple files share the same parent."""
    files = [
        "src/a.py",
        "src/b.py",
        "src/c.py",
    ]

    directories = extract_directories_from_files(files)

    assert directories.count("src") == 1


def test_extract_directories_from_files_empty():
    """Empty file list returns only root directory."""
    directories = extract_directories_from_files([])

    assert directories == [""]


def test_extract_directories_from_files_root_files():
    """Files at root level produce only root directory."""
    files = ["README.md", "setup.py"]

    directories = extract_directories_from_files(files)

    assert directories == [""]


def test_extract_directories_from_files_deep_nesting():
    """Deeply nested files produce all intermediate directories including root."""
    files = ["a/b/c/d/file.py"]

    directories = extract_directories_from_files(files)

    assert directories == ["", "a", "a/b", "a/b/c", "a/b/c/d"]


# Property-based test for alphabetical sorting
# **Property 2: Alphabetical Sorting** (directories portion)
# **Validates: Requirements 2.6, 7.4, 7.5**
@given(
    st.lists(
        st.text(
            alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyz/"),
            min_size=1,
            max_size=50,
        ).filter(lambda x: not x.startswith("/") and not x.endswith("/") and "//" not in x),
        min_size=0,
        max_size=20,
    )
)
@settings(max_examples=100)
def test_extract_directories_alphabetically_sorted_property(files: list[str]):
    """Property: For any list of files, extracted directories are always sorted alphabetically."""
    directories = extract_directories_from_files(files)

    # Property: output is always sorted
    assert directories == sorted(directories), "Directories must be sorted alphabetically"

    # Property: no duplicates
    assert len(directories) == len(set(directories)), "Directories must be unique"


# Tests for minified file detection


def test_excludes_minified_by_line_length(temp_repo: Path):
    """Files with very long lines (minified) are excluded."""
    # Create a file with extremely long lines (simulating minified code)
    long_line = "x" * 1000
    (temp_repo / "minified.js").write_text(long_line + "\n" + long_line)

    # Create a normal file with reasonable line lengths
    normal_content = "\n".join(["const x = 1;"] * 50)
    (temp_repo / "normal.js").write_text(normal_content)

    filter = FileFilter(temp_repo)
    files = filter.get_files()

    assert "minified.js" not in files
    assert "normal.js" in files


def test_minified_detection_samples_first_lines(temp_repo: Path):
    """Minified detection only samples first 20 lines."""
    # First 20 lines are normal, rest is long (should pass)
    normal_lines = ["const x = 1;"] * 25
    (temp_repo / "mostly_normal.js").write_text("\n".join(normal_lines))

    filter = FileFilter(temp_repo)
    files = filter.get_files()

    assert "mostly_normal.js" in files


class TestExtractDirectoriesIncludesRoot:
    """Tests for root directory inclusion."""

    def test_extract_directories_includes_root(self):
        """Root directory ('') is included in extracted directories."""
        files = ["src/main.py", "README.md", "tests/test_main.py"]

        result = extract_directories_from_files(files)

        assert "" in result  # Root directory
        assert "src" in result
        assert "tests" in result

    def test_extract_directories_root_only_for_top_level_files(self):
        """Root is included even when only top-level files exist."""
        files = ["README.md", "setup.py"]

        result = extract_directories_from_files(files)

        assert "" in result
        assert len(result) == 1  # Only root

    def test_extract_directories_root_first_in_sorted_order(self):
        """Root directory comes first in sorted output."""
        files = ["src/main.py", "tests/test.py"]

        result = extract_directories_from_files(files)

        assert result[0] == ""  # Root is first
