"""ChromaDB vector store implementation."""

import gc
from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings


class VectorStore:
    """Vector store wrapper for ChromaDB.

    Provides semantic search capabilities for:
    - Finding relevant code chunks for Q&A
    - Evidence gating (checking if sufficient sources exist)
    - Prioritizing notes over generated content
    """

    COLLECTION_NAME = "oya_documents"

    def __init__(self, persist_path: Path) -> None:
        """Initialize vector store with persistent storage.

        Args:
            persist_path: Directory path for ChromaDB persistence.
        """
        self._client = chromadb.PersistentClient(
            path=str(persist_path),
            settings=Settings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name=self.COLLECTION_NAME,
        )

    @property
    def collection(self) -> chromadb.Collection:
        """Get the underlying ChromaDB collection."""
        return self._collection

    def add_documents(
        self,
        ids: list[str],
        documents: list[str],
        metadatas: list[dict[str, Any]] | None = None,
    ) -> None:
        """Add documents to the vector store.

        Args:
            ids: Unique identifiers for each document.
            documents: Text content of each document.
            metadatas: Optional metadata dictionaries for each document.
        """
        self._collection.add(
            ids=ids,
            documents=documents,
            metadatas=metadatas,  # type: ignore[arg-type]
        )

    def query(
        self,
        query_text: str,
        n_results: int = 10,
        where: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Query the vector store for similar documents.

        Args:
            query_text: Text to search for.
            n_results: Maximum number of results to return.
            where: Optional metadata filter.

        Returns:
            Query results including ids, documents, metadatas, and distances.
        """
        result = self._collection.query(
            query_texts=[query_text],
            n_results=n_results,
            where=where,
        )
        return dict(result)

    def delete(self, ids: list[str]) -> None:
        """Delete documents by their IDs.

        Args:
            ids: List of document IDs to delete.
        """
        self._collection.delete(ids=ids)

    def clear(self) -> None:
        """Clear all documents from the collection."""
        # ChromaDB doesn't have a direct clear method, so we delete and recreate
        self._client.delete_collection(name=self.COLLECTION_NAME)
        self._collection = self._client.get_or_create_collection(
            name=self.COLLECTION_NAME,
        )

    def close(self) -> None:
        """Close the vector store and release resources.

        This should be called when the store is no longer needed to
        release file handles and other system resources.
        """
        # ChromaDB PersistentClient doesn't have an explicit close method,
        # but we can try to stop internal systems and clear references
        if self._client is not None:
            # Try to stop internal systems (ChromaDB uses a SegmentAPI internally)
            try:
                # Access internal identifier-to-system mapping and stop systems
                if hasattr(self._client, "_identifier_to_system"):
                    for system in list(self._client._identifier_to_system.values()):
                        if hasattr(system, "stop"):
                            system.stop()
            except Exception:
                pass  # Best effort cleanup

        self._collection = None  # type: ignore[assignment]
        self._client = None  # type: ignore[assignment]

        # Force garbage collection to release file handles
        gc.collect()
