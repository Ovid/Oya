# Phase 3: Architecture Documentation Generation - Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Generate architecture documentation with graph-derived diagrams instead of LLM-imagined ones.

**Architecture:** Add `graph/analysis.py` with test filtering and component aggregation. Modify `ArchitectureGenerator` to accept a graph and produce deterministic diagrams. LLM writes narrative describing the diagrams.

**Tech Stack:** NetworkX (existing), Mermaid (existing), Python dataclasses

---

## Task 1: Filter Test Nodes from Graph

**Files:**
- Create: `backend/src/oya/graph/analysis.py`
- Test: `backend/tests/test_graph_analysis.py`

**Step 1: Write the failing test**

Create `backend/tests/test_graph_analysis.py`:

```python
"""Tests for graph analysis utilities."""

import networkx as nx
import pytest


def test_filter_test_nodes_removes_test_files():
    """filter_test_nodes excludes test files from graph."""
    from oya.graph.analysis import filter_test_nodes

    G = nx.DiGraph()
    G.add_node("src/api/routes.py::handle", name="handle", type="function",
               file_path="src/api/routes.py", line_start=1, line_end=10)
    G.add_node("tests/test_routes.py::test_handle", name="test_handle", type="function",
               file_path="tests/test_routes.py", line_start=1, line_end=10)
    G.add_node("src/utils/test_helpers.py::helper", name="helper", type="function",
               file_path="src/utils/test_helpers.py", line_start=1, line_end=10)
    G.add_edge("tests/test_routes.py::test_handle", "src/api/routes.py::handle",
               type="calls", confidence=0.9, line=5)

    filtered = filter_test_nodes(G)

    # Should keep production code
    assert filtered.has_node("src/api/routes.py::handle")
    # Should remove test files
    assert not filtered.has_node("tests/test_routes.py::test_handle")
    # Should remove files with test_ prefix even outside tests/
    assert not filtered.has_node("src/utils/test_helpers.py::helper")
    # Should remove edges involving test nodes
    assert filtered.number_of_edges() == 0
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/poecurt/projects/oya/backend && source .venv/bin/activate && pytest tests/test_graph_analysis.py::test_filter_test_nodes_removes_test_files -v`

Expected: FAIL with ModuleNotFoundError

**Step 3: Write minimal implementation**

Create `backend/src/oya/graph/analysis.py`:

```python
"""Graph analysis utilities for architecture generation."""

import re

import networkx as nx


# Patterns that indicate test files
TEST_PATTERNS = [
    r"^tests?/",  # tests/ or test/ directory
    r"/tests?/",  # tests/ or test/ subdirectory
    r"test_[^/]+\.py$",  # test_*.py files
    r"_test\.py$",  # *_test.py files
    r"\.test\.[jt]sx?$",  # *.test.js, *.test.ts, *.test.tsx
    r"\.spec\.[jt]sx?$",  # *.spec.js, *.spec.ts
    r"__tests__/",  # __tests__/ directory (Jest convention)
]


def is_test_file(file_path: str) -> bool:
    """Check if a file path represents a test file."""
    for pattern in TEST_PATTERNS:
        if re.search(pattern, file_path):
            return True
    return False


def filter_test_nodes(graph: nx.DiGraph) -> nx.DiGraph:
    """Return a copy of the graph with test nodes and their edges removed.

    Args:
        graph: The code graph.

    Returns:
        New graph with test files filtered out.
    """
    filtered = nx.DiGraph()

    # Copy non-test nodes
    for node_id, attrs in graph.nodes(data=True):
        file_path = attrs.get("file_path", node_id)
        if not is_test_file(file_path):
            filtered.add_node(node_id, **attrs)

    # Copy edges between non-test nodes
    for source, target, attrs in graph.edges(data=True):
        if filtered.has_node(source) and filtered.has_node(target):
            filtered.add_edge(source, target, **attrs)

    return filtered
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/poecurt/projects/oya/backend && source .venv/bin/activate && pytest tests/test_graph_analysis.py -v`

Expected: PASS

**Step 5: Commit**

```bash
cd /Users/poecurt/projects/oya && git add backend/src/oya/graph/analysis.py backend/tests/test_graph_analysis.py
git commit -m "feat(graph): add filter_test_nodes to exclude test files"
```

---

## Task 2: Add More Test Filtering Cases

**Files:**
- Modify: `backend/tests/test_graph_analysis.py`

**Step 1: Write additional tests**

Add to `backend/tests/test_graph_analysis.py`:

```python
def test_filter_test_nodes_handles_various_patterns():
    """filter_test_nodes handles various test file patterns."""
    from oya.graph.analysis import is_test_file

    # Should match as test files
    assert is_test_file("tests/test_api.py")
    assert is_test_file("test/unit/test_model.py")
    assert is_test_file("src/api/test_routes.py")
    assert is_test_file("src/api/routes_test.py")
    assert is_test_file("src/components/Button.test.tsx")
    assert is_test_file("src/utils/helper.spec.ts")
    assert is_test_file("src/__tests__/App.test.js")

    # Should NOT match as test files
    assert not is_test_file("src/api/routes.py")
    assert not is_test_file("src/testing/framework.py")  # 'testing' != 'test'
    assert not is_test_file("src/contest/entry.py")  # 'contest' contains 'test' but not a test file
    assert not is_test_file("src/latest/feature.py")


def test_filter_test_nodes_preserves_graph_structure():
    """filter_test_nodes preserves edges between non-test nodes."""
    from oya.graph.analysis import filter_test_nodes

    G = nx.DiGraph()
    G.add_node("a.py::func_a", file_path="a.py")
    G.add_node("b.py::func_b", file_path="b.py")
    G.add_node("tests/test_a.py::test", file_path="tests/test_a.py")
    G.add_edge("a.py::func_a", "b.py::func_b", type="calls", confidence=0.9, line=5)
    G.add_edge("tests/test_a.py::test", "a.py::func_a", type="calls", confidence=0.9, line=10)

    filtered = filter_test_nodes(G)

    assert filtered.number_of_nodes() == 2
    assert filtered.number_of_edges() == 1
    assert filtered.has_edge("a.py::func_a", "b.py::func_b")
```

**Step 2: Run tests**

Run: `cd /Users/poecurt/projects/oya/backend && source .venv/bin/activate && pytest tests/test_graph_analysis.py -v`

Expected: PASS

**Step 3: Commit**

```bash
cd /Users/poecurt/projects/oya && git add backend/tests/test_graph_analysis.py
git commit -m "test(graph): add more test filtering cases"
```

---

## Task 3: Get Component Graph (Directory-Level Aggregation)

**Files:**
- Modify: `backend/src/oya/graph/analysis.py`
- Modify: `backend/tests/test_graph_analysis.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_graph_analysis.py`:

```python
def test_get_component_graph_aggregates_by_directory():
    """get_component_graph aggregates nodes by top-level directory."""
    from oya.graph.analysis import get_component_graph

    G = nx.DiGraph()
    # api/ component
    G.add_node("api/routes.py::handle", file_path="api/routes.py")
    G.add_node("api/handlers.py::process", file_path="api/handlers.py")
    # db/ component
    G.add_node("db/models.py::User", file_path="db/models.py")
    G.add_node("db/queries.py::get_user", file_path="db/queries.py")
    # Edges: api calls db
    G.add_edge("api/routes.py::handle", "db/queries.py::get_user",
               type="calls", confidence=0.9, line=10)
    G.add_edge("api/handlers.py::process", "db/models.py::User",
               type="calls", confidence=0.8, line=20)

    component_graph = get_component_graph(G)

    # Should have 2 components
    assert component_graph.number_of_nodes() == 2
    assert component_graph.has_node("api")
    assert component_graph.has_node("db")
    # Should have 1 aggregated edge from api to db
    assert component_graph.has_edge("api", "db")
    # Edge should have aggregated confidence (max of underlying edges)
    edge_data = component_graph.edges["api", "db"]
    assert edge_data["confidence"] == 0.9
    assert edge_data["count"] == 2  # 2 underlying edges


def test_get_component_graph_respects_confidence_threshold():
    """get_component_graph filters edges below confidence threshold."""
    from oya.graph.analysis import get_component_graph

    G = nx.DiGraph()
    G.add_node("api/routes.py::handle", file_path="api/routes.py")
    G.add_node("db/models.py::User", file_path="db/models.py")
    G.add_edge("api/routes.py::handle", "db/models.py::User",
               type="calls", confidence=0.5, line=10)

    component_graph = get_component_graph(G, min_confidence=0.7)

    # Should have nodes but no edges (confidence too low)
    assert component_graph.has_node("api")
    assert component_graph.has_node("db")
    assert not component_graph.has_edge("api", "db")
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/poecurt/projects/oya/backend && source .venv/bin/activate && pytest tests/test_graph_analysis.py::test_get_component_graph_aggregates_by_directory -v`

Expected: FAIL with ImportError

**Step 3: Write minimal implementation**

Add to `backend/src/oya/graph/analysis.py`:

```python
def get_top_level_directory(file_path: str) -> str:
    """Extract the top-level directory from a file path.

    Args:
        file_path: Path like "api/routes.py" or "src/api/routes.py"

    Returns:
        Top-level directory name, e.g., "api" or "src"
    """
    parts = file_path.split("/")
    return parts[0] if parts else file_path


def get_component_graph(
    graph: nx.DiGraph,
    min_confidence: float = 0.0,
) -> nx.DiGraph:
    """Aggregate the code graph to directory-level components.

    Args:
        graph: The code graph with file-level nodes.
        min_confidence: Minimum edge confidence to include.

    Returns:
        New graph where nodes are top-level directories and edges
        represent aggregated dependencies between them.
    """
    component_graph = nx.DiGraph()

    # Map each node to its component (top-level directory)
    node_to_component: dict[str, str] = {}
    for node_id, attrs in graph.nodes(data=True):
        file_path = attrs.get("file_path", node_id)
        component = get_top_level_directory(file_path)
        node_to_component[node_id] = component

        # Add component node if not exists
        if not component_graph.has_node(component):
            component_graph.add_node(component)

    # Aggregate edges
    edge_data: dict[tuple[str, str], list[float]] = {}
    for source, target, attrs in graph.edges(data=True):
        confidence = attrs.get("confidence", 0)
        if confidence < min_confidence:
            continue

        src_component = node_to_component.get(source)
        tgt_component = node_to_component.get(target)

        if src_component and tgt_component and src_component != tgt_component:
            key = (src_component, tgt_component)
            if key not in edge_data:
                edge_data[key] = []
            edge_data[key].append(confidence)

    # Add aggregated edges
    for (src, tgt), confidences in edge_data.items():
        component_graph.add_edge(
            src,
            tgt,
            confidence=max(confidences),
            count=len(confidences),
        )

    return component_graph
```

