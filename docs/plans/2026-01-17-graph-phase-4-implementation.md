# Phase 4: Graph-Augmented Q&A Retrieval - Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enhance Q&A retrieval by combining vector search with graph traversal to provide connected code context.

**Architecture:** Vector-first, graph-expand strategy. Vector search finds initial matches, then graph traversal (2 hops) finds connected code. Results are prioritized and formatted with a Mermaid diagram + code snippets.

**Tech Stack:** Python 3.11+, NetworkX (existing graph), ChromaDB (existing vector store), pytest

---

## Task 1: Add Graph Expansion Constants

**Files:**
- Modify: `backend/src/oya/constants/qa.py`
- Test: `backend/tests/test_constants.py` (verify imports work)

**Step 1: Add the new constants**

Add these constants to `backend/src/oya/constants/qa.py` at the end of the file:

```python
# =============================================================================
# Graph Expansion (Phase 4)
# =============================================================================
# When graph data is available, Q&A retrieval can expand vector search results
# by traversing the code graph to find connected code. This provides structural
# context that pure vector search misses.

GRAPH_EXPANSION_HOPS = 2
GRAPH_EXPANSION_CONFIDENCE_THRESHOLD = 0.5
GRAPH_MERMAID_TOKEN_BUDGET = 500
```

**Step 2: Verify the constants are importable**

Run: `cd /Users/poecurt/projects/oya/backend && python -c "from oya.constants.qa import GRAPH_EXPANSION_HOPS, GRAPH_EXPANSION_CONFIDENCE_THRESHOLD, GRAPH_MERMAID_TOKEN_BUDGET; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add backend/src/oya/constants/qa.py
git commit -m "feat(qa): add graph expansion constants for Phase 4"
```

---

## Task 2: Create Graph Retrieval Module - expand_with_graph

**Files:**
- Create: `backend/src/oya/qa/graph_retrieval.py`
- Create: `backend/tests/test_graph_retrieval.py`

**Step 1: Write the failing test**

Create `backend/tests/test_graph_retrieval.py`:

```python
"""Tests for graph-augmented Q&A retrieval."""

import networkx as nx
import pytest

from oya.graph.models import Subgraph


def _make_test_graph() -> nx.DiGraph:
    """Create a test graph with known structure.

    Structure:
        login -> verify_token -> get_user -> db_query
                      |
                      v
                 save_session
    """
    G = nx.DiGraph()

    # Add nodes
    nodes = [
        ("auth/handler.py::login", {"name": "login", "type": "function", "file_path": "auth/handler.py", "line_start": 10, "line_end": 30}),
        ("auth/verify.py::verify_token", {"name": "verify_token", "type": "function", "file_path": "auth/verify.py", "line_start": 5, "line_end": 25}),
        ("db/users.py::get_user", {"name": "get_user", "type": "function", "file_path": "db/users.py", "line_start": 20, "line_end": 40}),
        ("db/query.py::db_query", {"name": "db_query", "type": "function", "file_path": "db/query.py", "line_start": 1, "line_end": 15}),
        ("auth/session.py::save_session", {"name": "save_session", "type": "function", "file_path": "auth/session.py", "line_start": 10, "line_end": 20}),
    ]
    for node_id, attrs in nodes:
        G.add_node(node_id, **attrs)

    # Add edges with confidence
    edges = [
        ("auth/handler.py::login", "auth/verify.py::verify_token", {"type": "calls", "confidence": 0.9, "line": 15}),
        ("auth/verify.py::verify_token", "db/users.py::get_user", {"type": "calls", "confidence": 0.8, "line": 10}),
        ("auth/verify.py::verify_token", "auth/session.py::save_session", {"type": "calls", "confidence": 0.7, "line": 20}),
        ("db/users.py::get_user", "db/query.py::db_query", {"type": "calls", "confidence": 0.6, "line": 25}),
    ]
    for source, target, attrs in edges:
        G.add_edge(source, target, **attrs)

    return G


class TestExpandWithGraph:
    """Tests for expand_with_graph function."""

    def test_expand_finds_connected_nodes(self):
        """Expansion from login finds verify_token and save_session within 2 hops."""
        from oya.qa.graph_retrieval import expand_with_graph

        graph = _make_test_graph()
        node_ids = ["auth/handler.py::login"]

        subgraph = expand_with_graph(node_ids, graph, hops=2)

        # Should include login + 2 hops of neighbors
        node_names = {n.name for n in subgraph.nodes}
        assert "login" in node_names
        assert "verify_token" in node_names
        assert "get_user" in node_names  # 2 hops
        assert "save_session" in node_names  # 2 hops via verify_token

    def test_expand_respects_confidence_threshold(self):
        """Edges below confidence threshold are not traversed."""
        from oya.qa.graph_retrieval import expand_with_graph

        graph = _make_test_graph()
        node_ids = ["auth/verify.py::verify_token"]

        # With high threshold, db_query (0.6 confidence edge) should be excluded
        subgraph = expand_with_graph(node_ids, graph, hops=2, min_confidence=0.7)

        node_names = {n.name for n in subgraph.nodes}
        assert "verify_token" in node_names
        assert "get_user" in node_names  # 0.8 confidence, included
        assert "save_session" in node_names  # 0.7 confidence, included
        assert "db_query" not in node_names  # 0.6 confidence, excluded

    def test_expand_handles_missing_nodes(self):
        """Missing node IDs are gracefully skipped."""
        from oya.qa.graph_retrieval import expand_with_graph

        graph = _make_test_graph()
        node_ids = ["nonexistent::function", "auth/handler.py::login"]

        subgraph = expand_with_graph(node_ids, graph, hops=2)

        # Should still find nodes from the valid ID
        node_names = {n.name for n in subgraph.nodes}
        assert "login" in node_names

    def test_expand_empty_input(self):
        """Empty node list returns empty subgraph."""
        from oya.qa.graph_retrieval import expand_with_graph

        graph = _make_test_graph()

        subgraph = expand_with_graph([], graph, hops=2)

        assert len(subgraph.nodes) == 0
        assert len(subgraph.edges) == 0
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/poecurt/projects/oya/backend && pytest tests/test_graph_retrieval.py -v`
Expected: FAIL with "ModuleNotFoundError" or "ImportError"

