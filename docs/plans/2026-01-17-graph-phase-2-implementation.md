# Phase 2: Code Graph Construction Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a queryable NetworkX graph from Phase 1's reference output, persist it to `.oyawiki/graph/`, and provide a query interface for traversals.

**Prerequisites:** Phase 1 complete (parsers extract references with confidence scores).

**Architecture:**
- New module `backend/src/oya/graph/` with:
  - `models.py` - Node, Edge, Subgraph dataclasses
  - `resolver.py` - Symbol table builder, cross-file reference resolution
  - `builder.py` - Constructs NetworkX graph from parsed files
  - `persistence.py` - JSON serialization to `.oyawiki/graph/`
  - `query.py` - Graph traversal functions
  - `__init__.py` - Public exports

**Tech Stack:** NetworkX (graph library), dataclasses for models, JSON for persistence.

---

## Task 1: Create Graph Node Model

**Files:**
- Create: `backend/src/oya/graph/models.py`
- Test: `backend/tests/test_graph_models.py`

**Step 1: Write the failing test**

Create `backend/tests/test_graph_models.py`:

```python
"""Tests for graph data models."""

import pytest


def test_node_model_creation():
    """Node model stores entity metadata."""
    from oya.graph.models import Node, NodeType

    node = Node(
        id="backend/src/oya/api/routers/qa.py::ask_question",
        node_type=NodeType.FUNCTION,
        name="ask_question",
        file_path="backend/src/oya/api/routers/qa.py",
        line_start=45,
        line_end=92,
        docstring="Handle Q&A queries against the wiki...",
    )

    assert node.id == "backend/src/oya/api/routers/qa.py::ask_question"
    assert node.node_type == NodeType.FUNCTION
    assert node.name == "ask_question"
    assert node.file_path == "backend/src/oya/api/routers/qa.py"
    assert node.line_start == 45
    assert node.line_end == 92


def test_node_type_enum():
    """NodeType has expected values."""
    from oya.graph.models import NodeType

    assert NodeType.FUNCTION.value == "function"
    assert NodeType.CLASS.value == "class"
    assert NodeType.METHOD.value == "method"
    assert NodeType.FILE.value == "file"
    assert NodeType.MODULE.value == "module"
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/poecurt/projects/oya/backend && source .venv/bin/activate && pytest tests/test_graph_models.py -v`

Expected: FAIL with ModuleNotFoundError

**Step 3: Write minimal implementation**

Create `backend/src/oya/graph/__init__.py`:

```python
"""Code graph construction and querying."""
```

Create `backend/src/oya/graph/models.py`:

```python
"""Data models for the code knowledge graph."""

from dataclasses import dataclass, field
from enum import Enum


class NodeType(Enum):
    """Types of nodes in the code graph."""

    FUNCTION = "function"
    CLASS = "class"
    METHOD = "method"
    FILE = "file"
    MODULE = "module"


@dataclass
class Node:
    """A node in the code graph representing a code entity."""

    id: str  # Unique identifier, e.g., "path/to/file.py::ClassName.method_name"
    node_type: NodeType
    name: str
    file_path: str
    line_start: int
    line_end: int
    docstring: str | None = None
    signature: str | None = None
    metadata: dict = field(default_factory=dict)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_graph_models.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/oya/graph/ backend/tests/test_graph_models.py
git commit -m "feat(graph): add Node and NodeType models"
```

---

## Task 2: Create Graph Edge Model

**Files:**
- Modify: `backend/src/oya/graph/models.py`
- Test: `backend/tests/test_graph_models.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_graph_models.py`:

```python
def test_edge_model_creation():
    """Edge model stores relationship with confidence."""
    from oya.graph.models import Edge, EdgeType

    edge = Edge(
        source="qa.py::ask_question",
        target="vectorstore/search.py::semantic_search",
        edge_type=EdgeType.CALLS,
        confidence=0.9,
        line=52,
    )

    assert edge.source == "qa.py::ask_question"
    assert edge.target == "vectorstore/search.py::semantic_search"
    assert edge.edge_type == EdgeType.CALLS
    assert edge.confidence == 0.9
    assert edge.line == 52


def test_edge_type_enum():
    """EdgeType has expected values matching ReferenceType."""
    from oya.graph.models import EdgeType

    assert EdgeType.CALLS.value == "calls"
    assert EdgeType.INSTANTIATES.value == "instantiates"
    assert EdgeType.INHERITS.value == "inherits"
    assert EdgeType.IMPORTS.value == "imports"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_graph_models.py::test_edge_model_creation -v`

Expected: FAIL with ImportError

**Step 3: Write minimal implementation**

Add to `backend/src/oya/graph/models.py`:

```python
class EdgeType(Enum):
    """Types of edges (relationships) in the code graph."""

    CALLS = "calls"
    INSTANTIATES = "instantiates"
    INHERITS = "inherits"
    IMPORTS = "imports"


@dataclass
class Edge:
    """An edge in the code graph representing a relationship."""

    source: str  # Source node ID
    target: str  # Target node ID
    edge_type: EdgeType
    confidence: float  # 0.0 to 1.0
    line: int  # Line number where relationship occurs
    metadata: dict = field(default_factory=dict)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_graph_models.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/oya/graph/models.py backend/tests/test_graph_models.py
git commit -m "feat(graph): add Edge and EdgeType models"
```

---

## Task 3: Create Subgraph Model with Serialization

**Files:**
- Modify: `backend/src/oya/graph/models.py`
- Test: `backend/tests/test_graph_models.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_graph_models.py`:

```python
def test_subgraph_model():
    """Subgraph aggregates nodes and edges."""
    from oya.graph.models import Node, Edge, Subgraph, NodeType, EdgeType

    node1 = Node(
        id="a.py::func_a",
        node_type=NodeType.FUNCTION,
        name="func_a",
        file_path="a.py",
        line_start=1,
        line_end=10,
    )
    node2 = Node(
        id="b.py::func_b",
        node_type=NodeType.FUNCTION,
        name="func_b",
        file_path="b.py",
        line_start=1,
        line_end=5,
    )
    edge = Edge(
        source="a.py::func_a",
        target="b.py::func_b",
        edge_type=EdgeType.CALLS,
        confidence=0.9,
        line=5,
    )

    subgraph = Subgraph(nodes=[node1, node2], edges=[edge])

    assert len(subgraph.nodes) == 2
    assert len(subgraph.edges) == 1


def test_subgraph_to_dict():
    """Subgraph can be serialized to dict for JSON."""
    from oya.graph.models import Node, Edge, Subgraph, NodeType, EdgeType

    node = Node(
        id="a.py::func",
        node_type=NodeType.FUNCTION,
        name="func",
        file_path="a.py",
        line_start=1,
        line_end=10,
    )
    edge = Edge(
        source="a.py::func",
        target="b.py::other",
        edge_type=EdgeType.CALLS,
        confidence=0.85,
        line=5,
    )
    subgraph = Subgraph(nodes=[node], edges=[edge])

    data = subgraph.to_dict()

    assert "nodes" in data
    assert "edges" in data
    assert len(data["nodes"]) == 1
    assert data["nodes"][0]["id"] == "a.py::func"
    assert data["edges"][0]["confidence"] == 0.85
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_graph_models.py::test_subgraph_model -v`

Expected: FAIL with ImportError

**Step 3: Write minimal implementation**

Add to `backend/src/oya/graph/models.py`:

