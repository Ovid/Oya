# Phase 1: Relationship Extraction Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Extract function calls, instantiations, and imports from Python and TypeScript code with confidence scores.

**Architecture:** Extend existing parsers to extract references alongside definitions. Add a resolver module to match references to definitions across files. Store resolved references with confidence scores.

**Tech Stack:** Python ast module (Python parsing), tree-sitter (TypeScript parsing), dataclasses for models.

---

## Task 1: Add Reference Model

**Files:**
- Modify: `backend/src/oya/parsing/models.py`
- Test: `backend/tests/test_parsing_models.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_parsing_models.py`:

```python
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
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/poecurt/projects/oya/.worktrees/graph-phase-1/backend && source .venv/bin/activate && pytest tests/test_parsing_models.py::test_reference_model_creation -v`

Expected: FAIL with ImportError (Reference not defined)

**Step 3: Write minimal implementation**

Add to `backend/src/oya/parsing/models.py`:

```python
class ReferenceType(Enum):
    """Types of references between code entities."""

    CALLS = "calls"
    INSTANTIATES = "instantiates"
    INHERITS = "inherits"
    IMPORTS = "imports"


@dataclass
class Reference:
    """A reference from one code entity to another."""

    source: str  # e.g., "auth/handler.py::login"
    target: str  # e.g., "auth/session.py::create_session" or unresolved name
    reference_type: ReferenceType
    confidence: float  # 0.0 to 1.0
    line: int  # Line number where reference occurs
    target_resolved: bool = False  # True if target is a full path, False if just a name
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/poecurt/projects/oya/.worktrees/graph-phase-1/backend && source .venv/bin/activate && pytest tests/test_parsing_models.py -v`

Expected: PASS

**Step 5: Commit**

```bash
cd /Users/poecurt/projects/oya/.worktrees/graph-phase-1
git add backend/src/oya/parsing/models.py backend/tests/test_parsing_models.py
git commit -m "feat(parsing): add Reference model with confidence scores"
```

---

## Task 2: Add References to ParsedFile

**Files:**
- Modify: `backend/src/oya/parsing/models.py`
- Test: `backend/tests/test_parsing_models.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_parsing_models.py`:

```python
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
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_parsing_models.py::test_parsed_file_has_references -v`

Expected: FAIL with TypeError (unexpected keyword argument 'references')

**Step 3: Write minimal implementation**

Modify `ParsedFile` in `backend/src/oya/parsing/models.py`:

```python
@dataclass
class ParsedFile:
    """Result of parsing a single file."""

    path: str
    language: str
    symbols: list[ParsedSymbol]
    imports: list[str] = field(default_factory=list)
    exports: list[str] = field(default_factory=list)
    references: list[Reference] = field(default_factory=list)  # ADD THIS LINE
    raw_content: str | None = None
    line_count: int = 0
    metadata: dict = field(default_factory=dict)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_parsing_models.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/oya/parsing/models.py backend/tests/test_parsing_models.py
git commit -m "feat(parsing): add references field to ParsedFile"
```

---

## Task 3: Export New Models from parsing module

**Files:**
- Modify: `backend/src/oya/parsing/__init__.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_parsing_models.py`:

```python
def test_reference_exports():
    """Reference and ReferenceType are exported from parsing module."""
    from oya.parsing import Reference, ReferenceType

    assert ReferenceType.CALLS.value == "calls"
    ref = Reference(
        source="a",
        target="b",
        reference_type=ReferenceType.CALLS,
        confidence=0.5,
        line=1,
    )
    assert ref.source == "a"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_parsing_models.py::test_reference_exports -v`

Expected: FAIL with ImportError

**Step 3: Write minimal implementation**

Update `backend/src/oya/parsing/__init__.py`:

