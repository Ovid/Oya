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