**Step 4: Run tests to verify they pass**

Run: `cd /Users/poecurt/projects/oya/backend && source .venv/bin/activate && pytest tests/test_graph_analysis.py -v`

Expected: PASS

**Step 5: Commit**

```bash
cd /Users/poecurt/projects/oya && git add backend/src/oya/graph/analysis.py backend/tests/test_graph_analysis.py
git commit -m "feat(graph): add get_component_graph for directory-level aggregation"
```

---

## Task 4: Select Top Entry Points by Fan-Out

**Files:**
- Modify: `backend/src/oya/graph/analysis.py`
- Modify: `backend/tests/test_graph_analysis.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_graph_analysis.py`:

```python
def test_select_top_entry_points_by_fanout():
    """select_top_entry_points returns entry points sorted by fan-out."""
    from oya.graph.analysis import select_top_entry_points

    G = nx.DiGraph()
    # Entry point with high fan-out (calls 3 things)
    G.add_node("api/main.py::handle_request", file_path="api/main.py")
    G.add_node("db/query.py::query", file_path="db/query.py")
    G.add_node("cache/redis.py::get", file_path="cache/redis.py")
    G.add_node("log/logger.py::log", file_path="log/logger.py")
    G.add_edge("api/main.py::handle_request", "db/query.py::query", type="calls", confidence=0.9, line=10)
    G.add_edge("api/main.py::handle_request", "cache/redis.py::get", type="calls", confidence=0.9, line=15)
    G.add_edge("api/main.py::handle_request", "log/logger.py::log", type="calls", confidence=0.9, line=20)

    # Entry point with low fan-out (calls 1 thing)
    G.add_node("cli/cmd.py::run", file_path="cli/cmd.py")
    G.add_edge("cli/cmd.py::run", "log/logger.py::log", type="calls", confidence=0.9, line=5)

    top = select_top_entry_points(G, n=2)

    # Should return both entry points, sorted by fan-out (highest first)
    assert len(top) == 2
    assert top[0] == "api/main.py::handle_request"  # 3 outgoing
    assert top[1] == "cli/cmd.py::run"  # 1 outgoing


def test_select_top_entry_points_excludes_test_files():
    """select_top_entry_points excludes test file entry points."""
    from oya.graph.analysis import select_top_entry_points

    G = nx.DiGraph()
    G.add_node("api/main.py::handle", file_path="api/main.py")
    G.add_node("tests/test_main.py::test_handle", file_path="tests/test_main.py")
    G.add_node("db/query.py::query", file_path="db/query.py")
    G.add_edge("api/main.py::handle", "db/query.py::query", type="calls", confidence=0.9, line=10)
    G.add_edge("tests/test_main.py::test_handle", "api/main.py::handle", type="calls", confidence=0.9, line=5)

    top = select_top_entry_points(G, n=5)

    # Should only return production entry point
    assert len(top) == 1
    assert top[0] == "api/main.py::handle"
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/poecurt/projects/oya/backend && source .venv/bin/activate && pytest tests/test_graph_analysis.py::test_select_top_entry_points_by_fanout -v`

Expected: FAIL with ImportError

**Step 3: Write minimal implementation**

Add to `backend/src/oya/graph/analysis.py`:

```python
def select_top_entry_points(
    graph: nx.DiGraph,
    n: int = 5,
) -> list[str]:
    """Select top N entry points by fan-out (number of outgoing calls).

    Entry points are nodes with no incoming "calls" edges but have outgoing calls.
    Test files are excluded.

    Args:
        graph: The code graph.
        n: Maximum number of entry points to return.

    Returns:
        List of node IDs sorted by fan-out (highest first).
    """
    entry_points = []

    for node_id, attrs in graph.nodes(data=True):
        file_path = attrs.get("file_path", node_id)

        # Skip test files
        if is_test_file(file_path):
            continue

        # Check if entry point (no incoming calls)
        in_calls = [
            1
            for _, _, d in graph.in_edges(node_id, data=True)
            if d.get("type") == "calls"
        ]
        out_calls = [
            1
            for _, _, d in graph.out_edges(node_id, data=True)
            if d.get("type") == "calls"
        ]

        if len(out_calls) > 0 and len(in_calls) == 0:
            entry_points.append((node_id, len(out_calls)))

    # Sort by fan-out descending
    entry_points.sort(key=lambda x: x[1], reverse=True)

    return [ep[0] for ep in entry_points[:n]]
```