```python
"""Code parsing utilities."""

from oya.parsing.models import (
    ParsedSymbol,
    SymbolType,
    ParsedFile,
    ParseResult,
    Reference,      # ADD
    ReferenceType,  # ADD
)
from oya.parsing.base import BaseParser
from oya.parsing.python_parser import PythonParser
from oya.parsing.typescript_parser import TypeScriptParser
from oya.parsing.java_parser import JavaParser
from oya.parsing.fallback_parser import FallbackParser
from oya.parsing.registry import ParserRegistry

__all__ = [
    "ParsedSymbol",
    "SymbolType",
    "ParsedFile",
    "ParseResult",
    "Reference",      # ADD
    "ReferenceType",  # ADD
    "BaseParser",
    "PythonParser",
    "TypeScriptParser",
    "JavaParser",
    "FallbackParser",
    "ParserRegistry",
]
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_parsing_models.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/oya/parsing/__init__.py backend/tests/test_parsing_models.py
git commit -m "feat(parsing): export Reference and ReferenceType"
```

---

## Task 4: Extract Function Calls in Python Parser

**Files:**
- Modify: `backend/src/oya/parsing/python_parser.py`
- Test: `backend/tests/test_python_parser.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_python_parser.py`:

```python
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
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_python_parser.py::test_extracts_function_calls -v`

Expected: FAIL (references list is empty)

**Step 3: Write minimal implementation**

Add to `PythonParser` class in `backend/src/oya/parsing/python_parser.py`:

First, add the import at the top:
```python
from oya.parsing.models import ParsedFile, ParsedSymbol, ParseResult, SymbolType, Reference, ReferenceType
```

Add a new method to extract calls:
```python
def _extract_calls(self, node: ast.AST, current_scope: str) -> list[Reference]:
    """Extract function/method calls from an AST node.

    Args:
        node: The AST node to analyze.
        current_scope: The current function/method name for source.

    Returns:
        List of Reference objects for calls found.
    """
    references = []

    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            target, confidence = self._resolve_call_target(child)
            if target:
                references.append(Reference(
                    source=current_scope,
                    target=target,
                    reference_type=ReferenceType.CALLS,
                    confidence=confidence,
                    line=child.lineno,
                ))

    return references

def _resolve_call_target(self, node: ast.Call) -> tuple[str | None, float]:
    """Resolve the target of a call expression.

    Args:
        node: The Call AST node.

    Returns:
        Tuple of (target_name, confidence).
    """
    func = node.func

    if isinstance(func, ast.Name):
        # Simple call: func()
        return func.id, 0.9
    elif isinstance(func, ast.Attribute):
        # Method call: obj.method()
        attr_name = self._get_attribute_name(func)
        return attr_name, 0.7

    return None, 0.0
```

Modify `_parse_function` to collect references and update the `parse` method to aggregate them:

In the `parse` method, add reference collection:
```python
def parse(self, file_path: Path, content: str) -> ParseResult:
    """Parse Python file content and extract symbols."""
    try:
        tree = ast.parse(content, filename=str(file_path))
    except SyntaxError as e:
        return ParseResult.failure(str(file_path), f"Syntax error: {e}")

    symbols: list[ParsedSymbol] = []
    imports: list[str] = []
    references: list[Reference] = []

    # Process top-level nodes
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            symbols.append(self._parse_function(node, parent=None))
            scope = f"{file_path}::{node.name}"
            references.extend(self._extract_calls(node, scope))
        elif isinstance(node, ast.ClassDef):
            symbols.extend(self._parse_class(node))
            # Extract calls from methods
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    scope = f"{file_path}::{node.name}.{item.name}"
                    references.extend(self._extract_calls(item, scope))
        elif isinstance(node, ast.Import):
            imports.extend(self._parse_import(node))
        elif isinstance(node, ast.ImportFrom):
            imports.extend(self._parse_import_from(node))
        elif isinstance(node, ast.Assign):
            symbols.extend(self._parse_assignment(node))

    parsed_file = ParsedFile(
        path=str(file_path),
        language="python",
        symbols=symbols,
        imports=imports,
        references=references,
        raw_content=content,
        line_count=content.count("\n") + 1,
    )

    return ParseResult.success(parsed_file)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_python_parser.py::test_extracts_function_calls -v`

