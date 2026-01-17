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