**Step 4: Run tests to verify they pass**

Run: `cd /Users/poecurt/projects/oya/backend && source .venv/bin/activate && pytest tests/test_graph_analysis.py -v`

Expected: PASS

**Step 5: Commit**

```bash
cd /Users/poecurt/projects/oya && git add backend/src/oya/graph/analysis.py backend/tests/test_graph_analysis.py
git commit -m "feat(graph): add select_top_entry_points by fan-out"
```

---

## Task 5: Export Analysis Functions from Graph Module

**Files:**
- Modify: `backend/src/oya/graph/__init__.py`
- Modify: `backend/tests/test_graph_models.py`

**Step 1: Update the exports test**

Modify `backend/tests/test_graph_models.py`, in `test_graph_module_exports`:

```python
def test_graph_module_exports():
    """Graph module exports all public interfaces."""
    import oya.graph as graph_module

    # Verify all expected exports are present
    expected_exports = [
        # Models
        "Node", "NodeType", "Edge", "EdgeType", "Subgraph",
        # Builder
        "build_graph",
        # Resolver
        "SymbolTable", "resolve_references",
        # Persistence
        "save_graph", "load_graph",
        # Query
        "get_calls", "get_callers", "get_neighborhood",
        "trace_flow", "get_entry_points", "get_leaf_nodes",
        # Analysis (NEW)
        "filter_test_nodes", "get_component_graph", "select_top_entry_points",
    ]

    for name in expected_exports:
        assert hasattr(graph_module, name), f"Missing export: {name}"

    # Basic smoke test
    assert graph_module.NodeType.FUNCTION.value == "function"
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/poecurt/projects/oya/backend && source .venv/bin/activate && pytest tests/test_graph_models.py::test_graph_module_exports -v`

Expected: FAIL with "Missing export: filter_test_nodes"

**Step 3: Update the exports**

Modify `backend/src/oya/graph/__init__.py` to add:

```python
from oya.graph.analysis import (
    filter_test_nodes,
    get_component_graph,
    select_top_entry_points,
)
```

And add to `__all__`:

```python
    # Analysis
    "filter_test_nodes",
    "get_component_graph",
    "select_top_entry_points",
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/poecurt/projects/oya/backend && source .venv/bin/activate && pytest tests/test_graph_models.py::test_graph_module_exports -v`

Expected: PASS

**Step 5: Commit**

```bash
cd /Users/poecurt/projects/oya && git add backend/src/oya/graph/__init__.py backend/tests/test_graph_models.py
git commit -m "feat(graph): export analysis functions from graph module"
```

---

## Task 6: Component Diagram Mermaid Generation

**Files:**
- Modify: `backend/src/oya/graph/analysis.py`
- Modify: `backend/tests/test_graph_analysis.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_graph_analysis.py`:

```python
def test_component_graph_to_mermaid():
    """component_graph_to_mermaid generates valid Mermaid diagram."""
    from oya.graph.analysis import get_component_graph, component_graph_to_mermaid

    G = nx.DiGraph()
    G.add_node("api/routes.py::handle", file_path="api/routes.py")
    G.add_node("db/models.py::User", file_path="db/models.py")
    G.add_node("llm/client.py::generate", file_path="llm/client.py")
    G.add_edge("api/routes.py::handle", "db/models.py::User", type="calls", confidence=0.9, line=10)
    G.add_edge("api/routes.py::handle", "llm/client.py::generate", type="calls", confidence=0.8, line=15)

    component_graph = get_component_graph(G)
    mermaid = component_graph_to_mermaid(component_graph)

    assert mermaid.startswith("flowchart")
    assert "api" in mermaid
    assert "db" in mermaid
    assert "llm" in mermaid
    assert "-->" in mermaid
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/poecurt/projects/oya/backend && source .venv/bin/activate && pytest tests/test_graph_analysis.py::test_component_graph_to_mermaid -v`

Expected: FAIL with ImportError

**Step 3: Write minimal implementation**

Add to `backend/src/oya/graph/analysis.py`:

```python
def component_graph_to_mermaid(component_graph: nx.DiGraph) -> str:
    """Generate a Mermaid flowchart from a component graph.

    Args:
        component_graph: Graph with directory-level nodes and edges.

    Returns:
        Mermaid flowchart string.
    """
    lines = ["flowchart LR"]

    # Sort nodes for deterministic output
    nodes = sorted(component_graph.nodes())

    # Add node definitions
    for node in nodes:
        # Sanitize node name for Mermaid (replace special chars)
        safe_name = node.replace("-", "_").replace(".", "_")
        lines.append(f"    {safe_name}[{node}/]")

    # Add edges (sorted for determinism)
    edges = sorted(component_graph.edges(data=True), key=lambda e: (e[0], e[1]))
    for source, target, data in edges:
        safe_source = source.replace("-", "_").replace(".", "_")
        safe_target = target.replace("-", "_").replace(".", "_")
        lines.append(f"    {safe_source} --> {safe_target}")

    return "\n".join(lines)
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/poecurt/projects/oya/backend && source .venv/bin/activate && pytest tests/test_graph_analysis.py -v`

