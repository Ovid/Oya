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
