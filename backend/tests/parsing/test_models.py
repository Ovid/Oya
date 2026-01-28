"""Tests for parsing data models."""

from oya.parsing.models import ParsedFile


def test_parsed_file_has_synopsis_field():
    """ParsedFile should have optional synopsis field."""
    parsed_file = ParsedFile(
        path="test.py", language="python", symbols=[], synopsis="from mymodule import foo\nfoo()"
    )
    assert parsed_file.synopsis == "from mymodule import foo\nfoo()"


def test_parsed_file_synopsis_defaults_to_none():
    """ParsedFile.synopsis should default to None."""
    parsed_file = ParsedFile(path="test.py", language="python", symbols=[])
    assert parsed_file.synopsis is None