**Step 3: Write minimal implementation**

Create `backend/src/oya/qa/graph_retrieval.py`:

```python
"""Graph-augmented retrieval for Q&A."""

from __future__ import annotations

import networkx as nx

from oya.constants.qa import GRAPH_EXPANSION_CONFIDENCE_THRESHOLD, GRAPH_EXPANSION_HOPS
from oya.graph.models import Subgraph
from oya.graph.query import get_neighborhood


def expand_with_graph(
    node_ids: list[str],
    graph: nx.DiGraph,
    hops: int = GRAPH_EXPANSION_HOPS,
    min_confidence: float = GRAPH_EXPANSION_CONFIDENCE_THRESHOLD,
) -> Subgraph:
    """Expand vector search results by traversing the code graph.

    For each node ID found via vector search, find all connected nodes
    within N hops in the code graph.

    Args:
        node_ids: Node IDs from vector search results.
        graph: The code knowledge graph.
        hops: Maximum traversal depth.
        min_confidence: Minimum edge confidence to traverse.

    Returns:
        Subgraph containing all discovered nodes and edges.
    """
    if not node_ids:
        return Subgraph(nodes=[], edges=[])

    all_nodes = {}
    all_edges = {}

    for node_id in node_ids:
        if not graph.has_node(node_id):
            continue

        subgraph = get_neighborhood(graph, node_id, hops=hops, min_confidence=min_confidence)

        # Merge into combined result
        for node in subgraph.nodes:
            all_nodes[node.id] = node
        for edge in subgraph.edges:
            edge_key = (edge.source, edge.target)
            all_edges[edge_key] = edge

    return Subgraph(
        nodes=list(all_nodes.values()),
        edges=list(all_edges.values()),
    )
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/poecurt/projects/oya/backend && pytest tests/test_graph_retrieval.py::TestExpandWithGraph -v`
Expected: PASS (4 tests)

**Step 5: Commit**

```bash
git add backend/src/oya/qa/graph_retrieval.py backend/tests/test_graph_retrieval.py
git commit -m "feat(qa): add expand_with_graph for graph-augmented retrieval"
```

---

## Task 3: Add prioritize_nodes Function

**Files:**
- Modify: `backend/src/oya/qa/graph_retrieval.py`
- Modify: `backend/tests/test_graph_retrieval.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_graph_retrieval.py`:

```python
class TestPrioritizeNodes:
    """Tests for prioritize_nodes function."""

    def test_prioritize_by_centrality(self):
        """Nodes with more connections rank higher."""
        from oya.qa.graph_retrieval import prioritize_nodes
        from oya.graph.models import Node, NodeType

        # verify_token has more connections than db_query
        nodes = [
            Node(id="db/query.py::db_query", node_type=NodeType.FUNCTION, name="db_query",
                 file_path="db/query.py", line_start=1, line_end=15),
            Node(id="auth/verify.py::verify_token", node_type=NodeType.FUNCTION, name="verify_token",
                 file_path="auth/verify.py", line_start=5, line_end=25),
        ]

        graph = _make_test_graph()
        prioritized = prioritize_nodes(nodes, graph)

        # verify_token should rank first (more connections)
        assert prioritized[0].name == "verify_token"

    def test_prioritize_preserves_all_nodes(self):
        """All input nodes appear in output."""
        from oya.qa.graph_retrieval import prioritize_nodes
        from oya.graph.models import Node, NodeType

        nodes = [
            Node(id="a", node_type=NodeType.FUNCTION, name="a", file_path="a.py", line_start=1, line_end=10),
            Node(id="b", node_type=NodeType.FUNCTION, name="b", file_path="b.py", line_start=1, line_end=10),
        ]

        graph = nx.DiGraph()  # Empty graph
        prioritized = prioritize_nodes(nodes, graph)

        assert len(prioritized) == 2
        names = {n.name for n in prioritized}
        assert names == {"a", "b"}
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/poecurt/projects/oya/backend && pytest tests/test_graph_retrieval.py::TestPrioritizeNodes -v`
Expected: FAIL with "ImportError" or "AttributeError"