Expected: PASS

**Step 5: Run all Python parser tests to check for regressions**

Run: `pytest tests/test_python_parser.py -v`

Expected: All tests PASS

**Step 6: Commit**

```bash
git add backend/src/oya/parsing/python_parser.py backend/tests/test_python_parser.py
git commit -m "feat(parsing): extract function calls in Python parser"
```

---

## Task 5: Extract Class Instantiations in Python Parser

**Files:**
- Modify: `backend/src/oya/parsing/python_parser.py`
- Test: `backend/tests/test_python_parser.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_python_parser.py`:

```python
def test_extracts_instantiations(parser):
    """Extracts class instantiations."""
    code = '''
def main():
    user = User("alice")
    config = Config()
'''
    result = parser.parse_string(code, "test.py")

    assert result.ok
    refs = result.file.references

    # Should find instantiations of User and Config
    instantiations = [r for r in refs if r.reference_type.value == "instantiates"]
    targets = [r.target for r in instantiations]

    assert "User" in targets
    assert "Config" in targets
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_python_parser.py::test_extracts_instantiations -v`

Expected: FAIL (instantiations are classified as calls, not instantiates)

**Step 3: Write minimal implementation**

Modify `_resolve_call_target` in `backend/src/oya/parsing/python_parser.py`:

```python
def _resolve_call_target(self, node: ast.Call) -> tuple[str | None, float, ReferenceType]:
    """Resolve the target of a call expression.

    Args:
        node: The Call AST node.

    Returns:
        Tuple of (target_name, confidence, reference_type).
    """
    func = node.func

    if isinstance(func, ast.Name):
        name = func.id
        # Convention: CapitalCase names are likely classes (instantiation)
        if name and name[0].isupper():
            return name, 0.85, ReferenceType.INSTANTIATES
        return name, 0.9, ReferenceType.CALLS
    elif isinstance(func, ast.Attribute):
        attr_name = self._get_attribute_name(func)
        # Check if final component is CapitalCase
        parts = attr_name.split(".")
        if parts and parts[-1][0].isupper():
            return attr_name, 0.75, ReferenceType.INSTANTIATES
        return attr_name, 0.7, ReferenceType.CALLS

    return None, 0.0, ReferenceType.CALLS
```

Update `_extract_calls` to use the new return value:

```python
def _extract_calls(self, node: ast.AST, current_scope: str) -> list[Reference]:
    """Extract function/method calls from an AST node."""
    references = []

    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            target, confidence, ref_type = self._resolve_call_target(child)
            if target:
                references.append(Reference(
                    source=current_scope,
                    target=target,
                    reference_type=ref_type,
                    confidence=confidence,
                    line=child.lineno,
                ))

    return references
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_python_parser.py::test_extracts_instantiations -v`

Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/oya/parsing/python_parser.py backend/tests/test_python_parser.py
git commit -m "feat(parsing): extract class instantiations in Python parser"
```

---

## Task 6: Extract Class Inheritance in Python Parser

**Files:**
- Modify: `backend/src/oya/parsing/python_parser.py`
- Test: `backend/tests/test_python_parser.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_python_parser.py`:

```python
def test_extracts_inheritance(parser):
    """Extracts class inheritance relationships."""
    code = '''
class Animal:
    pass

class Dog(Animal):
    pass

class Labrador(Dog, Serializable):
    pass
'''
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
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_python_parser.py::test_extracts_inheritance -v`

Expected: FAIL (no inheritance references extracted)

**Step 3: Write minimal implementation**

Add to `PythonParser` class:

```python
def _extract_inheritance(self, node: ast.ClassDef, file_path: str) -> list[Reference]:
    """Extract inheritance relationships from a class definition.

    Args:
        node: The ClassDef AST node.
        file_path: Path to the file being parsed.

    Returns:
        List of Reference objects for inheritance.
    """
    references = []
    class_scope = f"{file_path}::{node.name}"

    for base in node.bases:
        if isinstance(base, ast.Name):
            references.append(Reference(
                source=class_scope,
                target=base.id,
                reference_type=ReferenceType.INHERITS,
                confidence=0.95,  # High confidence for direct name
                line=node.lineno,
            ))
        elif isinstance(base, ast.Attribute):
            target = self._get_attribute_name(base)
            references.append(Reference(
                source=class_scope,
                target=target,
                reference_type=ReferenceType.INHERITS,
                confidence=0.9,  # Slightly lower for dotted names
                line=node.lineno,
            ))

    return references
