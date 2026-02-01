# Decorator Pattern Detection for Dead Code Analysis

## Problem

The dead code detector has a 94% false positive rate. Classes used as `response_model=MyClass` in FastAPI route decorators appear unused because the analyzer only sees call-graph edges, not decorator keyword arguments.

**Root cause:** Decorator-based frameworks (FastAPI, pytest, Click) register code declaratively. The parser extracts type annotations but not decorator argument values.

## Solution

Add a declarative pattern registry that tells parsers which decorator arguments create references or mark entry points. Each language parser consults this registry during AST traversal.

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Where to extract | Parser-level | Keeps language-specific logic in parsers; graph builder and analyzer stay language-agnostic |
| Pattern format | Declarative config | Easy to extend, document, and maintain |
| Entry point handling | Node metadata | `is_entry_point: true` on graph nodes; analyzer filters simply |
| Config location | Python module | Type-checkable, importable, can include comments |
| Base class abstraction | Pattern matching in base, AST extraction in subclass | Maximizes code reuse while respecting language differences |

## Pattern Configuration Schema

```python
# backend/src/oya/parsing/decorator_patterns.py

from dataclasses import dataclass

@dataclass(frozen=True)
class ReferencePattern:
    """Pattern for decorators whose arguments create references."""

    decorator_name: str          # Regex matching decorator name (e.g., "get|post|put")
    object_name: str | None      # Regex matching object (e.g., "router|app"), None for bare decorators
    arguments: tuple[str, ...]   # Argument names that contain type references

@dataclass(frozen=True)
class EntryPointPattern:
    """Pattern for decorators that mark symbols as externally invoked."""

    decorator_name: str          # Regex matching decorator name
    object_name: str | None      # Regex matching object, None for bare decorators

# Registry keyed by language
REFERENCE_PATTERNS: dict[str, list[ReferencePattern]] = {
    "python": [...],
    "typescript": [...],
}

ENTRY_POINT_PATTERNS: dict[str, list[EntryPointPattern]] = {
    "python": [...],
    "typescript": [...],
}
```

**Pattern matching rules:**
- `decorator_name` is matched against the final name (e.g., `get` in `router.get`)
- `object_name` is matched against the object (e.g., `router` in `router.get`), or `None` for bare decorators like `@fixture`
- Both fields are regex patterns

## Initial Python Patterns

```python
REFERENCE_PATTERNS: dict[str, list[ReferencePattern]] = {
    "python": [
        # FastAPI/Starlette route handlers
        ReferencePattern(
            decorator_name=r"^(get|post|put|patch|delete|head|options|trace)$",
            object_name=r".*",  # router, app, or any object
            arguments=("response_model", "response_class"),
        ),
        # Dependency injection
        ReferencePattern(
            decorator_name=r"^Depends$",
            object_name=None,
            arguments=("dependency",),  # Depends(get_db) - positional becomes 'dependency'
        ),
    ],
    "typescript": [],  # Future: NestJS patterns
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

## Implementation Changes

### 1. Base Parser (`parsing/base.py`)

Add pattern lookup and matching helpers:

```python
class BaseParser(ABC):

    def _get_reference_patterns(self) -> list[ReferencePattern]:
        return REFERENCE_PATTERNS.get(self.language_name, [])

    def _get_entry_point_patterns(self) -> list[EntryPointPattern]:
        return ENTRY_POINT_PATTERNS.get(self.language_name, [])

    def _matches_decorator_pattern(
        self,
        decorator_name: str,
        object_name: str | None,
        pattern: ReferencePattern | EntryPointPattern,
    ) -> bool:
        """Check if decorator matches pattern. Language-agnostic."""
        if not re.match(pattern.decorator_name, decorator_name):
            return False
        if pattern.object_name and (not object_name or not re.match(pattern.object_name, object_name)):
            return False
        return True
```

### 2. Python Parser (`parsing/python_parser.py`)

Implement AST extraction that calls base class helpers:

```python
class PythonParser(BaseParser):

    def _extract_decorator_info(self, node: ast.expr) -> tuple[str, str | None]:
        """Extract decorator_name and object_name from Python AST."""
        # Language-specific AST traversal
        ...

    def _process_decorator(
        self,
        decorator: ast.expr,
        scope: str,
        line: int,
    ) -> tuple[list[Reference], bool]:
        """Extract references and entry point status from a decorator."""
        decorator_name, object_name = self._extract_decorator_info(decorator)

        references = []
        is_entry_point = False

        # Check reference patterns (uses base class helper)
        for pattern in self._get_reference_patterns():
            if self._matches_decorator_pattern(decorator_name, object_name, pattern):
                refs = self._extract_argument_references(
                    decorator, pattern.arguments, scope, line
                )
                references.extend(refs)

        # Check entry point patterns (uses base class helper)
        for pattern in self._get_entry_point_patterns():
            if self._matches_decorator_pattern(decorator_name, object_name, pattern):
                is_entry_point = True
                break

        return references, is_entry_point
```

### 3. Graph Builder (`graph/builder.py`)

Propagate `is_entry_point` to node attributes:

```python
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
    is_entry_point=symbol.metadata.get("is_entry_point", False),  # NEW
)
```

### 4. Dead Code Analyzer (`generation/deadcode.py`)

Filter nodes marked as entry points:

```python
for node in nodes:
    # ... existing filters ...

    # NEW: Skip entry points (framework-registered symbols)
    if node.get("is_entry_point", False):
        continue

    # ... rest of analysis ...
```

## Documentation

Create developer guide at `docs/language-customization/extending-decorator-patterns.md` explaining:

1. How the pattern registry works
2. Step-by-step guide to add patterns for a new language
3. How to implement AST extraction in a parser
4. Testing patterns
5. Common pitfalls

Also create `docs/language-customization/README.md` as an index for language customization docs.

## Files to Create/Modify

| File | Action |
|------|--------|
| `backend/src/oya/parsing/decorator_patterns.py` | Create |
| `backend/src/oya/parsing/base.py` | Modify |
| `backend/src/oya/parsing/python_parser.py` | Modify |
| `backend/src/oya/graph/builder.py` | Modify |
| `backend/src/oya/generation/deadcode.py` | Modify |
| `docs/language-customization/README.md` | Create |
| `docs/language-customization/extending-decorator-patterns.md` | Create |

## Expected Outcome

- False positive rate drops from 94% to near-zero for FastAPI projects
- Framework extensible to other languages without changing core logic
- Clear documentation for contributors adding new language support
