"""Tests for .oyaignore removal functionality.

This module tests the removals parameter added to the POST /api/repos/oyaignore endpoint,
which allows users to re-include files that were previously excluded via .oyaignore.

Requirements tested:
- Removals field removes patterns from .oyaignore
- Removals are processed before additions
- Normalized pattern matching (with/without trailing slash)
- Response includes removed patterns and count
"""

import subprocess
import pytest
from httpx import ASGITransport, AsyncClient

from hypothesis import given, settings as hypothesis_settings, HealthCheck
from hypothesis import strategies as st

from oya.main import app


@pytest.fixture
def temp_workspace_with_oyaignore(setup_active_repo):
    """Create workspace with existing .oyaignore using active repo fixture."""
    workspace = setup_active_repo["source_path"]
    paths = setup_active_repo["paths"]
    workspace.mkdir(parents=True, exist_ok=True)

    # Initialize git repo
    subprocess.run(["git", "init"], cwd=workspace, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"], cwd=workspace, capture_output=True
    )
    subprocess.run(["git", "config", "user.name", "Test"], cwd=workspace, capture_output=True)

    # Create directory structure
    (workspace / "src").mkdir()
    (workspace / "src" / "main.py").write_text("print('hello')")
    (workspace / "excluded_dir").mkdir()
    (workspace / "excluded_dir" / "file.py").write_text("# excluded")
    (workspace / "excluded_file.txt").write_text("excluded")

    # Create a file and commit
    (workspace / "README.md").write_text("# Test Repo")
    subprocess.run(["git", "add", "."], cwd=workspace, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=workspace, capture_output=True)

    # Create existing .oyaignore in meta directory (where API expects it)
    paths.oyaignore.write_text("excluded_dir/\nexcluded_file.txt\nold_pattern/\n")

    # Return both workspace and paths for tests that need to check .oyaignore
    return {"workspace": workspace, "paths": paths}


