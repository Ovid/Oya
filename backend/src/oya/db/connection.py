"""SQLite database connection management."""

import sqlite3
from pathlib import Path
from typing import Any


class Database:
    """SQLite database wrapper with connection management."""

    def __init__(self, db_path: Path):
        """Initialize database connection."""
        self.db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> sqlite3.Cursor:
        """Execute SQL statement."""
        return self._conn.execute(sql, params)

    def executemany(self, sql: str, params_list: list[tuple[Any, ...]]) -> sqlite3.Cursor:
        """Execute SQL statement for multiple parameter sets."""
        return self._conn.executemany(sql, params_list)

    def executescript(self, sql: str) -> sqlite3.Cursor:
        """Execute multiple SQL statements as a script."""
        return self._conn.executescript(sql)

    def commit(self) -> None:
        """Commit current transaction."""
        self._conn.commit()

    def rollback(self) -> None:
        """Rollback current transaction."""
        self._conn.rollback()

    def close(self) -> None:
        """Close database connection."""
        self._conn.close()