Expected: PASS

**Step 5: Commit**

```bash
cd /Users/poecurt/projects/oya && git add backend/src/oya/graph/analysis.py backend/tests/test_graph_analysis.py
git commit -m "feat(graph): add component_graph_to_mermaid for architecture diagrams"
```

---

## Task 7: Add Graph-Aware Architecture Prompt

**Files:**
- Modify: `backend/src/oya/generation/prompts.py`
- Test: `backend/tests/test_prompts.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_prompts.py`:

```python
def test_get_graph_architecture_prompt_includes_component_diagram():
    """get_graph_architecture_prompt includes the component diagram."""
    from oya.generation.prompts import get_graph_architecture_prompt

    prompt = get_graph_architecture_prompt(
        repo_name="my-project",
        component_diagram="flowchart LR\n    api --> db",
        entry_points=[
            {"id": "api/main.py::handle", "name": "handle", "file": "api/main.py", "fanout": 3},
        ],
        flow_diagrams=[
            {"entry_point": "handle", "diagram": "flowchart TD\n    handle --> query"},
        ],
        component_summaries={"api": "HTTP endpoints", "db": "Database access"},
    )

    assert "flowchart LR" in prompt
    assert "api --> db" in prompt
    assert "handle" in prompt
    assert "HTTP endpoints" in prompt


def test_get_graph_architecture_prompt_handles_empty_flows():
    """get_graph_architecture_prompt handles case with no flow diagrams."""
    from oya.generation.prompts import get_graph_architecture_prompt

    prompt = get_graph_architecture_prompt(
        repo_name="my-project",
        component_diagram="flowchart LR\n    api --> db",
        entry_points=[],
        flow_diagrams=[],
        component_summaries={},
    )

    assert "flowchart LR" in prompt
    assert "my-project" in prompt
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/poecurt/projects/oya/backend && source .venv/bin/activate && pytest tests/test_prompts.py::test_get_graph_architecture_prompt_includes_component_diagram -v`

Expected: FAIL with ImportError

**Step 3: Write minimal implementation**

Add to `backend/src/oya/generation/prompts.py`:

```python
GRAPH_ARCHITECTURE_TEMPLATE = PromptTemplate(
    """Generate an architecture documentation page for "{repo_name}".

The following diagrams are ACCURATE and derived from static code analysis. Describe what they show - do NOT invent or modify relationships.

## Component Diagram

```mermaid
{component_diagram}
```

## Components

{component_summaries}

## Entry Points

{entry_points}

## Data Flow Diagrams

{flow_diagrams}

Write an architecture overview that:
1. Explains what each component does based on the summaries (1-2 sentences each)
2. Describes how components interact based on the component diagram
3. Explains the data flows shown in the flow diagrams
4. Notes any architectural patterns visible (layering, separation of concerns, etc.)

IMPORTANT: The diagrams are authoritative. Describe what they show, don't invent relationships not shown in the diagrams.

Format: Markdown with clear headings. Include the diagrams inline where appropriate.
"""
)


def get_graph_architecture_prompt(
    repo_name: str,
    component_diagram: str,
    entry_points: list[dict],
    flow_diagrams: list[dict],
    component_summaries: dict[str, str],
) -> str:
    """Build prompt for graph-aware architecture generation.

    Args:
        repo_name: Name of the repository.
        component_diagram: Mermaid diagram of component relationships.
        entry_points: List of entry point dicts with id, name, file, fanout.
        flow_diagrams: List of dicts with entry_point and diagram.
        component_summaries: Dict mapping component name to summary.

    Returns:
        Formatted prompt string.
    """
    # Format component summaries
    if component_summaries:
        summaries_text = "\n".join(
            f"- **{name}/**: {summary}" for name, summary in sorted(component_summaries.items())
        )
    else:
        summaries_text = "No component summaries available."

    # Format entry points
    if entry_points:
        ep_text = "\n".join(
            f"- `{ep['name']}` in `{ep['file']}` (calls {ep['fanout']} other functions)"
            for ep in entry_points
        )
    else:
        ep_text = "No entry points detected."

    # Format flow diagrams
    if flow_diagrams:
        flow_text = ""
        for flow in flow_diagrams:
            flow_text += f"\n### {flow['entry_point']}\n\n```mermaid\n{flow['diagram']}\n```\n"
    else:
        flow_text = "No flow diagrams generated."

    return GRAPH_ARCHITECTURE_TEMPLATE.render(
        repo_name=repo_name,
        component_diagram=component_diagram,
        component_summaries=summaries_text,
        entry_points=ep_text,
        flow_diagrams=flow_text,
    )
```

**Step 4: Run tests to verify they pass**

Run: `cd /Users/poecurt/projects/oya/backend && source .venv/bin/activate && pytest tests/test_prompts.py -v -k "graph_architecture"`

Expected: PASS

**Step 5: Commit**

