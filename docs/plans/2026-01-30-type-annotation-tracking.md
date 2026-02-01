# Type Annotation Tracking Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add `TYPE_ANNOTATION` reference type to track type hints, eliminating false positives in dead code detection for Pydantic models, dataclasses, and custom types used in function signatures.

**Architecture:** Extend both Python and TypeScript parsers to extract type identifiers from annotations. Recursively handle nested generics (`Dict[str, List[Item]]`). Create reference edges with 0.9 confidence. Update dead code page content to be more cautious.

**Tech Stack:** Python ast module, tree-sitter for TypeScript, pytest

---

## Task 1: Add TYPE_ANNOTATION to ReferenceType Enum

**Files:**
- Modify: `backend/src/oya/parsing/models.py:7-14`

**Step 1: Add the new enum value**

```python
# In backend/src/oya/parsing/models.py, update ReferenceType enum

class ReferenceType(Enum):
    """Types of references between code entities."""

    CALLS = "calls"
    INSTANTIATES = "instantiates"
    INHERITS = "inherits"
    IMPORTS = "imports"
    TYPE_ANNOTATION = "type_annotation"  # NEW: Types used in annotations
```

**Step 2: Verify no tests break**

Run: `cd backend && pytest tests/test_python_parser.py tests/test_typescript_parser.py -v`
Expected: All existing tests PASS (enum extension is backwards compatible)

**Step 3: Commit**

```bash
git add backend/src/oya/parsing/models.py
git commit -m "feat(parsing): add TYPE_ANNOTATION reference type"
```

---

## Task 2: Add Python Built-in Types Constant

**Files:**
- Modify: `backend/src/oya/parsing/python_parser.py`
- Test: `backend/tests/test_python_parser.py`

**Step 1: Write the failing test**

```python
# Add to backend/tests/test_python_parser.py

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
```

**Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_python_parser.py::test_builtin_types_not_in_references -v`
Expected: FAIL with "no attribute 'value'" or similar (TYPE_ANNOTATION doesn't exist in references yet)

**Step 3: Add the built-in types constant**

```python
# Add after ROUTE_DECORATORS in backend/src/oya/parsing/python_parser.py (around line 21)

# Built-in types that should not create type annotation references
PYTHON_BUILTIN_TYPES = frozenset({
    # Primitives
    "int", "str", "float", "bool", "bytes", "None", "type", "object",
    # Built-in collections (lowercase)
    "list", "dict", "set", "tuple", "frozenset",
    # typing module capitalized versions
    "List", "Dict", "Set", "Tuple", "FrozenSet",
    # typing module special forms
    "Optional", "Union", "Any", "Callable", "Type",
    "Literal", "Final", "ClassVar", "Annotated",
    # typing module protocols
    "Sequence", "Mapping", "Iterable", "Iterator", "Generator",
    "Coroutine", "AsyncIterator", "AsyncIterable", "AsyncGenerator",
    "Awaitable", "ContextManager", "AsyncContextManager",
    # Other common typing constructs
    "TypeVar", "Generic", "Protocol", "NamedTuple", "TypedDict",
    "NoReturn", "Self", "Never",
})
```

**Step 4: Run test to verify behavior**

Run: `cd backend && pytest tests/test_python_parser.py::test_builtin_types_not_in_references -v`
Expected: Still FAIL (we haven't implemented extraction yet, but constant is defined)

**Step 5: Commit**

```bash
git add backend/src/oya/parsing/python_parser.py backend/tests/test_python_parser.py
git commit -m "feat(parsing): add PYTHON_BUILTIN_TYPES constant"
```

---

## Task 3: Implement Recursive Type Extraction for Python

**Files:**
- Modify: `backend/src/oya/parsing/python_parser.py`
- Test: `backend/tests/test_python_parser.py`

**Step 1: Write the failing test for simple types**

```python
# Add to backend/tests/test_python_parser.py

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
```

**Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_python_parser.py::test_extracts_type_annotation_simple -v`
Expected: FAIL with empty type_refs list

**Step 3: Add helper method to extract types from annotation node**

