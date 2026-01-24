"""Repository registry for multi-repo management."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class RepoRecord:
    """A repository record from the registry."""

    id: int
    origin_url: str
    source_type: str  # github, gitlab, bitbucket, git, local
    local_path: str  # Path within wikis/ directory
    display_name: str
    head_commit: Optional[str] = None
    branch: Optional[str] = None
    created_at: Optional[datetime] = None
    last_pulled: Optional[datetime] = None
    last_generated: Optional[datetime] = None
    generation_duration_secs: Optional[float] = None
    files_processed: Optional[int] = None
    pages_generated: Optional[int] = None
    generation_provider: Optional[str] = None
    generation_model: Optional[str] = None
    embedding_provider: Optional[str] = None
    embedding_model: Optional[str] = None
    status: str = "pending"  # pending, cloning, generating, ready, failed
    error_message: Optional[str] = None


SCHEMA = """
CREATE TABLE IF NOT EXISTS repos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    origin_url TEXT NOT NULL,
    source_type TEXT NOT NULL,
    local_path TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    head_commit TEXT,
    branch TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    last_pulled TEXT,
    last_generated TEXT,
    generation_duration_secs REAL,
    files_processed INTEGER,
    pages_generated INTEGER,
    generation_provider TEXT,
    generation_model TEXT,
    embedding_provider TEXT,
    embedding_model TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_repos_origin_url ON repos(origin_url);
CREATE INDEX IF NOT EXISTS idx_repos_status ON repos(status);
"""


class RepoRegistry:
    """SQLite-backed repository registry."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def add(
        self,
        origin_url: str,
        source_type: str,
        local_path: str,
        display_name: str,
    ) -> int:
        """Add a new repository. Returns the repo ID."""
        cursor = self._conn.execute(
            """
            INSERT INTO repos (origin_url, source_type, local_path, display_name)
            VALUES (?, ?, ?, ?)
            """,
            (origin_url, source_type, local_path, display_name),
        )
        self._conn.commit()
        # lastrowid is guaranteed non-None after INSERT
        assert cursor.lastrowid is not None
        return cursor.lastrowid

    def _row_to_record(self, row: sqlite3.Row) -> RepoRecord:
        """Convert a database row to a RepoRecord."""
        return RepoRecord(
            id=row["id"],
            origin_url=row["origin_url"],
            source_type=row["source_type"],
            local_path=row["local_path"],
            display_name=row["display_name"],
            head_commit=row["head_commit"],
            branch=row["branch"],
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
            last_pulled=datetime.fromisoformat(row["last_pulled"]) if row["last_pulled"] else None,
            last_generated=(
                datetime.fromisoformat(row["last_generated"]) if row["last_generated"] else None
            ),
            generation_duration_secs=row["generation_duration_secs"],
            files_processed=row["files_processed"],
            pages_generated=row["pages_generated"],
            generation_provider=row["generation_provider"],
            generation_model=row["generation_model"],
            embedding_provider=row["embedding_provider"],
            embedding_model=row["embedding_model"],
            status=row["status"],
            error_message=row["error_message"],
        )

    def get(self, repo_id: int) -> Optional[RepoRecord]:
        """Get a repo by ID. Returns None if not found."""
        cursor = self._conn.execute("SELECT * FROM repos WHERE id = ?", (repo_id,))
        row = cursor.fetchone()
        return self._row_to_record(row) if row else None

    def list_all(self) -> list[RepoRecord]:
        """List all repos ordered by creation date."""
        cursor = self._conn.execute("SELECT * FROM repos ORDER BY created_at")
        return [self._row_to_record(row) for row in cursor.fetchall()]

    def update(self, repo_id: int, **kwargs) -> None:
        """Update repo fields. Only updates fields that are provided."""
        if not kwargs:
            return

        allowed_fields = {
            "display_name",
            "head_commit",
            "branch",
            "last_pulled",
            "last_generated",
            "generation_duration_secs",
            "files_processed",
            "pages_generated",
            "generation_provider",
            "generation_model",
            "embedding_provider",
            "embedding_model",
            "status",
            "error_message",
        }

        fields = {k: v for k, v in kwargs.items() if k in allowed_fields}
        if not fields:
            return

        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [repo_id]

        self._conn.execute(f"UPDATE repos SET {set_clause} WHERE id = ?", values)
        self._conn.commit()

    def delete(self, repo_id: int) -> None:
        """Delete a repo by ID."""
        self._conn.execute("DELETE FROM repos WHERE id = ?", (repo_id,))
        self._conn.commit()

    def find_by_origin_url(self, origin_url: str) -> Optional[RepoRecord]:
        """Find a repo by its origin URL. Returns None if not found."""
        cursor = self._conn.execute("SELECT * FROM repos WHERE origin_url = ?", (origin_url,))
        row = cursor.fetchone()
        return self._row_to_record(row) if row else None

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()