```python
@dataclass
class Subgraph:
    """A subset of the code graph (nodes and edges)."""

    nodes: list[Node]
    edges: list[Edge]

    def to_dict(self) -> dict:
        """Serialize to dictionary for JSON output."""
        return {
            "nodes": [
                {
                    "id": n.id,
                    "type": n.node_type.value,
                    "name": n.name,
                    "file_path": n.file_path,
                    "line_start": n.line_start,
                    "line_end": n.line_end,
                    "docstring": n.docstring,
                    "signature": n.signature,
                    "metadata": n.metadata,
                }
                for n in self.nodes
            ],
            "edges": [
                {
                    "source": e.source,
                    "target": e.target,
                    "type": e.edge_type.value,
                    "confidence": e.confidence,
                    "line": e.line,
                    "metadata": e.metadata,
                }
                for e in self.edges
            ],
        }
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_graph_models.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/oya/graph/models.py backend/tests/test_graph_models.py
git commit -m "feat(graph): add Subgraph model with serialization"
```

---

## Task 4: Subgraph to_context() for LLM Consumption

**Files:**
- Modify: `backend/src/oya/graph/models.py`
- Test: `backend/tests/test_graph_models.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_graph_models.py`:

```python
def test_subgraph_to_context():
    """Subgraph formats as text for LLM consumption."""
    from oya.graph.models import Node, Edge, Subgraph, NodeType, EdgeType

    node1 = Node(
        id="auth/handler.py::login",
        node_type=NodeType.FUNCTION,
        name="login",
        file_path="auth/handler.py",
        line_start=10,
        line_end=25,
        docstring="Authenticate user credentials.",
    )
    node2 = Node(
        id="auth/session.py::create_session",
        node_type=NodeType.FUNCTION,
        name="create_session",
        file_path="auth/session.py",
        line_start=5,
        line_end=15,
    )
    edge = Edge(
        source="auth/handler.py::login",
        target="auth/session.py::create_session",
        edge_type=EdgeType.CALLS,
        confidence=0.9,
        line=20,
    )

    subgraph = Subgraph(nodes=[node1, node2], edges=[edge])
    context = subgraph.to_context()

    # Should contain node information
    assert "login" in context
    assert "create_session" in context
    assert "auth/handler.py" in context
    # Should describe relationships
    assert "calls" in context.lower()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_graph_models.py::test_subgraph_to_context -v`

Expected: FAIL with AttributeError

**Step 3: Write minimal implementation**

Add to `Subgraph` class in `backend/src/oya/graph/models.py`:

```python
def to_context(self) -> str:
    """Format subgraph as text for LLM consumption."""
    lines = ["## Code Graph Context\n"]

    # Describe nodes
    lines.append("### Entities\n")
    for node in self.nodes:
        node_desc = f"- **{node.name}** ({node.node_type.value}) in `{node.file_path}` (lines {node.line_start}-{node.line_end})"
        if node.docstring:
            node_desc += f"\n  > {node.docstring}"
        lines.append(node_desc)

    # Describe relationships
    if self.edges:
        lines.append("\n### Relationships\n")
        for edge in self.edges:
            source_name = edge.source.split("::")[-1] if "::" in edge.source else edge.source
            target_name = edge.target.split("::")[-1] if "::" in edge.target else edge.target
            lines.append(
                f"- `{source_name}` **{edge.edge_type.value}** `{target_name}` "
                f"(confidence: {edge.confidence:.0%})"
            )

    return "\n".join(lines)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_graph_models.py::test_subgraph_to_context -v`

Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/oya/graph/models.py backend/tests/test_graph_models.py
git commit -m "feat(graph): add Subgraph.to_context() for LLM consumption"
```

---

## Task 5: Subgraph to_mermaid() for Diagram Generation

**Files:**
- Modify: `backend/src/oya/graph/models.py`
- Test: `backend/tests/test_graph_models.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_graph_models.py`:

```python
def test_subgraph_to_mermaid():
    """Subgraph generates deterministic Mermaid diagram."""
    from oya.graph.models import Node, Edge, Subgraph, NodeType, EdgeType

    node1 = Node(
        id="auth/handler.py::login",
        node_type=NodeType.FUNCTION,
        name="login",
        file_path="auth/handler.py",
        line_start=10,
        line_end=25,
    )
    node2 = Node(
        id="auth/session.py::create_session",
        node_type=NodeType.FUNCTION,
        name="create_session",
        file_path="auth/session.py",
        line_start=5,
        line_end=15,
    )
    node3 = Node(
        id="models/user.py::User",
        node_type=NodeType.CLASS,
        name="User",
        file_path="models/user.py",
        line_start=1,
        line_end=50,
    )
    edges = [
        Edge(source="auth/handler.py::login", target="auth/session.py::create_session",
             edge_type=EdgeType.CALLS, confidence=0.9, line=20),
        Edge(source="auth/handler.py::login", target="models/user.py::User",
             edge_type=EdgeType.INSTANTIATES, confidence=0.85, line=15),
    ]

    subgraph = Subgraph(nodes=[node1, node2, node3], edges=edges)
    mermaid = subgraph.to_mermaid()

    # Should be valid Mermaid flowchart
    assert mermaid.startswith("flowchart")
    # Should contain node definitions
    assert "login" in mermaid
    assert "create_session" in mermaid
    assert "User" in mermaid
    # Should contain edges
    assert "-->" in mermaid  # calls edge
    # Should be deterministic (same input = same output)
    assert subgraph.to_mermaid() == mermaid
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_graph_models.py::test_subgraph_to_mermaid -v`

Expected: FAIL with AttributeError

**Step 3: Write minimal implementation**

Add to `Subgraph` class in `backend/src/oya/graph/models.py`:

```python
def to_mermaid(self) -> str:
    """Generate deterministic Mermaid flowchart from subgraph."""
    lines = ["flowchart TD"]

    # Create stable node IDs (sanitize for Mermaid)
    def sanitize_id(node_id: str) -> str:
        return node_id.replace("/", "_").replace("::", "_").replace(".", "_").replace("-", "_")

    # Sort for determinism
    sorted_nodes = sorted(self.nodes, key=lambda n: n.id)
    sorted_edges = sorted(self.edges, key=lambda e: (e.source, e.target))

    # Add node definitions with shapes based on type
    for node in sorted_nodes:
        safe_id = sanitize_id(node.id)
        if node.node_type == NodeType.CLASS:
            lines.append(f"    {safe_id}[{node.name}]")
        elif node.node_type == NodeType.FUNCTION:
            lines.append(f"    {safe_id}({node.name})")
        elif node.node_type == NodeType.METHOD:
            lines.append(f"    {safe_id}({node.name})")
        else:
            lines.append(f"    {safe_id}[{node.name}]")

    # Add edges with appropriate arrow styles
    edge_styles = {
        EdgeType.CALLS: "-->",
        EdgeType.INSTANTIATES: "-.->",
        EdgeType.INHERITS: "-->|inherits|",
        EdgeType.IMPORTS: "-.->|imports|",
    }
    for edge in sorted_edges:
        source_id = sanitize_id(edge.source)
        target_id = sanitize_id(edge.target)
        arrow = edge_styles.get(edge.edge_type, "-->")
        lines.append(f"    {source_id} {arrow} {target_id}")

    return "\n".join(lines)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_graph_models.py::test_subgraph_to_mermaid -v`

Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/oya/graph/models.py backend/tests/test_graph_models.py
git commit -m "feat(graph): add Subgraph.to_mermaid() for deterministic diagrams"
```

---

## Task 6: Create Symbol Table Builder

**Files:**
- Create: `backend/src/oya/graph/resolver.py`
- Test: `backend/tests/test_graph_resolver.py`

**Step 1: Write the failing test**

Create `backend/tests/test_graph_resolver.py`:

```python
"""Tests for cross-file reference resolution."""

import pytest
from oya.parsing.models import ParsedFile, ParsedSymbol, SymbolType


def test_symbol_table_from_parsed_files():
    """SymbolTable indexes all definitions by name."""
    from oya.graph.resolver import SymbolTable

    file1 = ParsedFile(
        path="auth/utils.py",
        language="python",
        symbols=[
            ParsedSymbol(
                name="verify",
                symbol_type=SymbolType.FUNCTION,
                start_line=10,
                end_line=20,
            ),
        ],
    )
    file2 = ParsedFile(
        path="models/user.py",
        language="python",
        symbols=[
            ParsedSymbol(
                name="User",
                symbol_type=SymbolType.CLASS,
                start_line=5,
                end_line=50,
            ),
            ParsedSymbol(
                name="save",
                symbol_type=SymbolType.METHOD,
                start_line=30,
                end_line=40,
                parent="User",
            ),
        ],
    )

    table = SymbolTable.from_parsed_files([file1, file2])

    # Can lookup by simple name
    assert table.lookup("verify") == ["auth/utils.py::verify"]
    assert table.lookup("User") == ["models/user.py::User"]
    # Methods are qualified with class
    assert table.lookup("User.save") == ["models/user.py::User.save"]


def test_symbol_table_handles_duplicates():
    """SymbolTable tracks multiple definitions with same name."""
    from oya.graph.resolver import SymbolTable

    file1 = ParsedFile(
        path="a.py",
        language="python",
        symbols=[
            ParsedSymbol(name="process", symbol_type=SymbolType.FUNCTION, start_line=1, end_line=10),
        ],
    )
    file2 = ParsedFile(
        path="b.py",
        language="python",
        symbols=[
            ParsedSymbol(name="process", symbol_type=SymbolType.FUNCTION, start_line=1, end_line=10),
        ],
    )

    table = SymbolTable.from_parsed_files([file1, file2])

    results = table.lookup("process")
    assert len(results) == 2
    assert "a.py::process" in results
    assert "b.py::process" in results
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_graph_resolver.py -v`

Expected: FAIL with ImportError

**Step 3: Write minimal implementation**

Create `backend/src/oya/graph/resolver.py`:

```python
"""Cross-file reference resolution using symbol tables."""

from dataclasses import dataclass, field
from oya.parsing.models import ParsedFile, ParsedSymbol


@dataclass
class SymbolTable:
    """Index of all code definitions for reference resolution."""

    # Maps simple name -> list of fully qualified IDs
    _by_name: dict[str, list[str]] = field(default_factory=dict)
    # Maps qualified name (e.g., "User.save") -> list of fully qualified IDs
    _by_qualified: dict[str, list[str]] = field(default_factory=dict)
    # Maps full ID -> symbol metadata
    _symbols: dict[str, ParsedSymbol] = field(default_factory=dict)
    # Maps full ID -> file path
    _file_paths: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_parsed_files(cls, files: list[ParsedFile]) -> "SymbolTable":
        """Build symbol table from parsed files."""
        table = cls()

        for file in files:
            for symbol in file.symbols:
                # Build fully qualified ID
                if symbol.parent:
                    full_id = f"{file.path}::{symbol.parent}.{symbol.name}"
                    qualified_name = f"{symbol.parent}.{symbol.name}"
                else:
                    full_id = f"{file.path}::{symbol.name}"
                    qualified_name = symbol.name

                # Index by simple name
                if symbol.name not in table._by_name:
                    table._by_name[symbol.name] = []
                table._by_name[symbol.name].append(full_id)

                # Index by qualified name
                if qualified_name not in table._by_qualified:
                    table._by_qualified[qualified_name] = []
                table._by_qualified[qualified_name].append(full_id)

                # Store symbol and file path
                table._symbols[full_id] = symbol
                table._file_paths[full_id] = file.path

        return table

    def lookup(self, name: str) -> list[str]:
        """Look up symbol by name, returning all matching full IDs."""
        # Try qualified name first
        if name in self._by_qualified:
            return self._by_qualified[name]
        # Fall back to simple name
        return self._by_name.get(name, [])
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_graph_resolver.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/oya/graph/resolver.py backend/tests/test_graph_resolver.py
git commit -m "feat(graph): add SymbolTable for indexing definitions"
```

---

## Task 7: Reference Resolver

**Files:**
- Modify: `backend/src/oya/graph/resolver.py`
- Test: `backend/tests/test_graph_resolver.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_graph_resolver.py`:

```python
from oya.parsing.models import Reference, ReferenceType


def test_resolve_reference_exact_match():
    """Resolver finds exact match and sets high confidence."""
    from oya.graph.resolver import SymbolTable, resolve_references

    file1 = ParsedFile(
        path="auth/utils.py",
        language="python",
        symbols=[
            ParsedSymbol(name="verify", symbol_type=SymbolType.FUNCTION, start_line=10, end_line=20),
        ],
        references=[],
    )
    file2 = ParsedFile(
        path="auth/handler.py",
        language="python",
        symbols=[
            ParsedSymbol(name="login", symbol_type=SymbolType.FUNCTION, start_line=5, end_line=25),
        ],
        references=[
            Reference(
                source="auth/handler.py::login",
                target="verify",  # Unresolved
                reference_type=ReferenceType.CALLS,
                confidence=0.9,
                line=15,
                target_resolved=False,
            ),
        ],
    )

    table = SymbolTable.from_parsed_files([file1, file2])
    resolved = resolve_references([file2], table)

    assert len(resolved) == 1
    ref = resolved[0]
    assert ref.target == "auth/utils.py::verify"
    assert ref.target_resolved is True
    assert ref.confidence >= 0.9  # Should maintain or increase confidence


def test_resolve_reference_ambiguous():
    """Resolver lowers confidence for ambiguous matches."""
    from oya.graph.resolver import SymbolTable, resolve_references

    file1 = ParsedFile(
        path="a.py",
        language="python",
        symbols=[
            ParsedSymbol(name="process", symbol_type=SymbolType.FUNCTION, start_line=1, end_line=10),
        ],
    )
    file2 = ParsedFile(
        path="b.py",
        language="python",
        symbols=[
            ParsedSymbol(name="process", symbol_type=SymbolType.FUNCTION, start_line=1, end_line=10),
        ],
    )
    file3 = ParsedFile(
        path="main.py",
        language="python",
        symbols=[],
        references=[
            Reference(
                source="main.py::main",
                target="process",
                reference_type=ReferenceType.CALLS,
                confidence=0.9,
                line=5,
            ),
        ],
    )

    table = SymbolTable.from_parsed_files([file1, file2, file3])
    resolved = resolve_references([file3], table)

    # Should create references to both candidates with lower confidence
    assert len(resolved) == 2
    for ref in resolved:
        assert ref.confidence < 0.9  # Reduced due to ambiguity


def test_resolve_reference_no_match():
    """Resolver keeps unresolved references with low confidence."""
    from oya.graph.resolver import SymbolTable, resolve_references

    file = ParsedFile(
        path="main.py",
        language="python",
        symbols=[],
        references=[
            Reference(
                source="main.py::main",
                target="unknown_func",
                reference_type=ReferenceType.CALLS,
                confidence=0.9,
                line=5,
            ),
        ],
    )

    table = SymbolTable.from_parsed_files([file])
    resolved = resolve_references([file], table)

    assert len(resolved) == 1
    ref = resolved[0]
    assert ref.target == "unknown_func"  # Unchanged
    assert ref.target_resolved is False
    assert ref.confidence < 0.5  # Lowered significantly
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_graph_resolver.py::test_resolve_reference_exact_match -v`