```python
# Add to PythonParser class in backend/src/oya/parsing/python_parser.py (after _extract_import_references)

def _extract_types_from_annotation(self, node: ast.expr, line: int) -> list[str]:
    """Recursively extract type names from a type annotation AST node.

    Handles simple types, generics (List[X]), unions (X | Y), and forward refs ("X").

    Args:
        node: The annotation AST node.
        line: Line number for the reference.

    Returns:
        List of type names found (excluding built-ins).
    """
    types: list[str] = []

    if isinstance(node, ast.Name):
        # Simple type: MyClass
        if node.id not in PYTHON_BUILTIN_TYPES:
            types.append(node.id)

    elif isinstance(node, ast.Attribute):
        # Qualified type: module.MyClass - extract final component
        if node.attr not in PYTHON_BUILTIN_TYPES:
            types.append(node.attr)

    elif isinstance(node, ast.Subscript):
        # Generic: List[MyClass], Dict[str, Item]
        # Extract from the base (usually builtin like List)
        types.extend(self._extract_types_from_annotation(node.value, line))
        # Extract from the slice (the type arguments)
        if isinstance(node.slice, ast.Tuple):
            # Multiple type args: Dict[K, V]
            for elt in node.slice.elts:
                types.extend(self._extract_types_from_annotation(elt, line))
        else:
            # Single type arg: List[X]
            types.extend(self._extract_types_from_annotation(node.slice, line))

    elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        # Union with | operator: X | Y | Z
        types.extend(self._extract_types_from_annotation(node.left, line))
        types.extend(self._extract_types_from_annotation(node.right, line))

    elif isinstance(node, ast.Constant) and isinstance(node.value, str):
        # Forward reference: "MyClass"
        # Simple heuristic: if it looks like a type name (starts with capital)
        value = node.value.strip()
        if value and value[0].isupper() and value not in PYTHON_BUILTIN_TYPES:
            types.append(value)

    return types
```

**Step 4: Add method to extract type annotation references**

```python
# Add to PythonParser class after _extract_types_from_annotation

def _extract_type_annotation_references(
    self, node: ast.AST, file_path: str
) -> list[Reference]:
    """Extract references from type annotations in functions and variables.

    Args:
        node: The AST node to analyze (typically module or function).
        file_path: Path to the file being parsed.

    Returns:
        List of Reference objects for type annotations.
    """
    references: list[Reference] = []
    file_scope = str(file_path)

    for child in ast.walk(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # Parameter annotations
            for arg in child.args.args + child.args.posonlyargs + child.args.kwonlyargs:
                if arg.annotation:
                    for type_name in self._extract_types_from_annotation(
                        arg.annotation, arg.lineno
                    ):
                        references.append(
                            Reference(
                                source=file_scope,
                                target=type_name,
                                reference_type=ReferenceType.TYPE_ANNOTATION,
                                confidence=0.9,
                                line=arg.lineno,
                            )
                        )

            # *args annotation
            if child.args.vararg and child.args.vararg.annotation:
                for type_name in self._extract_types_from_annotation(
                    child.args.vararg.annotation, child.args.vararg.lineno
                ):
                    references.append(
                        Reference(
                            source=file_scope,
                            target=type_name,
                            reference_type=ReferenceType.TYPE_ANNOTATION,
                            confidence=0.9,
                            line=child.args.vararg.lineno,
                        )
                    )

            # **kwargs annotation
            if child.args.kwarg and child.args.kwarg.annotation:
                for type_name in self._extract_types_from_annotation(
                    child.args.kwarg.annotation, child.args.kwarg.lineno
                ):
                    references.append(
                        Reference(
                            source=file_scope,
                            target=type_name,
                            reference_type=ReferenceType.TYPE_ANNOTATION,
                            confidence=0.9,
                            line=child.args.kwarg.lineno,
                        )
                    )

            # Return annotation
            if child.returns:
                for type_name in self._extract_types_from_annotation(
                    child.returns, child.lineno
                ):
                    references.append(
                        Reference(
                            source=file_scope,
                            target=type_name,
                            reference_type=ReferenceType.TYPE_ANNOTATION,
                            confidence=0.9,
                            line=child.lineno,
                        )
                    )

        elif isinstance(child, ast.AnnAssign):
            # Variable annotation: x: MyClass = ...
            if child.annotation:
                for type_name in self._extract_types_from_annotation(
                    child.annotation, child.lineno
                ):
                    references.append(
                        Reference(
                            source=file_scope,
                            target=type_name,
                            reference_type=ReferenceType.TYPE_ANNOTATION,
                            confidence=0.9,
                            line=child.lineno,
                        )
                    )

    return references
```

**Step 5: Integrate into parse() method**

