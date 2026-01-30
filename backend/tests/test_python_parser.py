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


def test_extracts_error_strings_from_raise(parser):
    """Parser should extract string literals from raise statements."""
    source = """
def process(data):
    if not data:
        raise ValueError("input cannot be empty")
    if data.get("type") not in VALID_TYPES:
        raise ValueError("invalid type specified")
"""
    result = parser.parse_string(source, "test.py")

    assert result.ok
    func = next(s for s in result.file.symbols if s.name == "process")
    assert "error_strings" in func.metadata
    assert "input cannot be empty" in func.metadata["error_strings"]
    assert "invalid type specified" in func.metadata["error_strings"]


def test_extracts_error_strings_from_logging(parser):
    """Parser should extract strings from logging.error calls."""
    source = """
def fetch_data(url):
    try:
        response = requests.get(url)
    except RequestException:
        logger.error("failed to fetch data from remote server")
        raise
"""
    result = parser.parse_string(source, "test.py")

    assert result.ok
    func = next(s for s in result.file.symbols if s.name == "fetch_data")
    assert "error_strings" in func.metadata
    assert "failed to fetch data from remote server" in func.metadata["error_strings"]


def test_non_logging_error_method_not_detected(parser):
    """Parser should NOT extract strings from non-logger .error() methods.

    This tests the fix for a bug where any object's .error() method was
    incorrectly detected as a logging call (e.g., result.error(), handler.error()).
    """
    source = """
def process_result(result):
    if result.error("validation failed"):
        return None
    handler.error("something went wrong")
    return result.data
"""
    result = parser.parse_string(source, "test.py")

    assert result.ok
    func = next(s for s in result.file.symbols if s.name == "process_result")
    # Should NOT have error_strings since result.error() and handler.error()
    # are not logger objects
    assert "error_strings" not in func.metadata or func.metadata["error_strings"] == []


def test_extracts_mutates_module_level(parser):
    """Parser should detect assignments to module-level state."""
    source = """
_cache = {}

def get_cached(key):
    if key not in _cache:
        _cache[key] = compute(key)
    return _cache[key]

def clear_cache():
    _cache.clear()
"""
    result = parser.parse_string(source, "test.py")

    assert result.ok
    get_func = next(s for s in result.file.symbols if s.name == "get_cached")
    assert "mutates" in get_func.metadata
    assert "_cache" in get_func.metadata["mutates"]

    clear_func = next(s for s in result.file.symbols if s.name == "clear_cache")
    assert "mutates" in clear_func.metadata
    assert "_cache" in clear_func.metadata["mutates"]


def test_extracts_mutates_self_attributes(parser):
    """Parser should detect assignments to self attributes."""
    source = """
class Service:
    def __init__(self):
        self.connection = None

    def connect(self, url):
        self.connection = create_connection(url)
        self.connected = True
"""
    result = parser.parse_string(source, "test.py")

    assert result.ok
    connect_func = next(s for s in result.file.symbols if s.name == "connect")
    assert "mutates" in connect_func.metadata
    assert "self.connection" in connect_func.metadata["mutates"]
    assert "self.connected" in connect_func.metadata["mutates"]


def test_extracts_mutates_augmented_assignment(parser):
    """Parser should detect augmented assignments to module-level state."""
    source = """
counter = 0
items = []

def increment():
    global counter
    counter += 1

def add_item(item):
    items.append(item)
"""
    result = parser.parse_string(source, "test.py")

    assert result.ok
    inc_func = next(s for s in result.file.symbols if s.name == "increment")
    assert "mutates" in inc_func.metadata
    assert "counter" in inc_func.metadata["mutates"]

    add_func = next(s for s in result.file.symbols if s.name == "add_item")
    assert "mutates" in add_func.metadata
    assert "items" in add_func.metadata["mutates"]


def test_no_mutates_for_local_variables(parser):
    """Parser should NOT detect mutations of local variables."""
    source = """
def process(data):
    local_cache = {}
    local_cache["key"] = data
    return local_cache
"""
    result = parser.parse_string(source, "test.py")

    assert result.ok
    func = next(s for s in result.file.symbols if s.name == "process")
    # local_cache is not module-level, so no mutates
    assert "mutates" not in func.metadata or func.metadata["mutates"] == []


def test_extract_synopsis_from_docstring_with_example_section(parser):
    """Should extract code from docstring Example: section."""
    code = '''"""Module for email validation.

Example:
    from mymodule import validate_email

    is_valid = validate_email("user@example.com")
"""

def validate_email(email: str) -> bool:
    return "@" in email
'''
    result = parser.parse_string(code, "test.py")
    expected = """from mymodule import validate_email

is_valid = validate_email("user@example.com")"""
    assert result.file.synopsis == expected


def test_extract_synopsis_from_docstring_with_usage_section(parser):
    """Should extract code from docstring Usage: section."""
    code = '''"""Utility functions.

Usage:
    >>> from utils import format_phone
    >>> format_phone("5551234567")
    '(555) 123-4567'
"""
'''
    result = parser.parse_string(code, "test.py")
    expected = """from utils import format_phone
format_phone("5551234567")
'(555) 123-4567'"""
    assert result.file.synopsis == expected


def test_no_synopsis_when_docstring_has_no_examples(parser):
    """Should return None when docstring has no example sections."""
    code = '''"""Module for authentication.

This module handles user authentication.
"""

def login(username, password):
    pass
'''
    result = parser.parse_string(code, "test.py")
    assert result.file.synopsis is None


def test_no_synopsis_when_example_section_is_empty(parser):
    """Should return None when Example section has only whitespace."""
    code = '''"""Module for testing.

Example:


"""

def foo():
    pass
'''
    result = parser.parse_string(code, "test.py")
    assert result.file.synopsis is None


def test_builtin_types_not_in_references(parser):
    """Built-in types like int, str, List should not create references."""
    code = """
def process(data: str, items: list, count: int) -> bool:
    pass
"""
    result = parser.parse_string(code, "test.py")

    assert result.ok
    # Should have no type annotation references for built-ins
    type_refs = [r for r in result.file.references if r.reference_type.value == "type_annotation"]
    assert len(type_refs) == 0


def test_extracts_type_annotation_simple(parser):
    """Extracts simple type annotations from function parameters."""
    code = """
def create_user(request: CreateRequest) -> UserResponse:
    pass
"""
    result = parser.parse_string(code, "test.py")

    assert result.ok
    type_refs = [r for r in result.file.references if r.reference_type.value == "type_annotation"]

    targets = [r.target for r in type_refs]
    assert "CreateRequest" in targets
    assert "UserResponse" in targets
    assert all(r.confidence == 0.9 for r in type_refs)