**Step 3: Write minimal implementation**

Add to `backend/src/oya/qa/graph_retrieval.py`:

```python
from oya.graph.models import Node, Subgraph


def prioritize_nodes(
    nodes: list[Node],
    graph: nx.DiGraph,
) -> list[Node]:
    """Rank nodes by importance for context inclusion.

    Prioritizes nodes that are more central in the graph (more connections).

    Args:
        nodes: Nodes to prioritize.
        graph: The code graph for computing centrality.

    Returns:
        Nodes sorted by priority (highest first).
    """
    if not nodes:
        return []

    def node_score(node: Node) -> int:
        """Score based on graph connectivity."""
        if not graph.has_node(node.id):
            return 0
        in_degree = graph.in_degree(node.id)
        out_degree = graph.out_degree(node.id)
        return in_degree + out_degree

    return sorted(nodes, key=node_score, reverse=True)
```

Also update the import at the top of the file to include `Node`:

```python
from oya.graph.models import Node, Subgraph
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/poecurt/projects/oya/backend && pytest tests/test_graph_retrieval.py::TestPrioritizeNodes -v`
Expected: PASS (2 tests)

**Step 5: Commit**

```bash
git add backend/src/oya/qa/graph_retrieval.py backend/tests/test_graph_retrieval.py
git commit -m "feat(qa): add prioritize_nodes for ranking graph context"
```

---

## Task 4: Add build_graph_context Function

**Files:**
- Modify: `backend/src/oya/qa/graph_retrieval.py`
- Modify: `backend/tests/test_graph_retrieval.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_graph_retrieval.py`:

```python
class TestBuildGraphContext:
    """Tests for build_graph_context function."""

    def test_includes_mermaid_diagram(self):
        """Output includes Mermaid diagram."""
        from oya.qa.graph_retrieval import build_graph_context
        from oya.graph.models import Node, Edge, NodeType, EdgeType, Subgraph

        subgraph = Subgraph(
            nodes=[
                Node(id="a.py::func_a", node_type=NodeType.FUNCTION, name="func_a",
                     file_path="a.py", line_start=1, line_end=10),
                Node(id="b.py::func_b", node_type=NodeType.FUNCTION, name="func_b",
                     file_path="b.py", line_start=1, line_end=10),
            ],
            edges=[
                Edge(source="a.py::func_a", target="b.py::func_b",
                     edge_type=EdgeType.CALLS, confidence=0.9, line=5),
            ],
        )

        mermaid, code = build_graph_context(subgraph, token_budget=2000)

        assert "flowchart" in mermaid
        assert "func_a" in mermaid
        assert "func_b" in mermaid

    def test_includes_code_snippets(self):
        """Output includes code location info."""
        from oya.qa.graph_retrieval import build_graph_context
        from oya.graph.models import Node, NodeType, Subgraph

        subgraph = Subgraph(
            nodes=[
                Node(id="auth/handler.py::login", node_type=NodeType.FUNCTION, name="login",
                     file_path="auth/handler.py", line_start=10, line_end=30,
                     docstring="Handle user login."),
            ],
            edges=[],
        )

        mermaid, code = build_graph_context(subgraph, token_budget=2000)

        assert "auth/handler.py" in code
        assert "login" in code
        assert "10" in code  # line number

    def test_respects_token_budget(self):
        """Code output respects token budget."""
        from oya.qa.graph_retrieval import build_graph_context
        from oya.graph.models import Node, NodeType, Subgraph
        from oya.generation.chunking import estimate_tokens

        # Create many nodes
        nodes = [
            Node(id=f"file{i}.py::func{i}", node_type=NodeType.FUNCTION, name=f"func{i}",
                 file_path=f"file{i}.py", line_start=1, line_end=100,
                 docstring="A" * 500)  # Long docstring
            for i in range(20)
        ]
        subgraph = Subgraph(nodes=nodes, edges=[])

        mermaid, code = build_graph_context(subgraph, token_budget=500)

        # Total should be under budget (with some margin for structure)
        total_tokens = estimate_tokens(mermaid) + estimate_tokens(code)
        assert total_tokens < 700  # Budget + some overhead

    def test_empty_subgraph(self):
        """Empty subgraph returns empty strings."""
        from oya.qa.graph_retrieval import build_graph_context
        from oya.graph.models import Subgraph

        subgraph = Subgraph(nodes=[], edges=[])

        mermaid, code = build_graph_context(subgraph, token_budget=2000)

        assert mermaid == ""
        assert code == ""
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/poecurt/projects/oya/backend && pytest tests/test_graph_retrieval.py::TestBuildGraphContext -v`
Expected: FAIL with "ImportError" or "AttributeError"