Find the line in `parse()` that creates `ParsedFile` (around line 134) and add type annotation extraction before it:

```python
# In parse() method, before the ParsedFile creation, add:

        # Extract type annotation references
        references.extend(self._extract_type_annotation_references(tree, str(file_path)))

        parsed_file = ParsedFile(
            # ... existing code
        )
```

**Step 6: Run test to verify it passes**

Run: `cd backend && pytest tests/test_python_parser.py::test_extracts_type_annotation_simple -v`
Expected: PASS

**Step 7: Run all parser tests to verify no regressions**

Run: `cd backend && pytest tests/test_python_parser.py -v`
Expected: All tests PASS

**Step 8: Commit**

```bash
git add backend/src/oya/parsing/python_parser.py backend/tests/test_python_parser.py
git commit -m "feat(parsing): extract type annotation references in Python parser"
```

---

## Task 4: Add Tests for Nested Generic Types in Python

**Files:**
- Test: `backend/tests/test_python_parser.py`

**Step 1: Write the test for nested generics**

```python
# Add to backend/tests/test_python_parser.py

def test_extracts_type_annotation_nested_generics(parser):
    """Extracts types from nested generics like Dict[str, List[Item]]."""
    code = """
def process(data: Dict[str, List[Item]], mapping: Mapping[Key, Tuple[Value, Status]]) -> None:
    pass
"""
    result = parser.parse_string(code, "test.py")

    assert result.ok
    type_refs = [r for r in result.file.references if r.reference_type.value == "type_annotation"]

    targets = [r.target for r in type_refs]
    # Should extract custom types from inside generics
    assert "Item" in targets
    assert "Key" in targets
    assert "Value" in targets
    assert "Status" in targets
    # Should NOT extract built-in types
    assert "str" not in targets
    assert "Dict" not in targets
    assert "List" not in targets


def test_extracts_type_annotation_union_types(parser):
    """Extracts types from union annotations (X | Y)."""
    code = """
def handle(result: Success | Failure | None) -> Response | Error:
    pass
"""
    result = parser.parse_string(code, "test.py")

    assert result.ok
    type_refs = [r for r in result.file.references if r.reference_type.value == "type_annotation"]

    targets = [r.target for r in type_refs]
    assert "Success" in targets
    assert "Failure" in targets
    assert "Response" in targets
    assert "Error" in targets
    # None is a built-in, should not appear
    assert "None" not in targets


def test_extracts_type_annotation_forward_refs(parser):
    """Extracts types from forward references (string annotations)."""
    code = '''
def create() -> "MyClass":
    pass

class MyClass:
    def clone(self) -> "MyClass":
        pass
'''
    result = parser.parse_string(code, "test.py")

    assert result.ok
    type_refs = [r for r in result.file.references if r.reference_type.value == "type_annotation"]

    targets = [r.target for r in type_refs]
    assert "MyClass" in targets


def test_extracts_type_annotation_variable(parser):
    """Extracts types from variable annotations."""
    code = """
config: Settings
users: List[User] = []
"""
    result = parser.parse_string(code, "test.py")

    assert result.ok
    type_refs = [r for r in result.file.references if r.reference_type.value == "type_annotation"]

    targets = [r.target for r in type_refs]
    assert "Settings" in targets
    assert "User" in targets
```

**Step 2: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_python_parser.py -k "type_annotation" -v`
Expected: All PASS (implementation from Task 3 handles these cases)

**Step 3: Commit**

```bash
git add backend/tests/test_python_parser.py
git commit -m "test(parsing): add Python type annotation edge case tests"
```

---

## Task 5: Add TypeScript Built-in Types Constant

**Files:**
- Modify: `backend/src/oya/parsing/typescript_parser.py`

**Step 1: Add the constant**

```python
# Add at top of backend/src/oya/parsing/typescript_parser.py, after imports (around line 18)

