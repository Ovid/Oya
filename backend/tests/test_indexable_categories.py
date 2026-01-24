"""Tests for indexable items API with exclusion categories."""

import subprocess
import pytest
from httpx import ASGITransport, AsyncClient

from oya.main import app


@pytest.fixture
def temp_workspace(setup_active_repo):
    """Create a temporary workspace with test files using active repo fixture."""
    workspace = setup_active_repo["source_path"]

    # Ensure workspace exists and init git
    workspace.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=workspace, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"], cwd=workspace, capture_output=True
    )
    subprocess.run(["git", "config", "user.name", "Test"], cwd=workspace, capture_output=True)

    # Create included files
    (workspace / "src").mkdir()
    (workspace / "src" / "main.py").write_text("print('hello')")
    (workspace / "README.md").write_text("# README")

    # Create files that will be excluded by rules (DEFAULT_EXCLUDES)
    (workspace / "node_modules").mkdir()
    (workspace / "node_modules" / "dep.js").write_text("module.exports = {}")

    # Create .oyaignore file to exclude specific files
    (workspace / ".oyaignore").write_text("excluded_dir/\nexcluded_file.txt\n")
    (workspace / "excluded_dir").mkdir()
    (workspace / "excluded_dir" / "file.py").write_text("# excluded by oyaignore")
    (workspace / "excluded_file.txt").write_text("excluded by oyaignore")

    # Commit everything
    subprocess.run(["git", "add", "-f", "."], cwd=workspace, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=workspace, capture_output=True)

    return workspace


@pytest.fixture
async def client():
    """Create async test client."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client


async def test_get_indexable_items_returns_three_categories(client, temp_workspace):
    """Test that /api/repos/indexable returns included, excluded_by_oyaignore, and excluded_by_rule."""
    response = await client.get("/api/repos/indexable")

    assert response.status_code == 200
    data = response.json()

    # Check structure has three categories
    assert "included" in data
    assert "excluded_by_oyaignore" in data
    assert "excluded_by_rule" in data

    # Check each category has files and directories
    assert "files" in data["included"]
    assert "directories" in data["included"]
    assert "files" in data["excluded_by_oyaignore"]
    assert "directories" in data["excluded_by_oyaignore"]
    assert "files" in data["excluded_by_rule"]
    assert "directories" in data["excluded_by_rule"]


async def test_included_files_are_correct(client, temp_workspace):
    """Test that included category contains the right files."""
    response = await client.get("/api/repos/indexable")

    assert response.status_code == 200
    data = response.json()

    # Source files should be included
    assert "src/main.py" in data["included"]["files"]
    assert "README.md" in data["included"]["files"]

    # Excluded files should NOT be in included
    assert "excluded_file.txt" not in data["included"]["files"]
    assert "excluded_dir/file.py" not in data["included"]["files"]


async def test_oyaignore_excluded_files_are_correct(client, temp_workspace):
    """Test that excluded_by_oyaignore category contains directories excluded via .oyaignore."""
    response = await client.get("/api/repos/indexable")

    assert response.status_code == 200
    data = response.json()

    # Files excluded by file pattern (not directory) are still listed
    assert "excluded_file.txt" in data["excluded_by_oyaignore"]["files"]

    # Directory excluded by pattern - directory listed, not individual files
    assert "excluded_dir" in data["excluded_by_oyaignore"]["directories"]
    assert "excluded_dir/file.py" not in data["excluded_by_oyaignore"]["files"]


async def test_rule_excluded_files_are_correct(client, temp_workspace):
    """Test that excluded_by_rule category contains directories excluded via DEFAULT_EXCLUDES."""
    response = await client.get("/api/repos/indexable")

    assert response.status_code == 200
    data = response.json()

    # node_modules directory should be in excluded_by_rule directories
    # (files inside are no longer listed individually)
    assert "node_modules" in data["excluded_by_rule"]["directories"]

    # Individual files inside excluded directories are NOT listed
    assert "node_modules/dep.js" not in data["excluded_by_rule"]["files"]


async def test_included_directories_are_derived_from_files(client, temp_workspace):
    """Test that directories are derived from file paths."""
    response = await client.get("/api/repos/indexable")

    assert response.status_code == 200
    data = response.json()

    # If src/main.py is included, "src" should be in included directories
    assert "src" in data["included"]["directories"]

    # Root directory should always be included
    assert "" in data["included"]["directories"]


async def test_no_overlap_between_categories(client, temp_workspace):
    """Test that files don't appear in multiple categories."""
    response = await client.get("/api/repos/indexable")

    assert response.status_code == 200
    data = response.json()

    included_files = set(data["included"]["files"])
    oyaignore_files = set(data["excluded_by_oyaignore"]["files"])
    rule_files = set(data["excluded_by_rule"]["files"])

    # No file should appear in multiple categories
    assert len(included_files & oyaignore_files) == 0, (
        "Files overlap between included and oyaignore"
    )
    assert len(included_files & rule_files) == 0, "Files overlap between included and rule"
    assert len(oyaignore_files & rule_files) == 0, "Files overlap between oyaignore and rule"


