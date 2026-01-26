# backend/tests/test_code_index.py - new file

import pytest
from oya.db.code_index import CodeIndexBuilder, CodeIndexEntry
from oya.db.connection import Database
from oya.parsing.models import ParsedFile, ParsedSymbol, SymbolType


@pytest.fixture
def temp_db_with_code_index(tmp_path):
    """Create temp database with code_index table."""
    from oya.db.migrations import run_migrations

    db_path = tmp_path / "test.db"
    db = Database(db_path)
    run_migrations(db)
    yield db
    db.close()


def test_build_code_index_from_parsed_files(temp_db_with_code_index):
    """Should build code index entries from parsed files."""
    db = temp_db_with_code_index

    # Create mock parsed file
    symbol = ParsedSymbol(
        name="get_db",
        symbol_type=SymbolType.FUNCTION,
        start_line=10,
        end_line=25,
        docstring="Get database connection.",
        signature="def get_db(repo: RepoInfo) -> Database",
        decorators=[],
        parent=None,
        metadata={
            "raises": ["sqlite3.OperationalError"],
            "error_strings": ["database is locked"],
            "mutates": ["_db_instances"],
        },
    )
    parsed_file = ParsedFile(
        path="backend/src/oya/api/deps.py",
        language="python",
        symbols=[symbol],
        imports=["sqlite3", "oya.db.connection"],
        exports=[],
        references=[],
        raw_content="...",
        line_count=100,
        metadata={},
    )

    builder = CodeIndexBuilder(db)
    builder.build([parsed_file], source_hash="abc123")

    # Query and verify
    cursor = db.execute(
        "SELECT * FROM code_index WHERE file_path = ?", ("backend/src/oya/api/deps.py",)
    )
    row = cursor.fetchone()

    assert row is not None
    entry = CodeIndexEntry.from_row(row)
    assert entry.symbol_name == "get_db"
    assert entry.signature == "def get_db(repo: RepoInfo) -> Database"
    assert "sqlite3.OperationalError" in entry.raises
    assert "_db_instances" in entry.mutates


def test_code_index_incremental_update(temp_db_with_code_index):
    """Should replace entries when file hash changes."""
    db = temp_db_with_code_index
    builder = CodeIndexBuilder(db)

    # Initial build
    symbol1 = ParsedSymbol(
        name="old_func",
        symbol_type=SymbolType.FUNCTION,
        start_line=1,
        end_line=5,
        docstring=None,
        signature="def old_func()",
        decorators=[],
        parent=None,
        metadata={},
    )
    parsed_file = ParsedFile(
        path="test.py",
        language="python",
        symbols=[symbol1],
        imports=[],
        exports=[],
        references=[],
        raw_content="",
        line_count=10,
        metadata={},
    )
    builder.build([parsed_file], source_hash="hash1")

    # Update with new content
    symbol2 = ParsedSymbol(
        name="new_func",
        symbol_type=SymbolType.FUNCTION,
        start_line=1,
        end_line=5,
        docstring=None,
        signature="def new_func()",
        decorators=[],
        parent=None,
        metadata={},
    )
    parsed_file.symbols = [symbol2]
    builder.build([parsed_file], source_hash="hash2")

    # Old entry should be gone, new entry should exist
    cursor = db.execute("SELECT symbol_name FROM code_index WHERE file_path = ?", ("test.py",))
    rows = cursor.fetchall()
    names = [r[0] for r in rows]

    assert "old_func" not in names
    assert "new_func" in names