**Step 3: Write minimal implementation**

Add to `backend/src/oya/qa/graph_retrieval.py`:

```python
from oya.constants.qa import (
    GRAPH_EXPANSION_CONFIDENCE_THRESHOLD,
    GRAPH_EXPANSION_HOPS,
    GRAPH_MERMAID_TOKEN_BUDGET,
)
from oya.generation.chunking import estimate_tokens


def build_graph_context(
    subgraph: Subgraph,
    token_budget: int,
) -> tuple[str, str]:
    """Format subgraph as context for LLM consumption.

    Returns a Mermaid diagram showing relationships and formatted
    code snippets for each node, respecting the token budget.

    Args:
        subgraph: The expanded subgraph from graph traversal.
        token_budget: Maximum tokens for the combined output.

    Returns:
        Tuple of (mermaid_diagram, code_snippets).
    """
    if not subgraph.nodes:
        return "", ""

    # Generate Mermaid diagram
    mermaid = subgraph.to_mermaid()
    mermaid_tokens = estimate_tokens(mermaid)

    # Reserve budget for mermaid, rest for code
    mermaid_budget = min(mermaid_tokens, GRAPH_MERMAID_TOKEN_BUDGET)
    code_budget = token_budget - mermaid_budget

    # If mermaid is too big, truncate it
    if mermaid_tokens > GRAPH_MERMAID_TOKEN_BUDGET:
        # Simple truncation - could be smarter
        lines = mermaid.split("\n")
        truncated_lines = [lines[0]]  # Keep header
        current_tokens = estimate_tokens(truncated_lines[0])
        for line in lines[1:]:
            line_tokens = estimate_tokens(line)
            if current_tokens + line_tokens > GRAPH_MERMAID_TOKEN_BUDGET:
                break
            truncated_lines.append(line)
            current_tokens += line_tokens
        mermaid = "\n".join(truncated_lines)

    # Build code snippets
    code_parts = []
    current_tokens = 0

    for node in subgraph.nodes:
        snippet = _format_node_snippet(node)
        snippet_tokens = estimate_tokens(snippet)

        if current_tokens + snippet_tokens > code_budget:
            break

        code_parts.append(snippet)
        current_tokens += snippet_tokens

    code = "\n\n".join(code_parts)

    return mermaid, code


def _format_node_snippet(node: Node) -> str:
    """Format a node as a code reference snippet."""
    parts = [f"### {node.file_path}::{node.name} (lines {node.line_start}-{node.line_end})"]

    if node.docstring:
        parts.append(f"> {node.docstring}")

    if node.signature:
        parts.append(f"```\n{node.signature}\n```")

    return "\n".join(parts)
```

Update the imports at the top:

```python
from oya.constants.qa import (
    GRAPH_EXPANSION_CONFIDENCE_THRESHOLD,
    GRAPH_EXPANSION_HOPS,
    GRAPH_MERMAID_TOKEN_BUDGET,
)
from oya.generation.chunking import estimate_tokens
from oya.graph.models import Node, Subgraph
from oya.graph.query import get_neighborhood
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/poecurt/projects/oya/backend && pytest tests/test_graph_retrieval.py::TestBuildGraphContext -v`
Expected: PASS (4 tests)

**Step 5: Commit**

```bash
git add backend/src/oya/qa/graph_retrieval.py backend/tests/test_graph_retrieval.py
git commit -m "feat(qa): add build_graph_context for LLM-ready formatting"
```

---

## Task 5: Add Graph-Augmented Q&A Prompt Template

**Files:**
- Modify: `backend/src/oya/generation/prompts.py`
- Create: `backend/tests/test_graph_qa_prompt.py`

**Step 1: Write the failing test**

Create `backend/tests/test_graph_qa_prompt.py`:

```python
"""Tests for graph-augmented Q&A prompt."""


def test_graph_qa_prompt_includes_mermaid():
    """Prompt template includes mermaid diagram placeholder."""
    from oya.generation.prompts import GRAPH_QA_CONTEXT_TEMPLATE

    assert "{mermaid_diagram}" in GRAPH_QA_CONTEXT_TEMPLATE


def test_graph_qa_prompt_includes_code():
    """Prompt template includes code snippets placeholder."""
    from oya.generation.prompts import GRAPH_QA_CONTEXT_TEMPLATE

    assert "{code_snippets}" in GRAPH_QA_CONTEXT_TEMPLATE


def test_format_graph_qa_context():
    """Format function produces valid context string."""
    from oya.generation.prompts import format_graph_qa_context

    mermaid = "flowchart TD\n    A --> B"
    code = "### a.py::func (lines 1-10)\n> Does something"

    result = format_graph_qa_context(mermaid, code)

    assert "flowchart TD" in result
    assert "a.py::func" in result
    assert "Code Relationships" in result
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/poecurt/projects/oya/backend && pytest tests/test_graph_qa_prompt.py -v`
Expected: FAIL with "ImportError"

