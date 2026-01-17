"""Query interface for the code knowledge graph."""

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
