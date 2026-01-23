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
        return cursor.lastrowid

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()