**Step 3: Write minimal implementation**

Add to `backend/src/oya/generation/prompts.py` (at the end of the file):

```python
# =============================================================================
# Graph-Augmented Q&A (Phase 4)
# =============================================================================

GRAPH_QA_CONTEXT_TEMPLATE = """## Code Relationships
The following diagram shows how the relevant code connects:

```mermaid
{mermaid_diagram}
```

## Relevant Code

{code_snippets}
"""


def format_graph_qa_context(mermaid_diagram: str, code_snippets: str) -> str:
    """Format graph context for Q&A prompt.

    Args:
        mermaid_diagram: Mermaid flowchart showing code relationships.
        code_snippets: Formatted code snippets with file paths and line numbers.

    Returns:
        Formatted context string for inclusion in Q&A prompt.
    """
    if not mermaid_diagram and not code_snippets:
        return ""

    return GRAPH_QA_CONTEXT_TEMPLATE.format(
        mermaid_diagram=mermaid_diagram,
        code_snippets=code_snippets,
    )
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/poecurt/projects/oya/backend && pytest tests/test_graph_qa_prompt.py -v`
Expected: PASS (3 tests)

**Step 5: Commit**

```bash
git add backend/src/oya/generation/prompts.py backend/tests/test_graph_qa_prompt.py
git commit -m "feat(qa): add graph-augmented Q&A prompt template"
```

---

## Task 6: Add map_search_results_to_node_ids Helper

**Files:**
- Modify: `backend/src/oya/qa/graph_retrieval.py`
- Modify: `backend/tests/test_graph_retrieval.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_graph_retrieval.py`:

```python
class TestMapSearchResultsToNodeIds:
    """Tests for mapping vector search results to graph node IDs."""

    def test_maps_file_paths_to_node_ids(self):
        """Search result paths are mapped to matching node IDs in graph."""
        from oya.qa.graph_retrieval import map_search_results_to_node_ids

        graph = _make_test_graph()
        search_results = [
            {"path": "files/auth-handler-py.md", "content": "..."},
            {"path": "files/db-users-py.md", "content": "..."},
        ]

        node_ids = map_search_results_to_node_ids(search_results, graph)

        # Should find nodes whose file_path matches
        assert any("auth/handler.py" in nid for nid in node_ids)

    def test_handles_no_matches(self):
        """Returns empty list when no matches found."""
        from oya.qa.graph_retrieval import map_search_results_to_node_ids

        graph = _make_test_graph()
        search_results = [
            {"path": "files/unknown-py.md", "content": "..."},
        ]

        node_ids = map_search_results_to_node_ids(search_results, graph)

        assert node_ids == []
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/poecurt/projects/oya/backend && pytest tests/test_graph_retrieval.py::TestMapSearchResultsToNodeIds -v`
Expected: FAIL with "ImportError"

**Step 3: Write minimal implementation**

Add to `backend/src/oya/qa/graph_retrieval.py`:

```python
from typing import Any


def map_search_results_to_node_ids(
    search_results: list[dict[str, Any]],
    graph: nx.DiGraph,
) -> list[str]:
    """Map vector search results to graph node IDs.

    Search results have wiki paths like 'files/auth-handler-py.md'.
    We need to find corresponding node IDs like 'auth/handler.py::login'.

    Args:
        search_results: Vector search results with 'path' field.
        graph: The code graph with node file_path attributes.

    Returns:
        List of graph node IDs that match the search results.
    """
    node_ids = []

    # Build index of file paths to node IDs
    file_to_nodes: dict[str, list[str]] = {}
    for node_id in graph.nodes():
        node_data = graph.nodes[node_id]
        file_path = node_data.get("file_path", "")
        if file_path:
            if file_path not in file_to_nodes:
                file_to_nodes[file_path] = []
            file_to_nodes[file_path].append(node_id)

    for result in search_results:
        wiki_path = result.get("path", "")

        # Convert wiki path to source path
        # 'files/auth-handler-py.md' -> 'auth/handler.py'
        source_path = _wiki_path_to_source_path(wiki_path)

        if source_path in file_to_nodes:
            node_ids.extend(file_to_nodes[source_path])

    return node_ids


def _wiki_path_to_source_path(wiki_path: str) -> str:
    """Convert wiki path back to source file path.

    Examples:
        'files/auth-handler-py.md' -> 'auth/handler.py'
        'files/src-utils-ts.md' -> 'src/utils.ts'
    """
    # Remove 'files/' prefix and '.md' suffix
    if wiki_path.startswith("files/"):
        wiki_path = wiki_path[6:]
    if wiki_path.endswith(".md"):
        wiki_path = wiki_path[:-3]

    # Replace '-' with '/' for directory separators, except for file extension
    # This is tricky because 'auth-handler-py' should become 'auth/handler.py'
    # We assume the last '-' before a known extension is the extension separator

    parts = wiki_path.rsplit("-", 1)
    if len(parts) == 2 and parts[1] in ("py", "ts", "js", "tsx", "jsx", "java", "go", "rs", "rb"):
        base = parts[0].replace("-", "/")
        ext = parts[1]
        return f"{base}.{ext}"

    # Fallback: just replace all '-' with '/'
    return wiki_path.replace("-", "/")
```

