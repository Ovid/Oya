# Decorator Pattern Detection - Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Reduce dead code false positive rate from 94% to near-zero by detecting decorator-based framework usage (FastAPI routes, pytest fixtures, etc.)

**Architecture:** Add declarative pattern registry that parsers consult during AST traversal. Patterns define which decorator arguments create references and which decorators mark symbols as entry points. Graph builder propagates `is_entry_point` metadata, and dead code analyzer filters entry points.

**Tech Stack:** Python dataclasses, regex for pattern matching, existing AST infrastructure

---

## Task 1: Create Pattern Registry Module

**Files:**
- Create: `backend/src/oya/parsing/decorator_patterns.py`
- Test: `backend/tests/test_decorator_patterns.py`

**Step 1: Write the failing test**

Create `backend/tests/test_decorator_patterns.py`:

```python
"""Tests for decorator pattern registry."""

import re

from oya.parsing.decorator_patterns import (
    ENTRY_POINT_PATTERNS,
    REFERENCE_PATTERNS,
    EntryPointPattern,
    ReferencePattern,
)


def test_reference_pattern_dataclass_is_frozen():
    """ReferencePattern is immutable (frozen dataclass)."""
    pattern = ReferencePattern(
        decorator_name=r"^get$",
        object_name=r".*",
        arguments=("response_model",),
    )
    # Attempting to modify should raise
    try:
        pattern.decorator_name = "new"
        assert False, "Should have raised FrozenInstanceError"
    except AttributeError:
        pass  # Expected - frozen dataclass


def test_entry_point_pattern_dataclass_is_frozen():
    """EntryPointPattern is immutable (frozen dataclass)."""
    pattern = EntryPointPattern(
        decorator_name=r"^fixture$",
        object_name=r"^pytest$",
    )
    try:
        pattern.decorator_name = "new"
        assert False, "Should have raised FrozenInstanceError"
    except AttributeError:
        pass  # Expected


def test_python_reference_patterns_exist():
    """Python reference patterns are defined."""
    assert "python" in REFERENCE_PATTERNS
    assert len(REFERENCE_PATTERNS["python"]) > 0


def test_python_entry_point_patterns_exist():
    """Python entry point patterns are defined."""
    assert "python" in ENTRY_POINT_PATTERNS
    assert len(ENTRY_POINT_PATTERNS["python"]) > 0


def test_fastapi_route_pattern_matches():
    """FastAPI route patterns match HTTP methods."""
    patterns = REFERENCE_PATTERNS["python"]
    route_pattern = next(
        p for p in patterns if "response_model" in p.arguments
    )

    # Should match HTTP methods
    assert re.match(route_pattern.decorator_name, "get")
    assert re.match(route_pattern.decorator_name, "post")
    assert re.match(route_pattern.decorator_name, "put")
    assert re.match(route_pattern.decorator_name, "patch")
    assert re.match(route_pattern.decorator_name, "delete")

    # Should NOT match non-HTTP methods
    assert not re.match(route_pattern.decorator_name, "route")
    assert not re.match(route_pattern.decorator_name, "depends")


def test_fastapi_entry_point_pattern_matches():
    """FastAPI route handlers are marked as entry points."""
    patterns = ENTRY_POINT_PATTERNS["python"]
    route_patterns = [
        p for p in patterns
        if re.match(p.decorator_name, "get")
    ]

    assert len(route_patterns) > 0
```

**Step 2: Run test to verify it fails**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_decorator_patterns.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'oya.parsing.decorator_patterns'"

**Step 3: Write minimal implementation**

Create `backend/src/oya/parsing/decorator_patterns.py`:

```python
"""Decorator pattern registry for reference and entry point detection.

This module defines patterns for framework decorators that:
1. Create references to types (e.g., FastAPI response_model=MyClass)
2. Mark symbols as entry points (e.g., route handlers, fixtures)

Parsers consult these patterns during AST traversal to extract
references that wouldn't otherwise be detected.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ReferencePattern:
    """Pattern for decorators whose arguments create references.

    Attributes:
        decorator_name: Regex matching decorator name (e.g., "get|post|put").
        object_name: Regex matching object (e.g., "router|app"), None for bare decorators.
        arguments: Tuple of argument names that contain type references.
    """

    decorator_name: str
    object_name: str | None
    arguments: tuple[str, ...]


@dataclass(frozen=True)
class EntryPointPattern:
    """Pattern for decorators that mark symbols as externally invoked.

    Attributes:
        decorator_name: Regex matching decorator name.
        object_name: Regex matching object, None for bare decorators.
    """

    decorator_name: str
    object_name: str | None


# Registry keyed by language
REFERENCE_PATTERNS: dict[str, list[ReferencePattern]] = {
    "python": [
        # FastAPI/Starlette route handlers
        ReferencePattern(
            decorator_name=r"^(get|post|put|patch|delete|head|options|trace)$",
            object_name=r".*",  # router, app, or any object
            arguments=("response_model", "response_class"),
        ),
    ],
    "typescript": [],
}

ENTRY_POINT_PATTERNS: dict[str, list[EntryPointPattern]] = {
    "python": [
        # FastAPI/Starlette routes
        EntryPointPattern(
            decorator_name=r"^(get|post|put|patch|delete|head|options|trace)$",
            object_name=r".*",
        ),
        # pytest
        EntryPointPattern(decorator_name=r"^fixture$", object_name=r"^pytest$"),
        EntryPointPattern(decorator_name=r"^fixture$", object_name=None),  # bare @fixture
        EntryPointPattern(decorator_name=r"^parametrize$", object_name=r"^pytest\.mark$"),
        # Click CLI
        EntryPointPattern(decorator_name=r"^command$", object_name=r".*"),
        EntryPointPattern(decorator_name=r"^group$", object_name=r".*"),
        # Celery
        EntryPointPattern(decorator_name=r"^task$", object_name=r".*"),
        # SQLAlchemy events
        EntryPointPattern(decorator_name=r"^listens_for$", object_name=r"^event$"),
    ],
    "typescript": [],
}
```

**Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_decorator_patterns.py -v`
Expected: PASS (all 7 tests)

**Step 5: Commit**

```bash
git add backend/src/oya/parsing/decorator_patterns.py backend/tests/test_decorator_patterns.py
git commit -m "$(cat <<'EOF'
feat(deadcode): add decorator pattern registry

Add dataclasses and initial patterns for FastAPI routes, pytest fixtures,
Click commands, Celery tasks, and SQLAlchemy events.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Add Pattern Matching Helpers to Base Parser

**Files:**
- Modify: `backend/src/oya/parsing/base.py`
- Test: `backend/tests/test_base_parser.py` (new file)

**Step 1: Write the failing test**

Create `backend/tests/test_base_parser.py`:

```python
"""Tests for base parser pattern matching helpers."""

from oya.parsing.base import BaseParser
from oya.parsing.decorator_patterns import EntryPointPattern, ReferencePattern


class ConcreteParser(BaseParser):
    """Minimal concrete parser for testing base class methods."""

    @property
    def supported_extensions(self) -> list[str]:
        return [".test"]

    @property
    def language_name(self) -> str:
        return "python"  # Use python to get real patterns

    def parse(self, file_path, content):
        raise NotImplementedError


def test_get_reference_patterns_returns_python_patterns():
    """_get_reference_patterns returns patterns for parser's language."""
    parser = ConcreteParser()
    patterns = parser._get_reference_patterns()

    assert len(patterns) > 0
    assert all(isinstance(p, ReferencePattern) for p in patterns)


def test_get_entry_point_patterns_returns_python_patterns():
    """_get_entry_point_patterns returns patterns for parser's language."""
    parser = ConcreteParser()
    patterns = parser._get_entry_point_patterns()

    assert len(patterns) > 0
    assert all(isinstance(p, EntryPointPattern) for p in patterns)


def test_matches_decorator_pattern_simple_match():
    """_matches_decorator_pattern returns True for matching decorator."""
    parser = ConcreteParser()
    pattern = ReferencePattern(
        decorator_name=r"^get$",
        object_name=r".*",
        arguments=("response_model",),
    )

    assert parser._matches_decorator_pattern("get", "router", pattern) is True
    assert parser._matches_decorator_pattern("get", "app", pattern) is True


def test_matches_decorator_pattern_name_mismatch():
    """_matches_decorator_pattern returns False for wrong decorator name."""
    parser = ConcreteParser()
    pattern = ReferencePattern(
        decorator_name=r"^get$",
        object_name=r".*",
        arguments=("response_model",),
    )

    assert parser._matches_decorator_pattern("post", "router", pattern) is False
    assert parser._matches_decorator_pattern("route", "app", pattern) is False


def test_matches_decorator_pattern_object_mismatch():
    """_matches_decorator_pattern returns False for wrong object name."""
    parser = ConcreteParser()
    pattern = ReferencePattern(
        decorator_name=r"^fixture$",
        object_name=r"^pytest$",  # Only matches pytest
        arguments=(),
    )

    assert parser._matches_decorator_pattern("fixture", "pytest", pattern) is True
    assert parser._matches_decorator_pattern("fixture", "other", pattern) is False


def test_matches_decorator_pattern_none_object_for_bare_decorator():
    """_matches_decorator_pattern handles bare decorators (no object)."""
    parser = ConcreteParser()
    pattern = EntryPointPattern(
        decorator_name=r"^fixture$",
        object_name=None,  # Bare decorator
    )

    # None pattern matches any object_name (including None)
    assert parser._matches_decorator_pattern("fixture", None, pattern) is True
    assert parser._matches_decorator_pattern("fixture", "pytest", pattern) is True


def test_matches_decorator_pattern_requires_object_when_specified():
    """_matches_decorator_pattern requires object when pattern specifies one."""
    parser = ConcreteParser()
    pattern = ReferencePattern(
        decorator_name=r"^get$",
        object_name=r"^router$",  # Must be 'router'
        arguments=("response_model",),
    )

    # Object must match when pattern specifies one
    assert parser._matches_decorator_pattern("get", "router", pattern) is True
    assert parser._matches_decorator_pattern("get", None, pattern) is False
```

**Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_base_parser.py -v`
Expected: FAIL with "AttributeError: 'ConcreteParser' object has no attribute '_get_reference_patterns'"

**Step 3: Write minimal implementation**

Modify `backend/src/oya/parsing/base.py` to add the helper methods:

```python
"""Base parser interface."""

import re
from abc import ABC, abstractmethod
from pathlib import Path

from oya.parsing.models import ParseResult
from oya.parsing.decorator_patterns import (
    ENTRY_POINT_PATTERNS,
    REFERENCE_PATTERNS,
    EntryPointPattern,
    ReferencePattern,
)


class BaseParser(ABC):
    """Abstract base class for language-specific parsers."""

    @property
    @abstractmethod
    def supported_extensions(self) -> list[str]:
        """File extensions this parser handles (e.g., ['.py'])."""
        pass

    @property
    @abstractmethod
    def language_name(self) -> str:
        """Human-readable language name."""
        pass

    @abstractmethod
    def parse(self, file_path: Path, content: str) -> ParseResult:
        """Parse file content and extract symbols.

        Args:
            file_path: Path to the file (for error messages).
            content: File content as string.

        Returns:
            ParseResult with extracted symbols or error.
        """
        pass

    def can_parse(self, file_path: Path) -> bool:
        """Check if this parser can handle the given file.

        Args:
            file_path: Path to check.

        Returns:
            True if this parser supports the file extension.
        """
        return file_path.suffix.lower() in self.supported_extensions

    def _get_reference_patterns(self) -> list[ReferencePattern]:
        """Get reference patterns for this parser's language."""
        return REFERENCE_PATTERNS.get(self.language_name.lower(), [])

    def _get_entry_point_patterns(self) -> list[EntryPointPattern]:
        """Get entry point patterns for this parser's language."""
        return ENTRY_POINT_PATTERNS.get(self.language_name.lower(), [])

    def _matches_decorator_pattern(
        self,
        decorator_name: str,
        object_name: str | None,
        pattern: ReferencePattern | EntryPointPattern,
    ) -> bool:
        """Check if decorator matches pattern.

        Args:
            decorator_name: The decorator's method/function name (e.g., "get" in router.get).
            object_name: The object the decorator is called on (e.g., "router"), or None.
            pattern: The pattern to match against.

        Returns:
            True if the decorator matches the pattern.
        """
        # Decorator name must match
        if not re.match(pattern.decorator_name, decorator_name):
            return False

        # If pattern specifies an object, it must match
        if pattern.object_name is not None:
            if object_name is None:
                return False
            if not re.match(pattern.object_name, object_name):
                return False

        return True
```

**Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_base_parser.py -v`
Expected: PASS (all 7 tests)

**Step 5: Commit**

```bash
git add backend/src/oya/parsing/base.py backend/tests/test_base_parser.py
git commit -m "$(cat <<'EOF'
feat(parsing): add pattern matching helpers to BaseParser

Add _get_reference_patterns(), _get_entry_point_patterns(), and
_matches_decorator_pattern() to base class for decorator pattern detection.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Implement Decorator AST Extraction in Python Parser

**Files:**
- Modify: `backend/src/oya/parsing/python_parser.py`
- Modify: `backend/tests/test_python_parser.py` (add tests)

**Step 1: Write the failing test**

Add to `backend/tests/test_python_parser.py`:

```python
def test_extracts_fastapi_response_model_reference(parser):
    """Extracts reference from response_model decorator argument."""
    code = '''
from pydantic import BaseModel

class UserResponse(BaseModel):
    id: int
    name: str

@router.get("/users/{user_id}", response_model=UserResponse)
def get_user(user_id: int):
    pass
'''
    result = parser.parse_string(code, "api/users.py")

    assert result.ok
    refs = result.file.references

    # Should have a reference from get_user to UserResponse
    decorator_refs = [
        r for r in refs
        if r.target == "UserResponse" and "get_user" in r.source
    ]
    assert len(decorator_refs) == 1
    assert decorator_refs[0].reference_type.value == "decorator_argument"