```

Update the `parse` method to call `_extract_inheritance`:

In the `elif isinstance(node, ast.ClassDef):` block, add:
```python
elif isinstance(node, ast.ClassDef):
    symbols.extend(self._parse_class(node))
    # Extract inheritance
    references.extend(self._extract_inheritance(node, str(file_path)))
    # Extract calls from methods
    for item in node.body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            scope = f"{file_path}::{node.name}.{item.name}"
            references.extend(self._extract_calls(item, scope))
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_python_parser.py::test_extracts_inheritance -v`

Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/oya/parsing/python_parser.py backend/tests/test_python_parser.py
git commit -m "feat(parsing): extract class inheritance in Python parser"
```

---

## Task 7: Extract Import References in Python Parser

**Files:**
- Modify: `backend/src/oya/parsing/python_parser.py`
- Test: `backend/tests/test_python_parser.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_python_parser.py`:

```python
def test_extracts_import_references(parser):
    """Extracts import statements as references."""
    code = '''
import os
from pathlib import Path
from typing import List, Dict
from myapp.models import User
'''
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
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_python_parser.py::test_extracts_import_references -v`

Expected: FAIL (no import references in references list)

**Step 3: Write minimal implementation**

Add to `PythonParser` class:

```python
def _extract_import_references(self, node: ast.Import | ast.ImportFrom, file_path: str) -> list[Reference]:
    """Extract import statements as references.

    Args:
        node: The Import or ImportFrom AST node.
        file_path: Path to the file being parsed.

    Returns:
        List of Reference objects for imports.
    """
    references = []
    file_scope = str(file_path)

    if isinstance(node, ast.Import):
        for alias in node.names:
            references.append(Reference(
                source=file_scope,
                target=alias.name,
                reference_type=ReferenceType.IMPORTS,
                confidence=0.99,
                line=node.lineno,
            ))
    elif isinstance(node, ast.ImportFrom):
        module = node.module or ""
        for alias in node.names:
            target = f"{module}.{alias.name}" if module else alias.name
            references.append(Reference(
                source=file_scope,
                target=target,
                reference_type=ReferenceType.IMPORTS,
                confidence=0.99,
                line=node.lineno,
            ))

    return references
```

Update the `parse` method to call `_extract_import_references`:

```python
elif isinstance(node, ast.Import):
    imports.extend(self._parse_import(node))
    references.extend(self._extract_import_references(node, str(file_path)))
elif isinstance(node, ast.ImportFrom):
    imports.extend(self._parse_import_from(node))
    references.extend(self._extract_import_references(node, str(file_path)))
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_python_parser.py::test_extracts_import_references -v`

Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/oya/parsing/python_parser.py backend/tests/test_python_parser.py
git commit -m "feat(parsing): extract import references in Python parser"
```

---

## Task 8: Run Full Test Suite and Fix Any Regressions

**Files:**
- All modified files

**Step 1: Run all backend tests**

Run: `cd /Users/poecurt/projects/oya/.worktrees/graph-phase-1/backend && source .venv/bin/activate && pytest -v --tb=short`

**Step 2: Fix any failing tests**

If any tests fail, analyze the failure and fix. Common issues:
- Tests that assert on exact reference counts may need updating
- Tests that check ParsedFile structure may need updating

**Step 3: Commit fixes if any**

```bash
git add -A
git commit -m "fix: resolve test regressions from reference extraction"
```

---

## Task 9: Extract Function Calls in TypeScript Parser

**Files:**
- Modify: `backend/src/oya/parsing/typescript_parser.py`
- Test: `backend/tests/test_typescript_parser.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_typescript_parser.py`:

```python
def test_extracts_function_calls(parser):
    """Extracts function calls with confidence."""
    code = '''
function main() {
    const result = helper();
    process(result);
}
'''
    result = parser.parse_string(code, "test.ts")

    assert result.ok
    refs = result.file.references

    call_names = [r.target for r in refs if r.reference_type.value == "calls"]
    assert "helper" in call_names
    assert "process" in call_names
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_typescript_parser.py::test_extracts_function_calls -v`

Expected: FAIL (references list is empty)

**Step 3: Write minimal implementation**

Add import at top of `backend/src/oya/parsing/typescript_parser.py`:
```python
from oya.parsing.models import ParsedFile, ParsedSymbol, ParseResult, SymbolType, Reference, ReferenceType
```

Add methods to extract calls:

```python
def _extract_calls_from_node(
    self,
    node,
    references: list[Reference],
    content: str,
    current_scope: str,
) -> None:
    """Recursively extract function calls from a tree-sitter node.

    Args:
        node: Current tree-sitter node.
        references: List to append references to.
        content: Original source content.
        current_scope: Current function/method scope.
    """
    if node.type == "call_expression":
        func_node = node.child_by_field_name("function")
        if func_node:
            target, confidence, ref_type = self._resolve_ts_call_target(func_node, content)
            if target:
                references.append(Reference(
                    source=current_scope,
                    target=target,
                    reference_type=ref_type,
                    confidence=confidence,
                    line=node.start_point[0] + 1,
                ))

    # Recurse into children
    for child in node.children:
        self._extract_calls_from_node(child, references, content, current_scope)

def _resolve_ts_call_target(self, func_node, content: str) -> tuple[str | None, float, ReferenceType]:
    """Resolve the target of a TypeScript call expression.

    Args:
        func_node: The function node of the call_expression.
        content: Original source content.

    Returns:
        Tuple of (target_name, confidence, reference_type).
    """
    node_type = func_node.type

    if node_type == "identifier":
        name = self._get_node_text(func_node, content)
        # CapitalCase = likely class instantiation
        if name and name[0].isupper():
            return name, 0.85, ReferenceType.INSTANTIATES
        return name, 0.9, ReferenceType.CALLS
    elif node_type == "member_expression":
        # obj.method()
        text = self._get_node_text(func_node, content)
        return text, 0.7, ReferenceType.CALLS
    elif node_type == "new_expression":
        # new ClassName()
        return None, 0.0, ReferenceType.CALLS  # Handled separately

    return None, 0.0, ReferenceType.CALLS
```

Update `_extract_function` to extract calls:

```python
def _extract_function(
    self,
    node,
    symbols: list[ParsedSymbol],
    content: str,
    parent_class: str | None = None,
    references: list[Reference] | None = None,
    file_path: str = "",
) -> None:
    """Extract a function declaration."""
    name_node = node.child_by_field_name("name")
    if not name_node:
        return

    name = self._get_node_text(name_node, content)
    start_line = node.start_point[0] + 1
    end_line = node.end_point[0] + 1

    symbols.append(
        ParsedSymbol(
            name=name,
            symbol_type=SymbolType.METHOD if parent_class else SymbolType.FUNCTION,
            start_line=start_line,
            end_line=end_line,
            parent=parent_class,
        )
    )

    # Extract calls if references list provided
    if references is not None:
        scope = f"{file_path}::{parent_class}.{name}" if parent_class else f"{file_path}::{name}"
        body_node = node.child_by_field_name("body")
        if body_node:
            self._extract_calls_from_node(body_node, references, content, scope)