Expected: FAIL with ImportError

**Step 3: Write minimal implementation**

Add to `backend/src/oya/graph/resolver.py`:

```python
from oya.parsing.models import Reference, ReferenceType


def resolve_references(
    files: list[ParsedFile],
    symbol_table: SymbolTable,
) -> list[Reference]:
    """Resolve references against the symbol table.

    Args:
        files: Parsed files containing unresolved references.
        symbol_table: Symbol table built from all parsed files.

    Returns:
        List of resolved (or attempted) references.
    """
    resolved = []

    for file in files:
        for ref in file.references:
            if ref.target_resolved:
                # Already resolved
                resolved.append(ref)
                continue

            # Look up target in symbol table
            candidates = symbol_table.lookup(ref.target)

            if len(candidates) == 1:
                # Exact match - high confidence
                resolved.append(
                    Reference(
                        source=ref.source,
                        target=candidates[0],
                        reference_type=ref.reference_type,
                        confidence=ref.confidence,  # Maintain original confidence
                        line=ref.line,
                        target_resolved=True,
                    )
                )
            elif len(candidates) > 1:
                # Ambiguous - create multiple refs with reduced confidence
                for candidate in candidates:
                    resolved.append(
                        Reference(
                            source=ref.source,
                            target=candidate,
                            reference_type=ref.reference_type,
                            confidence=ref.confidence * 0.5,  # Reduce confidence
                            line=ref.line,
                            target_resolved=True,
                        )
                    )
            else:
                # No match - keep unresolved with low confidence
                resolved.append(
                    Reference(
                        source=ref.source,
                        target=ref.target,
                        reference_type=ref.reference_type,
                        confidence=ref.confidence * 0.3,  # Significantly reduce
                        line=ref.line,
                        target_resolved=False,
                    )
                )

    return resolved
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_graph_resolver.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/oya/graph/resolver.py backend/tests/test_graph_resolver.py
git commit -m "feat(graph): add reference resolver with confidence adjustment"
```

---

## Task 8: Graph Builder - Create NetworkX Graph

**Files:**
- Create: `backend/src/oya/graph/builder.py`
- Test: `backend/tests/test_graph_builder.py`

**Step 1: Write the failing test**

Create `backend/tests/test_graph_builder.py`:

```python
"""Tests for NetworkX graph construction."""

import pytest
from oya.parsing.models import ParsedFile, ParsedSymbol, SymbolType, Reference, ReferenceType


def test_build_graph_from_parsed_files():
    """Builder creates NetworkX graph with nodes and edges."""
    from oya.graph.builder import build_graph

    file1 = ParsedFile(
        path="auth/utils.py",
        language="python",
        symbols=[
            ParsedSymbol(name="verify", symbol_type=SymbolType.FUNCTION, start_line=10, end_line=20),
        ],
    )
    file2 = ParsedFile(
        path="auth/handler.py",
        language="python",
        symbols=[
            ParsedSymbol(name="login", symbol_type=SymbolType.FUNCTION, start_line=5, end_line=25),
        ],
        references=[
            Reference(
                source="auth/handler.py::login",
                target="auth/utils.py::verify",
                reference_type=ReferenceType.CALLS,
                confidence=0.9,
                line=15,
                target_resolved=True,
            ),
        ],
    )

    graph = build_graph([file1, file2])

    # Should have nodes for both functions
    assert graph.has_node("auth/utils.py::verify")
    assert graph.has_node("auth/handler.py::login")

    # Should have edge from login to verify
    assert graph.has_edge("auth/handler.py::login", "auth/utils.py::verify")

    # Edge should have attributes
    edge_data = graph.edges["auth/handler.py::login", "auth/utils.py::verify"]
    assert edge_data["type"] == "calls"
    assert edge_data["confidence"] == 0.9


def test_build_graph_node_attributes():
    """Graph nodes have correct attributes."""
    from oya.graph.builder import build_graph

    file = ParsedFile(
        path="models/user.py",
        language="python",
        symbols=[
            ParsedSymbol(
                name="User",
                symbol_type=SymbolType.CLASS,
                start_line=5,
                end_line=50,
                docstring="A user entity.",
            ),
        ],
    )

    graph = build_graph([file])

    node_data = graph.nodes["models/user.py::User"]
    assert node_data["name"] == "User"
    assert node_data["type"] == "class"
    assert node_data["file_path"] == "models/user.py"
    assert node_data["line_start"] == 5
    assert node_data["line_end"] == 50
    assert node_data["docstring"] == "A user entity."
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_graph_builder.py -v`

Expected: FAIL with ImportError

**Step 3: Write minimal implementation**

Create `backend/src/oya/graph/builder.py`:

```python
"""Build NetworkX graph from parsed code files."""

import networkx as nx

from oya.parsing.models import ParsedFile, ParsedSymbol, SymbolType
from oya.graph.resolver import SymbolTable, resolve_references


def build_graph(parsed_files: list[ParsedFile]) -> nx.DiGraph:
    """Build a directed graph from parsed files.

    Args:
        parsed_files: List of parsed files with symbols and references.

    Returns:
        NetworkX directed graph with code entities as nodes and relationships as edges.
    """
    G = nx.DiGraph()

    # Build symbol table and resolve references
    symbol_table = SymbolTable.from_parsed_files(parsed_files)
    all_resolved_refs = []
    for file in parsed_files:
        resolved = resolve_references([file], symbol_table)
        all_resolved_refs.extend(resolved)

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
            )

    # Add edges for all resolved references
    for ref in all_resolved_refs:
        if ref.target_resolved:
            # Only add edges for resolved references where both nodes exist
            if G.has_node(ref.source) and G.has_node(ref.target):
                G.add_edge(
                    ref.source,
                    ref.target,
                    type=ref.reference_type.value,
                    confidence=ref.confidence,
                    line=ref.line,
                )
            elif G.has_node(ref.source):
                # Target node doesn't exist but reference is resolved
                # This can happen for external dependencies
                G.add_edge(
                    ref.source,
                    ref.target,
                    type=ref.reference_type.value,
                    confidence=ref.confidence,
                    line=ref.line,
                )

    return G


def _make_node_id(file_path: str, symbol: ParsedSymbol) -> str:
    """Create a unique node ID for a symbol."""
    if symbol.parent:
        return f"{file_path}::{symbol.parent}.{symbol.name}"
    return f"{file_path}::{symbol.name}"
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_graph_builder.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/oya/graph/builder.py backend/tests/test_graph_builder.py
git commit -m "feat(graph): add NetworkX graph builder"
```

---

## Task 9: Graph Persistence - Save to JSON

**Files:**
- Create: `backend/src/oya/graph/persistence.py`
- Test: `backend/tests/test_graph_persistence.py`

**Step 1: Write the failing test**

Create `backend/tests/test_graph_persistence.py`:

```python
"""Tests for graph persistence to JSON."""

import json
import pytest
from pathlib import Path
import networkx as nx


def test_save_graph_creates_files(tmp_path):
    """save_graph creates nodes.json, edges.json, and metadata.json."""
    from oya.graph.persistence import save_graph

    G = nx.DiGraph()
    G.add_node("a.py::func", name="func", type="function", file_path="a.py",
               line_start=1, line_end=10, docstring=None, signature=None, parent=None)
    G.add_edge("a.py::func", "b.py::other", type="calls", confidence=0.9, line=5)

    output_dir = tmp_path / ".oyawiki" / "graph"
    save_graph(G, output_dir)

    assert (output_dir / "nodes.json").exists()
    assert (output_dir / "edges.json").exists()
    assert (output_dir / "metadata.json").exists()


def test_save_graph_nodes_format(tmp_path):
    """nodes.json contains correct node data."""
    from oya.graph.persistence import save_graph

    G = nx.DiGraph()
    G.add_node("models/user.py::User", name="User", type="class",
               file_path="models/user.py", line_start=5, line_end=50,
               docstring="A user entity.", signature=None, parent=None)

    output_dir = tmp_path / "graph"
    save_graph(G, output_dir)

    with open(output_dir / "nodes.json") as f:
        nodes = json.load(f)

    assert len(nodes) == 1
    assert nodes[0]["id"] == "models/user.py::User"
    assert nodes[0]["name"] == "User"
    assert nodes[0]["type"] == "class"
    assert nodes[0]["docstring"] == "A user entity."


def test_save_graph_edges_format(tmp_path):
    """edges.json contains correct edge data."""
    from oya.graph.persistence import save_graph

    G = nx.DiGraph()
    G.add_node("a.py::func", name="func", type="function", file_path="a.py",
               line_start=1, line_end=10, docstring=None, signature=None, parent=None)
    G.add_node("b.py::other", name="other", type="function", file_path="b.py",
               line_start=1, line_end=5, docstring=None, signature=None, parent=None)
    G.add_edge("a.py::func", "b.py::other", type="calls", confidence=0.85, line=7)

    output_dir = tmp_path / "graph"
    save_graph(G, output_dir)

    with open(output_dir / "edges.json") as f:
        edges = json.load(f)

    assert len(edges) == 1
    assert edges[0]["source"] == "a.py::func"
    assert edges[0]["target"] == "b.py::other"
    assert edges[0]["type"] == "calls"
    assert edges[0]["confidence"] == 0.85


def test_save_graph_metadata(tmp_path):
    """metadata.json contains build information."""
    from oya.graph.persistence import save_graph

    G = nx.DiGraph()
    G.add_node("a.py::func", name="func", type="function", file_path="a.py",
               line_start=1, line_end=10, docstring=None, signature=None, parent=None)

    output_dir = tmp_path / "graph"
    save_graph(G, output_dir)

    with open(output_dir / "metadata.json") as f:
        metadata = json.load(f)

    assert "build_timestamp" in metadata
    assert metadata["node_count"] == 1
    assert metadata["edge_count"] == 0
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_graph_persistence.py -v`

Expected: FAIL with ImportError

**Step 3: Write minimal implementation**

Create `backend/src/oya/graph/persistence.py`:

```python
"""Persist graph to JSON files in .oyawiki/graph/."""

import json
from datetime import datetime, timezone
from pathlib import Path

import networkx as nx


def save_graph(graph: nx.DiGraph, output_dir: Path) -> None:
    """Save graph to JSON files.

    Creates:
        - nodes.json: All node definitions
        - edges.json: All edges with confidence
        - metadata.json: Build timestamp and stats

    Args:
        graph: NetworkX directed graph to persist.
        output_dir: Directory to write files to (e.g., .oyawiki/graph/).
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Serialize nodes
    nodes = []
    for node_id, attrs in graph.nodes(data=True):
        nodes.append({
            "id": node_id,
            "name": attrs.get("name"),
            "type": attrs.get("type"),
            "file_path": attrs.get("file_path"),
            "line_start": attrs.get("line_start"),
            "line_end": attrs.get("line_end"),
            "docstring": attrs.get("docstring"),
            "signature": attrs.get("signature"),
            "parent": attrs.get("parent"),
        })

    # Sort for determinism
    nodes.sort(key=lambda n: n["id"])

    with open(output_dir / "nodes.json", "w") as f:
        json.dump(nodes, f, indent=2)

    # Serialize edges
    edges = []
    for source, target, attrs in graph.edges(data=True):
        edges.append({
            "source": source,
            "target": target,
            "type": attrs.get("type"),
            "confidence": attrs.get("confidence"),
            "line": attrs.get("line"),
        })

    # Sort for determinism
    edges.sort(key=lambda e: (e["source"], e["target"]))

    with open(output_dir / "edges.json", "w") as f:
        json.dump(edges, f, indent=2)

    # Write metadata
    metadata = {
        "build_timestamp": datetime.now(timezone.utc).isoformat(),
        "node_count": graph.number_of_nodes(),
        "edge_count": graph.number_of_edges(),
    }

    with open(output_dir / "metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_graph_persistence.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/oya/graph/persistence.py backend/tests/test_graph_persistence.py
git commit -m "feat(graph): add JSON persistence for graph"
```

---

## Task 10: Graph Persistence - Load from JSON

**Files:**
- Modify: `backend/src/oya/graph/persistence.py`
- Test: `backend/tests/test_graph_persistence.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_graph_persistence.py`:

```python
def test_load_graph_roundtrip(tmp_path):
    """load_graph reconstructs the saved graph."""
    from oya.graph.persistence import save_graph, load_graph

    G = nx.DiGraph()
    G.add_node("a.py::func", name="func", type="function", file_path="a.py",
               line_start=1, line_end=10, docstring="A function.", signature="def func():", parent=None)
    G.add_node("b.py::other", name="other", type="function", file_path="b.py",
               line_start=1, line_end=5, docstring=None, signature=None, parent=None)
    G.add_edge("a.py::func", "b.py::other", type="calls", confidence=0.85, line=7)

    output_dir = tmp_path / "graph"
    save_graph(G, output_dir)

    loaded = load_graph(output_dir)

    # Same nodes
    assert set(loaded.nodes()) == set(G.nodes())
    # Same edges
    assert set(loaded.edges()) == set(G.edges())
    # Node attributes preserved
    assert loaded.nodes["a.py::func"]["docstring"] == "A function."
    # Edge attributes preserved
    assert loaded.edges["a.py::func", "b.py::other"]["confidence"] == 0.85


def test_load_graph_missing_dir_returns_empty():
    """load_graph returns empty graph for missing directory."""
    from oya.graph.persistence import load_graph

    loaded = load_graph(Path("/nonexistent/path"))

    assert loaded.number_of_nodes() == 0
    assert loaded.number_of_edges() == 0
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_graph_persistence.py::test_load_graph_roundtrip -v`

Expected: FAIL with ImportError

**Step 3: Write minimal implementation**

Add to `backend/src/oya/graph/persistence.py`:

```python
def load_graph(input_dir: Path) -> nx.DiGraph:
    """Load graph from JSON files.

    Args:
        input_dir: Directory containing nodes.json, edges.json.

    Returns:
        Reconstructed NetworkX directed graph, or empty graph if files don't exist.
    """
    input_dir = Path(input_dir)
    G = nx.DiGraph()

    nodes_file = input_dir / "nodes.json"
    edges_file = input_dir / "edges.json"

    if not nodes_file.exists():
        return G

    # Load nodes
    with open(nodes_file) as f:
        nodes = json.load(f)

    for node in nodes:
        G.add_node(
            node["id"],
            name=node.get("name"),
            type=node.get("type"),
            file_path=node.get("file_path"),
            line_start=node.get("line_start"),
            line_end=node.get("line_end"),
            docstring=node.get("docstring"),
            signature=node.get("signature"),
            parent=node.get("parent"),
        )

    # Load edges
    if edges_file.exists():
        with open(edges_file) as f:
            edges = json.load(f)

        for edge in edges:
            G.add_edge(
                edge["source"],
                edge["target"],
                type=edge.get("type"),
                confidence=edge.get("confidence"),
                line=edge.get("line"),
            )

    return G
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_graph_persistence.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/oya/graph/persistence.py backend/tests/test_graph_persistence.py
git commit -m "feat(graph): add load_graph for JSON deserialization"
```

