"""Parsing data model tests."""

from oya.parsing.models import (
    ParsedSymbol,
    SymbolType,
    ParsedFile,
    ParseResult,
)


def test_parsed_symbol_creation():
    """Can create a parsed symbol."""
    symbol = ParsedSymbol(
        name="my_function",
        symbol_type=SymbolType.FUNCTION,
        start_line=10,
        end_line=25,
        docstring="Does something useful.",
        signature="def my_function(a: int, b: str) -> bool",
    )

    assert symbol.name == "my_function"
    assert symbol.symbol_type == SymbolType.FUNCTION
    assert symbol.start_line == 10
    assert symbol.end_line == 25
    assert symbol.docstring == "Does something useful."


def test_symbol_types_exist():
    """All required symbol types exist."""
    assert SymbolType.FUNCTION
    assert SymbolType.CLASS
    assert SymbolType.METHOD
    assert SymbolType.IMPORT
    assert SymbolType.EXPORT
    assert SymbolType.VARIABLE
    assert SymbolType.CONSTANT


def test_parsed_file_creation():
    """Can create a parsed file with symbols."""
    symbols = [
        ParsedSymbol(
            name="MyClass",
            symbol_type=SymbolType.CLASS,
            start_line=1,
            end_line=50,
        ),
        ParsedSymbol(
            name="helper",
            symbol_type=SymbolType.FUNCTION,
            start_line=52,
            end_line=60,
        ),
    ]

    parsed = ParsedFile(
        path="src/module.py",
        language="python",
        symbols=symbols,
        imports=["os", "sys"],
        exports=["MyClass", "helper"],
    )

    assert parsed.path == "src/module.py"
    assert parsed.language == "python"
    assert len(parsed.symbols) == 2
    assert "os" in parsed.imports


def test_parse_result_success():
    """ParseResult can represent success."""
    parsed = ParsedFile(path="test.py", language="python", symbols=[])
    result = ParseResult.success(parsed)

    assert result.ok
    assert result.file == parsed
    assert result.error is None


def test_parse_result_failure():
    """ParseResult can represent failure."""
    result = ParseResult.failure("test.py", "Syntax error on line 5")

    assert not result.ok
    assert result.file is None
    assert "Syntax error" in result.error


def test_reference_model_creation():
    """Reference model stores source, target, type, and confidence."""
    from oya.parsing.models import Reference, ReferenceType

    ref = Reference(
        source="auth/handler.py::login",
        target="auth/session.py::create_session",
        reference_type=ReferenceType.CALLS,
        confidence=0.85,
        line=42,
    )

    assert ref.source == "auth/handler.py::login"
    assert ref.target == "auth/session.py::create_session"
    assert ref.reference_type == ReferenceType.CALLS
    assert ref.confidence == 0.85
    assert ref.line == 42


def test_reference_type_enum():
    """ReferenceType has expected values."""
    from oya.parsing.models import ReferenceType

    assert ReferenceType.CALLS.value == "calls"
    assert ReferenceType.INSTANTIATES.value == "instantiates"
    assert ReferenceType.INHERITS.value == "inherits"
    assert ReferenceType.IMPORTS.value == "imports"


def test_parsed_file_has_references():
    """ParsedFile includes references field."""
    from oya.parsing.models import ParsedFile, Reference, ReferenceType

    ref = Reference(
        source="test.py::main",
        target="helper",
        reference_type=ReferenceType.CALLS,
        confidence=0.9,
        line=10,
    )

    parsed = ParsedFile(
        path="test.py",
        language="python",
        symbols=[],
        references=[ref],
    )

    assert len(parsed.references) == 1
    assert parsed.references[0].target == "helper"