```

Update `_walk_tree` to pass references list and update `parse` to initialize it.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_typescript_parser.py::test_extracts_function_calls -v`

Expected: PASS

**Step 5: Run all TypeScript parser tests**

Run: `pytest tests/test_typescript_parser.py -v`

Expected: All PASS

**Step 6: Commit**

```bash
git add backend/src/oya/parsing/typescript_parser.py backend/tests/test_typescript_parser.py
git commit -m "feat(parsing): extract function calls in TypeScript parser"
```

---

## Task 10: Extract new Expressions (Instantiations) in TypeScript Parser

**Files:**
- Modify: `backend/src/oya/parsing/typescript_parser.py`
- Test: `backend/tests/test_typescript_parser.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_typescript_parser.py`:

```python
def test_extracts_new_expressions(parser):
    """Extracts class instantiations via new keyword."""
    code = '''
function main() {
    const user = new User("alice");
    const config = new Config();
}
'''
    result = parser.parse_string(code, "test.ts")

    assert result.ok
    refs = result.file.references

    instantiations = [r for r in refs if r.reference_type.value == "instantiates"]
    targets = [r.target for r in instantiations]

    assert "User" in targets
    assert "Config" in targets
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_typescript_parser.py::test_extracts_new_expressions -v`

Expected: FAIL

**Step 3: Write minimal implementation**

Add handling for `new_expression` in `_extract_calls_from_node`:

```python
def _extract_calls_from_node(
    self,
    node,
    references: list[Reference],
    content: str,
    current_scope: str,
) -> None:
    """Recursively extract function calls from a tree-sitter node."""
    if node.type == "call_expression":
        func_node = node.child_by_field_name("function")
        if func_node:
            target, confidence, ref_type = self._resolve_ts_call_target(func_node, content)
            if target:
                references.append(Reference(
                    source=current_scope,
                    target=target,
                    reference_type=ref_type,
                    confidence=confidence,
                    line=node.start_point[0] + 1,
                ))
    elif node.type == "new_expression":
        # new ClassName(...)
        constructor_node = node.child_by_field_name("constructor")
        if constructor_node:
            target = self._get_node_text(constructor_node, content)
            references.append(Reference(
                source=current_scope,
                target=target,
                reference_type=ReferenceType.INSTANTIATES,
                confidence=0.95,
                line=node.start_point[0] + 1,
            ))

    # Recurse into children
    for child in node.children:
        self._extract_calls_from_node(child, references, content, current_scope)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_typescript_parser.py::test_extracts_new_expressions -v`

Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/oya/parsing/typescript_parser.py backend/tests/test_typescript_parser.py
git commit -m "feat(parsing): extract new expressions in TypeScript parser"
```

---

## Task 11: Extract Class Inheritance in TypeScript Parser

**Files:**
- Modify: `backend/src/oya/parsing/typescript_parser.py`
- Test: `backend/tests/test_typescript_parser.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_typescript_parser.py`:

```python
def test_extracts_inheritance(parser):
    """Extracts class inheritance (extends)."""
    code = '''
class Animal {}

class Dog extends Animal {}

class Labrador extends Dog implements Serializable {}
'''
    result = parser.parse_string(code, "test.ts")

    assert result.ok
    refs = result.file.references

    inherits = [r for r in refs if r.reference_type.value == "inherits"]

    # Dog extends Animal
    dog_inherits = [r for r in inherits if "Dog" in r.source]
    assert len(dog_inherits) >= 1
    assert any(r.target == "Animal" for r in dog_inherits)

    # Labrador extends Dog
    lab_inherits = [r for r in inherits if "Labrador" in r.source]
    assert any(r.target == "Dog" for r in lab_inherits)
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_typescript_parser.py::test_extracts_inheritance -v`

Expected: FAIL

**Step 3: Write minimal implementation**

Update `_extract_class` to extract inheritance:

```python
def _extract_class(
    self,
    node,
    symbols: list[ParsedSymbol],
    content: str,
    references: list[Reference] | None = None,
    file_path: str = "",
) -> None:
    """Extract a class declaration and its methods."""
    name_node = node.child_by_field_name("name")
    if not name_node:
        return

    class_name = self._get_node_text(name_node, content)
    start_line = node.start_point[0] + 1
    end_line = node.end_point[0] + 1
    class_scope = f"{file_path}::{class_name}"

    symbols.append(
        ParsedSymbol(
            name=class_name,
            symbol_type=SymbolType.CLASS,
            start_line=start_line,
            end_line=end_line,
        )
    )

    # Extract inheritance (extends clause)
    if references is not None:
        for child in node.children:
            if child.type == "class_heritage":
                for heritage_child in child.children:
                    if heritage_child.type == "extends_clause":
                        # Get the class being extended
                        for ext_child in heritage_child.children:
                            if ext_child.type == "identifier":
                                target = self._get_node_text(ext_child, content)
                                references.append(Reference(
                                    source=class_scope,
                                    target=target,
                                    reference_type=ReferenceType.INHERITS,
                                    confidence=0.95,
                                    line=start_line,
                                ))

    # Process class body for methods
    body_node = node.child_by_field_name("body")
    if body_node:
        for child in body_node.children:
            if child.type == "method_definition":
                self._extract_method(child, symbols, content, class_name, references, file_path)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_typescript_parser.py::test_extracts_inheritance -v`

Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/oya/parsing/typescript_parser.py backend/tests/test_typescript_parser.py
git commit -m "feat(parsing): extract class inheritance in TypeScript parser"
```

