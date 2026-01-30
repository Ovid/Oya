# Type Annotation Tracking for Dead Code Detection

## Problem

The dead code detection feature reports many false positives because the code graph doesn't track type annotation usage. Classes used only in type hints appear "unused":

```python
# CreateRepoRequest appears unused because this reference isn't tracked:
async def create_repo(request: CreateRepoRequest) -> CreateRepoResponse:
```

This affects Pydantic models, dataclasses, enums, and any custom types used in function signatures.

## Solution

Add a new reference type `TYPE_ANNOTATION` that creates graph edges for type hints in function parameters, return types, and variable annotations.

## Data Model

Add to `ReferenceType` enum in `backend/src/oya/parsing/models.py`:

```python
class ReferenceType(Enum):
    CALLS = "calls"
    INSTANTIATES = "instantiates"
    INHERITS = "inherits"
    IMPORTS = "imports"
    TYPE_ANNOTATION = "type_annotation"  # NEW
```

**Confidence level:** 0.9

Rationale: Type annotations are explicit in source code, but not 1.0 because:
- Forward references may not resolve
- External types won't match symbol table
- Typos in annotations are possible

## Recursive Type Extraction Algorithm

Type annotations can be nested arbitrarily deep: `Dict[str, List[Tuple[A, B]]]`

The algorithm recursively walks the type annotation AST:

```
function extract_types_from_annotation(node):
    results = []

    if node is Identifier:
        name = node.text
        if name not in BUILTIN_TYPES:
            results.append(name)

    elif node is Subscript (e.g., List[X]):
        results.extend(extract_types_from_annotation(node.base))
        for arg in node.type_arguments:
            results.extend(extract_types_from_annotation(arg))

    elif node is BinaryOp with "|" (union):
        results.extend(extract_types_from_annotation(node.left))
        results.extend(extract_types_from_annotation(node.right))

    elif node is StringLiteral (forward reference):
        results.append(node.string_value)

    return results
```

Handles:
- Simple types: `MyClass` → `["MyClass"]`
- Generics: `List[MyClass]` → `["MyClass"]`
- Nested: `Dict[str, List[Item]]` → `["Item"]`
- Unions: `A | B | C` → `["A", "B", "C"]`
- Forward refs: `"MyClass"` → `["MyClass"]`

## Python Parser Integration

**Built-in types to skip:**

```python
PYTHON_BUILTIN_TYPES = {
    "int", "str", "float", "bool", "bytes", "None", "type",
    "list", "dict", "set", "tuple", "frozenset",
    "List", "Dict", "Set", "Tuple", "FrozenSet",
    "Optional", "Union", "Any", "Callable", "Type",
    "Literal", "Final", "ClassVar", "Annotated",
    "Sequence", "Mapping", "Iterable", "Iterator",
}
```

**Annotation locations to extract from:**

| Location | AST Node | Example |
|----------|----------|---------|
| Function parameters | `arg.annotation` | `def foo(x: MyClass)` |
| Return type | `FunctionDef.returns` | `def foo() -> MyClass` |
| Variable annotation | `AnnAssign.annotation` | `x: MyClass = ...` |
| Class attributes | `AnnAssign` in class body | `name: str` in dataclass |

**New method in `python_parser.py`:**

```python
def _extract_type_annotation_references(
    self, node: ast.AST, file_path: str
) -> list[Reference]:
    """Extract references from type annotations."""
    refs = []

    for child in ast.walk(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # Parameter annotations
            for arg in child.args.args + child.args.kwonlyargs:
                if arg.annotation:
                    refs.extend(self._extract_types_from_annotation(
                        arg.annotation, arg.lineno
                    ))
            # Return annotation
            if child.returns:
                refs.extend(self._extract_types_from_annotation(
                    child.returns, child.lineno
                ))

        elif isinstance(child, ast.AnnAssign):
            refs.extend(self._extract_types_from_annotation(
                child.annotation, child.lineno
            ))

    return refs
```

## TypeScript Parser Integration

**Built-in types to skip:**