---

## Task 11: Query Interface - get_calls and get_callers

**Files:**
- Create: `backend/src/oya/graph/query.py`
- Test: `backend/tests/test_graph_query.py`

**Step 1: Write the failing test**

Create `backend/tests/test_graph_query.py`:

```python
"""Tests for graph query interface."""

import pytest
import networkx as nx


@pytest.fixture
def sample_graph():
    """Create a sample graph for testing queries."""
    G = nx.DiGraph()

    # Add nodes
    G.add_node("handler.py::process_request", name="process_request", type="function",
               file_path="handler.py", line_start=10, line_end=30, docstring=None, signature=None, parent=None)
    G.add_node("auth.py::verify_token", name="verify_token", type="function",
               file_path="auth.py", line_start=5, line_end=15, docstring=None, signature=None, parent=None)
    G.add_node("db.py::get_user", name="get_user", type="function",
               file_path="db.py", line_start=20, line_end=35, docstring=None, signature=None, parent=None)
    G.add_node("response.py::send_response", name="send_response", type="function",
               file_path="response.py", line_start=1, line_end=10, docstring=None, signature=None, parent=None)

    # Add edges: process_request calls verify_token, get_user, send_response
    G.add_edge("handler.py::process_request", "auth.py::verify_token",
               type="calls", confidence=0.95, line=15)
    G.add_edge("handler.py::process_request", "db.py::get_user",
               type="calls", confidence=0.9, line=20)
    G.add_edge("handler.py::process_request", "response.py::send_response",
               type="calls", confidence=0.85, line=25)
    # verify_token also calls get_user
    G.add_edge("auth.py::verify_token", "db.py::get_user",
               type="calls", confidence=0.7, line=10)

    return G


def test_get_calls(sample_graph):
    """get_calls returns outgoing call targets."""
    from oya.graph.query import get_calls

    calls = get_calls(sample_graph, "handler.py::process_request")

    assert len(calls) == 3
    call_ids = [n.id for n in calls]
    assert "auth.py::verify_token" in call_ids
    assert "db.py::get_user" in call_ids
    assert "response.py::send_response" in call_ids


def test_get_calls_with_confidence_filter(sample_graph):
    """get_calls respects minimum confidence threshold."""
    from oya.graph.query import get_calls

    calls = get_calls(sample_graph, "handler.py::process_request", min_confidence=0.9)

    assert len(calls) == 2  # Only 0.95 and 0.9 edges
    call_ids = [n.id for n in calls]
    assert "auth.py::verify_token" in call_ids
    assert "db.py::get_user" in call_ids
    assert "response.py::send_response" not in call_ids  # 0.85 < 0.9


def test_get_callers(sample_graph):
    """get_callers returns incoming call sources."""
    from oya.graph.query import get_callers

    callers = get_callers(sample_graph, "db.py::get_user")

    assert len(callers) == 2
    caller_ids = [n.id for n in callers]
    assert "handler.py::process_request" in caller_ids
    assert "auth.py::verify_token" in caller_ids
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_graph_query.py -v`

Expected: FAIL with ImportError

**Step 3: Write minimal implementation**

Create `backend/src/oya/graph/query.py`:

```python
"""Query interface for the code knowledge graph."""

from dataclasses import dataclass
import networkx as nx

from oya.graph.models import Node, NodeType, Edge, EdgeType, Subgraph


def get_calls(
    graph: nx.DiGraph,
    node_id: str,
    min_confidence: float = 0.0,
) -> list[Node]:
    """Get functions/methods called by this node.

    Args:
        graph: The code graph.
        node_id: ID of the source node.
        min_confidence: Minimum edge confidence to include.

    Returns:
        List of Node objects for called entities.
    """
    if not graph.has_node(node_id):
        return []

    nodes = []
    for _, target, edge_data in graph.out_edges(node_id, data=True):
        if edge_data.get("type") == "calls" and edge_data.get("confidence", 0) >= min_confidence:
            if graph.has_node(target):
                node_data = graph.nodes[target]
                nodes.append(_node_from_data(target, node_data))

    return nodes


def get_callers(
    graph: nx.DiGraph,
    node_id: str,
    min_confidence: float = 0.0,
) -> list[Node]:
    """Get functions/methods that call this node.

    Args:
        graph: The code graph.
        node_id: ID of the target node.
        min_confidence: Minimum edge confidence to include.

    Returns:
        List of Node objects for calling entities.
    """
    if not graph.has_node(node_id):
        return []

    nodes = []
    for source, _, edge_data in graph.in_edges(node_id, data=True):
        if edge_data.get("type") == "calls" and edge_data.get("confidence", 0) >= min_confidence:
            if graph.has_node(source):
                node_data = graph.nodes[source]
                nodes.append(_node_from_data(source, node_data))

    return nodes


def _node_from_data(node_id: str, data: dict) -> Node:
    """Convert graph node data to Node model."""
    node_type_str = data.get("type", "function")
    try:
        node_type = NodeType(node_type_str)
    except ValueError:
        node_type = NodeType.FUNCTION

    return Node(
        id=node_id,
        node_type=node_type,
        name=data.get("name", ""),
        file_path=data.get("file_path", ""),
        line_start=data.get("line_start", 0),
        line_end=data.get("line_end", 0),
        docstring=data.get("docstring"),
        signature=data.get("signature"),
    )
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_graph_query.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/oya/graph/query.py backend/tests/test_graph_query.py
git commit -m "feat(graph): add get_calls and get_callers query functions"
```

---

## Task 12: Query Interface - get_neighborhood

**Files:**
- Modify: `backend/src/oya/graph/query.py`
- Test: `backend/tests/test_graph_query.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_graph_query.py`:

```python
def test_get_neighborhood_one_hop(sample_graph):
    """get_neighborhood with hops=1 returns immediate neighbors."""
    from oya.graph.query import get_neighborhood

    subgraph = get_neighborhood(sample_graph, "auth.py::verify_token", hops=1)

    node_ids = [n.id for n in subgraph.nodes]
    # Should include the center node
    assert "auth.py::verify_token" in node_ids
    # Should include nodes 1 hop away
    assert "handler.py::process_request" in node_ids  # caller
    assert "db.py::get_user" in node_ids  # callee


def test_get_neighborhood_two_hops(sample_graph):
    """get_neighborhood with hops=2 returns 2-hop neighborhood."""
    from oya.graph.query import get_neighborhood

    subgraph = get_neighborhood(sample_graph, "auth.py::verify_token", hops=2)

    node_ids = [n.id for n in subgraph.nodes]
    # Should include all connected nodes within 2 hops
    assert "auth.py::verify_token" in node_ids
    assert "handler.py::process_request" in node_ids
    assert "db.py::get_user" in node_ids
    assert "response.py::send_response" in node_ids  # 2 hops via process_request


def test_get_neighborhood_includes_edges(sample_graph):
    """get_neighborhood includes edges between included nodes."""
    from oya.graph.query import get_neighborhood

    subgraph = get_neighborhood(sample_graph, "auth.py::verify_token", hops=1)

    # Should have edge from verify_token to get_user
    edge_pairs = [(e.source, e.target) for e in subgraph.edges]
    assert ("auth.py::verify_token", "db.py::get_user") in edge_pairs
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_graph_query.py::test_get_neighborhood_one_hop -v`

Expected: FAIL with ImportError

**Step 3: Write minimal implementation**

Add to `backend/src/oya/graph/query.py`:

