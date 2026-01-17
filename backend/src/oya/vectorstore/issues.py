"""ChromaDB collection for code issues."""

import re
from pathlib import Path
from typing import Any, cast

import chromadb
from chromadb.config import Settings
from chromadb.types import Where

from oya.generation.summaries import FileIssue


class IssuesStore:
    """Vector store for code issues.

    Stores issues detected during file analysis in a dedicated ChromaDB
    collection, enabling semantic search and filtered queries for Q&A.
    """

    COLLECTION_NAME = "oya_issues"

    def __init__(self, persist_path: Path) -> None:
        """Initialize issues store with persistent storage."""
        self._client = chromadb.PersistentClient(
            path=str(persist_path),
            settings=Settings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name=self.COLLECTION_NAME,
        )

    def _make_id(self, file_path: str, title: str, index: int) -> str:
        """Create a unique ID for an issue."""
        slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
        return f"{file_path}::{slug}::{index}"

    def add_issues(self, file_path: str, issues: list[FileIssue]) -> None:
        """Add issues for a file to the store. Replaces existing issues for file."""
        self.delete_issues_for_file(file_path)
        if not issues:
            return

        ids: list[str] = []
        documents: list[str] = []
        metadatas: list[dict[str, str | int]] = []
        for i, issue in enumerate(issues):
            issue_id = self._make_id(file_path, issue.title, i)
            content = f"{issue.title}\n\n{issue.description}"
            metadata: dict[str, str | int] = {
                "file_path": file_path,
                "category": issue.category,
                "severity": issue.severity,
                "title": issue.title,
            }
            if issue.line_range:
                metadata["line_start"] = issue.line_range[0]
                metadata["line_end"] = issue.line_range[1]

            ids.append(issue_id)
            documents.append(content)
            metadatas.append(metadata)

        self._collection.add(ids=ids, documents=documents, metadatas=cast(Any, metadatas))

    def delete_issues_for_file(self, file_path: str) -> None:
        """Delete all issues for a specific file."""
        try:
            results = self._collection.get(where={"file_path": file_path})
            if results["ids"]:
                self._collection.delete(ids=results["ids"])
        except Exception:
            pass

    def query_issues(
        self,
        query: str | None = None,
        category: str | None = None,
        severity: str | None = None,
        file_path: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Query issues with optional filters."""
        where_clauses: list[dict[str, str]] = []
        if category:
            where_clauses.append({"category": category})
        if severity:
            where_clauses.append({"severity": severity})
        if file_path:
            where_clauses.append({"file_path": file_path})

        where: Where | None = None
        if len(where_clauses) == 1:
            where = cast(Where, where_clauses[0])
        elif len(where_clauses) > 1:
            where = cast(Where, {"$and": where_clauses})

        try:
            if query:
                results = self._collection.query(query_texts=[query], n_results=limit, where=where)
                ids = (results.get("ids") or [[]])[0]
                documents = (results.get("documents") or [[]])[0]
                metadatas = (results.get("metadatas") or [[]])[0]
            else:
                get_results = self._collection.get(where=where, limit=limit)
                ids = get_results.get("ids") or []
                documents = get_results.get("documents") or []
                metadatas = get_results.get("metadatas") or []

            issues = []
            for i, issue_id in enumerate(ids):
                if i < len(metadatas):
                    issue = dict(metadatas[i])
                    issue["id"] = issue_id
                    issue["content"] = documents[i] if i < len(documents) else ""
                    issues.append(issue)
            return issues
        except Exception:
            return []

    def clear(self) -> None:
        """Clear all issues from the collection."""
        self._client.delete_collection(name=self.COLLECTION_NAME)
        self._collection = self._client.get_or_create_collection(name=self.COLLECTION_NAME)

    def close(self) -> None:
        """Close the store and release resources."""
        import gc

        if self._client is not None:
            try:
                if hasattr(self._client, "_identifier_to_system"):
                    for system in list(self._client._identifier_to_system.values()):
                        if hasattr(system, "stop"):
                            system.stop()
            except Exception:
                pass

        self._collection = None  # type: ignore[assignment]
        self._client = None  # type: ignore[assignment]
        gc.collect()