```python
TS_BUILTIN_TYPES = {
    "string", "number", "boolean", "void", "null", "undefined",
    "any", "unknown", "never", "object", "symbol", "bigint",
    "Array", "Object", "String", "Number", "Boolean",
    "Promise", "Map", "Set", "WeakMap", "WeakSet",
    "Record", "Partial", "Required", "Readonly", "Pick", "Omit",
    "Exclude", "Extract", "NonNullable", "ReturnType", "Parameters",
}
```

**Annotation locations:**

| Location | Tree-sitter node type | Example |
|----------|----------------------|---------|
| Parameter type | `type_annotation` child of `required_parameter` | `(x: MyClass)` |
| Return type | `type_annotation` child of function | `): MyClass {` |
| Variable type | `type_annotation` child of `variable_declarator` | `const x: MyClass` |
| Generic args | `type_arguments` | `Array<MyClass>` |
| Union types | `union_type` | `A \| B` |
| Intersection | `intersection_type` | `A & B` |

**Tree-sitter query approach:**

```python
def _extract_type_annotation_references(self, tree, source_code):
    refs = []

    query = self.ts_language.query("""
        (type_annotation) @type
    """)

    for node, _ in query.captures(tree.root_node):
        refs.extend(self._extract_types_from_ts_node(node))

    return refs

def _extract_types_from_ts_node(self, node):
    """Recursively extract type identifiers from a type node."""
    results = []

    if node.type == "type_identifier":
        name = node.text.decode()
        if name not in TS_BUILTIN_TYPES:
            results.append(Reference(
                name=name,
                type=ReferenceType.TYPE_ANNOTATION,
                line=node.start_point[0] + 1,
                confidence=0.9,
            ))

    for child in node.children:
        results.extend(self._extract_types_from_ts_node(child))

    return results
```

## Resolver Integration

No changes needed. The existing resolver:
- Matches references to symbols by name
- Automatically skips external types (not in symbol table)
- Creates edges with the reference type and confidence

## Dead Code Detection Changes

No logic changes needed to `analyze_deadcode()`. The existing confidence threshold (0.7) correctly handles TYPE_ANNOTATION edges (0.9 confidence).

**Page content changes** - rewrite to be more cautious:

```markdown
# Code Health: Potential Dead Code

This page lists symbols where static analysis found no callers.
**Many of these are false positives.** Review each carefully before removing.

## Common False Positives

Before removing anything, consider whether the symbol is:

- **Test code** - pytest discovers `Test*` classes and `test_*` methods by naming convention
- **Entry points** - CLI commands, route handlers, event listeners registered via decorators
- **Framework hooks** - `__init__`, lifecycle methods, signal handlers
- **Public API** - Symbols intended for external consumers
- **Dynamic calls** - Code invoked via `getattr()`, reflection, or string-based dispatch

## Review Candidates

The following symbols have no detected callers. This does NOT mean they are unused.

### Functions ({count})

| Name | File | Line |
|------|------|------|
| [func](files/path.py#L42) | path.py | 42 |

### Classes ({count})

| Name | File | Line |
|------|------|------|
| [MyClass](files/path.py#L10) | path.py | 10 |
```

## Limitations

Even with type annotation tracking, false positives will occur for:

- Test classes (pytest naming convention discovery)
- Route handlers and event listeners (decorator-based registration)
- Plugin hooks and factory patterns
- Reflection-based calls (`getattr`, `importlib`)
- Cross-language calls (Python calling JavaScript)

The cautious page content addresses this by framing results as "review candidates" rather than confirmed dead code.

## Files to Modify

| File | Change |
|------|--------|
| `backend/src/oya/parsing/models.py` | Add `TYPE_ANNOTATION` to enum |
| `backend/src/oya/parsing/python_parser.py` | Add type annotation extraction |
| `backend/src/oya/parsing/typescript_parser.py` | Add type annotation extraction |
| `backend/src/oya/generation/deadcode.py` | Update page content only |
| `backend/tests/test_deadcode.py` | Add tests for new reference type |
| `backend/tests/parsing/test_python_parser.py` | Add type annotation tests |
| `backend/tests/parsing/test_typescript_parser.py` | Add type annotation tests |