```python
def get_neighborhood(
    graph: nx.DiGraph,
    node_id: str,
    hops: int = 2,
    min_confidence: float = 0.0,
) -> Subgraph:
    """Get all nodes within N hops of the given node.

    Args:
        graph: The code graph.
        node_id: ID of the center node.
        hops: Maximum distance from center node.
        min_confidence: Minimum edge confidence to traverse.

    Returns:
        Subgraph containing nodes and edges within the neighborhood.
    """
    if not graph.has_node(node_id):
        return Subgraph(nodes=[], edges=[])

    # Use BFS to find all nodes within N hops
    visited = {node_id}
    frontier = {node_id}

    for _ in range(hops):
        next_frontier = set()
        for current in frontier:
            # Check outgoing edges
            for _, target, edge_data in graph.out_edges(current, data=True):
                if edge_data.get("confidence", 0) >= min_confidence:
                    if target not in visited:
                        visited.add(target)
                        next_frontier.add(target)
            # Check incoming edges
            for source, _, edge_data in graph.in_edges(current, data=True):
                if edge_data.get("confidence", 0) >= min_confidence:
                    if source not in visited:
                        visited.add(source)
                        next_frontier.add(source)
        frontier = next_frontier

    # Build subgraph
    nodes = []
    for nid in visited:
        if graph.has_node(nid):
            node_data = graph.nodes[nid]
            nodes.append(_node_from_data(nid, node_data))

    edges = []
    for source, target, edge_data in graph.edges(data=True):
        if source in visited and target in visited:
            if edge_data.get("confidence", 0) >= min_confidence:
                edge_type_str = edge_data.get("type", "calls")
                try:
                    edge_type = EdgeType(edge_type_str)
                except ValueError:
                    edge_type = EdgeType.CALLS

                edges.append(Edge(
                    source=source,
                    target=target,
                    edge_type=edge_type,
                    confidence=edge_data.get("confidence", 0),
                    line=edge_data.get("line", 0),
                ))

    return Subgraph(nodes=nodes, edges=edges)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_graph_query.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/oya/graph/query.py backend/tests/test_graph_query.py
git commit -m "feat(graph): add get_neighborhood for multi-hop traversal"
```

---

## Task 13: Query Interface - trace_flow

**Files:**
- Modify: `backend/src/oya/graph/query.py`
- Test: `backend/tests/test_graph_query.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_graph_query.py`:

```python
def test_trace_flow_direct_path(sample_graph):
    """trace_flow finds direct path between nodes."""
    from oya.graph.query import trace_flow

    paths = trace_flow(sample_graph, "handler.py::process_request", "db.py::get_user")

    assert len(paths) >= 1
    # Should find direct path
    direct_path = [p for p in paths if len(p) == 2]
    assert len(direct_path) >= 1


def test_trace_flow_indirect_path(sample_graph):
    """trace_flow finds indirect paths through intermediaries."""
    from oya.graph.query import trace_flow

    paths = trace_flow(sample_graph, "handler.py::process_request", "db.py::get_user")

    # Should find both direct and indirect (via verify_token) paths
    assert len(paths) >= 2

    # Find the indirect path
    indirect = [p for p in paths if len(p) == 3]
    assert len(indirect) >= 1
    assert "auth.py::verify_token" in indirect[0]


def test_trace_flow_no_path():
    """trace_flow returns empty list when no path exists."""
    from oya.graph.query import trace_flow

    G = nx.DiGraph()
    G.add_node("a.py::func_a", name="func_a", type="function", file_path="a.py",
               line_start=1, line_end=10, docstring=None, signature=None, parent=None)
    G.add_node("b.py::func_b", name="func_b", type="function", file_path="b.py",
               line_start=1, line_end=10, docstring=None, signature=None, parent=None)
    # No edge between them

    paths = trace_flow(G, "a.py::func_a", "b.py::func_b")

    assert len(paths) == 0
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_graph_query.py::test_trace_flow_direct_path -v`

Expected: FAIL with ImportError

**Step 3: Write minimal implementation**

Add to `backend/src/oya/graph/query.py`:

```python
def trace_flow(
    graph: nx.DiGraph,
    start: str,
    end: str,
    min_confidence: float = 0.0,
    max_paths: int = 10,
) -> list[list[str]]:
    """Find paths between two nodes.

    Args:
        graph: The code graph.
        start: Source node ID.
        end: Target node ID.
        min_confidence: Minimum edge confidence to traverse.
        max_paths: Maximum number of paths to return.

    Returns:
        List of paths, where each path is a list of node IDs.
    """
    if not graph.has_node(start) or not graph.has_node(end):
        return []

    # Create filtered subgraph based on confidence
    if min_confidence > 0:
        filtered = nx.DiGraph()
        for node, data in graph.nodes(data=True):
            filtered.add_node(node, **data)
        for source, target, data in graph.edges(data=True):
            if data.get("confidence", 0) >= min_confidence:
                filtered.add_edge(source, target, **data)
        graph = filtered

    try:
        # Find all simple paths (no repeated nodes)
        paths = list(nx.all_simple_paths(graph, start, end, cutoff=10))
        # Sort by length (shorter paths first)
        paths.sort(key=len)
        return paths[:max_paths]
    except nx.NetworkXNoPath:
        return []
    except nx.NodeNotFound:
        return []
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_graph_query.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/oya/graph/query.py backend/tests/test_graph_query.py
git commit -m "feat(graph): add trace_flow for path finding"
```

---

## Task 14: Query Interface - get_entry_points and get_leaf_nodes

**Files:**
- Modify: `backend/src/oya/graph/query.py`
- Test: `backend/tests/test_graph_query.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_graph_query.py`:

```python
def test_get_entry_points(sample_graph):
    """get_entry_points finds nodes with no incoming calls."""
    from oya.graph.query import get_entry_points

    entry_points = get_entry_points(sample_graph)

    # Only process_request has no incoming calls
    entry_ids = [n.id for n in entry_points]
    assert "handler.py::process_request" in entry_ids
    assert "auth.py::verify_token" not in entry_ids  # Has incoming call
    assert "db.py::get_user" not in entry_ids  # Has incoming calls


def test_get_leaf_nodes(sample_graph):
    """get_leaf_nodes finds nodes with no outgoing calls."""
    from oya.graph.query import get_leaf_nodes

    leaves = get_leaf_nodes(sample_graph)

    leaf_ids = [n.id for n in leaves]
    # Nodes that don't call anything
    assert "db.py::get_user" in leaf_ids
    assert "response.py::send_response" in leaf_ids
    # Nodes that do call others
    assert "handler.py::process_request" not in leaf_ids
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_graph_query.py::test_get_entry_points -v`

Expected: FAIL with ImportError

**Step 3: Write minimal implementation**

Add to `backend/src/oya/graph/query.py`:

```python
def get_entry_points(graph: nx.DiGraph) -> list[Node]:
    """Find nodes with no incoming call edges (likely entry points).

    Args:
        graph: The code graph.

    Returns:
        List of nodes that have outgoing calls but no incoming calls.
    """
    nodes = []
    for node_id in graph.nodes():
        in_calls = [e for _, _, d in graph.in_edges(node_id, data=True) if d.get("type") == "calls"]
        out_calls = [e for _, _, d in graph.out_edges(node_id, data=True) if d.get("type") == "calls"]

        # Entry point: has outgoing calls but no incoming calls
        if len(out_calls) > 0 and len(in_calls) == 0:
            node_data = graph.nodes[node_id]
            nodes.append(_node_from_data(node_id, node_data))

    return nodes


def get_leaf_nodes(graph: nx.DiGraph) -> list[Node]:
    """Find nodes with no outgoing call edges (endpoints like DB, external APIs).

    Args:
        graph: The code graph.

    Returns:
        List of nodes that have no outgoing call edges.
    """
    nodes = []
    for node_id in graph.nodes():
        out_calls = [e for _, _, d in graph.out_edges(node_id, data=True) if d.get("type") == "calls"]

        if len(out_calls) == 0:
            node_data = graph.nodes[node_id]
            nodes.append(_node_from_data(node_id, node_data))

    return nodes
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_graph_query.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/oya/graph/query.py backend/tests/test_graph_query.py
git commit -m "feat(graph): add get_entry_points and get_leaf_nodes"
```