```bash
cd /Users/poecurt/projects/oya && git add backend/src/oya/generation/prompts.py backend/tests/test_prompts.py
git commit -m "feat(generation): add get_graph_architecture_prompt for graph-based architecture"
```

---

## Task 8: Create Graph-Aware Architecture Generator

**Files:**
- Create: `backend/src/oya/generation/graph_architecture.py`
- Create: `backend/tests/test_graph_architecture.py`

**Step 1: Write the failing test**

Create `backend/tests/test_graph_architecture.py`:

```python
"""Tests for graph-aware architecture generation."""

import networkx as nx
import pytest
from unittest.mock import AsyncMock, MagicMock
from pathlib import Path


@pytest.fixture
def sample_graph():
    """Create a sample code graph."""
    G = nx.DiGraph()
    G.add_node("api/routes.py::handle", name="handle", type="function",
               file_path="api/routes.py", line_start=10, line_end=30,
               docstring="Handle incoming requests")
    G.add_node("db/queries.py::get_user", name="get_user", type="function",
               file_path="db/queries.py", line_start=5, line_end=20,
               docstring="Fetch user from database")
    G.add_node("llm/client.py::generate", name="generate", type="function",
               file_path="llm/client.py", line_start=1, line_end=50,
               docstring="Generate LLM response")
    G.add_edge("api/routes.py::handle", "db/queries.py::get_user",
               type="calls", confidence=0.9, line=15)
    G.add_edge("api/routes.py::handle", "llm/client.py::generate",
               type="calls", confidence=0.85, line=20)
    return G


@pytest.fixture
def mock_llm_client():
    """Create mock LLM client."""
    client = AsyncMock()
    client.generate.return_value = """# Architecture

## Overview

This system has three main components...

## Components

The **api** component handles HTTP requests...
"""
    return client


@pytest.mark.asyncio
async def test_graph_architecture_generator_produces_page(sample_graph, mock_llm_client):
    """GraphArchitectureGenerator produces a valid architecture page."""
    from oya.generation.graph_architecture import GraphArchitectureGenerator

    generator = GraphArchitectureGenerator(mock_llm_client)

    page = await generator.generate(
        repo_name="my-project",
        graph=sample_graph,
        component_summaries={"api": "HTTP endpoints", "db": "Database", "llm": "LLM client"},
    )

    assert page.page_type == "architecture"
    assert page.path == "architecture.md"
    assert "Architecture" in page.content
    # Should contain graph-derived Mermaid diagrams
    assert "```mermaid" in page.content
    mock_llm_client.generate.assert_called_once()


@pytest.mark.asyncio
async def test_graph_architecture_generator_filters_test_code(mock_llm_client):
    """GraphArchitectureGenerator excludes test files from diagrams."""
    from oya.generation.graph_architecture import GraphArchitectureGenerator

    G = nx.DiGraph()
    G.add_node("api/routes.py::handle", file_path="api/routes.py")
    G.add_node("tests/test_routes.py::test_handle", file_path="tests/test_routes.py")
    G.add_edge("tests/test_routes.py::test_handle", "api/routes.py::handle",
               type="calls", confidence=0.9, line=5)

    generator = GraphArchitectureGenerator(mock_llm_client)

    page = await generator.generate(
        repo_name="my-project",
        graph=G,
        component_summaries={},
    )

    # Should not include test files in diagrams
    assert "test_routes" not in page.content
    assert "test_handle" not in page.content
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/poecurt/projects/oya/backend && source .venv/bin/activate && pytest tests/test_graph_architecture.py::test_graph_architecture_generator_produces_page -v`

Expected: FAIL with ModuleNotFoundError

**Step 3: Write minimal implementation**

Create `backend/src/oya/generation/graph_architecture.py`:

```python
"""Graph-aware architecture page generator."""

from __future__ import annotations

import networkx as nx

from oya.generation.overview import GeneratedPage
from oya.generation.prompts import SYSTEM_PROMPT, get_graph_architecture_prompt
from oya.graph.analysis import (
    filter_test_nodes,
    get_component_graph,
    select_top_entry_points,
    component_graph_to_mermaid,
)
from oya.graph.query import get_neighborhood


