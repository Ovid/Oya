"""Database connection and schema tests."""

import tempfile
from pathlib import Path

import pytest

from oya.db.connection import Database
from oya.db.migrations import run_migrations


@pytest.fixture
def temp_db():
    """Create a temporary database."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        yield db_path


def test_database_connects(temp_db: Path):
    """Database connects and creates file."""
    db = Database(temp_db)

    assert temp_db.exists()
    db.close()


def test_migrations_create_tables(temp_db: Path):
    """Migrations create required tables."""
    db = Database(temp_db)
    run_migrations(db)

    # Check tables exist
    tables = db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    table_names = {row[0] for row in tables}

    assert "generations" in table_names
    assert "wiki_pages" in table_names
    assert "notes" in table_names
    assert "citations" in table_names

    db.close()


def test_code_index_table_exists(temp_db: Path):
    """Code index table should exist after migrations."""
    db = Database(temp_db)
    run_migrations(db)

    cursor = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='code_index'")
    assert cursor.fetchone() is not None
    db.close()


def test_code_index_insert_and_query(temp_db: Path):
    """Should be able to insert and query code index entries."""
    db = Database(temp_db)
    run_migrations(db)

    db.execute(
        """
        INSERT INTO code_index
        (file_path, symbol_name, symbol_type, line_start, line_end,
         signature, docstring, calls, called_by, raises, mutates, error_strings, source_hash)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
        (
            "backend/src/oya/api/deps.py",
            "get_db",
            "function",
            45,
            62,
            "def get_db(repo: RepoInfo) -> Database",
            "Get cached database connection.",
            '["Database", "_db_instances.get"]',
            '["get_notes_service"]',
            '["sqlite3.OperationalError"]',
            '["_db_instances"]',
            '["database is locked"]',
            "abc123",
        ),
    )
    db.commit()

    cursor = db.execute(
        "SELECT symbol_name, raises FROM code_index WHERE file_path = ?",
        ("backend/src/oya/api/deps.py",),
    )
    row = cursor.fetchone()
    assert row[0] == "get_db"
    assert "sqlite3.OperationalError" in row[1]
    db.close()


def test_code_index_unique_constraint(temp_db: Path):
    """Unique constraint on (file_path, symbol_name) should prevent duplicates."""
    import sqlite3

    db = Database(temp_db)
    run_migrations(db)

    # Insert first entry
    db.execute(
        """INSERT INTO code_index
           (file_path, symbol_name, symbol_type, line_start, line_end, source_hash)
           VALUES (?, ?, ?, ?, ?, ?)""",
        ("test.py", "my_func", "function", 1, 10, "hash1"),
    )
    db.commit()

    # Attempt duplicate should fail
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            """INSERT INTO code_index
               (file_path, symbol_name, symbol_type, line_start, line_end, source_hash)
               VALUES (?, ?, ?, ?, ?, ?)""",
            ("test.py", "my_func", "function", 5, 15, "hash2"),
        )
    db.close()