def test_extracts_multiple_response_model_arguments(parser):
    """Extracts references from multiple decorator arguments."""
    code = '''
@router.post("/items", response_model=ItemResponse, response_class=JSONResponse)
def create_item():
    pass
'''
    result = parser.parse_string(code, "api/items.py")

    assert result.ok
    refs = result.file.references

    # Should have refs for both response_model and response_class
    targets = {r.target for r in refs if "create_item" in r.source}
    assert "ItemResponse" in targets
    assert "JSONResponse" in targets


def test_marks_route_handler_as_entry_point(parser):
    """Route handlers have is_entry_point metadata."""
    code = '''
@app.get("/health")
def health_check():
    return {"status": "ok"}
'''
    result = parser.parse_string(code, "api/health.py")

    assert result.ok
    func = next(s for s in result.file.symbols if s.name == "health_check")
    assert func.metadata.get("is_entry_point") is True


def test_marks_pytest_fixture_as_entry_point(parser):
    """pytest fixtures have is_entry_point metadata."""
    code = '''
import pytest

@pytest.fixture
def db_session():
    return create_session()
'''
    result = parser.parse_string(code, "tests/conftest.py")

    assert result.ok
    func = next(s for s in result.file.symbols if s.name == "db_session")
    assert func.metadata.get("is_entry_point") is True


def test_marks_click_command_as_entry_point(parser):
    """Click commands have is_entry_point metadata."""
    code = '''
import click

@click.command()
def main():
    pass
'''
    result = parser.parse_string(code, "cli.py")

    assert result.ok
    func = next(s for s in result.file.symbols if s.name == "main")
    assert func.metadata.get("is_entry_point") is True


def test_non_decorated_function_not_entry_point(parser):
    """Regular functions don't have is_entry_point metadata."""
    code = '''
def helper_function():
    return 42
'''
    result = parser.parse_string(code, "utils.py")

    assert result.ok
    func = next(s for s in result.file.symbols if s.name == "helper_function")
    assert func.metadata.get("is_entry_point", False) is False
```

**Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_python_parser.py::test_extracts_fastapi_response_model_reference -v`
Expected: FAIL (no decorator_argument references extracted)

**Step 3: Write minimal implementation**

First, add `DECORATOR_ARGUMENT` to `ReferenceType` in `backend/src/oya/parsing/models.py`:

```python
class ReferenceType(Enum):
    """Types of references between code entities."""

    CALLS = "calls"
    INSTANTIATES = "instantiates"
    INHERITS = "inherits"
    IMPORTS = "imports"
    TYPE_ANNOTATION = "type_annotation"
    DECORATOR_ARGUMENT = "decorator_argument"  # Types in decorator arguments
```

Then modify `backend/src/oya/parsing/python_parser.py`. Add these methods to `PythonParser`:

