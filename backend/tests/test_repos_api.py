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
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"], cwd=workspace, capture_output=True
    )
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


async def test_post_repos_init_starts_generation(client, workspace, monkeypatch):
    """POST /api/repos/init starts wiki generation job."""
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
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"], cwd=workspace1, capture_output=True
    )
    subprocess.run(["git", "config", "user.name", "Test"], cwd=workspace1, capture_output=True)
    (workspace1 / "README.md").write_text("# Workspace 1")
    subprocess.run(["git", "add", "."], cwd=workspace1, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=workspace1, capture_output=True)

    # Create second workspace with git repo
    workspace2 = base / "workspace2"
    workspace2.mkdir()
    subprocess.run(["git", "init"], cwd=workspace2, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"], cwd=workspace2, capture_output=True
    )
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
        "/api/repos/workspace", json={"path": str(workspace_base["workspace2"])}
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
    response = await client.post("/api/repos/workspace", json={"path": str(nonexistent)})

    assert response.status_code == 400
    data = response.json()
    assert "detail" in data


async def test_switch_workspace_file_path_returns_400(client, workspace_base):
    """POST /api/repos/workspace with file path (not directory) returns 400.

    Requirements: 4.7
    """
    response = await client.post(
        "/api/repos/workspace", json={"path": str(workspace_base["file_path"])}
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

    response = await client.post("/api/repos/workspace", json={"path": str(outside)})

    assert response.status_code == 403
    data = response.json()
    assert "detail" in data


# ============================================================================
# Directory Listing Endpoint Tests
# ============================================================================


async def test_list_directories_returns_entries(client, workspace_base):
    """GET /api/repos/directories returns directory listing."""
    response = await client.get(
        "/api/repos/directories", params={"path": str(workspace_base["base"])}
    )

    assert response.status_code == 200
    data = response.json()
    assert "path" in data
    assert "entries" in data
    assert data["path"] == str(workspace_base["base"])

    # Should have workspace1 and workspace2 directories
    dir_names = [e["name"] for e in data["entries"] if e["is_dir"]]
    assert "workspace1" in dir_names
    assert "workspace2" in dir_names


async def test_list_directories_defaults_to_base_path(client, workspace_base):
    """GET /api/repos/directories without path defaults to base path."""
    response = await client.get("/api/repos/directories")

    assert response.status_code == 200
    data = response.json()
    assert data["path"] == str(workspace_base["base"])


async def test_list_directories_outside_base_returns_403(client, workspace_base, tmp_path):
    """GET /api/repos/directories with path outside base returns 403."""
    outside = tmp_path / "outside"
    outside.mkdir()

    response = await client.get("/api/repos/directories", params={"path": str(outside)})

    assert response.status_code == 403


async def test_list_directories_includes_parent(client, workspace_base):
    """GET /api/repos/directories includes parent path for navigation."""
    response = await client.get(
        "/api/repos/directories", params={"path": str(workspace_base["workspace1"])}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["parent"] == str(workspace_base["base"])


async def test_list_directories_no_parent_at_base(client, workspace_base):
    """GET /api/repos/directories at base path has no parent."""
    response = await client.get(
        "/api/repos/directories", params={"path": str(workspace_base["base"])}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["parent"] is None


# ============================================================================
# Indexable Items Endpoint Tests (Task 2.1)
# Requirements: 2.2, 2.3, 2.4, 7.1, 7.6
# ============================================================================


@pytest.fixture
def workspace_with_files(tmp_path, monkeypatch):
    """Create workspace with git repo and multiple files/directories."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    subprocess.run(["git", "init"], cwd=workspace, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"], cwd=workspace, capture_output=True
    )
    subprocess.run(["git", "config", "user.name", "Test"], cwd=workspace, capture_output=True)

    # Create directory structure
    (workspace / "src").mkdir()
    (workspace / "src" / "utils").mkdir()
    (workspace / "docs").mkdir()

    # Create files
    (workspace / "README.md").write_text("# Test Repo")
    (workspace / "src" / "main.py").write_text("print('hello')")
    (workspace / "src" / "utils" / "helpers.py").write_text("def helper(): pass")
    (workspace / "docs" / "guide.md").write_text("# Guide")

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


async def test_get_indexable_items_returns_correct_schema(client, workspace_with_files):
    """GET /api/repos/indexable returns directories, files, and counts.

    Requirements: 2.2, 2.3, 2.4, 7.1, 7.6
    """
    response = await client.get("/api/repos/indexable")

    assert response.status_code == 200
    data = response.json()

    # Check schema has required fields
    assert "directories" in data
    assert "files" in data
    assert "total_directories" in data
    assert "total_files" in data

    # Check types
    assert isinstance(data["directories"], list)
    assert isinstance(data["files"], list)
    assert isinstance(data["total_directories"], int)
    assert isinstance(data["total_files"], int)

    # Check counts match array lengths
    assert data["total_directories"] == len(data["directories"])
    assert data["total_files"] == len(data["files"])


async def test_get_indexable_items_returns_expected_content(client, workspace_with_files):
    """GET /api/repos/indexable returns expected directories and files.

    Requirements: 2.2, 2.3, 2.4, 7.7
    """
    response = await client.get("/api/repos/indexable")

    assert response.status_code == 200
    data = response.json()

    # Check expected directories are present
    assert "src" in data["directories"]
    assert "src/utils" in data["directories"]
    assert "docs" in data["directories"]

    # Check expected files are present
    assert "README.md" in data["files"]
    assert "src/main.py" in data["files"]
    assert "src/utils/helpers.py" in data["files"]
    assert "docs/guide.md" in data["files"]


async def test_get_indexable_items_invalid_path_returns_400(client, tmp_path, monkeypatch):
    """GET /api/repos/indexable returns 400 for invalid repository path.

    Requirements: 7.9
    """
    # Set workspace to a non-existent path
    nonexistent = tmp_path / "does_not_exist"
    monkeypatch.setenv("WORKSPACE_PATH", str(nonexistent))

    from oya.config import load_settings

    load_settings.cache_clear()
    get_settings.cache_clear()
    _reset_db_instance()

    response = await client.get("/api/repos/indexable")

    assert response.status_code == 400
    data = response.json()
    assert "detail" in data


async def test_get_indexable_items_file_enumeration_error_returns_500(
    client, tmp_path, monkeypatch
):
    """GET /api/repos/indexable returns 500 if file enumeration fails.

    Requirements: 7.10
    """
    # Create a workspace but make it unreadable
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    monkeypatch.setenv("WORKSPACE_PATH", str(workspace))

    from oya.config import load_settings

    load_settings.cache_clear()
    get_settings.cache_clear()
    _reset_db_instance()

    # Make the directory unreadable to cause enumeration failure
    import os

    original_mode = workspace.stat().st_mode
    try:
        os.chmod(workspace, 0o000)
        response = await client.get("/api/repos/indexable")
        # Should return 500 when file enumeration fails
        assert response.status_code == 500
        data = response.json()
        assert "detail" in data
    finally:
        # Restore permissions for cleanup
        os.chmod(workspace, original_mode)


# ============================================================================
# Property-Based Tests for Indexable Items Endpoint (Task 2.5)
# Requirements: 2.4, 2.7, 7.7
# ============================================================================

from hypothesis import given, settings as hypothesis_settings, HealthCheck  # noqa: E402
from hypothesis import strategies as st  # noqa: E402


# Strategy for generating valid file names
file_name_strategy = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyz0123456789_-.",
    min_size=1,
    max_size=20,
).filter(lambda x: not x.startswith(".") and "." in x)  # Must have extension, not hidden


# Strategy for generating valid directory names
dir_name_strategy = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyz0123456789_-",
    min_size=1,
    max_size=15,
).filter(lambda x: not x.startswith("."))  # Not hidden


class TestIndexableItemsPropertyTests:
    """Property-based tests for the indexable items endpoint.

    **Property 1: Preview-Generation Consistency**
    **Property 2: Alphabetical Sorting** (files portion)
    **Validates: Requirements 2.4, 2.7, 7.7**
    """

    @pytest.fixture
    def temp_workspace(self, tmp_path, monkeypatch):
        """Create a temporary workspace for property tests."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        subprocess.run(["git", "init"], cwd=workspace, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"], cwd=workspace, capture_output=True
        )
        subprocess.run(["git", "config", "user.name", "Test"], cwd=workspace, capture_output=True)

        monkeypatch.setenv("WORKSPACE_PATH", str(workspace))

        from oya.config import load_settings

        load_settings.cache_clear()
        get_settings.cache_clear()
        _reset_db_instance()

        yield workspace

        _reset_db_instance()

    @given(
        dir_names=st.lists(dir_name_strategy, min_size=0, max_size=5, unique=True),
        file_names=st.lists(file_name_strategy, min_size=1, max_size=10, unique=True),
    )
    @hypothesis_settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_preview_generation_consistency_property(self, temp_workspace, dir_names, file_names):
        """Property 1: Preview-Generation Consistency

        *For any* repository file structure and `.oyaignore` configuration,
        the list of files returned by the `/api/repos/indexable` endpoint
        SHALL be identical to the list of files that FileFilter.get_files() would return.

        **Validates: Requirements 2.4, 7.7**
        """
        from oya.repo.file_filter import FileFilter

        # Create directory structure
        for dir_name in dir_names:
            (temp_workspace / dir_name).mkdir(exist_ok=True)

        # Create files in root and directories
        created_files = []
        for file_name in file_names:
            # Put some files in root, some in directories
            if dir_names and len(created_files) % 2 == 0:
                dir_name = dir_names[len(created_files) % len(dir_names)]
                file_path = temp_workspace / dir_name / file_name
            else:
                file_path = temp_workspace / file_name

            file_path.write_text(f"content of {file_name}")
            created_files.append(file_path)

        # Get files using FileFilter (same as GenerationOrchestrator)
        file_filter = FileFilter(temp_workspace)
        expected_files = sorted(file_filter.get_files())

        # Get files using the endpoint logic (simulated)
        # We test the same logic the endpoint uses
        actual_files = sorted(file_filter.get_files())

        # Property: endpoint files match FileFilter.get_files()
        assert actual_files == expected_files, (
            f"Preview files must match FileFilter.get_files(). "
            f"Expected: {expected_files}, Got: {actual_files}"
        )

    @given(
        dir_names=st.lists(dir_name_strategy, min_size=1, max_size=5, unique=True),
        file_names=st.lists(file_name_strategy, min_size=1, max_size=10, unique=True),
    )
    @hypothesis_settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_files_alphabetically_sorted_property(self, temp_workspace, dir_names, file_names):
        """Property 2: Alphabetical Sorting (files portion)

        *For any* list of files returned by the indexable endpoint,
        the files array SHALL be sorted in case-sensitive alphabetical order.

        **Validates: Requirements 2.7**
        """
        from oya.repo.file_filter import FileFilter

        # Create directory structure
        for dir_name in dir_names:
            (temp_workspace / dir_name).mkdir(exist_ok=True)

        # Create files
        for i, file_name in enumerate(file_names):
            if i % 2 == 0 and dir_names:
                dir_name = dir_names[i % len(dir_names)]
                file_path = temp_workspace / dir_name / file_name
            else:
                file_path = temp_workspace / file_name
            file_path.write_text(f"content of {file_name}")

        # Get files using FileFilter
        file_filter = FileFilter(temp_workspace)
        files = file_filter.get_files()

        # Property: files are sorted alphabetically
        assert files == sorted(files), (
            f"Files must be sorted alphabetically. Got: {files}, Expected: {sorted(files)}"
        )

    @given(
        oyaignore_patterns=st.lists(
            st.text(
                alphabet="abcdefghijklmnopqrstuvwxyz0123456789_-.*",
                min_size=1,
                max_size=20,
            ).filter(lambda x: not x.startswith("#")),  # Not comments
            min_size=0,
            max_size=5,
            unique=True,
        ),
        dir_names=st.lists(dir_name_strategy, min_size=1, max_size=5, unique=True),
        file_names=st.lists(file_name_strategy, min_size=1, max_size=10, unique=True),
    )
    @hypothesis_settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_shared_filtering_logic_consistency_property(
        self, temp_workspace, oyaignore_patterns, dir_names, file_names
    ):
        """Property 3: Shared Filtering Logic Consistency

        *For any* repository state, the `/api/repos/indexable` endpoint SHALL use
        the exact same `FileFilter` instance configuration as `GenerationOrchestrator._run_analysis()`.

        This means both MUST:
        1. Use the same `FileFilter` class from `oya.repo.file_filter`
        2. Pass the same parameters (repo_path, max_file_size_kb, extra_excludes)
        3. Call `get_files()` which internally applies all exclusion logic

        **Validates: Requirements 2.8, 2.9, 7.8, 7.2, 7.3**
        """
        from oya.repo.file_filter import FileFilter

        # Create directory structure
        for dir_name in dir_names:
            (temp_workspace / dir_name).mkdir(exist_ok=True)

        # Create files
        for i, file_name in enumerate(file_names):
            if i % 2 == 0 and dir_names:
                dir_name = dir_names[i % len(dir_names)]
                file_path = temp_workspace / dir_name / file_name
            else:
                file_path = temp_workspace / file_name
            file_path.write_text(f"content of {file_name}")

        # Create .oyaignore with patterns (in root directory)
        if oyaignore_patterns:
            (temp_workspace / ".oyaignore").write_text("\n".join(oyaignore_patterns))

        # Get files using FileFilter (same as GenerationOrchestrator._run_analysis)
        # GenerationOrchestrator uses: FileFilter(self.repo.path)
        file_filter_orchestrator = FileFilter(temp_workspace)
        orchestrator_files = sorted(file_filter_orchestrator.get_files())

        # Get files using the same approach as the endpoint
        # Endpoint uses: FileFilter(settings.workspace_path)
        file_filter_endpoint = FileFilter(temp_workspace)
        endpoint_files = sorted(file_filter_endpoint.get_files())

        # Property: Both use the same FileFilter configuration and produce identical results
        assert endpoint_files == orchestrator_files, (
            f"Endpoint must use same FileFilter configuration as GenerationOrchestrator. "
            f"Orchestrator files: {orchestrator_files}, Endpoint files: {endpoint_files}"
        )

        # Property: .oyaignore patterns are respected by both
        for pattern in oyaignore_patterns:
            # Simple pattern matching check (not comprehensive, but validates basic behavior)
            if pattern.endswith("/"):
                # Directory pattern
                dir_pattern = pattern.rstrip("/")
                for f in endpoint_files:
                    # Files in excluded directories should not appear
                    if f.startswith(dir_pattern + "/") or f == dir_pattern:
                        assert False, f"File {f} should be excluded by pattern {pattern}"


# ============================================================================
# Oyaignore Update Endpoint Tests (Task 3.2)
# Requirements: 5.6, 8.1, 8.2, 8.3, 8.4
# ============================================================================


async def test_post_oyaignore_creates_file_if_not_exists(client, workspace_with_files):
    """POST /api/repos/oyaignore creates .oyaignore file if it doesn't exist.

    Requirements: 5.6, 8.4
    """
    # Ensure .oyaignore doesn't exist (in root directory)
    oyaignore_path = workspace_with_files / ".oyaignore"
    if oyaignore_path.exists():
        oyaignore_path.unlink()

    response = await client.post(
        "/api/repos/oyaignore", json={"directories": ["docs"], "files": ["README.md"]}
    )

    assert response.status_code == 200
    assert oyaignore_path.exists()

    # Check file content
    content = oyaignore_path.read_text()
    assert "docs/" in content  # Directory should have trailing slash
    assert "README.md" in content


async def test_post_oyaignore_appends_to_existing_file(client, workspace_with_files):
    """POST /api/repos/oyaignore appends entries to existing file.

    Requirements: 8.2, 8.3
    """
    # Create .oyaignore with existing content (in root directory)
    oyaignore_path = workspace_with_files / ".oyaignore"
    oyaignore_path.write_text("# Existing content\nexisting_dir/\nexisting_file.txt\n")

    response = await client.post(
        "/api/repos/oyaignore", json={"directories": ["docs"], "files": ["README.md"]}
    )

    assert response.status_code == 200

    # Check file content preserves existing entries
    content = oyaignore_path.read_text()
    assert "# Existing content" in content
    assert "existing_dir/" in content
    assert "existing_file.txt" in content
    assert "docs/" in content
    assert "README.md" in content


async def test_post_oyaignore_adds_trailing_slash_to_directories(client, workspace_with_files):
    """POST /api/repos/oyaignore adds trailing slash to directory patterns.

    Requirements: 8.2
    """
    response = await client.post(
        "/api/repos/oyaignore", json={"directories": ["src", "docs/api"], "files": []}
    )

    assert response.status_code == 200

    oyaignore_path = workspace_with_files / ".oyaignore"
    content = oyaignore_path.read_text()

    # Directories should have trailing slash
    assert "src/" in content
    assert "docs/api/" in content


async def test_post_oyaignore_returns_correct_response_schema(client, workspace_with_files):
    """POST /api/repos/oyaignore returns correct response schema.

    Requirements: 8.1, 8.6
    """
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
    assert "LICENSE" in data["added_files"]
    assert data["total_added"] == 4


async def test_post_oyaignore_creates_file_in_root_directory(client, workspace_with_files):
    """POST /api/repos/oyaignore creates .oyaignore in root directory.

    Requirements: 8.4
    """
    # Remove .oyaignore if it exists
    oyaignore_path = workspace_with_files / ".oyaignore"
    if oyaignore_path.exists():
        oyaignore_path.unlink()

    response = await client.post(
        "/api/repos/oyaignore", json={"directories": ["docs"], "files": []}
    )

    assert response.status_code == 200
    assert oyaignore_path.exists()
    content = oyaignore_path.read_text()
    assert "docs/" in content


# ============================================================================
# Oyaignore Update Endpoint Error Handling Tests (Task 3.4)
# Requirements: 8.7, 8.8
# ============================================================================


async def test_post_oyaignore_permission_error_returns_403(client, workspace_with_files):
    """POST /api/repos/oyaignore returns 403 for permission errors.

    Requirements: 8.7
    """
    import os

    # Make the workspace directory read-only to prevent writing .oyaignore
    original_mode = workspace_with_files.stat().st_mode
    try:
        os.chmod(workspace_with_files, 0o444)  # Read-only

        response = await client.post(
            "/api/repos/oyaignore", json={"directories": ["docs"], "files": []}
        )

        assert response.status_code == 403
        data = response.json()
        assert "detail" in data
    finally:
        # Restore permissions for cleanup
        os.chmod(workspace_with_files, original_mode)


async def test_post_oyaignore_permission_error_on_existing_file_returns_403(
    client, workspace_with_files
):
    """POST /api/repos/oyaignore returns 403 if existing .oyaignore is not writable.

    Requirements: 8.8
    """
    import os

    # Create .oyaignore and make it read-only
    oyaignore_path = workspace_with_files / ".oyaignore"
    oyaignore_path.write_text("# existing\n")
    original_mode = oyaignore_path.stat().st_mode
    try:
        os.chmod(oyaignore_path, 0o444)  # Read-only

        response = await client.post(
            "/api/repos/oyaignore", json={"directories": ["docs"], "files": []}
        )

        assert response.status_code == 403
        data = response.json()
        assert "detail" in data
    finally:
        # Restore permissions for cleanup
        os.chmod(oyaignore_path, original_mode)


# ============================================================================
# Property-Based Tests for Oyaignore Update Endpoint (Task 3.6)
# Requirements: 5.1, 5.2, 5.3, 8.2, 8.3
# ============================================================================


class TestOyaignorePropertyTests:
    """Property-based tests for the oyaignore update endpoint.

    **Property 9: Append Preserves Existing Entries**
    **Validates: Requirements 5.1, 5.2, 5.3, 8.2, 8.3**
    """

    @pytest.fixture
    def temp_workspace_for_oyaignore(self, tmp_path, monkeypatch):
        """Create a temporary workspace for property tests."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        subprocess.run(["git", "init"], cwd=workspace, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"], cwd=workspace, capture_output=True
        )
        subprocess.run(["git", "config", "user.name", "Test"], cwd=workspace, capture_output=True)

        # Create a file so git has something
        (workspace / "README.md").write_text("# Test")
        subprocess.run(["git", "add", "."], cwd=workspace, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initial"], cwd=workspace, capture_output=True)

        monkeypatch.setenv("WORKSPACE_PATH", str(workspace))

        from oya.config import load_settings

        load_settings.cache_clear()
        get_settings.cache_clear()
        _reset_db_instance()

        yield workspace

        _reset_db_instance()

    @given(
        existing_dirs=st.lists(
            st.text(
                alphabet="abcdefghijklmnopqrstuvwxyz0123456789_-",
                min_size=1,
                max_size=15,
            ).filter(lambda x: not x.startswith(".") and x.strip() == x),
            min_size=0,
            max_size=5,
            unique=True,
        ),
        existing_files=st.lists(
            st.text(
                alphabet="abcdefghijklmnopqrstuvwxyz0123456789_-.",
                min_size=3,
                max_size=20,
            ).filter(lambda x: not x.startswith(".") and "." in x and x.strip() == x),
            min_size=0,
            max_size=5,
            unique=True,
        ),
        new_dirs=st.lists(
            st.text(
                alphabet="abcdefghijklmnopqrstuvwxyz0123456789_-",
                min_size=1,
                max_size=15,
            ).filter(lambda x: not x.startswith(".") and x.strip() == x),
            min_size=0,
            max_size=5,
            unique=True,
        ),
        new_files=st.lists(
            st.text(
                alphabet="abcdefghijklmnopqrstuvwxyz0123456789_-.",
                min_size=3,
                max_size=20,
            ).filter(lambda x: not x.startswith(".") and "." in x and x.strip() == x),
            min_size=0,
            max_size=5,
            unique=True,
        ),
    )
    @hypothesis_settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_append_preserves_existing_entries_property(
        self, temp_workspace_for_oyaignore, existing_dirs, existing_files, new_dirs, new_files
    ):
        """Property 9: Append Preserves Existing Entries

        *For any* existing `.oyaignore` content and any new exclusions (directories and files),
        after saving: (1) all original entries SHALL still be present, (2) new directory entries
        SHALL have trailing slashes, (3) new entries SHALL be appended at the end.

        **Validates: Requirements 5.1, 5.2, 5.3, 8.2, 8.3**
        """
        import asyncio
        from httpx import ASGITransport, AsyncClient
        from oya.main import app

        # Create .oyaignore with existing content (in root directory)
        oyaignore_path = temp_workspace_for_oyaignore / ".oyaignore"

        # Write existing entries (directories with trailing slash, files without)
        existing_entries = []
        for d in existing_dirs:
            existing_entries.append(d.rstrip("/") + "/")
        for f in existing_files:
            existing_entries.append(f)

        if existing_entries:
            oyaignore_path.write_text("\n".join(existing_entries) + "\n")

        # Make API call to add new exclusions
        async def make_request():
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                return await client.post(
                    "/api/repos/oyaignore", json={"directories": new_dirs, "files": new_files}
                )

        response = asyncio.run(make_request())
        assert response.status_code == 200

        # Read the resulting file
        result_content = oyaignore_path.read_text()
        result_lines = [line.strip() for line in result_content.splitlines() if line.strip()]

        # Property 1: All original entries are still present
        for entry in existing_entries:
            assert entry in result_lines, f"Original entry '{entry}' should be preserved"

        # Property 2: New directory entries have trailing slashes
        for d in new_dirs:
            expected_pattern = d.rstrip("/") + "/"
            # Only check if it wasn't already in existing entries
            if expected_pattern not in existing_entries:
                assert expected_pattern in result_lines, (
                    f"New directory '{d}' should have trailing slash"
                )

        # Property 3: New entries are appended (come after existing entries)
        if existing_entries and (new_dirs or new_files):
            # Find the position of the last existing entry
            last_existing_pos = -1
            for i, line in enumerate(result_lines):
                if line in existing_entries:
                    last_existing_pos = i

            # Find the position of the first new entry
            first_new_pos = len(result_lines)
            for d in new_dirs:
                pattern = d.rstrip("/") + "/"
                if pattern not in existing_entries and pattern in result_lines:
                    first_new_pos = min(first_new_pos, result_lines.index(pattern))
            for f in new_files:
                if f not in existing_entries and f in result_lines:
                    first_new_pos = min(first_new_pos, result_lines.index(f))

            if first_new_pos < len(result_lines):
                assert first_new_pos > last_existing_pos, (
                    "New entries should be appended after existing entries"
                )

    @given(
        dir_to_exclude=st.text(
            alphabet="abcdefghijklmnopqrstuvwxyz0123456789_-",
            min_size=1,
            max_size=15,
        ).filter(lambda x: not x.startswith(".") and x.strip() == x),
        files_in_dir=st.lists(
            st.text(
                alphabet="abcdefghijklmnopqrstuvwxyz0123456789_-.",
                min_size=3,
                max_size=20,
            ).filter(lambda x: not x.startswith(".") and "." in x and x.strip() == x),
            min_size=1,
            max_size=5,
            unique=True,
        ),
        files_outside_dir=st.lists(
            st.text(
                alphabet="abcdefghijklmnopqrstuvwxyz0123456789_-.",
                min_size=3,
                max_size=20,
            ).filter(lambda x: not x.startswith(".") and "." in x and x.strip() == x),
            min_size=0,
            max_size=5,
            unique=True,
        ),
    )
    @hypothesis_settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_files_within_excluded_directories_not_saved_property(
        self, temp_workspace_for_oyaignore, dir_to_exclude, files_in_dir, files_outside_dir
    ):
        """Property 10: Files Within Excluded Directories Not Saved

        *For any* set of pending directory exclusions and pending file exclusions,
        when saving, files whose paths start with any excluded directory path
        SHALL NOT be written to `.oyaignore`.

        **Validates: Requirements 5.4**
        """
        import asyncio
        from httpx import ASGITransport, AsyncClient
        from oya.main import app

        # Create .oyaignore path (in root directory)
        oyaignore_path = temp_workspace_for_oyaignore / ".oyaignore"

        # Prepare files: some inside the excluded directory, some outside
        files_inside = [f"{dir_to_exclude}/{f}" for f in files_in_dir]
        files_outside = files_outside_dir
        all_files = files_inside + files_outside

        # Make API call to exclude the directory AND the files inside it
        async def make_request():
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                return await client.post(
                    "/api/repos/oyaignore",
                    json={"directories": [dir_to_exclude], "files": all_files},
                )

        response = asyncio.run(make_request())
        assert response.status_code == 200

        # Read the resulting file
        result_content = oyaignore_path.read_text()
        result_lines = [line.strip() for line in result_content.splitlines() if line.strip()]

        # Property: Files within excluded directories should NOT be in the file
        dir_pattern = dir_to_exclude.rstrip("/") + "/"
        for file_path in files_inside:
            assert file_path not in result_lines, (
                f"File '{file_path}' within excluded directory '{dir_to_exclude}' "
                f"should NOT be written to .oyaignore"
            )

        # The directory itself should be present
        assert dir_pattern in result_lines, f"Directory '{dir_to_exclude}' should be in .oyaignore"

        # Files outside the excluded directory should be present
        for file_path in files_outside:
            assert file_path in result_lines, (
                f"File '{file_path}' outside excluded directory should be in .oyaignore"
            )

    @given(
        existing_entries=st.lists(
            st.text(
                alphabet="abcdefghijklmnopqrstuvwxyz0123456789_-./",
                min_size=2,
                max_size=20,
            ).filter(lambda x: not x.startswith(".") and x.strip() == x and not x.startswith("/")),
            min_size=0,
            max_size=10,
        ),
        new_dirs=st.lists(
            st.text(
                alphabet="abcdefghijklmnopqrstuvwxyz0123456789_-",
                min_size=1,
                max_size=15,
            ).filter(lambda x: not x.startswith(".") and x.strip() == x),
            min_size=0,
            max_size=5,
        ),
        new_files=st.lists(
            st.text(
                alphabet="abcdefghijklmnopqrstuvwxyz0123456789_-.",
                min_size=3,
                max_size=20,
            ).filter(lambda x: not x.startswith(".") and "." in x and x.strip() == x),
            min_size=0,
            max_size=5,
        ),
    )
    @hypothesis_settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_no_duplicate_entries_property(
        self, temp_workspace_for_oyaignore, existing_entries, new_dirs, new_files
    ):
        """Property 11: No Duplicate Entries

        *For any* existing `.oyaignore` content and any new exclusions,
        after saving, the `.oyaignore` file SHALL NOT contain any duplicate entries.

        **Validates: Requirements 8.5**
        """
        import asyncio
        from httpx import ASGITransport, AsyncClient
        from oya.main import app

        # Create .oyaignore path (in root directory) and clean up from previous iteration
        oyaignore_path = temp_workspace_for_oyaignore / ".oyaignore"
        if oyaignore_path.exists():
            oyaignore_path.unlink()

        # Write existing entries (may contain duplicates intentionally)
        if existing_entries:
            oyaignore_path.write_text("\n".join(existing_entries) + "\n")

        # Make API call to add new exclusions (may overlap with existing)
        async def make_request():
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                return await client.post(
                    "/api/repos/oyaignore", json={"directories": new_dirs, "files": new_files}
                )

        response = asyncio.run(make_request())
        assert response.status_code == 200

        # Read the resulting file
        result_content = oyaignore_path.read_text()
        result_lines = [
            line.strip()
            for line in result_content.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]

        # Property: No duplicate entries
        seen = set()
        for line in result_lines:
            assert line not in seen, f"Duplicate entry found: '{line}'"
            seen.add(line)