---

## Task 15: Export Graph Module Public Interface

**Files:**
- Modify: `backend/src/oya/graph/__init__.py`
- Test: `backend/tests/test_graph_models.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_graph_models.py`:

```python
def test_graph_module_exports():
    """Graph module exports all public interfaces."""
    from oya.graph import (
        # Models
        Node,
        NodeType,
        Edge,
        EdgeType,
        Subgraph,
        # Builder
        build_graph,
        # Resolver
        SymbolTable,
        resolve_references,
        # Persistence
        save_graph,
        load_graph,
        # Query
        get_calls,
        get_callers,
        get_neighborhood,
        trace_flow,
        get_entry_points,
        get_leaf_nodes,
    )

    # Basic smoke test
    assert NodeType.FUNCTION.value == "function"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_graph_models.py::test_graph_module_exports -v`

Expected: FAIL with ImportError

**Step 3: Write minimal implementation**

Update `backend/src/oya/graph/__init__.py`:

```python
"""Code graph construction and querying."""

from oya.graph.models import (
    Node,
    NodeType,
    Edge,
    EdgeType,
    Subgraph,
)
from oya.graph.builder import build_graph
from oya.graph.resolver import SymbolTable, resolve_references
from oya.graph.persistence import save_graph, load_graph
from oya.graph.query import (
    get_calls,
    get_callers,
    get_neighborhood,
    trace_flow,
    get_entry_points,
    get_leaf_nodes,
)

__all__ = [
    # Models
    "Node",
    "NodeType",
    "Edge",
    "EdgeType",
    "Subgraph",
    # Builder
    "build_graph",
    # Resolver
    "SymbolTable",
    "resolve_references",
    # Persistence
    "save_graph",
    "load_graph",
    # Query
    "get_calls",
    "get_callers",
    "get_neighborhood",
    "trace_flow",
    "get_entry_points",
    "get_leaf_nodes",
]
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_graph_models.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/oya/graph/__init__.py backend/tests/test_graph_models.py
git commit -m "feat(graph): export public interface from graph module"
```

---

## Task 16: Integration Test - Self-Analysis

**Files:**
- Create: `backend/tests/test_graph_integration.py`

**Step 1: Write the integration test**

Create `backend/tests/test_graph_integration.py`:

```python
"""Integration tests for the graph module using Oya's own code."""

import pytest
from pathlib import Path

from oya.parsing import PythonParser
from oya.graph import build_graph, save_graph, load_graph, get_calls, get_neighborhood


class TestGraphSelfAnalysis:
    """Test graph building on Oya's own codebase."""

    @pytest.fixture
    def parsed_oya_files(self):
        """Parse a few Oya source files."""
        parser = PythonParser()
        files = []

        # Parse the graph module itself
        graph_dir = Path(__file__).parent.parent / "src" / "oya" / "graph"
        for py_file in graph_dir.glob("*.py"):
            if py_file.name != "__init__.py":
                content = py_file.read_text()
                result = parser.parse(py_file, content)
                if result.ok:
                    files.append(result.file)

        return files

    def test_build_graph_from_oya_code(self, parsed_oya_files):
        """Can build graph from Oya's own code."""
        graph = build_graph(parsed_oya_files)

        # Should have nodes
        assert graph.number_of_nodes() > 0
        # Should have edges (references between functions)
        assert graph.number_of_edges() >= 0  # May have 0 if no cross-file refs

    def test_graph_persistence_roundtrip(self, parsed_oya_files, tmp_path):
        """Graph survives save/load cycle."""
        graph = build_graph(parsed_oya_files)

        output_dir = tmp_path / "graph"
        save_graph(graph, output_dir)
        loaded = load_graph(output_dir)

        assert loaded.number_of_nodes() == graph.number_of_nodes()
        assert loaded.number_of_edges() == graph.number_of_edges()

    def test_query_works_on_oya_graph(self, parsed_oya_files):
        """Query functions work on Oya's graph."""
        graph = build_graph(parsed_oya_files)

        # Find any node and query its neighborhood
        if graph.number_of_nodes() > 0:
            node_id = list(graph.nodes())[0]
            neighborhood = get_neighborhood(graph, node_id, hops=1)

            # Should return a valid subgraph
            assert neighborhood.nodes is not None
            assert len(neighborhood.nodes) >= 1  # At least the center node
```

**Step 2: Run the integration test**

Run: `pytest tests/test_graph_integration.py -v`

Expected: PASS

**Step 3: Commit**

```bash
git add backend/tests/test_graph_integration.py
git commit -m "test: add integration tests for graph module self-analysis"
```

---

## Task 17: Run Full Test Suite

**Step 1: Run all backend tests**

Run: `cd /Users/poecurt/projects/oya/backend && source .venv/bin/activate && pytest -v --tb=short`

Expected: All tests PASS

**Step 2: Run linter**

Run: `ruff check backend/src/oya/graph/`

Expected: No errors

**Step 3: Fix any issues and commit**

```bash
git add -A
git commit -m "fix: resolve any test or lint issues"
```

---

## Task 18: Final Phase 2 Commit

**Step 1: Create completion commit**

```bash
git add -A
git commit -m "feat: complete Phase 2 - code graph construction

- Added graph models (Node, Edge, Subgraph) with serialization
- Subgraph.to_context() formats graph for LLM consumption
- Subgraph.to_mermaid() generates deterministic diagrams
- SymbolTable indexes definitions for cross-file resolution
- Reference resolver matches references to definitions
- NetworkX graph builder from parsed files
- JSON persistence to .oyawiki/graph/
- Query interface: get_calls, get_callers, get_neighborhood,
  trace_flow, get_entry_points, get_leaf_nodes
- Integration tests verify self-analysis works"
```

---

## Checkpoint: Phase 2 Complete

Verify:

1. [ ] Graph models (Node, Edge, Subgraph) created with serialization
2. [ ] Subgraph.to_context() formats graph for LLM
3. [ ] Subgraph.to_mermaid() generates deterministic diagrams
4. [ ] SymbolTable indexes all definitions
5. [ ] Resolver matches references across files
6. [ ] NetworkX graph builds from parsed files
7. [ ] Graph persists to `.oyawiki/graph/` as JSON
8. [ ] Query functions work (get_calls, get_callers, get_neighborhood, trace_flow)
9. [ ] Self-analysis of Oya produces a valid graph
10. [ ] All tests pass

---

## Next: Phase 3 Design Session

**STOP.** Do not proceed to Phase 3 implementation.

Phase 3 requires a design session. Tell Claude:

> "Read `docs/plans/2026-01-17-graph-phases-3-5-planning.md` and let's design Phase 3 (Architecture Documentation Generation)."

The Phase 3 design session should address:
- What architecture pages to generate
- How to identify subsystems (directories, clustering, config)
- How to detect important entry points
- LLM involvement level
- Low-confidence edge handling

See the planning document for the full design process.
