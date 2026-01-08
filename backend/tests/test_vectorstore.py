"""Vector store tests."""

import tempfile
from pathlib import Path

import pytest

from oya.vectorstore import VectorStore


@pytest.fixture
def temp_index():
    """Create temporary index directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


def test_vectorstore_initializes(temp_index: Path):
    """Vector store initializes and creates collection."""
    store = VectorStore(temp_index)
    assert store.collection is not None


def test_add_and_query_documents(temp_index: Path):
    """Can add documents and query them."""
    store = VectorStore(temp_index)

    store.add_documents(
        ids=["doc1", "doc2"],
        documents=[
            "The login function handles user authentication",
            "The database schema defines user tables",
        ],
        metadatas=[
            {"source": "auth.py", "type": "code"},
            {"source": "schema.sql", "type": "code"},
        ],
    )

    results = store.query("how does login work", n_results=1)

    assert len(results["ids"][0]) == 1
    assert results["ids"][0][0] == "doc1"


def test_query_with_filter(temp_index: Path):
    """Can filter queries by metadata."""
    store = VectorStore(temp_index)

    store.add_documents(
        ids=["code1", "note1"],
        documents=[
            "Authentication uses JWT tokens",
            "CORRECTION: Authentication uses OAuth2, not JWT",
        ],
        metadatas=[
            {"source": "auth.py", "type": "code"},
            {"source": "note-001.md", "type": "note"},
        ],
    )

    results = store.query(
        "how does authentication work",
        n_results=2,
        where={"type": "note"},
    )

    assert len(results["ids"][0]) == 1
    assert results["ids"][0][0] == "note1"


def test_delete_documents(temp_index: Path):
    """Can delete documents by ID."""
    store = VectorStore(temp_index)

    store.add_documents(
        ids=["doc1", "doc2"],
        documents=["First document", "Second document"],
    )

    store.delete(ids=["doc1"])
    results = store.query("document", n_results=10)

    assert len(results["ids"][0]) == 1
    assert results["ids"][0][0] == "doc2"


def test_clear_all_documents(temp_index: Path):
    """Can clear all documents from the collection."""
    store = VectorStore(temp_index)

    store.add_documents(
        ids=["doc1", "doc2"],
        documents=["First document", "Second document"],
    )

    store.clear()
    results = store.query("document", n_results=10)

    assert len(results["ids"][0]) == 0