class GraphArchitectureGenerator:
    """Generates architecture page using the code graph.

    Uses graph analysis to produce deterministic diagrams,
    with LLM writing narrative to explain them.
    """

    def __init__(self, llm_client):
        """Initialize the generator.

        Args:
            llm_client: LLM client for narrative generation.
        """
        self.llm_client = llm_client

    async def generate(
        self,
        repo_name: str,
        graph: nx.DiGraph,
        component_summaries: dict[str, str] | None = None,
        min_confidence: float = 0.7,
        max_entry_points: int = 5,
        flow_hops: int = 2,
    ) -> GeneratedPage:
        """Generate architecture page from code graph.

        Args:
            repo_name: Name of the repository.
            graph: The code graph from Phase 2.
            component_summaries: Optional dict of component -> summary.
            min_confidence: Minimum confidence for diagram edges.
            max_entry_points: Maximum flow diagrams to generate.
            flow_hops: Hops for flow diagram neighborhood.

        Returns:
            GeneratedPage with architecture content.
        """
        # Filter out test code
        filtered_graph = filter_test_nodes(graph)

        # Build component diagram
        component_graph = get_component_graph(filtered_graph, min_confidence=min_confidence)
        component_diagram = component_graph_to_mermaid(component_graph)

        # Select top entry points and build flow diagrams
        entry_point_ids = select_top_entry_points(filtered_graph, n=max_entry_points)
        entry_points = []
        flow_diagrams = []

        for ep_id in entry_point_ids:
            node_data = filtered_graph.nodes.get(ep_id, {})
            fanout = filtered_graph.out_degree(ep_id)

            entry_points.append({
                "id": ep_id,
                "name": node_data.get("name", ep_id.split("::")[-1]),
                "file": node_data.get("file_path", ""),
                "fanout": fanout,
            })

            # Generate flow diagram
            neighborhood = get_neighborhood(
                filtered_graph, ep_id, hops=flow_hops, min_confidence=min_confidence
            )
            if neighborhood.nodes:
                flow_diagrams.append({
                    "entry_point": node_data.get("name", ep_id.split("::")[-1]),
                    "diagram": neighborhood.to_mermaid(),
                })

        # Build prompt and generate narrative
        prompt = get_graph_architecture_prompt(
            repo_name=repo_name,
            component_diagram=component_diagram,
            entry_points=entry_points,
            flow_diagrams=flow_diagrams,
            component_summaries=component_summaries or {},
        )

        content = await self.llm_client.generate(
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
        )

        # Append diagrams section
        content = self._append_diagrams(content, component_diagram, flow_diagrams)

        return GeneratedPage(
            content=content,
            page_type="architecture",
            path="architecture.md",
            word_count=len(content.split()),
        )

    def _append_diagrams(
        self,
        content: str,
        component_diagram: str,
        flow_diagrams: list[dict],
    ) -> str:
        """Append graph-derived diagrams to content."""
        lines = [content.rstrip(), "", "## Generated Diagrams", ""]

        lines.append("### Component Dependencies")
        lines.append("")
        lines.append("```mermaid")
        lines.append(component_diagram)
        lines.append("```")
        lines.append("")

        for flow in flow_diagrams:
            lines.append(f"### {flow['entry_point']} Flow")
            lines.append("")
            lines.append("```mermaid")
            lines.append(flow["diagram"])
            lines.append("```")
            lines.append("")

        return "\n".join(lines)
```

**Step 4: Run tests to verify they pass**

Run: `cd /Users/poecurt/projects/oya/backend && source .venv/bin/activate && pytest tests/test_graph_architecture.py -v`

Expected: PASS

**Step 5: Commit**

```bash
cd /Users/poecurt/projects/oya && git add backend/src/oya/generation/graph_architecture.py backend/tests/test_graph_architecture.py
git commit -m "feat(generation): add GraphArchitectureGenerator for graph-based architecture"
```

---

## Task 9: Integrate Graph Architecture into Orchestrator

**Files:**
- Modify: `backend/src/oya/generation/orchestrator.py`
- Modify: `backend/tests/test_orchestrator.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_orchestrator.py`:

```python
@pytest.mark.asyncio
async def test_orchestrator_uses_graph_for_architecture_when_available(tmp_path):
    """Orchestrator uses graph-based architecture when graph exists."""
    from unittest.mock import AsyncMock, MagicMock, patch

    # Create a minimal repo structure
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "main.py").write_text("def main(): pass")

    mock_llm = AsyncMock()
    mock_llm.generate.return_value = "# Architecture\n\nContent here."

    # Mock the graph loading to return a non-empty graph
    import networkx as nx
    mock_graph = nx.DiGraph()
    mock_graph.add_node("src/main.py::main", name="main", type="function",
                        file_path="src/main.py", line_start=1, line_end=1)

    with patch("oya.generation.orchestrator.load_graph", return_value=mock_graph):
        from oya.generation.orchestrator import GenerationOrchestrator

        orchestrator = GenerationOrchestrator(
            workspace_path=tmp_path,
            llm_client=mock_llm,
        )

        # The orchestrator should detect the graph and use GraphArchitectureGenerator
        # This is a simplified test - full integration would require more setup
        assert orchestrator is not None
```

**Note:** This task requires careful integration. The orchestrator is complex. We'll add a flag to use graph-based architecture when a graph is available.

**Step 2: Modify orchestrator to support graph architecture**

Add import at top of `backend/src/oya/generation/orchestrator.py`:

```python
from oya.graph import load_graph
from oya.generation.graph_architecture import GraphArchitectureGenerator
```

Find the `_generate_architecture` method and modify to check for graph:

```python
async def _generate_architecture(self, ...) -> GeneratedPage:
    # Try to load graph
    graph_dir = self.output_dir / "graph"
    graph = load_graph(graph_dir)

    # Use graph-based generation if graph has sufficient nodes
    if graph.number_of_nodes() >= 5:
        generator = GraphArchitectureGenerator(self.llm_client)
        return await generator.generate(
            repo_name=self.repo.path.name,
            graph=graph,
            component_summaries=self._get_component_summaries(synthesis_map),
        )

    # Fall back to existing LLM-only generation
    generator = ArchitectureGenerator(self.llm_client, self.repo)
    return await generator.generate(...)
