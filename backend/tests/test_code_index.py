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


def test_compute_called_by(temp_db_with_code_index):
    """Should compute reverse call relationships."""
    db = temp_db_with_code_index
    builder = CodeIndexBuilder(db)

    # Create caller function that calls helper
    caller = ParsedSymbol(
        name="main",
        symbol_type=SymbolType.FUNCTION,
        start_line=1,
        end_line=10,
        docstring=None,
        signature="def main()",
        decorators=[],
        parent=None,
        metadata={"calls": ["helper", "utility"]},
    )
    # Create helper function (callee)
    helper = ParsedSymbol(
        name="helper",
        symbol_type=SymbolType.FUNCTION,
        start_line=12,
        end_line=20,
        docstring=None,
        signature="def helper()",
        decorators=[],
        parent=None,
        metadata={"calls": []},
    )
    # Create utility function (callee)
    utility = ParsedSymbol(
        name="utility",
        symbol_type=SymbolType.FUNCTION,
        start_line=22,
        end_line=30,
        docstring=None,
        signature="def utility()",
        decorators=[],
        parent=None,
        metadata={"calls": ["helper"]},  # utility also calls helper
    )

    parsed_file = ParsedFile(
        path="module.py",
        language="python",
        symbols=[caller, helper, utility],
        imports=[],
        exports=[],
        references=[],
        raw_content="",
        line_count=30,
        metadata={},
    )
    builder.build([parsed_file], source_hash="hash1")

    # Compute reverse relationships
    builder.compute_called_by()

    # Verify helper is called by both main and utility
    cursor = db.execute("SELECT called_by FROM code_index WHERE symbol_name = ?", ("helper",))
    row = cursor.fetchone()
    assert row is not None
    import json

    called_by = json.loads(row[0])
    assert "main" in called_by
    assert "utility" in called_by

    # Verify utility is called by main
    cursor = db.execute("SELECT called_by FROM code_index WHERE symbol_name = ?", ("utility",))
    row = cursor.fetchone()
    called_by = json.loads(row[0])
    assert "main" in called_by

    # Verify main is not called by anyone
    cursor = db.execute("SELECT called_by FROM code_index WHERE symbol_name = ?", ("main",))
    row = cursor.fetchone()
    called_by = json.loads(row[0])
    assert called_by == []


def test_delete_file(temp_db_with_code_index):
    """Should remove all entries for a file."""
    db = temp_db_with_code_index
    builder = CodeIndexBuilder(db)

    # Create two files with symbols
    symbol1 = ParsedSymbol(
        name="func_a",
        symbol_type=SymbolType.FUNCTION,
        start_line=1,
        end_line=5,
        docstring=None,
        signature="def func_a()",
        decorators=[],
        parent=None,
        metadata={},
    )
    symbol2 = ParsedSymbol(
        name="func_b",
        symbol_type=SymbolType.FUNCTION,
        start_line=1,
        end_line=5,
        docstring=None,
        signature="def func_b()",
        decorators=[],
        parent=None,
        metadata={},
    )
    file1 = ParsedFile(
        path="file1.py",
        language="python",
        symbols=[symbol1],
        imports=[],
        exports=[],
        references=[],
        raw_content="",
        line_count=10,
        metadata={},
    )
    file2 = ParsedFile(
        path="file2.py",
        language="python",
        symbols=[symbol2],
        imports=[],
        exports=[],
        references=[],
        raw_content="",
        line_count=10,
        metadata={},
    )
    builder.build([file1, file2], source_hash="hash1")

    # Verify both files indexed
    cursor = db.execute("SELECT COUNT(*) FROM code_index")
    assert cursor.fetchone()[0] == 2

    # Delete file1
    builder.delete_file("file1.py")

    # Verify only file2 remains
    cursor = db.execute("SELECT COUNT(*) FROM code_index")
    assert cursor.fetchone()[0] == 1

    cursor = db.execute("SELECT file_path FROM code_index")
    assert cursor.fetchone()[0] == "file2.py"


