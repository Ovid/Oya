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
    code = """
def main():
    result = helper()
    process(result)
"""
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


def test_extracts_instantiations(parser):
    """Extracts class instantiations."""
    code = """
def main():
    user = User("alice")
    config = Config()
"""
    result = parser.parse_string(code, "test.py")

    assert result.ok
    refs = result.file.references

    # Should find instantiations of User and Config
    instantiations = [r for r in refs if r.reference_type.value == "instantiates"]
    targets = [r.target for r in instantiations]

    assert "User" in targets
    assert "Config" in targets


def test_extracts_inheritance(parser):
    """Extracts class inheritance relationships."""
    code = """
class Animal:
    pass

class Dog(Animal):
    pass

class Labrador(Dog, Serializable):
    pass
"""
    result = parser.parse_string(code, "test.py")

    assert result.ok
    refs = result.file.references

    inherits = [r for r in refs if r.reference_type.value == "inherits"]

    # Dog inherits from Animal
    dog_inherits = [r for r in inherits if "Dog" in r.source]
    assert len(dog_inherits) == 1
    assert dog_inherits[0].target == "Animal"

    # Labrador inherits from Dog and Serializable
    lab_inherits = [r for r in inherits if "Labrador" in r.source]
    assert len(lab_inherits) == 2
    targets = [r.target for r in lab_inherits]
    assert "Dog" in targets
    assert "Serializable" in targets


def test_extracts_import_references(parser):
    """Extracts import statements as references."""
    code = """
import os
from pathlib import Path
from typing import List, Dict
from myapp.models import User
"""
    result = parser.parse_string(code, "test.py")

    assert result.ok
    refs = result.file.references

    import_refs = [r for r in refs if r.reference_type.value == "imports"]
    targets = [r.target for r in import_refs]

    assert "os" in targets
    assert "pathlib.Path" in targets
    assert "typing.List" in targets
    assert "typing.Dict" in targets
    assert "myapp.models.User" in targets

    # All imports should have high confidence
    for ref in import_refs:
        assert ref.confidence >= 0.95


def test_extracts_raises_from_function(parser):
    """Parser should extract exception types from raise statements."""
    source = '''
def validate_input(data):
    """Validate input data."""
    if not data:
        raise ValueError("Data cannot be empty")
    if not isinstance(data, dict):
        raise TypeError("Data must be a dictionary")
    return True
'''
    result = parser.parse_string(source, "test.py")

    assert result.ok
    func = next(s for s in result.file.symbols if s.name == "validate_input")
    assert "raises" in func.metadata
    assert set(func.metadata["raises"]) == {"ValueError", "TypeError"}


def test_extracts_raises_from_reraise(parser):
    """Parser should handle re-raise patterns."""
    source = """
def wrapper():
    try:
        do_something()
    except Exception as e:
        logger.error(f"Failed: {e}")
        raise
"""
    result = parser.parse_string(source, "test.py")

    assert result.ok
    func = next(s for s in result.file.symbols if s.name == "wrapper")
    # Re-raise without exception type should not add to raises
    assert func.metadata.get("raises", []) == []