Update the imports:

```python
from typing import Any
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/poecurt/projects/oya/backend && pytest tests/test_graph_retrieval.py::TestMapSearchResultsToNodeIds -v`
Expected: PASS (2 tests)

**Step 5: Commit**

```bash
git add backend/src/oya/qa/graph_retrieval.py backend/tests/test_graph_retrieval.py
git commit -m "feat(qa): add map_search_results_to_node_ids helper"
```

---

## Task 7: Integrate Graph Retrieval into QAService

**Files:**
- Modify: `backend/src/oya/qa/service.py`
- Modify: `backend/tests/test_qa_service.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_qa_service.py`:

```python
class TestQAServiceGraphAugmented:
    """Tests for graph-augmented Q&A."""

    @pytest.mark.asyncio
    async def test_qa_with_graph_expands_context(self, mock_vectorstore, mock_db, mock_llm):
        """When graph is provided, Q&A expands context using graph traversal."""
        import networkx as nx

        # Create a simple graph
        graph = nx.DiGraph()
        graph.add_node("auth/handler.py::login", name="login", type="function",
                       file_path="auth/handler.py", line_start=10, line_end=30)
        graph.add_node("auth/verify.py::verify", name="verify", type="function",
                       file_path="auth/verify.py", line_start=5, line_end=20)
        graph.add_edge("auth/handler.py::login", "auth/verify.py::verify",
                       type="calls", confidence=0.9, line=15)

        service = QAService(mock_vectorstore, mock_db, mock_llm, graph=graph)
        request = QARequest(question="How does login work?")

        await service.ask(request)

        # LLM should be called with expanded context
        call_args = mock_llm.generate.call_args
        prompt = call_args.kwargs.get("prompt") or call_args.args[0]

        # Should include graph context (mermaid or code relationships)
        assert "login" in prompt.lower() or "flowchart" in prompt.lower()

    @pytest.mark.asyncio
    async def test_qa_falls_back_without_graph(self, mock_vectorstore, mock_db, mock_llm):
        """Without graph, Q&A uses normal vector retrieval."""
        service = QAService(mock_vectorstore, mock_db, mock_llm, graph=None)
        request = QARequest(question="How does X work?")

        response = await service.ask(request)

        # Should still work and return response
        assert response.answer is not None
        assert response.confidence is not None

    @pytest.mark.asyncio
    async def test_qa_graph_can_be_disabled(self, mock_vectorstore, mock_db, mock_llm):
        """Graph expansion can be disabled via parameter."""
        import networkx as nx

        graph = nx.DiGraph()
        graph.add_node("test::func", name="func", type="function",
                       file_path="test.py", line_start=1, line_end=10)

        service = QAService(mock_vectorstore, mock_db, mock_llm, graph=graph)
        request = QARequest(question="Test question", use_graph=False)

        await service.ask(request)

        # Should work without graph expansion
        mock_llm.generate.assert_called_once()
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/poecurt/projects/oya/backend && pytest tests/test_qa_service.py::TestQAServiceGraphAugmented -v`
Expected: FAIL with "TypeError" (unexpected keyword argument 'graph')

**Step 3: Write the implementation**

Modify `backend/src/oya/qa/service.py`:

1. Update the imports at the top:

```python
from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

import networkx as nx

from oya.constants.issues import ISSUE_QUERY_KEYWORDS
from oya.constants.qa import (
    GRAPH_EXPANSION_CONFIDENCE_THRESHOLD,
    GRAPH_EXPANSION_HOPS,
    HIGH_CONFIDENCE_THRESHOLD,
    MAX_CONTEXT_TOKENS,
    MAX_RESULT_TOKENS,
    MEDIUM_CONFIDENCE_THRESHOLD,
    MIN_STRONG_MATCHES_FOR_HIGH,
    STRONG_MATCH_THRESHOLD,
)
from oya.constants.search import DEDUP_HASH_LENGTH, TYPE_PRIORITY
from oya.db.connection import Database
from oya.generation.chunking import estimate_tokens
from oya.generation.prompts import format_graph_qa_context
from oya.llm.client import LLMClient
from oya.qa.graph_retrieval import (
    build_graph_context,
    expand_with_graph,
    map_search_results_to_node_ids,
    prioritize_nodes,
)
from oya.qa.ranking import RRFRanker
from oya.qa.schemas import Citation, ConfidenceLevel, QARequest, QAResponse, SearchQuality
from oya.vectorstore.store import VectorStore

if TYPE_CHECKING:
    from oya.vectorstore.issues import IssuesStore
```