async def test_binary_and_large_files_excluded_by_rule(client, temp_workspace):
    """Test that binary files and large files are excluded by rule."""
    # Create a binary file
    (temp_workspace / "image.bin").write_bytes(b"\x00\x01\x02\x03")

    # Create a large file (over 500KB default limit)
    (temp_workspace / "large.txt").write_text("x" * (600 * 1024))

    response = await client.get("/api/repos/indexable")

    assert response.status_code == 200
    data = response.json()

    # Binary files should be excluded by rule
    assert "image.bin" in data["excluded_by_rule"]["files"]

    # Large files should be excluded by rule
    assert "large.txt" in data["excluded_by_rule"]["files"]


async def test_minified_files_excluded_by_rule(client, temp_workspace):
    """Test that minified files (long lines) are excluded by rule."""
    # Create a minified file with very long lines
    long_line = "x" * 1000
    (temp_workspace / "app.min.js").write_text(long_line + "\n" + long_line)

    response = await client.get("/api/repos/indexable")

    assert response.status_code == 200
    data = response.json()

    # Minified files should be excluded by rule (either by pattern or detection)
    assert "app.min.js" in data["excluded_by_rule"]["files"]


async def test_dotfiles_excluded_by_rule(client, temp_workspace):
    """Test that dotfiles/dotdirs are excluded by rule."""
    # Create some dotfiles
    (temp_workspace / ".env").write_text("SECRET=value")
    (temp_workspace / ".config").mkdir()
    (temp_workspace / ".config" / "settings.json").write_text("{}")

    response = await client.get("/api/repos/indexable")

    assert response.status_code == 200
    data = response.json()

    # Dotfiles should be excluded by rule
    assert ".env" in data["excluded_by_rule"]["files"]

    # Dotdirs should be in directories, not individual files
    assert ".config" in data["excluded_by_rule"]["directories"]
    assert ".config/settings.json" not in data["excluded_by_rule"]["files"]


async def test_empty_oyaignore_returns_empty_oyaignore_category(client, temp_workspace):
    """Test that when .oyaignore has no entries, excluded_by_oyaignore is empty."""
    # Clear .oyaignore
    (temp_workspace / ".oyaignore").write_text("")

    response = await client.get("/api/repos/indexable")

    assert response.status_code == 200
    data = response.json()

    # excluded_by_oyaignore should be empty (or only have root directory)
    assert len(data["excluded_by_oyaignore"]["files"]) == 0


async def test_workspace_without_oyaignore(client, setup_active_repo):
    """Test response when .oyaignore doesn't exist."""
    workspace = setup_active_repo["source_path"]
    workspace.mkdir(parents=True, exist_ok=True)

    subprocess.run(["git", "init"], cwd=workspace, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"], cwd=workspace, capture_output=True
    )
    subprocess.run(["git", "config", "user.name", "Test"], cwd=workspace, capture_output=True)

    (workspace / "main.py").write_text("print('hello')")
    subprocess.run(["git", "add", "."], cwd=workspace, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=workspace, capture_output=True)

    # No .oyaignore file

    response = await client.get("/api/repos/indexable")

    assert response.status_code == 200
    data = response.json()

    # Should have all three categories
    assert "included" in data
    assert "excluded_by_oyaignore" in data
    assert "excluded_by_rule" in data

    # excluded_by_oyaignore should be empty
    assert len(data["excluded_by_oyaignore"]["files"]) == 0


async def test_excluded_directory_children_not_listed(client, temp_workspace):
    """Files inside explicitly excluded directories should not appear individually."""
    # Create a deeply nested structure in node_modules
    (temp_workspace / "node_modules" / "lodash").mkdir(parents=True)
    (temp_workspace / "node_modules" / "lodash" / "index.js").write_text("module.exports = {}")
    (temp_workspace / "node_modules" / "lodash" / "fp.js").write_text("module.exports = {}")

    response = await client.get("/api/repos/indexable")

    assert response.status_code == 200
    data = response.json()

    # node_modules directory should be in excluded_by_rule directories
    assert "node_modules" in data["excluded_by_rule"]["directories"]

    # Individual files inside should NOT be listed
    assert "node_modules/dep.js" not in data["excluded_by_rule"]["files"]
    assert "node_modules/lodash/index.js" not in data["excluded_by_rule"]["files"]
    assert "node_modules/lodash/fp.js" not in data["excluded_by_rule"]["files"]


async def test_oyaignore_directory_children_not_listed(client, temp_workspace):
    """Files inside directories excluded by .oyaignore should not appear individually."""
    # Create nested files in excluded_dir (already excluded by .oyaignore in fixture)
    (temp_workspace / "excluded_dir" / "subdir").mkdir()
    (temp_workspace / "excluded_dir" / "subdir" / "deep.py").write_text("# deep file")

    response = await client.get("/api/repos/indexable")

    assert response.status_code == 200
    data = response.json()

    # excluded_dir should be in directories
    assert "excluded_dir" in data["excluded_by_oyaignore"]["directories"]

    # Individual files should NOT be listed
    assert "excluded_dir/file.py" not in data["excluded_by_oyaignore"]["files"]
    assert "excluded_dir/subdir/deep.py" not in data["excluded_by_oyaignore"]["files"]
