"""Graph-augmented retrieval for Q&A."""

from __future__ import annotations

import networkx as nx

from oya.constants.qa import (
    GRAPH_EXPANSION_CONFIDENCE_THRESHOLD,
    GRAPH_EXPANSION_HOPS,
    GRAPH_MERMAID_TOKEN_BUDGET,
)
from oya.generation.chunking import estimate_tokens
from oya.graph.models import Node, Subgraph
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
