"""Tests for cross-file reference resolution."""

import pytest
from oya.parsing.models import ParsedFile, ParsedSymbol, SymbolType


def test_symbol_table_from_parsed_files():
    """SymbolTable indexes all definitions by name."""
    from oya.graph.resolver import SymbolTable

    file1 = ParsedFile(
        path="auth/utils.py",
        language="python",
        symbols=[
            ParsedSymbol(
                name="verify",
                symbol_type=SymbolType.FUNCTION,
                start_line=10,
                end_line=20,
            ),
        ],
    )
    file2 = ParsedFile(
        path="models/user.py",
        language="python",
        symbols=[
            ParsedSymbol(
                name="User",
                symbol_type=SymbolType.CLASS,
                start_line=5,
                end_line=50,
            ),
            ParsedSymbol(
                name="save",
                symbol_type=SymbolType.METHOD,
                start_line=30,
                end_line=40,
                parent="User",
            ),
        ],
    )

    table = SymbolTable.from_parsed_files([file1, file2])

    # Can lookup by simple name
    assert table.lookup("verify") == ["auth/utils.py::verify"]
    assert table.lookup("User") == ["models/user.py::User"]
    # Methods are qualified with class
    assert table.lookup("User.save") == ["models/user.py::User.save"]


def test_symbol_table_handles_duplicates():
    """SymbolTable tracks multiple definitions with same name."""
    from oya.graph.resolver import SymbolTable

    file1 = ParsedFile(
        path="a.py",
        language="python",
        symbols=[
            ParsedSymbol(name="process", symbol_type=SymbolType.FUNCTION, start_line=1, end_line=10),
        ],
    )
    file2 = ParsedFile(
        path="b.py",
        language="python",
        symbols=[
            ParsedSymbol(name="process", symbol_type=SymbolType.FUNCTION, start_line=1, end_line=10),
        ],
    )

    table = SymbolTable.from_parsed_files([file1, file2])

    results = table.lookup("process")
    assert len(results) == 2
    assert "a.py::process" in results
    assert "b.py::process" in results
