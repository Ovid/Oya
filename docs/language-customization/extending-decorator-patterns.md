# Extending Decorator Patterns

Oya uses a declarative pattern registry to detect framework decorators that:
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
