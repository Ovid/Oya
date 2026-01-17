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


def get_entry_points(graph: nx.DiGraph) -> list[Node]:
    """Find nodes with no incoming call edges (likely entry points).

    Args:
        graph: The code graph.

    Returns:
        List of nodes that have outgoing calls but no incoming calls.
    """
    nodes = []
    for node_id in graph.nodes():
        in_calls = [1 for _, _, d in graph.in_edges(node_id, data=True) if d.get("type") == "calls"]
        out_calls = [1 for _, _, d in graph.out_edges(node_id, data=True) if d.get("type") == "calls"]

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
        out_calls = [1 for _, _, d in graph.out_edges(node_id, data=True) if d.get("type") == "calls"]

        if len(out_calls) == 0:
            node_data = graph.nodes[node_id]
            nodes.append(_node_from_data(node_id, node_data))

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
