"""TypeScript/JavaScript parser tests."""

import pytest

from oya.parsing import SymbolType
from oya.parsing.typescript_parser import TypeScriptParser


@pytest.fixture
def parser():
    """Create TypeScript parser instance."""
    return TypeScriptParser()


def test_parser_supported_extensions(parser):
    """Parser supports TS and JS files."""
    assert ".ts" in parser.supported_extensions
    assert ".tsx" in parser.supported_extensions
    assert ".js" in parser.supported_extensions
    assert ".jsx" in parser.supported_extensions


def test_parses_function_declaration(parser):
    """Extracts function declarations."""
    code = """
function greet(name: string): string {
    return `Hello, ${name}`;
}
"""
    result = parser.parse_string(code, "test.ts")

    assert result.ok
    func = result.file.symbols[0]
    assert func.name == "greet"
    assert func.symbol_type == SymbolType.FUNCTION


def test_parses_arrow_function(parser):
    """Extracts arrow function assignments."""
    code = """
const add = (a: number, b: number): number => {
    return a + b;
};
"""
    result = parser.parse_string(code, "test.ts")

    assert result.ok
    symbols = result.file.symbols
    assert any(s.name == "add" for s in symbols)


def test_parses_class(parser):
    """Extracts class with methods."""
    code = """
class Calculator {
    add(a: number, b: number): number {
        return a + b;
    }

    subtract(a: number, b: number): number {
        return a - b;
    }
}
"""
    result = parser.parse_string(code, "test.ts")

    assert result.ok
    class_sym = next(s for s in result.file.symbols if s.symbol_type == SymbolType.CLASS)
    assert class_sym.name == "Calculator"

    methods = [s for s in result.file.symbols if s.symbol_type == SymbolType.METHOD]
    assert len(methods) == 2


def test_parses_interface(parser):
    """Extracts TypeScript interfaces."""
    code = """
interface User {
    id: number;
    name: string;
    email?: string;
}
"""
    result = parser.parse_string(code, "test.ts")

    assert result.ok
    interface = next(s for s in result.file.symbols if s.symbol_type == SymbolType.INTERFACE)
    assert interface.name == "User"


def test_parses_type_alias(parser):
    """Extracts TypeScript type aliases."""
    code = """
type Status = "pending" | "active" | "completed";
type UserMap = Record<string, User>;
"""
    result = parser.parse_string(code, "test.ts")

    assert result.ok
    types = [s for s in result.file.symbols if s.symbol_type == SymbolType.TYPE_ALIAS]
    names = [t.name for t in types]
    assert "Status" in names
    assert "UserMap" in names


def test_parses_enum(parser):
    """Extracts TypeScript enums."""
    code = """
enum Status {
    PENDING,
    ACTIVE,
    COMPLETED
}
"""
    result = parser.parse_string(code, "test.ts")

    assert result.ok
    enum_sym = next(s for s in result.file.symbols if s.symbol_type == SymbolType.ENUM)
    assert enum_sym.name == "Status"


def test_parses_imports(parser):
    """Extracts import statements."""
    code = """
import React from 'react';
import { useState, useEffect } from 'react';
import type { User } from './types';
"""
    result = parser.parse_string(code, "test.ts")

    assert result.ok
    imports = result.file.imports
    assert any("react" in imp for imp in imports)


def test_parses_exports(parser):
    """Extracts export statements."""
    code = """
export function helper() {}
export const VERSION = "1.0.0";
export default class App {}
"""
    result = parser.parse_string(code, "test.ts")

    assert result.ok
    exports = result.file.exports
    assert "helper" in exports
    assert "VERSION" in exports


def test_handles_jsx(parser):
    """Handles JSX/TSX syntax."""
    code = """
function Button({ label }: { label: string }) {
    return <button>{label}</button>;
}
"""
    result = parser.parse_string(code, "test.tsx")

    assert result.ok
    assert any(s.name == "Button" for s in result.file.symbols)


def test_handles_malformed_code(parser):
    """Returns result for invalid syntax (tree-sitter is lenient)."""
    code = """
function broken( {
    // missing closing
"""
    result = parser.parse_string(code, "test.ts")

    # Tree-sitter is lenient, so it may still parse partially
    # Just ensure no crash
    assert isinstance(result.ok, bool)