```python
def _extract_decorator_info(self, node: ast.expr) -> tuple[str, str | None]:
    """Extract decorator_name and object_name from a decorator AST node.

    Args:
        node: The decorator AST node (Call, Attribute, or Name).

    Returns:
        Tuple of (decorator_name, object_name). object_name is None for bare decorators.
    """
    # Handle @decorator(...) - called decorator
    if isinstance(node, ast.Call):
        return self._extract_decorator_info(node.func)

    # Handle @obj.method - attribute decorator
    if isinstance(node, ast.Attribute):
        decorator_name = node.attr
        # Get the object part
        if isinstance(node.value, ast.Name):
            object_name = node.value.id
        elif isinstance(node.value, ast.Attribute):
            # e.g., pytest.mark.parametrize -> object="pytest.mark", name="parametrize"
            object_name = self._get_attribute_name(node.value)
        else:
            object_name = None
        return decorator_name, object_name

    # Handle @decorator - bare decorator
    if isinstance(node, ast.Name):
        return node.id, None

    return "", None

def _extract_decorator_argument_values(
    self,
    decorator: ast.Call,
    argument_names: tuple[str, ...],
) -> list[tuple[str, int]]:
    """Extract values from specific keyword arguments in a decorator call.

    Args:
        decorator: The decorator Call AST node.
        argument_names: Names of arguments to extract.

    Returns:
        List of (value_name, line_number) tuples for found arguments.
    """
    values: list[tuple[str, int]] = []

    if not isinstance(decorator, ast.Call):
        return values

    for keyword in decorator.keywords:
        if keyword.arg in argument_names:
            # Extract the name from the value
            if isinstance(keyword.value, ast.Name):
                values.append((keyword.value.id, keyword.value.lineno))
            elif isinstance(keyword.value, ast.Attribute):
                values.append((keyword.value.attr, keyword.value.lineno))

    return values

def _process_decorator(
    self,
    decorator: ast.expr,
    scope: str,
) -> tuple[list[Reference], bool]:
    """Extract references and entry point status from a decorator.

    Args:
        decorator: The decorator AST node.
        scope: The current function/method scope (e.g., "file.py::func_name").

    Returns:
        Tuple of (references, is_entry_point).
    """
    decorator_name, object_name = self._extract_decorator_info(decorator)
    if not decorator_name:
        return [], False

    references: list[Reference] = []
    is_entry_point = False

    # Check reference patterns
    for pattern in self._get_reference_patterns():
        if self._matches_decorator_pattern(decorator_name, object_name, pattern):
            if isinstance(decorator, ast.Call):
                for value, line in self._extract_decorator_argument_values(
                    decorator, pattern.arguments
                ):
                    references.append(
                        Reference(
                            source=scope,
                            target=value,
                            reference_type=ReferenceType.DECORATOR_ARGUMENT,
                            confidence=0.95,
                            line=line,
                        )
                    )

    # Check entry point patterns
    for pattern in self._get_entry_point_patterns():
        if self._matches_decorator_pattern(decorator_name, object_name, pattern):
            is_entry_point = True
            break

    return references, is_entry_point
```

Modify `_parse_function` to call `_process_decorator` and set `is_entry_point`:

```python
def _parse_function(
    self,
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    parent: str | None,
    file_path: str | None = None,
) -> tuple[ParsedSymbol, list[Reference]]:
    """Parse a function or async function definition.

    Args:
        node: The AST function node.
        parent: Name of the parent class, if any.
        file_path: Path to the file being parsed (for scope).

    Returns:
        Tuple of (ParsedSymbol, list of decorator references).
    """
    decorators = self._extract_decorators(node)
    is_route = self._is_route_handler(decorators)

    # Determine symbol type
    if is_route:
        symbol_type = SymbolType.ROUTE
    elif parent is not None:
        symbol_type = SymbolType.METHOD
    else:
        symbol_type = SymbolType.FUNCTION

    # Build metadata
    metadata = {}
    raises = self._extract_raises(node)
    if raises:
        metadata["raises"] = raises
    error_strings = self._extract_error_strings(node)
    if error_strings:
        metadata["error_strings"] = error_strings
    mutates = self._extract_mutates(node, self._module_level_names)
    if mutates:
        metadata["mutates"] = mutates

    # Process decorators for references and entry point status
    decorator_refs: list[Reference] = []
    is_entry_point = False

    if file_path:
        if parent:
            scope = f"{file_path}::{parent}.{node.name}"
        else:
            scope = f"{file_path}::{node.name}"

        for dec in node.decorator_list:
            refs, is_ep = self._process_decorator(dec, scope)
            decorator_refs.extend(refs)
            if is_ep:
                is_entry_point = True

    if is_entry_point:
        metadata["is_entry_point"] = True

    symbol = ParsedSymbol(
        name=node.name,
        symbol_type=symbol_type,
        start_line=node.lineno,
        end_line=node.end_lineno or node.lineno,
        docstring=ast.get_docstring(node),
        signature=self._build_signature(node),
        decorators=decorators,
        parent=parent,
        metadata=metadata,
    )

    return symbol, decorator_refs
```

Update the `parse` method to pass `file_path` and collect decorator references:

In the parse method, change the function/method parsing:

```python
# Process top-level nodes
for node in ast.iter_child_nodes(tree):
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        symbol, dec_refs = self._parse_function(node, parent=None, file_path=str(file_path))
        symbols.append(symbol)
        references.extend(dec_refs)
        scope = f"{file_path}::{node.name}"
        references.extend(self._extract_calls(node, scope))
    elif isinstance(node, ast.ClassDef):
        class_symbols, class_dec_refs = self._parse_class(node, str(file_path))
        symbols.extend(class_symbols)
        references.extend(class_dec_refs)
        # ... rest of class handling
```

And update `_parse_class` similarly to return decorator references.

**Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_python_parser.py -v -k "decorator or entry_point"`
Expected: PASS (all 6 new tests)

**Step 5: Run full test suite to ensure no regressions**

Run: `cd backend && pytest tests/test_python_parser.py -v`
Expected: PASS (all tests)

**Step 6: Commit**

```bash
git add backend/src/oya/parsing/models.py backend/src/oya/parsing/python_parser.py backend/tests/test_python_parser.py
git commit -m "$(cat <<'EOF'
feat(parsing): extract decorator arguments and entry points

- Add DECORATOR_ARGUMENT reference type
- Extract response_model/response_class from FastAPI routes
- Mark route handlers, fixtures, Click commands as entry points
- Set is_entry_point in symbol metadata

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Propagate is_entry_point to Graph Nodes

**Files:**
- Modify: `backend/src/oya/graph/builder.py`
- Modify: `backend/tests/test_graph_builder.py` (add test)

**Step 1: Write the failing test**

Add to `backend/tests/test_graph_builder.py`:

```python
def test_propagates_is_entry_point_to_node():
    """Graph nodes include is_entry_point metadata from symbols."""
    from oya.graph.builder import build_graph
    from oya.parsing.models import ParsedFile, ParsedSymbol, SymbolType

    files = [
        ParsedFile(
            path="api/routes.py",
            language="python",
            symbols=[
                ParsedSymbol(
                    name="get_users",
                    symbol_type=SymbolType.ROUTE,
                    start_line=10,
                    end_line=20,
                    metadata={"is_entry_point": True},
                ),
                ParsedSymbol(
                    name="helper",
                    symbol_type=SymbolType.FUNCTION,
                    start_line=25,
                    end_line=30,
                    metadata={},  # Not an entry point
                ),
            ],
            references=[],
        )
    ]

    G = build_graph(files)

    # Entry point should have is_entry_point=True
    entry_node = G.nodes["api/routes.py::get_users"]
    assert entry_node.get("is_entry_point") is True

    # Regular function should have is_entry_point=False
    helper_node = G.nodes["api/routes.py::helper"]
    assert entry_node.get("is_entry_point", False) is False
```

**Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_graph_builder.py::test_propagates_is_entry_point_to_node -v`
Expected: FAIL (is_entry_point not in node attributes)

**Step 3: Write minimal implementation**

Modify `backend/src/oya/graph/builder.py`, in `build_graph()` where nodes are added:

```python
# Add nodes for all symbols
for file in parsed_files:
    for symbol in file.symbols:
        node_id = _make_node_id(file.path, symbol)
        G.add_node(
            node_id,
            name=symbol.name,
            type=symbol.symbol_type.value,
            file_path=file.path,
            line_start=symbol.start_line,
            line_end=symbol.end_line,
            docstring=symbol.docstring,
            signature=symbol.signature,
            parent=symbol.parent,
            is_entry_point=symbol.metadata.get("is_entry_point", False),
        )
```

**Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_graph_builder.py::test_propagates_is_entry_point_to_node -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/oya/graph/builder.py backend/tests/test_graph_builder.py
git commit -m "$(cat <<'EOF'
feat(graph): propagate is_entry_point to graph nodes

Include is_entry_point metadata from symbols when building graph nodes.
This allows the dead code analyzer to filter framework-registered symbols.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Filter Entry Points in Dead Code Analyzer

**Files:**
- Modify: `backend/src/oya/generation/deadcode.py`
- Modify: `backend/tests/test_deadcode.py` (add test)

**Step 1: Write the failing test**

Add to `backend/tests/test_deadcode.py`:

```python
def test_analyze_deadcode_excludes_entry_points(tmp_path):
    """Entry points are not flagged even without callers."""
    from oya.generation.deadcode import analyze_deadcode

    graph_dir = tmp_path / "graph"
    graph_dir.mkdir()

    nodes = [
        {
            "id": "api/users.py::get_users",
            "name": "get_users",
            "type": "route",
            "file_path": "api/users.py",
            "line_start": 10,
            "line_end": 20,
            "docstring": None,
            "signature": None,
            "parent": None,
            "is_entry_point": True,  # FastAPI route handler
        },
        {
            "id": "api/users.py::UserResponse",
            "name": "UserResponse",
            "type": "class",
            "file_path": "api/users.py",
            "line_start": 5,
            "line_end": 8,
            "docstring": None,
            "signature": None,
            "parent": None,
            "is_entry_point": False,  # Used via response_model, not entry point
        },
        {
            "id": "utils.py::unused_helper",
            "name": "unused_helper",
            "type": "function",
            "file_path": "utils.py",
            "line_start": 1,
            "line_end": 5,
            "docstring": None,
            "signature": None,
            "parent": None,
            "is_entry_point": False,  # Regular function, no callers
        },
    ]

    # Edge from route to response class (decorator_argument reference)
    edges = [
        {
            "source": "api/users.py::get_users",
            "target": "api/users.py::UserResponse",
            "type": "decorator_argument",
            "confidence": 0.95,
            "line": 10,
        }
    ]

    (graph_dir / "nodes.json").write_text(json.dumps(nodes))
    (graph_dir / "edges.json").write_text(json.dumps(edges))

    report = analyze_deadcode(graph_dir)

    # Entry point (route handler) should NOT be flagged
    all_functions = report.probably_unused_functions + report.possibly_unused_functions
    assert not any(f.name == "get_users" for f in all_functions)

    # UserResponse has incoming edge from get_users, should NOT be flagged
    all_classes = report.probably_unused_classes + report.possibly_unused_classes
    assert not any(c.name == "UserResponse" for c in all_classes)

    # unused_helper has no callers and is not entry point, should be flagged
    assert any(f.name == "unused_helper" for f in report.probably_unused_functions)
