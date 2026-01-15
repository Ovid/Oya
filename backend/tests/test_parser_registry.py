# backend/tests/test_parser_registry.py
"""Parser registry tests."""

from pathlib import Path

import pytest

from oya.parsing.registry import ParserRegistry


@pytest.fixture
def registry():
    """Create parser registry with all parsers."""
    return ParserRegistry()


def test_gets_python_parser(registry):
    """Returns Python parser for .py files."""
    parser = registry.get_parser(Path("test.py"))

    assert parser is not None
    assert parser.language_name == "Python"


def test_gets_typescript_parser(registry):
    """Returns TypeScript parser for .ts files."""
    parser = registry.get_parser(Path("test.ts"))

    assert parser is not None
    assert parser.language_name == "TypeScript"


def test_gets_java_parser(registry):
    """Returns Java parser for .java files."""
    parser = registry.get_parser(Path("test.java"))

    assert parser is not None
    assert parser.language_name == "Java"


def test_falls_back_for_unknown(registry):
    """Returns fallback parser for unsupported extensions."""
    parser = registry.get_parser(Path("test.pl"))

    assert parser is not None
    assert parser.language_name == "Generic"  # FallbackParser returns "Generic"


def test_parse_file_uses_correct_parser(registry):
    """parse_file selects appropriate parser."""
    result = registry.parse_file(Path("test.py"), "def hello(): pass")

    assert result.ok
    assert result.file.language == "python"


def test_parse_file_with_fallback(registry):
    """parse_file uses fallback for unknown extensions."""
    result = registry.parse_file(Path("test.rs"), "fn main() {}")

    assert result.ok
    assert result.file.language == "rust"
