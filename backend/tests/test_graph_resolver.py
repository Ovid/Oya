"""Tests for cross-file reference resolution."""

from oya.parsing.models import ParsedFile, ParsedSymbol, SymbolType, Reference, ReferenceType


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
            ParsedSymbol(
                name="process", symbol_type=SymbolType.FUNCTION, start_line=1, end_line=10
            ),
        ],
    )
    file2 = ParsedFile(
        path="b.py",
        language="python",
        symbols=[
            ParsedSymbol(
                name="process", symbol_type=SymbolType.FUNCTION, start_line=1, end_line=10
            ),
        ],
    )

    table = SymbolTable.from_parsed_files([file1, file2])

    results = table.lookup("process")
    assert len(results) == 2
    assert "a.py::process" in results
    assert "b.py::process" in results


def test_resolve_reference_exact_match():
    """Resolver finds exact match and sets high confidence."""
    from oya.graph.resolver import SymbolTable, resolve_references

    file1 = ParsedFile(
        path="auth/utils.py",
        language="python",
        symbols=[
            ParsedSymbol(
                name="verify", symbol_type=SymbolType.FUNCTION, start_line=10, end_line=20
            ),
        ],
        references=[],
    )
    file2 = ParsedFile(
        path="auth/handler.py",
        language="python",
        symbols=[
            ParsedSymbol(name="login", symbol_type=SymbolType.FUNCTION, start_line=5, end_line=25),
        ],
        references=[
            Reference(
                source="auth/handler.py::login",
                target="verify",  # Unresolved
                reference_type=ReferenceType.CALLS,
                confidence=0.9,
                line=15,
                target_resolved=False,
            ),
        ],
    )

    table = SymbolTable.from_parsed_files([file1, file2])
    resolved = resolve_references([file2], table)

    assert len(resolved) == 1
    ref = resolved[0]
    assert ref.target == "auth/utils.py::verify"
    assert ref.target_resolved is True
    assert ref.confidence >= 0.9  # Should maintain or increase confidence


def test_resolve_reference_ambiguous():
    """Resolver lowers confidence for ambiguous matches."""
    from oya.graph.resolver import SymbolTable, resolve_references

    file1 = ParsedFile(
        path="a.py",
        language="python",
        symbols=[
            ParsedSymbol(
                name="process", symbol_type=SymbolType.FUNCTION, start_line=1, end_line=10
            ),
        ],
    )
    file2 = ParsedFile(
        path="b.py",
        language="python",
        symbols=[
            ParsedSymbol(
                name="process", symbol_type=SymbolType.FUNCTION, start_line=1, end_line=10
            ),
        ],
    )
    file3 = ParsedFile(
        path="main.py",
        language="python",
        symbols=[],
        references=[
            Reference(
                source="main.py::main",
                target="process",
                reference_type=ReferenceType.CALLS,
                confidence=0.9,
                line=5,
            ),
        ],
    )

    table = SymbolTable.from_parsed_files([file1, file2, file3])
    resolved = resolve_references([file3], table)

    # Should create references to both candidates with lower confidence
    assert len(resolved) == 2
    for ref in resolved:
        assert ref.confidence < 0.9  # Reduced due to ambiguity


def test_resolve_reference_no_match():
    """Resolver keeps unresolved references with low confidence."""
    from oya.graph.resolver import SymbolTable, resolve_references

    file = ParsedFile(
        path="main.py",
        language="python",
        symbols=[],
        references=[
            Reference(
                source="main.py::main",
                target="unknown_func",
                reference_type=ReferenceType.CALLS,
                confidence=0.9,
                line=5,
            ),
        ],
    )

    table = SymbolTable.from_parsed_files([file])
    resolved = resolve_references([file], table)

    assert len(resolved) == 1
    ref = resolved[0]
    assert ref.target == "unknown_func"  # Unchanged
    assert ref.target_resolved is False
    assert ref.confidence < 0.5  # Lowered significantly