```

**Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_deadcode.py::test_analyze_deadcode_excludes_entry_points -v`
Expected: FAIL (get_users flagged as unused because is_entry_point check not implemented)

**Step 3: Write minimal implementation**

Modify `backend/src/oya/generation/deadcode.py`, in `analyze_deadcode()`:

```python
for node in nodes:
    node_id = node.get("id", "")
    name = node.get("name", "")
    node_type = node.get("type", "")
    file_path = node.get("file_path", "")
    line = node.get("line_start", 0)

    # Skip symbols in test files
    if is_test_file(file_path):
        continue

    # Skip excluded names
    if is_excluded(name):
        continue

    # Skip entry points (framework-registered symbols)
    if node.get("is_entry_point", False):
        continue

    # Check if this node has incoming edges...
    # (rest of existing logic)
```

**Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_deadcode.py::test_analyze_deadcode_excludes_entry_points -v`
Expected: PASS

**Step 5: Run full deadcode test suite**

Run: `cd backend && pytest tests/test_deadcode.py -v`
Expected: PASS (all tests)

**Step 6: Commit**

```bash
git add backend/src/oya/generation/deadcode.py backend/tests/test_deadcode.py
git commit -m "$(cat <<'EOF'
feat(deadcode): filter entry points from dead code report

Skip symbols marked with is_entry_point=True (route handlers, fixtures, etc.)
since they are invoked by frameworks, not direct calls.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Run Full Test Suite and Fix Any Issues

**Files:**
- None (verification only)

**Step 1: Run full backend test suite**

Run: `cd backend && pytest -v`
Expected: All 1091+ tests pass

**Step 2: If any tests fail, fix them**

Common issues to check:
- Import errors from new modules
- Signature changes in _parse_function (now returns tuple)
- Missing `file_path` argument in _parse_function calls

**Step 3: Commit any fixes**

```bash
git add -A
git commit -m "$(cat <<'EOF'
fix: address test failures from decorator pattern changes

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Create Documentation

**Files:**
- Create: `docs/language-customization/README.md`
- Create: `docs/language-customization/extending-decorator-patterns.md`

**Step 1: Create index file**

Create `docs/language-customization/README.md`:

```markdown
# Language Customization

This directory contains guides for extending Ọya's language support.

## Contents

- [Extending Decorator Patterns](./extending-decorator-patterns.md) - Add patterns for framework decorators in your language
```

**Step 2: Create the decorator patterns guide**

Create `docs/language-customization/extending-decorator-patterns.md`:

```markdown
# Extending Decorator Patterns

Ọya uses a declarative pattern registry to detect framework decorators that:
1. Create references to types (e.g., FastAPI `response_model=MyClass`)
2. Mark symbols as entry points (e.g., route handlers, test fixtures)

This guide explains how to add patterns for new languages or frameworks.

## Pattern Types

### ReferencePattern

Use when decorator arguments contain type references that should create graph edges.

```python
@dataclass(frozen=True)
class ReferencePattern:
    decorator_name: str          # Regex matching decorator name
    object_name: str | None      # Regex matching object, None for bare decorators
    arguments: tuple[str, ...]   # Argument names containing type references
```

### EntryPointPattern

Use when decorators mark symbols as externally invoked (by frameworks).

```python
@dataclass(frozen=True)
class EntryPointPattern:
    decorator_name: str          # Regex matching decorator name
    object_name: str | None      # Regex matching object, None for bare decorators
```

## Adding Patterns

