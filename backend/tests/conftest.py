"""Shared pytest fixtures for all tests.

These fixtures properly clean up resources to prevent file descriptor leaks.
"""

import gc

import pytest

from oya.db.connection import Database
from oya.vectorstore.store import VectorStore


@pytest.fixture(autouse=True)
def cleanup_after_test():
    """Clean up resources after each test to prevent file descriptor leaks.

    This runs automatically after every test to help garbage collect
    any lingering ChromaDB or SQLite connections.
    """
    yield
    # Force garbage collection to release file handles
    gc.collect()


@pytest.fixture
def temp_vectorstore(tmp_path):
    """Create a temporary vector store that cleans up properly.

    This fixture should be used instead of creating VectorStore instances
    directly in tests to ensure ChromaDB connections are released.
    """
    index_path = tmp_path / "index"
    index_path.mkdir()
    store = VectorStore(index_path)
    yield store
    # Clean up to release file handles
    store.close()
    gc.collect()


@pytest.fixture
def temp_db(tmp_path):
    """Create a temporary database with FTS table that cleans up properly.

    This fixture should be used instead of creating Database instances
    directly in tests to ensure SQLite connections are released.
    """
    db_path = tmp_path / "test.db"
    db = Database(db_path)
    # Create FTS table matching production schema
    db.executescript("""
        CREATE VIRTUAL TABLE IF NOT EXISTS fts_content USING fts5(
            content,
            title,
            path UNINDEXED,
            type UNINDEXED,
            tokenize='porter'
        );
    """)
    yield db
    # Clean up to release file handles
    db.close()
    gc.collect()


@pytest.fixture
def temp_db_path(tmp_path):
    """Create a temporary database path (for tests that manage their own connection)."""
    return tmp_path / "test.db"


@pytest.fixture
def setup_active_repo(tmp_path, monkeypatch):
    """Set up a temporary active repository for tests.

    This fixture:
    1. Creates a temp OYA_DATA_DIR
    2. Registers a test repo
    3. Sets it as active
    4. Clears caches

    Yields:
        dict with 'data_dir', 'local_path', 'repo_id', and 'wiki_path'
    """
    from oya.config import load_settings
    from oya.api.deps import get_settings, _reset_db_instance
    from oya.db.repo_registry import RepoRegistry

    # Set up temp data dir
    data_dir = tmp_path / "oya"
    data_dir.mkdir()
    monkeypatch.setenv("OYA_DATA_DIR", str(data_dir))

    # Clear caches before setting up
    load_settings.cache_clear()
    get_settings.cache_clear()
    _reset_db_instance()

    # Create a test repo in the registry
    settings = load_settings()
    registry = RepoRegistry(settings.repos_db_path)
    try:
        local_path = "test/repo"
        repo_id = registry.add(
            origin_url="file:///test/repo",
            display_name="Test Repo",
            local_path=local_path,
            source_type="local",
        )
        # Set as active
        registry.set_setting("active_repo_id", str(repo_id))
    finally:
        registry.close()

    # Set up wiki directory structure
    from oya.repo.repo_paths import RepoPaths

    paths = RepoPaths(data_dir, local_path)
    paths.wiki_dir.mkdir(parents=True, exist_ok=True)
    paths.meta_dir.mkdir(parents=True, exist_ok=True)

    # Re-clear caches so they pick up the new state
    load_settings.cache_clear()
    get_settings.cache_clear()
    _reset_db_instance()

    yield {
        "data_dir": data_dir,
        "local_path": local_path,
        "repo_id": repo_id,
        "wiki_path": paths.wiki_dir,
        "source_path": paths.source,
        "paths": paths,
    }

    # Cleanup
    _reset_db_instance()
    load_settings.cache_clear()
    get_settings.cache_clear()
