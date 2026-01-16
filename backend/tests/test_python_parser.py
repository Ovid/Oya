"""Python AST parser tests."""

import pytest

from oya.parsing import SymbolType
from oya.parsing.python_parser import PythonParser


@pytest.fixture
def parser():
    """Create Python parser instance."""
    return PythonParser()


def test_parser_supported_extensions(parser):
    """Parser supports .py and .pyi files."""
    assert ".py" in parser.supported_extensions
    assert ".pyi" in parser.supported_extensions


def test_parses_simple_function(parser):
    """Extracts function with docstring."""
    code = '''
def greet(name: str) -> str:
    """Say hello to someone."""
    return f"Hello, {name}"
'''
    result = parser.parse_string(code, "test.py")

    assert result.ok
    assert len(result.file.symbols) == 1

    func = result.file.symbols[0]
    assert func.name == "greet"
    assert func.symbol_type == SymbolType.FUNCTION
    assert func.docstring == "Say hello to someone."
    assert "name: str" in func.signature


def test_parses_class_with_methods(parser):
    """Extracts class and its methods."""
    code = '''
class Calculator:
    """A simple calculator."""

    def add(self, a: int, b: int) -> int:
        """Add two numbers."""
        return a + b

    def subtract(self, a: int, b: int) -> int:
        """Subtract b from a."""
        return a - b
'''
    result = parser.parse_string(code, "test.py")

    assert result.ok
    symbols = result.file.symbols

    # Should have class + 2 methods
    class_sym = next(s for s in symbols if s.symbol_type == SymbolType.CLASS)
    assert class_sym.name == "Calculator"
    assert class_sym.docstring == "A simple calculator."

    methods = [s for s in symbols if s.symbol_type == SymbolType.METHOD]
    assert len(methods) == 2
    assert all(m.parent == "Calculator" for m in methods)


def test_parses_imports(parser):
    """Extracts import statements."""
    code = """
import os
import sys
from pathlib import Path
from typing import List, Dict
"""
    result = parser.parse_string(code, "test.py")

    assert result.ok
    imports = result.file.imports

    assert "os" in imports
    assert "sys" in imports
    assert "pathlib.Path" in imports
    assert "typing.List" in imports


def test_parses_decorated_functions(parser):
    """Extracts decorators from functions."""
    code = '''
@app.route("/api/users")
@require_auth
def get_users():
    """Get all users."""
    pass
'''
    result = parser.parse_string(code, "test.py")

    assert result.ok
    func = result.file.symbols[0]
    assert "app.route" in func.decorators
    assert "require_auth" in func.decorators


def test_identifies_fastapi_routes(parser):
    """Identifies FastAPI route handlers."""
    code = """
from fastapi import FastAPI

app = FastAPI()

@app.get("/users")
def list_users():
    pass

@app.post("/users")
def create_user():
    pass
"""
    result = parser.parse_string(code, "test.py")

    assert result.ok
    routes = [s for s in result.file.symbols if s.symbol_type == SymbolType.ROUTE]
    assert len(routes) == 2


def test_handles_syntax_error_gracefully(parser):
    """Returns error result for invalid Python."""
    code = """
def broken(
    # missing closing paren
"""
    result = parser.parse_string(code, "test.py")

    assert not result.ok
    assert "syntax" in result.error.lower() or "error" in result.error.lower()


def test_parses_module_level_variables(parser):
    """Extracts module-level constants and variables."""
    code = """
VERSION = "1.0.0"
DEBUG = True
_private = "hidden"

config = {
    "timeout": 30,
}
"""
    result = parser.parse_string(code, "test.py")

    assert result.ok
    variables = [
        s
        for s in result.file.symbols
        if s.symbol_type in (SymbolType.VARIABLE, SymbolType.CONSTANT)
    ]

    names = [v.name for v in variables]
    assert "VERSION" in names
    assert "DEBUG" in names


def test_extracts_function_calls(parser):
    """Extracts function calls with confidence."""
    code = '''
def main():
    result = helper()
    process(result)
'''
    result = parser.parse_string(code, "test.py")

    assert result.ok
    refs = result.file.references

    # Should find calls to helper() and process()
    call_names = [r.target for r in refs if r.reference_type.value == "calls"]
    assert "helper" in call_names
    assert "process" in call_names

    # All calls should have confidence > 0
    for ref in refs:
        assert ref.confidence > 0
        assert ref.line > 0