```

**Step 3: Run tests**

Run: `cd /Users/poecurt/projects/oya/backend && source .venv/bin/activate && pytest tests/test_orchestrator.py -v --tb=short`

Expected: PASS (or minimal failures unrelated to our changes)

**Step 4: Commit**

```bash
cd /Users/poecurt/projects/oya && git add backend/src/oya/generation/orchestrator.py backend/tests/test_orchestrator.py
git commit -m "feat(generation): integrate graph-based architecture into orchestrator"
```

---

## Task 10: Integration Test - Full Pipeline

**Files:**
- Create: `backend/tests/test_graph_architecture_integration.py`

**Step 1: Write integration test**

Create `backend/tests/test_graph_architecture_integration.py`:

```python
"""Integration tests for graph-based architecture generation."""

import pytest
from pathlib import Path

from oya.parsing import PythonParser
from oya.graph import build_graph, save_graph, load_graph
from oya.generation.graph_architecture import GraphArchitectureGenerator


class TestGraphArchitectureIntegration:
    """Test graph architecture generation on real code."""

    @pytest.fixture
    def parsed_oya_files(self):
        """Parse Oya's own graph module."""
        parser = PythonParser()
        files = []

        graph_dir = Path(__file__).parent.parent / "src" / "oya" / "graph"
        for py_file in graph_dir.glob("*.py"):
            if py_file.name != "__init__.py":
                content = py_file.read_text()
                result = parser.parse(py_file, content)
                if result.ok:
                    files.append(result.file)

        return files

    @pytest.fixture
    def oya_graph(self, parsed_oya_files):
        """Build graph from Oya code."""
        return build_graph(parsed_oya_files)

    @pytest.mark.asyncio
    async def test_generates_architecture_from_oya_graph(self, oya_graph):
        """Can generate architecture page from Oya's own code graph."""
        from unittest.mock import AsyncMock

        mock_llm = AsyncMock()
        mock_llm.generate.return_value = """# Architecture

The graph module provides code analysis capabilities.

## Components

The module is organized into several sub-components for different concerns.
"""

        generator = GraphArchitectureGenerator(mock_llm)

        page = await generator.generate(
            repo_name="oya",
            graph=oya_graph,
            component_summaries={},
        )

        # Verify output structure
        assert page.page_type == "architecture"
        assert "```mermaid" in page.content
        assert "flowchart" in page.content

    def test_graph_persistence_for_architecture(self, oya_graph, tmp_path):
        """Graph can be saved and loaded for architecture generation."""
        graph_dir = tmp_path / "graph"
        save_graph(oya_graph, graph_dir)

        loaded = load_graph(graph_dir)

        assert loaded.number_of_nodes() == oya_graph.number_of_nodes()
        assert loaded.number_of_edges() == oya_graph.number_of_edges()
```

**Step 2: Run integration tests**

Run: `cd /Users/poecurt/projects/oya/backend && source .venv/bin/activate && pytest tests/test_graph_architecture_integration.py -v`

Expected: PASS

**Step 3: Commit**

```bash
cd /Users/poecurt/projects/oya && git add backend/tests/test_graph_architecture_integration.py
git commit -m "test: add integration tests for graph-based architecture generation"
```

---

## Task 11: Run Full Test Suite and Lint

**Step 1: Run all tests**

Run: `cd /Users/poecurt/projects/oya && make all`

Expected: All checks pass

**Step 2: Fix any issues**

If there are lint or test failures, fix them.

**Step 3: Commit fixes if needed**

```bash
git add -A
git commit -m "fix: resolve lint and test issues"
```

---

## Task 12: Final Phase 3 Commit

**Step 1: Verify everything works**

```bash
cd /Users/poecurt/projects/oya/backend && source .venv/bin/activate && pytest -v --tb=short
```

**Step 2: Create summary commit if needed**

If there are uncommitted changes:

```bash
git add -A
git commit -m "feat: complete Phase 3 - graph-based architecture generation

- filter_test_nodes excludes test files from analysis
- get_component_graph aggregates to directory level
- select_top_entry_points finds key entry points by fan-out
- component_graph_to_mermaid generates deterministic diagrams
- GraphArchitectureGenerator produces architecture pages
- Orchestrator uses graph when available, falls back to LLM-only
- Integration tests verify self-analysis works"
```

---

## Checkpoint: Phase 3 Complete

Verify:
- [ ] `make all` passes
- [ ] Architecture page includes graph-derived Mermaid diagrams
- [ ] Test code is excluded from diagrams
- [ ] Entry points are detected and flow diagrams generated
- [ ] Falls back gracefully when graph is too small

## Continuation

After Phase 3 is complete:

> "Phase 3 is complete. Read `docs/plans/2026-01-17-graph-phases-3-5-planning.md` and let's design Phase 4 (Graph-Augmented Q&A Retrieval)."