# Built-in types that should not create type annotation references
TS_BUILTIN_TYPES = frozenset({
    # Primitives
    "string", "number", "boolean", "void", "null", "undefined",
    "any", "unknown", "never", "object", "symbol", "bigint",
    # Capitalized primitives
    "String", "Number", "Boolean", "Object", "Symbol", "BigInt",
    # Built-in objects
    "Array", "Promise", "Map", "Set", "WeakMap", "WeakSet",
    "Date", "RegExp", "Error", "Function",
    # Utility types
    "Record", "Partial", "Required", "Readonly", "Pick", "Omit",
    "Exclude", "Extract", "NonNullable", "ReturnType", "Parameters",
    "InstanceType", "ThisType", "Awaited",
    # React types (common enough to exclude)
    "React", "ReactNode", "ReactElement", "JSX",
})
```

**Step 2: Commit**

```bash
git add backend/src/oya/parsing/typescript_parser.py
git commit -m "feat(parsing): add TS_BUILTIN_TYPES constant"
```

---

## Task 6: Implement Type Annotation Extraction for TypeScript

**Files:**
- Modify: `backend/src/oya/parsing/typescript_parser.py`
- Test: `backend/tests/test_typescript_parser.py`

**Step 1: Write the failing test**

```python
# Add to backend/tests/test_typescript_parser.py

def test_extracts_type_annotation_simple(parser):
    """Extracts simple type annotations from function parameters."""
    code = """
function createUser(request: CreateRequest): UserResponse {
    return {} as UserResponse;
}
"""
    result = parser.parse_string(code, "test.ts")

    assert result.ok
    type_refs = [r for r in result.file.references if r.reference_type.value == "type_annotation"]

    targets = [r.target for r in type_refs]
    assert "CreateRequest" in targets
    assert "UserResponse" in targets
    assert all(r.confidence == 0.9 for r in type_refs)
```

**Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_typescript_parser.py::test_extracts_type_annotation_simple -v`
Expected: FAIL with empty type_refs list

**Step 3: Add helper method to recursively extract types from tree-sitter node**

```python
# Add to TypeScriptParser class in backend/src/oya/parsing/typescript_parser.py (after _resolve_ts_call_target)

def _extract_types_from_ts_annotation(self, node, content: str) -> list[str]:
    """Recursively extract type names from a tree-sitter type annotation node.

    Args:
        node: Tree-sitter node representing a type.
        content: Original source content.

    Returns:
        List of type names found (excluding built-ins).
    """
    types: list[str] = []
    node_type = node.type

    if node_type in ("type_identifier", "identifier"):
        # Simple type: MyClass
        name = self._get_node_text(node, content)
        if name not in TS_BUILTIN_TYPES:
            types.append(name)

    elif node_type == "generic_type":
        # Generic: Array<Item>, Map<K, V>
        # Get the base type
        for child in node.children:
            if child.type in ("type_identifier", "identifier"):
                name = self._get_node_text(child, content)
                if name not in TS_BUILTIN_TYPES:
                    types.append(name)
            elif child.type == "type_arguments":
                # Recurse into type arguments
                for arg in child.children:
                    types.extend(self._extract_types_from_ts_annotation(arg, content))

    elif node_type == "union_type":
        # Union: A | B | C
        for child in node.children:
            if child.type != "|":
                types.extend(self._extract_types_from_ts_annotation(child, content))

    elif node_type == "intersection_type":
        # Intersection: A & B
        for child in node.children:
            if child.type != "&":
                types.extend(self._extract_types_from_ts_annotation(child, content))

    elif node_type == "array_type":
        # Array shorthand: Item[]
        for child in node.children:
            types.extend(self._extract_types_from_ts_annotation(child, content))

    elif node_type == "parenthesized_type":
        # Parenthesized: (A | B)
        for child in node.children:
            types.extend(self._extract_types_from_ts_annotation(child, content))

    elif node_type == "type_annotation":
        # type_annotation wrapper node - recurse into children
        for child in node.children:
            if child.type != ":":
                types.extend(self._extract_types_from_ts_annotation(child, content))

    else:
        # Recurse into unknown node types to catch nested types
        for child in node.children:
            types.extend(self._extract_types_from_ts_annotation(child, content))

    return types
```

**Step 4: Add method to extract type annotation references from a function**