@pytest.fixture
async def client():
    """Create async test client."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client


# ============================================================================
# Basic Removal Tests
# ============================================================================


async def test_oyaignore_removal_basic(client, temp_workspace_with_oyaignore):
    """Test that removals parameter removes patterns from .oyaignore."""
    response = await client.post(
        "/api/repos/oyaignore",
        json={
            "directories": [],
            "files": [],
            "removals": ["excluded_dir/", "old_pattern/"],
        },
    )

    assert response.status_code == 200
    data = response.json()

    # Check removals are reported
    assert "removed" in data
    assert "total_removed" in data
    assert len(data["removed"]) == 2
    assert data["total_removed"] == 2
    assert "excluded_dir/" in data["removed"]
    assert "old_pattern/" in data["removed"]

    # Verify file content
    oyaignore_content = temp_workspace_with_oyaignore["paths"].oyaignore.read_text()
    assert "excluded_file.txt" in oyaignore_content
    assert "excluded_dir" not in oyaignore_content
    assert "old_pattern" not in oyaignore_content


async def test_oyaignore_removal_normalizes_trailing_slash(client, temp_workspace_with_oyaignore):
    """Test that removal patterns are normalized (with/without trailing slash)."""
    # Remove pattern without trailing slash, but it exists with trailing slash
    response = await client.post(
        "/api/repos/oyaignore",
        json={
            "directories": [],
            "files": [],
            "removals": ["excluded_dir"],  # No trailing slash
        },
    )

    assert response.status_code == 200
    data = response.json()

    # Should match the entry with trailing slash
    assert len(data["removed"]) == 1
    assert "excluded_dir/" in data["removed"]

    # Verify file content
    oyaignore_content = temp_workspace_with_oyaignore["paths"].oyaignore.read_text()
    assert "excluded_dir" not in oyaignore_content
    assert "excluded_file.txt" in oyaignore_content


async def test_oyaignore_removal_file_pattern(client, temp_workspace_with_oyaignore):
    """Test that file patterns (without trailing slash) can be removed."""
    response = await client.post(
        "/api/repos/oyaignore",
        json={
            "directories": [],
            "files": [],
            "removals": ["excluded_file.txt"],
        },
    )

    assert response.status_code == 200
    data = response.json()

    # Should remove the file pattern
    assert len(data["removed"]) == 1
    assert "excluded_file.txt" in data["removed"]

    # Verify file content
    oyaignore_content = temp_workspace_with_oyaignore["paths"].oyaignore.read_text()
    assert "excluded_file.txt" not in oyaignore_content
    assert "excluded_dir/" in oyaignore_content


async def test_oyaignore_removal_nonexistent_pattern(client, temp_workspace_with_oyaignore):
    """Test that removing a nonexistent pattern does not error."""
    response = await client.post(
        "/api/repos/oyaignore",
        json={
            "directories": [],
            "files": [],
            "removals": ["nonexistent_pattern/"],
        },
    )

    assert response.status_code == 200
    data = response.json()

    # Should report no removals (pattern didn't exist)
    assert len(data["removed"]) == 0
    assert data["total_removed"] == 0

    # Verify file content unchanged (except possibly whitespace)
    oyaignore_content = temp_workspace_with_oyaignore["paths"].oyaignore.read_text()
    assert "excluded_dir/" in oyaignore_content
    assert "excluded_file.txt" in oyaignore_content
    assert "old_pattern/" in oyaignore_content


# ============================================================================
# Removal + Addition Combined Tests
# ============================================================================


async def test_oyaignore_removal_then_addition(client, temp_workspace_with_oyaignore):
    """Test that removals are processed before additions."""
    response = await client.post(
        "/api/repos/oyaignore",
        json={
            "directories": ["new_dir"],
            "files": ["new_file.txt"],
            "removals": ["excluded_dir/", "old_pattern/"],
        },
    )

    assert response.status_code == 200
    data = response.json()

    # Check both additions and removals
    assert len(data["removed"]) == 2
    assert data["total_removed"] == 2
    assert "new_dir/" in data["added_directories"]
    assert "new_file.txt" in data["added_files"]
    assert data["total_added"] == 2

    # Verify file content
    oyaignore_content = temp_workspace_with_oyaignore["paths"].oyaignore.read_text()
    assert "excluded_dir" not in oyaignore_content
    assert "old_pattern" not in oyaignore_content
    assert "excluded_file.txt" in oyaignore_content  # Not removed
    assert "new_dir/" in oyaignore_content  # Added
    assert "new_file.txt" in oyaignore_content  # Added


async def test_oyaignore_removal_and_readd_same_pattern(client, temp_workspace_with_oyaignore):
    """Test that removing and re-adding the same pattern works."""
    # Remove and then add the same pattern
    response = await client.post(
        "/api/repos/oyaignore",
        json={
            "directories": ["excluded_dir"],  # Re-add
            "files": [],
            "removals": ["excluded_dir/"],  # Remove first
        },
    )

    assert response.status_code == 200
    data = response.json()

    # Should remove and then add (net result: pattern is present)
    assert "excluded_dir/" in data["removed"]
    assert "excluded_dir/" in data["added_directories"]

    # Verify file content - pattern should be present
    oyaignore_content = temp_workspace_with_oyaignore["paths"].oyaignore.read_text()
    assert "excluded_dir/" in oyaignore_content


# ============================================================================
# Response Schema Tests
# ============================================================================


async def test_oyaignore_response_schema_with_removals(client, temp_workspace_with_oyaignore):
    """Test that response schema includes all required fields."""
    response = await client.post(
        "/api/repos/oyaignore",
        json={
            "directories": ["new_dir"],
            "files": ["new_file.txt"],
            "removals": ["excluded_dir/"],
        },
    )

    assert response.status_code == 200
    data = response.json()

    # Check all fields are present
    assert "added_directories" in data
    assert "added_files" in data
    assert "removed" in data
    assert "total_added" in data
    assert "total_removed" in data

    # Check types
    assert isinstance(data["added_directories"], list)
    assert isinstance(data["added_files"], list)
    assert isinstance(data["removed"], list)
    assert isinstance(data["total_added"], int)
    assert isinstance(data["total_removed"], int)


async def test_oyaignore_empty_removals_field(client, temp_workspace_with_oyaignore):
    """Test that empty removals field works correctly."""
    response = await client.post(
        "/api/repos/oyaignore",
        json={
            "directories": ["new_dir"],
            "files": [],
            "removals": [],
        },
    )

    assert response.status_code == 200
    data = response.json()

    # Should have empty removed list
    assert data["removed"] == []
    assert data["total_removed"] == 0

    # Additions should work normally
    assert "new_dir/" in data["added_directories"]


async def test_oyaignore_default_removals_field(client, temp_workspace_with_oyaignore):
    """Test that omitting removals field defaults to empty list."""
    response = await client.post(
        "/api/repos/oyaignore",
        json={
            "directories": ["new_dir"],
            "files": [],
            # removals field omitted
        },
    )

    assert response.status_code == 200
    data = response.json()

    # Should have empty removed list (default)
    assert data["removed"] == []
    assert data["total_removed"] == 0


# ============================================================================
# Edge Cases
# ============================================================================


async def test_oyaignore_removal_preserves_comments(client, temp_workspace_with_oyaignore):
    """Test that removals preserve comments in .oyaignore."""
    # Add comments to the file
    oyaignore_path = temp_workspace_with_oyaignore["paths"].oyaignore
    oyaignore_path.write_text(
        "# Header comment\nexcluded_dir/\n# Another comment\nexcluded_file.txt\nold_pattern/\n"
    )

    response = await client.post(
        "/api/repos/oyaignore",
        json={
            "directories": [],
            "files": [],
            "removals": ["excluded_dir/"],
        },
    )

    assert response.status_code == 200

    # Verify comments are preserved
    content = oyaignore_path.read_text()
    assert "# Header comment" in content
    assert "# Another comment" in content
    assert "excluded_dir" not in content


async def test_oyaignore_removal_no_oyaignore_file(client, setup_active_repo):
    """Test removals when .oyaignore doesn't exist."""
    workspace = setup_active_repo["source_path"]
    workspace.mkdir(parents=True, exist_ok=True)

    # Initialize git repo
    subprocess.run(["git", "init"], cwd=workspace, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"], cwd=workspace, capture_output=True
    )
    subprocess.run(["git", "config", "user.name", "Test"], cwd=workspace, capture_output=True)
    (workspace / "README.md").write_text("# Test")
    subprocess.run(["git", "add", "."], cwd=workspace, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=workspace, capture_output=True)

    # No .oyaignore file

    response = await client.post(
        "/api/repos/oyaignore",
        json={
            "directories": [],
            "files": [],
            "removals": ["some_pattern/"],
        },
    )

    assert response.status_code == 200
    data = response.json()

    # Should report no removals (file didn't exist)
    assert data["removed"] == []
    assert data["total_removed"] == 0

    # File should not be created if nothing to write
    # File may or may not exist depending on implementation
    # If it exists, it should be empty or not contain the removal pattern


