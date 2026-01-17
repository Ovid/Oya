"""Tests for graph analysis utilities."""

import networkx as nx


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
