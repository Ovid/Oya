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