```python
# Add to TypeScriptParser class after _extract_types_from_ts_annotation

def _extract_type_annotation_references(
    self, node, content: str, file_path: str
) -> list[Reference]:
    """Extract type annotation references from a function or method node.

    Args:
        node: The function_declaration or method_definition node.
        content: Original source content.
        file_path: Path to the file being parsed.

    Returns:
        List of Reference objects for type annotations.
    """
    references: list[Reference] = []
    file_scope = str(file_path)

    # Find parameters node
    params_node = node.child_by_field_name("parameters")
    if params_node:
        for child in params_node.children:
            if child.type in ("required_parameter", "optional_parameter"):
                # Look for type_annotation child
                for param_child in child.children:
                    if param_child.type == "type_annotation":
                        line = param_child.start_point[0] + 1
                        for type_name in self._extract_types_from_ts_annotation(
                            param_child, content
                        ):
                            references.append(
                                Reference(
                                    source=file_scope,
                                    target=type_name,
                                    reference_type=ReferenceType.TYPE_ANNOTATION,
                                    confidence=0.9,
                                    line=line,
                                )
                            )

    # Find return type annotation
    return_type = node.child_by_field_name("return_type")
    if return_type:
        line = return_type.start_point[0] + 1
        for type_name in self._extract_types_from_ts_annotation(return_type, content):
            references.append(
                Reference(
                    source=file_scope,
                    target=type_name,
                    reference_type=ReferenceType.TYPE_ANNOTATION,
                    confidence=0.9,
                    line=line,
                )
            )

    return references
```

**Step 5: Integrate into _extract_function method**

Update `_extract_function` in TypeScriptParser to call type annotation extraction:

```python
# In _extract_function method, after the "Extract calls" block (around line 233), add:

        # Extract type annotations
        if references is not None:
            references.extend(
                self._extract_type_annotation_references(node, content, file_path)
            )
```

**Step 6: Integrate into _extract_method method**

Update `_extract_method` in TypeScriptParser similarly:

```python
# In _extract_method method, after the "Extract calls" block (around line 403), add:

        # Extract type annotations
        if references is not None:
            references.extend(
                self._extract_type_annotation_references(node, content, file_path)
            )
```

**Step 7: Integrate into _extract_lexical_declaration for arrow functions**

Update `_extract_lexical_declaration` to handle arrow function type annotations:

```python
# In _extract_lexical_declaration, inside the arrow function branch (around line 281), add:

                        # Extract type annotations from arrow function
                        if references is not None:
                            references.extend(
                                self._extract_type_annotation_references(
                                    value_node, content, file_path
                                )
                            )
```

**Step 8: Run test to verify it passes**

Run: `cd backend && pytest tests/test_typescript_parser.py::test_extracts_type_annotation_simple -v`
Expected: PASS

**Step 9: Run all TypeScript parser tests**

Run: `cd backend && pytest tests/test_typescript_parser.py -v`
Expected: All tests PASS

**Step 10: Commit**

```bash
git add backend/src/oya/parsing/typescript_parser.py backend/tests/test_typescript_parser.py
git commit -m "feat(parsing): extract type annotation references in TypeScript parser"
```

---

## Task 7: Add Tests for Nested Generic Types in TypeScript

**Files:**
- Test: `backend/tests/test_typescript_parser.py`

**Step 1: Write additional tests**

```python
# Add to backend/tests/test_typescript_parser.py

def test_extracts_type_annotation_nested_generics(parser):
    """Extracts types from nested generics like Map<string, Array<Item>>."""
    code = """
function process(data: Map<string, Array<Item>>, config: Record<Key, Value>): void {
}
"""
    result = parser.parse_string(code, "test.ts")

    assert result.ok
    type_refs = [r for r in result.file.references if r.reference_type.value == "type_annotation"]

    targets = [r.target for r in type_refs]
    assert "Item" in targets
    assert "Key" in targets
    assert "Value" in targets
    # Built-ins should not appear
    assert "string" not in targets
    assert "Map" not in targets
    assert "Array" not in targets


def test_extracts_type_annotation_union_types(parser):
    """Extracts types from union annotations (A | B)."""
    code = """
function handle(result: Success | Failure | null): Response | Error {
    return {} as Response;
}
"""
    result = parser.parse_string(code, "test.ts")

    assert result.ok
    type_refs = [r for r in result.file.references if r.reference_type.value == "type_annotation"]

    targets = [r.target for r in type_refs]
    assert "Success" in targets
    assert "Failure" in targets
    assert "Response" in targets
    assert "Error" in targets
    # null is built-in
    assert "null" not in targets


def test_extracts_type_annotation_array_shorthand(parser):
    """Extracts types from array shorthand syntax (Item[])."""
    code = """
function getItems(): Item[] {
    return [];
}
"""
    result = parser.parse_string(code, "test.ts")

    assert result.ok
    type_refs = [r for r in result.file.references if r.reference_type.value == "type_annotation"]

    targets = [r.target for r in type_refs]
    assert "Item" in targets


def test_extracts_type_annotation_arrow_function(parser):
    """Extracts types from arrow function parameters and return type."""
    code = """
const createUser = (request: CreateRequest): UserResponse => {
    return {} as UserResponse;
};
"""
    result = parser.parse_string(code, "test.ts")

    assert result.ok
    type_refs = [r for r in result.file.references if r.reference_type.value == "type_annotation"]

    targets = [r.target for r in type_refs]
    assert "CreateRequest" in targets
    assert "UserResponse" in targets


def test_builtin_types_not_in_references(parser):
    """Built-in types like string, number should not create references."""
    code = """
function process(name: string, count: number, items: Array<string>): boolean {
    return true;
}
"""
    result = parser.parse_string(code, "test.ts")

    assert result.ok
    type_refs = [r for r in result.file.references if r.reference_type.value == "type_annotation"]
    # Should have no type annotation references for built-ins only
    assert len(type_refs) == 0
```