def test_duplicate_symbol_names_in_same_file(temp_db_with_code_index):
    """Should handle duplicate symbol names gracefully using INSERT OR REPLACE."""
    db = temp_db_with_code_index
    builder = CodeIndexBuilder(db)

    # Create two symbols with same name (e.g., overloaded methods or nested classes)
    symbol1 = ParsedSymbol(
        name="process",
        symbol_type=SymbolType.FUNCTION,
        start_line=1,
        end_line=5,
        docstring="First process",
        signature="def process(x: int)",
        decorators=[],
        parent=None,
        metadata={},
    )
    symbol2 = ParsedSymbol(
        name="process",
        symbol_type=SymbolType.FUNCTION,
        start_line=10,
        end_line=15,
        docstring="Second process",
        signature="def process(x: str)",
        decorators=[],
        parent=None,
        metadata={},
    )
    parsed_file = ParsedFile(
        path="overloads.py",
        language="python",
        symbols=[symbol1, symbol2],
        imports=[],
        exports=[],
        references=[],
        raw_content="",
        line_count=20,
        metadata={},
    )

    # Should not raise - INSERT OR REPLACE handles duplicates
    builder.build([parsed_file], source_hash="hash1")

    # Should have one entry (second replaces first due to UNIQUE constraint)
    cursor = db.execute("SELECT COUNT(*) FROM code_index WHERE file_path = ?", ("overloads.py",))
    assert cursor.fetchone()[0] == 1

    # The second symbol should be the one that remains
    cursor = db.execute(
        "SELECT line_start, signature FROM code_index WHERE symbol_name = ?", ("process",)
    )
    row = cursor.fetchone()
    assert row[0] == 10  # line_start of second symbol
    assert row[1] == "def process(x: str)"


def test_query_by_raises(temp_db_with_code_index):
    """Should find functions by exception type."""
    db = temp_db_with_code_index

    # Insert test data
    db.execute("""
        INSERT INTO code_index
        (file_path, symbol_name, symbol_type, line_start, line_end, raises, source_hash)
        VALUES
        ('a.py', 'func1', 'function', 1, 10, '["ValueError", "TypeError"]', 'h1'),
        ('b.py', 'func2', 'function', 1, 10, '["IOError"]', 'h2'),
        ('c.py', 'func3', 'function', 1, 10, '["ValueError"]', 'h3')
    """)
    db.commit()

    from oya.db.code_index import CodeIndexQuery

    query = CodeIndexQuery(db)

    results = query.find_by_raises("ValueError")
    names = [r.symbol_name for r in results]

    assert "func1" in names
    assert "func3" in names
    assert "func2" not in names


def test_query_by_error_string(temp_db_with_code_index):
    """Should find functions by error string pattern."""
    db = temp_db_with_code_index

    db.execute("""
        INSERT INTO code_index
        (file_path, symbol_name, symbol_type, line_start, line_end, error_strings, source_hash)
        VALUES
        ('a.py', 'func1', 'function', 1, 10, '["database is locked", "connection failed"]', 'h1'),
        ('b.py', 'func2', 'function', 1, 10, '["invalid input"]', 'h2')
    """)
    db.commit()

    from oya.db.code_index import CodeIndexQuery

    query = CodeIndexQuery(db)

    results = query.find_by_error_string("database")
    assert len(results) == 1
    assert results[0].symbol_name == "func1"


def test_query_by_file_and_symbol(temp_db_with_code_index):
    """Should find specific symbol by file pattern and name."""
    db = temp_db_with_code_index

    db.execute("""
        INSERT INTO code_index
        (file_path, symbol_name, symbol_type, line_start, line_end, source_hash)
        VALUES
        ('backend/src/oya/api/deps.py', 'get_db', 'function', 1, 10, 'h1'),
        ('backend/src/oya/api/deps.py', 'get_store', 'function', 11, 20, 'h2'),
        ('other/deps.py', 'get_db', 'function', 1, 10, 'h3')
    """)
    db.commit()

    from oya.db.code_index import CodeIndexQuery

    query = CodeIndexQuery(db)

    results = query.find_by_file_and_symbol("deps.py", "get_db")
    assert len(results) == 2  # Both files match

    results = query.find_by_file_and_symbol("oya/api/deps.py", "get_db")
    assert len(results) == 1
    assert results[0].file_path == "backend/src/oya/api/deps.py"