---

## Task 12: Final Integration Test - Self-Analysis

**Files:**
- Test: `backend/tests/test_reference_extraction.py` (new file)

**Step 1: Write the integration test**

Create `backend/tests/test_reference_extraction.py`:

```python
"""Integration tests for reference extraction."""

import pytest
from pathlib import Path

from oya.parsing import PythonParser, TypeScriptParser, ReferenceType


class TestPythonReferenceExtraction:
    """Test reference extraction on real Python code."""

    @pytest.fixture
    def parser(self):
        return PythonParser()

    def test_extracts_references_from_real_code(self, parser):
        """Parse a realistic Python file and verify reference extraction."""
        code = '''
from typing import Optional
from dataclasses import dataclass

@dataclass
class User:
    """A user entity."""
    name: str
    email: str

class UserService:
    """Service for user operations."""

    def __init__(self, db: Database):
        self.db = db

    def create_user(self, name: str, email: str) -> User:
        """Create a new user."""
        user = User(name=name, email=email)
        self.db.save(user)
        return user

    def find_user(self, email: str) -> Optional[User]:
        """Find user by email."""
        return self.db.query(User).filter_by(email=email).first()
'''
        result = parser.parse_string(code, "user_service.py")

        assert result.ok
        refs = result.file.references

        # Should have imports
        imports = [r for r in refs if r.reference_type == ReferenceType.IMPORTS]
        assert len(imports) >= 2

        # Should have instantiation of User
        instantiations = [r for r in refs if r.reference_type == ReferenceType.INSTANTIATES]
        assert any(r.target == "User" for r in instantiations)

        # Should have method calls
        calls = [r for r in refs if r.reference_type == ReferenceType.CALLS]
        assert any("save" in r.target for r in calls)
        assert any("query" in r.target for r in calls)


class TestTypeScriptReferenceExtraction:
    """Test reference extraction on real TypeScript code."""

    @pytest.fixture
    def parser(self):
        return TypeScriptParser()

    def test_extracts_references_from_real_code(self, parser):
        """Parse a realistic TypeScript file and verify reference extraction."""
        code = '''
import { User } from './models';
import { Database } from './database';

export class UserService {
    private db: Database;

    constructor(db: Database) {
        this.db = db;
    }

    async createUser(name: string, email: string): Promise<User> {
        const user = new User(name, email);
        await this.db.save(user);
        return user;
    }

    async findUser(email: string): Promise<User | null> {
        return this.db.query(User).filterBy({ email }).first();
    }
}
'''
        result = parser.parse_string(code, "user_service.ts")

        assert result.ok
        refs = result.file.references

        # Should have instantiation of User via new
        instantiations = [r for r in refs if r.reference_type == ReferenceType.INSTANTIATES]
        assert any(r.target == "User" for r in instantiations)

        # Should have method calls
        calls = [r for r in refs if r.reference_type == ReferenceType.CALLS]
        assert len(calls) > 0
```