### Step 1: Define patterns in the registry

Edit `backend/src/oya/parsing/decorator_patterns.py`:

```python
REFERENCE_PATTERNS["python"].append(
    ReferencePattern(
        decorator_name=r"^my_decorator$",
        object_name=r"^my_module$",  # or None for bare decorators
        arguments=("type_arg", "other_arg"),
    )
)

ENTRY_POINT_PATTERNS["python"].append(
    EntryPointPattern(
        decorator_name=r"^my_entry_decorator$",
        object_name=None,
    )
)
```

### Step 2: Add tests

Create tests in `backend/tests/test_decorator_patterns.py` that verify:
1. Patterns match expected decorator names
2. Patterns don't match unrelated decorators

### Step 3: Test with real code

Run the parser on sample code using your decorators and verify:
- References are extracted from decorator arguments
- Entry point metadata is set on decorated functions

## Examples

### FastAPI Routes

```python
# Pattern
ReferencePattern(
    decorator_name=r"^(get|post|put|patch|delete)$",
    object_name=r".*",  # Any router/app object
    arguments=("response_model", "response_class"),
)

# Matches
@router.get("/users", response_model=UserResponse)  # UserResponse referenced
@app.post("/items", response_model=ItemOut)         # ItemOut referenced
```

### pytest Fixtures

```python
# Pattern
EntryPointPattern(
    decorator_name=r"^fixture$",
    object_name=r"^pytest$",
)

# Matches
@pytest.fixture
def db_session():  # Marked as entry point
    ...
```

## Pattern Matching Rules

1. `decorator_name` matches the final name (e.g., `get` in `router.get`)
2. `object_name` matches the object (e.g., `router` in `router.get`)
3. Both are regex patterns anchored with `^...$`
4. `object_name=None` matches bare decorators like `@fixture`

## Adding Support for a New Language

1. Add empty lists to both registries:
   ```python
   REFERENCE_PATTERNS["newlang"] = []
   ENTRY_POINT_PATTERNS["newlang"] = []
   ```

2. Implement AST extraction in the language parser (see `python_parser.py` for example)

3. Add patterns specific to that language's frameworks
```

**Step 3: Commit documentation**

```bash
git add docs/language-customization/README.md docs/language-customization/extending-decorator-patterns.md
git commit -m "$(cat <<'EOF'
docs: add language customization guide for decorator patterns

Explains how to add patterns for new frameworks and languages.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: Update PROGRESS.md

**Files:**
- Modify: `backend/PROGRESS.md`

**Step 1: Update the progress document**

Update `backend/PROGRESS.md` to mark the decorator pattern detection as implemented:

```markdown
## Next Phase: Decorator Pattern Detection

~~An accuracy report (2026-02-01) showed 94% false positive rate...~~

**Status: IMPLEMENTED**

The decorator pattern detection was implemented:
- Pattern registry at `parsing/decorator_patterns.py`
- Base class helpers in `parsing/base.py`
- Python parser extracts decorator arguments and marks entry points
- Graph builder propagates `is_entry_point` metadata
- Dead code analyzer filters entry points

**Files created/modified:**
| File | Status |
|------|--------|
| `backend/src/oya/parsing/decorator_patterns.py` | Created |
| `backend/src/oya/parsing/base.py` | Modified |
| `backend/src/oya/parsing/python_parser.py` | Modified |
| `backend/src/oya/parsing/models.py` | Modified |
| `backend/src/oya/graph/builder.py` | Modified |
| `backend/src/oya/generation/deadcode.py` | Modified |
| `docs/language-customization/README.md` | Created |
| `docs/language-customization/extending-decorator-patterns.md` | Created |

**Next steps:**
- Run full wiki regeneration on test repository
- Verify false positive rate reduction
- Consider adding TypeScript patterns (NestJS, etc.)
```

**Step 2: Commit**

```bash
git add backend/PROGRESS.md
git commit -m "$(cat <<'EOF'
docs: update PROGRESS.md - decorator pattern detection implemented

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

## Summary

This plan implements decorator pattern detection in 8 tasks:

1. **Task 1**: Create pattern registry module with dataclasses and initial patterns
2. **Task 2**: Add pattern matching helpers to BaseParser
3. **Task 3**: Implement AST extraction in Python parser
4. **Task 4**: Propagate is_entry_point to graph nodes
5. **Task 5**: Filter entry points in dead code analyzer
6. **Task 6**: Run full test suite and fix any issues
7. **Task 7**: Create documentation
8. **Task 8**: Update PROGRESS.md

Each task follows TDD: write failing test, implement, verify, commit.
