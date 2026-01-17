"""Tests for graph query interface."""

import pytest
import networkx as nx


@pytest.fixture
def sample_graph():
    """Create a sample graph for testing queries."""
    G = nx.DiGraph()

    # Add nodes
    G.add_node(
        "handler.py::process_request",
        name="process_request",
        type="function",
        file_path="handler.py",
        line_start=10,
        line_end=30,
        docstring=None,
        signature=None,
        parent=None,
    )
    G.add_node(
        "auth.py::verify_token",
        name="verify_token",
        type="function",
        file_path="auth.py",
        line_start=5,
        line_end=15,
        docstring=None,
        signature=None,
        parent=None,
    )
    G.add_node(
        "db.py::get_user",
        name="get_user",
        type="function",
        file_path="db.py",
        line_start=20,
        line_end=35,
        docstring=None,
        signature=None,
        parent=None,
    )
    G.add_node(
        "response.py::send_response",
        name="send_response",
        type="function",
        file_path="response.py",
        line_start=1,
        line_end=10,
        docstring=None,
        signature=None,
        parent=None,
    )

    # Add edges: process_request calls verify_token, get_user, send_response
    G.add_edge(
        "handler.py::process_request",
        "auth.py::verify_token",
        type="calls",
        confidence=0.95,
        line=15,
    )
    G.add_edge(
        "handler.py::process_request", "db.py::get_user", type="calls", confidence=0.9, line=20
    )
    G.add_edge(
        "handler.py::process_request",
        "response.py::send_response",
        type="calls",
        confidence=0.85,
        line=25,
    )
    # verify_token also calls get_user
    G.add_edge("auth.py::verify_token", "db.py::get_user", type="calls", confidence=0.7, line=10)

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
    G.add_node(
        "a.py::func_a",
        name="func_a",
        type="function",
        file_path="a.py",
        line_start=1,
        line_end=10,
        docstring=None,
        signature=None,
        parent=None,
    )
    G.add_node(
        "b.py::func_b",
        name="func_b",
        type="function",
        file_path="b.py",
        line_start=1,
        line_end=10,
        docstring=None,
        signature=None,
        parent=None,
    )
    # No edge between them

    paths = trace_flow(G, "a.py::func_a", "b.py::func_b")

    assert len(paths) == 0


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