2. Update `__init__` to accept optional graph:

```python
def __init__(
    self,
    vectorstore: VectorStore,
    db: Database,
    llm: LLMClient,
    issues_store: IssuesStore | None = None,
    graph: nx.DiGraph | None = None,
) -> None:
    """Initialize Q&A service.

    Args:
        vectorstore: ChromaDB vector store for semantic search.
        db: SQLite database for full-text search.
        llm: LLM client for answer generation.
        issues_store: Optional IssuesStore for issue-aware Q&A.
        graph: Optional code graph for graph-augmented retrieval.
    """
    self._vectorstore = vectorstore
    self._db = db
    self._llm = llm
    self._issues_store = issues_store
    self._graph = graph
    self._ranker = RRFRanker(k=60)
```

3. Update `_ask_normal` to use graph when available:

```python
async def _ask_normal(self, request: QARequest) -> QAResponse:
    """Answer a question using normal hybrid search.

    Args:
        request: Q&A request with question.

    Returns:
        Q&A response with answer, citations, confidence, and search quality.
    """
    # Perform hybrid search
    results, semantic_ok, fts_ok = await self.search(request.question)

    # Calculate confidence from results
    confidence = self._calculate_confidence(results)

    # Build prompt with token budgeting
    prompt, results_used = self._build_context_prompt(request.question, results)

    # Add graph context if available and enabled
    graph_context = ""
    use_graph = getattr(request, 'use_graph', True)
    if self._graph is not None and use_graph and results:
        graph_context = self._build_graph_context(results)
        if graph_context:
            prompt = graph_context + "\n\n" + prompt

    try:
        raw_answer = await self._llm.generate(
            prompt=prompt,
            system_prompt=QA_SYSTEM_PROMPT,
            temperature=0.2,  # Lower for factual Q&A
        )
    except Exception as e:
        return QAResponse(
            answer=f"Error generating answer: {str(e)}",
            citations=[],
            confidence=confidence,
            disclaimer="An error occurred while generating the answer.",
            search_quality=SearchQuality(
                semantic_searched=semantic_ok,
                fts_searched=fts_ok,
                results_found=len(results),
                results_used=results_used,
            ),
        )

    # Extract citations and answer from structured response
    citations = self._extract_citations(raw_answer, results)
    answer = self._extract_answer(raw_answer)

    # Build disclaimer based on confidence
    disclaimers = {
        ConfidenceLevel.HIGH: "Based on strong evidence from the codebase.",
        ConfidenceLevel.MEDIUM: "Based on partial evidence. Verify against source code.",
        ConfidenceLevel.LOW: "Limited evidence found. This answer may be speculative.",
    }

    return QAResponse(
        answer=answer,
        citations=citations,
        confidence=confidence,
        disclaimer=disclaimers[confidence],
        search_quality=SearchQuality(
            semantic_searched=semantic_ok,
            fts_searched=fts_ok,
            results_found=len(results),
            results_used=results_used,
        ),
    )
```

4. Add the `_build_graph_context` helper method:

```python
def _build_graph_context(self, results: list[dict[str, Any]]) -> str:
    """Build graph-augmented context from search results.

    Args:
        results: Search results from hybrid search.

    Returns:
        Formatted graph context string, or empty string if no graph data.
    """
    if self._graph is None:
        return ""

    # Map search results to graph node IDs
    node_ids = map_search_results_to_node_ids(results, self._graph)

    if not node_ids:
        return ""

    # Expand via graph traversal
    subgraph = expand_with_graph(
        node_ids,
        self._graph,
        hops=GRAPH_EXPANSION_HOPS,
        min_confidence=GRAPH_EXPANSION_CONFIDENCE_THRESHOLD,
    )

    if not subgraph.nodes:
        return ""

    # Prioritize nodes
    prioritized = prioritize_nodes(subgraph.nodes, self._graph)
    subgraph = Subgraph(nodes=prioritized, edges=subgraph.edges)

    # Build context with budget
    # Reserve some budget for graph context (1/3 of total)
    graph_budget = MAX_CONTEXT_TOKENS // 3
    mermaid, code = build_graph_context(subgraph, token_budget=graph_budget)

    return format_graph_qa_context(mermaid, code)
```

5. Add the import for Subgraph:

```python
from oya.graph.models import Subgraph
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/poecurt/projects/oya/backend && pytest tests/test_qa_service.py::TestQAServiceGraphAugmented -v`
Expected: PASS (3 tests)

**Step 5: Commit**

```bash
git add backend/src/oya/qa/service.py backend/tests/test_qa_service.py
git commit -m "feat(qa): integrate graph-augmented retrieval into QAService"
```

---

## Task 8: Update QARequest Schema

**Files:**
- Modify: `backend/src/oya/qa/schemas.py`
- Modify: `backend/tests/test_qa_service.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_qa_service.py` (or verify existing tests work):