async def test_oyaignore_removal_all_patterns(client, temp_workspace_with_oyaignore):
    """Test removing all patterns from .oyaignore."""
    response = await client.post(
        "/api/repos/oyaignore",
        json={
            "directories": [],
            "files": [],
            "removals": ["excluded_dir/", "excluded_file.txt", "old_pattern/"],
        },
    )

    assert response.status_code == 200
    data = response.json()

    # All patterns should be removed
    assert len(data["removed"]) == 3
    assert data["total_removed"] == 3

    # File should be empty (or contain only whitespace/newlines)
    oyaignore_path = temp_workspace_with_oyaignore["paths"].oyaignore
    content = oyaignore_path.read_text()
    # Only whitespace should remain
    assert content.strip() == ""


# ============================================================================
# Property-Based Tests
# ============================================================================


# Strategy for generating valid patterns
pattern_strategy = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyz0123456789_-./",
    min_size=1,
    max_size=20,
).filter(lambda x: not x.startswith(".") and x.strip() == x and not x.startswith("/"))


class TestOyaignoreRemovalsPropertyTests:
    """Property-based tests for oyaignore removals."""

    @pytest.fixture
    def temp_workspace_property(self, setup_active_repo):
        """Create a temporary workspace for property tests using active repo fixture."""
        workspace = setup_active_repo["source_path"]
        paths = setup_active_repo["paths"]
        workspace.mkdir(parents=True, exist_ok=True)

        subprocess.run(["git", "init"], cwd=workspace, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"], cwd=workspace, capture_output=True
        )
        subprocess.run(["git", "config", "user.name", "Test"], cwd=workspace, capture_output=True)

        (workspace / "README.md").write_text("# Test")
        subprocess.run(["git", "add", "."], cwd=workspace, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initial"], cwd=workspace, capture_output=True)

        return {"workspace": workspace, "paths": paths}

    @given(
        existing_patterns=st.lists(pattern_strategy, min_size=1, max_size=10, unique=True),
        patterns_to_remove=st.lists(pattern_strategy, min_size=0, max_size=5, unique=True),
    )
    @hypothesis_settings(
        max_examples=50,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_removal_removes_only_specified_patterns_property(
        self, temp_workspace_property, existing_patterns, patterns_to_remove
    ):
        """Property: Removing patterns removes only those specified, leaving others intact."""
        import asyncio
        from httpx import ASGITransport, AsyncClient
        from oya.main import app

        oyaignore_path = temp_workspace_property["paths"].oyaignore

        # Normalize existing patterns (directories get trailing slash)
        normalized_existing = []
        for p in existing_patterns:
            if "/" not in p or not p.endswith("/"):
                # Treat as file
                normalized_existing.append(p)
            else:
                normalized_existing.append(p)

        # Write existing patterns
        oyaignore_path.write_text("\n".join(normalized_existing) + "\n")

        # Make API call to remove patterns
        async def make_request():
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                return await client.post(
                    "/api/repos/oyaignore",
                    json={"directories": [], "files": [], "removals": patterns_to_remove},
                )

        response = asyncio.run(make_request())
        assert response.status_code == 200

        # Read resulting file
        result_content = oyaignore_path.read_text()
        result_lines = [
            line.strip()
            for line in result_content.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]

        # Property: Patterns that were requested to be removed and existed should not be present
        # (accounting for normalization)
        for removal in patterns_to_remove:
            removal_normalized = removal.rstrip("/")
            # Check both with and without trailing slash
            patterns_to_check = [removal, removal_normalized, removal_normalized + "/"]
            for pattern in patterns_to_check:
                if pattern in normalized_existing:
                    assert pattern not in result_lines, (
                        f"Pattern '{pattern}' should have been removed"
                    )

        # Property: Patterns not requested for removal should still be present
        for pattern in normalized_existing:
            was_removed = False
            for removal in patterns_to_remove:
                removal_normalized = removal.rstrip("/")
                if (
                    pattern == removal
                    or pattern == removal_normalized
                    or pattern == removal_normalized + "/"
                ):
                    was_removed = True
                    break
            if not was_removed:
                assert pattern in result_lines, f"Pattern '{pattern}' should NOT have been removed"