**Step 2: Run tests**

Run: `cd backend && pytest tests/test_typescript_parser.py -k "type_annotation" -v`
Expected: All PASS

**Step 3: Commit**

```bash
git add backend/tests/test_typescript_parser.py
git commit -m "test(parsing): add TypeScript type annotation edge case tests"
```

---

## Task 8: Update Dead Code Page Content

**Files:**
- Modify: `backend/src/oya/generation/deadcode.py`
- Test: `backend/tests/test_deadcode.py`

**Step 1: Write the test for new page content**

```python
# Add to backend/tests/test_deadcode.py

def test_generate_deadcode_page_cautious_content():
    """Page content includes false positive warnings."""
    from oya.generation.deadcode import generate_deadcode_page, DeadcodeReport, UnusedSymbol

    report = DeadcodeReport(
        probably_unused_functions=[
            UnusedSymbol(
                name="old_func",
                file_path="utils/legacy.py",
                line=42,
                symbol_type="function",
            ),
        ],
    )

    content = generate_deadcode_page(report)

    # Check for cautious language
    assert "false positives" in content.lower() or "False Positives" in content
    assert "Review" in content or "review" in content
    assert "Test code" in content or "test" in content.lower()
    # Should NOT use "Probably Unused" language
    assert "Review Candidates" in content or "Potential" in content
```

**Step 2: Run test to see current behavior**

Run: `cd backend && pytest tests/test_deadcode.py::test_generate_deadcode_page_cautious_content -v`
Expected: FAIL (current content uses "Probably Unused" language)

**Step 3: Update generate_deadcode_page function**

```python
# Replace the generate_deadcode_page function in backend/src/oya/generation/deadcode.py

def generate_deadcode_page(report: DeadcodeReport) -> str:
    """Generate markdown content for the Code Health wiki page.

    Args:
        report: DeadcodeReport with categorized unused symbols.

    Returns:
        Markdown string for the wiki page.
    """
    lines = [
        "# Code Health: Potential Dead Code",
        "",
        "This page lists symbols where static analysis found no callers.",
        "**Many of these are false positives.** Review each carefully before removing.",
        "",
        "## Common False Positives",
        "",
        "Before removing anything, consider whether the symbol is:",
        "",
        "- **Test code** - pytest discovers `Test*` classes and `test_*` methods by naming convention",
        "- **Entry points** - CLI commands, route handlers, event listeners registered via decorators",
        "- **Framework hooks** - `__init__`, lifecycle methods, signal handlers",
        "- **Public API** - Symbols intended for external consumers",
        "- **Dynamic calls** - Code invoked via `getattr()`, reflection, or string-based dispatch",
        "",
    ]

    # Count totals for summary
    total_functions = len(report.probably_unused_functions) + len(report.possibly_unused_functions)
    total_classes = len(report.probably_unused_classes) + len(report.possibly_unused_classes)
    total_variables = len(report.possibly_unused_variables)

    # Review Candidates section
    lines.append("## Review Candidates")
    lines.append("")
    lines.append("The following symbols have no detected callers. This does NOT mean they are unused.")
    lines.append("")

    # Combine probably and possibly into single lists (less judgmental)
    all_functions = report.probably_unused_functions + report.possibly_unused_functions
    all_classes = report.probably_unused_classes + report.possibly_unused_classes
    all_variables = report.possibly_unused_variables

    _add_symbol_section(lines, "Functions", all_functions)
    _add_symbol_section(lines, "Classes", all_classes)
    _add_symbol_section(lines, "Variables", all_variables)

    return "\n".join(lines)
```

**Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_deadcode.py::test_generate_deadcode_page_cautious_content -v`
Expected: PASS

**Step 5: Run all deadcode tests**

Run: `cd backend && pytest tests/test_deadcode.py -v`
Expected: Some tests may need updating due to content changes

**Step 6: Update other affected tests**

```python
# Update test_generate_deadcode_page_content in backend/tests/test_deadcode.py

def test_generate_deadcode_page_content():
    """generate_deadcode_page creates markdown with tables."""
    from oya.generation.deadcode import generate_deadcode_page, DeadcodeReport, UnusedSymbol

    report = DeadcodeReport(
        probably_unused_functions=[
            UnusedSymbol(
                name="old_func",
                file_path="utils/legacy.py",
                line=42,
                symbol_type="function",
            ),
        ],
        probably_unused_classes=[
            UnusedSymbol(
                name="DeprecatedParser",
                file_path="parsing/old.py",
                line=10,
                symbol_type="class",
            ),
        ],
        possibly_unused_functions=[],
        possibly_unused_classes=[],
        possibly_unused_variables=[
            UnusedSymbol(
                name="OLD_CONFIG",
                file_path="config.py",
                line=5,
                symbol_type="variable",
            ),
        ],
    )

    content = generate_deadcode_page(report)

    # Check header
    assert "Code Health" in content
    assert "Potential Dead Code" in content

    # Check functions section
    assert "### Functions" in content
    assert "old_func" in content
    assert "utils/legacy.py" in content

    # Check classes section
    assert "### Classes" in content
    assert "DeprecatedParser" in content

    # Check variables section
    assert "### Variables" in content
    assert "OLD_CONFIG" in content
```

**Step 7: Run all deadcode tests again**

Run: `cd backend && pytest tests/test_deadcode.py -v`
Expected: All PASS

**Step 8: Commit**

```bash
git add backend/src/oya/generation/deadcode.py backend/tests/test_deadcode.py
git commit -m "feat(deadcode): update page content with cautious language"
```

---

## Task 9: Run Full Test Suite

**Files:** None (verification only)

**Step 1: Run all backend tests**

Run: `cd backend && pytest`
Expected: All tests pass

**Step 2: Run linting**

Run: `cd backend && ruff check src/oya/parsing/python_parser.py src/oya/parsing/typescript_parser.py src/oya/generation/deadcode.py`
Run: `cd backend && ruff format --check src/oya/parsing/ src/oya/generation/deadcode.py`
Expected: No issues

**Step 3: Fix any issues and commit**

If tests fail or linting issues found, fix and commit with appropriate message.

---

## Task 10: Integration Test

**Files:** None (manual verification)

**Step 1: Regenerate wiki for Oya**

```bash
# Start backend if not running
cd backend && source .venv/bin/activate && uvicorn oya.main:app --reload &

# Trigger regeneration (adjust endpoint as needed)
curl -X POST http://localhost:8000/api/repos/init -H "Content-Type: application/json" \
  -d '{"url": "file:///Users/poecurt/projects/oya"}'
```

**Step 2: Check code-health.md**

```bash
cat ~/.oya/wikis/*/meta/.oyawiki/wiki/code-health.md | head -50
```

Expected: Significantly fewer false positives for Pydantic models and schemas.

**Step 3: Verify type annotation edges exist**

```bash
cat ~/.oya/wikis/*/meta/.oyawiki/graph/edges.json | grep type_annotation | head -10
```

Expected: Edges with `"type": "type_annotation"` should appear.

**Step 4: Final commit**

```bash
git add -A
git commit -m "feat(deadcode): complete type annotation tracking feature"
```

---

## Summary

| Task | Description | Files |
|------|-------------|-------|
| 1 | Add TYPE_ANNOTATION enum | models.py |
| 2 | Add Python builtin types constant | python_parser.py |
| 3 | Implement Python type extraction | python_parser.py |
| 4 | Test Python edge cases | test_python_parser.py |
| 5 | Add TypeScript builtin types constant | typescript_parser.py |
| 6 | Implement TypeScript type extraction | typescript_parser.py |
| 7 | Test TypeScript edge cases | test_typescript_parser.py |
| 8 | Update dead code page content | deadcode.py |
| 9 | Full test suite | verification |
| 10 | Integration test | manual verification |