```python
def test_qa_request_has_use_graph_field():
    """QARequest has optional use_graph field defaulting to True."""
    from oya.qa.schemas import QARequest

    # Default should be True
    request = QARequest(question="How does X work?")
    assert request.use_graph is True

    # Can be set to False
    request = QARequest(question="How does X work?", use_graph=False)
    assert request.use_graph is False
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/poecurt/projects/oya/backend && pytest tests/test_qa_service.py::test_qa_request_has_use_graph_field -v`
Expected: FAIL with "AttributeError" or validation error

**Step 3: Write the implementation**

Read and modify `backend/src/oya/qa/schemas.py` to add `use_graph` field to `QARequest`:

```python
class QARequest(BaseModel):
    """Request model for Q&A endpoint."""

    question: str
    use_graph: bool = True
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/poecurt/projects/oya/backend && pytest tests/test_qa_service.py::test_qa_request_has_use_graph_field -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/oya/qa/schemas.py backend/tests/test_qa_service.py
git commit -m "feat(qa): add use_graph field to QARequest schema"
```

---

## Task 9: Wire Graph Loading in Q&A Router

**Files:**
- Modify: `backend/src/oya/api/routers/qa.py`
- Test manually or add integration test

**Step 1: Read the current router**

Read `backend/src/oya/api/routers/qa.py` to understand the current structure.

**Step 2: Modify to load graph**

Update the router to load the graph when answering questions. The graph should be loaded from `.oyawiki/graph/` if it exists.

Add imports:

```python
from pathlib import Path
from oya.graph.persistence import load_graph
```

Update the endpoint to load the graph:

```python
@router.post("/ask", response_model=QAResponse)
async def ask_question(
    request: QARequest,
    vectorstore: VectorStore = Depends(get_vectorstore),
    db: Database = Depends(get_db),
    llm: LLMClient = Depends(get_llm),
    issues_store: IssuesStore | None = Depends(get_issues_store),
) -> QAResponse:
    """Answer a question about the codebase."""
    # Load graph if available
    workspace = Path(settings.WORKSPACE_PATH)
    graph_dir = workspace / ".oyawiki" / "graph"
    graph = None
    if graph_dir.exists():
        try:
            graph = load_graph(graph_dir)
            if graph.number_of_nodes() == 0:
                graph = None
        except Exception:
            # Graph loading failed, proceed without it
            pass

    service = QAService(vectorstore, db, llm, issues_store, graph=graph)
    return await service.ask(request)
```

**Step 3: Test manually**

Run the server and test with a Q&A query to verify it works with and without graph.

**Step 4: Commit**

```bash
git add backend/src/oya/api/routers/qa.py
git commit -m "feat(qa): load code graph in Q&A router for graph-augmented retrieval"
```

---

## Task 10: Run Full Test Suite

**Files:** None (verification only)

**Step 1: Run all backend tests**

Run: `cd /Users/poecurt/projects/oya/backend && pytest -v`
Expected: All tests pass

**Step 2: Run linting**

Run: `cd /Users/poecurt/projects/oya/backend && ruff check src/ tests/`
Expected: No errors (or fix any that appear)

**Step 3: Run formatting**

Run: `cd /Users/poecurt/projects/oya/backend && ruff format src/ tests/`
Expected: Files formatted

**Step 4: Run make all**

Run: `cd /Users/poecurt/projects/oya && make all`
Expected: All checks pass

**Step 5: Commit any fixes**

```bash
git add -A
git commit -m "fix: address lint and test issues from Phase 4 implementation"
```

---

## Task 11: Final Phase 4 Commit

**Step 1: Verify all changes are committed**

Run: `git status`
Expected: Clean working tree

**Step 2: Create summary commit if needed**

If there are uncommitted changes:

```bash
git add -A
git commit -m "feat(qa): complete Phase 4 graph-augmented Q&A retrieval

- Add graph expansion constants to qa.py
- Create graph_retrieval module with expand/prioritize/build functions
- Add graph Q&A prompt template
- Integrate graph retrieval into QAService
- Wire graph loading in Q&A router
- Add comprehensive tests"
```

---

## Summary

| Task | Description | Files |
|------|-------------|-------|
| 1 | Add graph expansion constants | `constants/qa.py` |
| 2 | Create expand_with_graph | `qa/graph_retrieval.py` |
| 3 | Add prioritize_nodes | `qa/graph_retrieval.py` |
| 4 | Add build_graph_context | `qa/graph_retrieval.py` |
| 5 | Add graph Q&A prompt | `generation/prompts.py` |
| 6 | Add map_search_results_to_node_ids | `qa/graph_retrieval.py` |
| 7 | Integrate into QAService | `qa/service.py` |
| 8 | Update QARequest schema | `qa/schemas.py` |
| 9 | Wire graph in Q&A router | `api/routers/qa.py` |
| 10 | Run full test suite | - |
| 11 | Final commit | - |

**Estimated tests:** 15+ new tests across 3 test files