**Step 2: Run the integration test**

Run: `pytest tests/test_reference_extraction.py -v`

Expected: PASS

**Step 3: Run full test suite**

Run: `pytest -v --tb=short`

Expected: All tests PASS

**Step 4: Commit**

```bash
git add backend/tests/test_reference_extraction.py
git commit -m "test: add integration tests for reference extraction"
```

---

## Task 13: Update Existing Tests If Needed

**Files:**
- Various test files that may assert on ParsedFile structure

**Step 1: Run full test suite and identify failures**

Run: `pytest -v 2>&1 | grep -E "(FAILED|ERROR)"`

**Step 2: Fix any tests that fail due to new references field**

Common fixes:
- Tests checking `len(result.file.symbols)` may need adjustment
- Tests that construct ParsedFile manually may need to handle references

**Step 3: Commit fixes**

```bash
git add -A
git commit -m "fix: update tests for new references field"
```

---

## Task 14: Documentation Update

**Files:**
- Modify: `backend/src/oya/parsing/models.py` (docstrings)

**Step 1: Ensure all new models have complete docstrings**

Verify `Reference` and `ReferenceType` have proper docstrings explaining:
- What each field means
- Confidence score interpretation
- When each ReferenceType is used

**Step 2: Commit**

```bash
git add backend/src/oya/parsing/models.py
git commit -m "docs: add docstrings for Reference model"
```

---

## Task 15: Final Verification

**Step 1: Run full test suite**

Run: `cd /Users/poecurt/projects/oya/.worktrees/graph-phase-1/backend && source .venv/bin/activate && pytest -v`

Expected: All 569+ tests PASS

**Step 2: Run linter**

Run: `ruff check backend/src/oya/parsing/`

Expected: No errors

**Step 3: Verify self-analysis works**

Run a quick manual test parsing Oya's own orchestrator:

```python
# Quick verification script
from pathlib import Path
from oya.parsing import PythonParser

parser = PythonParser()
content = Path("backend/src/oya/generation/orchestrator.py").read_text()
result = parser.parse(Path("orchestrator.py"), content)

print(f"Symbols: {len(result.file.symbols)}")
print(f"References: {len(result.file.references)}")
print(f"Sample calls: {[r.target for r in result.file.references if r.reference_type.value == 'calls'][:5]}")
```

**Step 4: Create Phase 1 completion commit**

```bash
git add -A
git commit -m "feat: complete Phase 1 - reference extraction with confidence scores

- Added Reference and ReferenceType models
- Python parser extracts calls, instantiations, inheritance, imports
- TypeScript parser extracts calls, new expressions, inheritance
- All references include confidence scores
- Integration tests verify extraction on realistic code"
```

---

## Checkpoint: Phase 1 Complete

At this point, Phase 1 is complete. Verify:

1. [ ] Python parser extracts function calls with confidence
2. [ ] Python parser extracts class instantiations with confidence
3. [ ] Python parser extracts inheritance relationships
4. [ ] Python parser extracts import references
5. [ ] TypeScript parser extracts function calls
6. [ ] TypeScript parser extracts new expressions (instantiations)
7. [ ] TypeScript parser extracts class inheritance
8. [ ] All existing tests still pass
9. [ ] Self-analysis of Oya's code produces sensible references

**Next: Phase 2 (Graph Building)** - but first, run a design session for Phase 2.
