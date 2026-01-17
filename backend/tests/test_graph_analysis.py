"""Tests for graph analysis utilities."""

import networkx as nx


def test_filter_test_nodes_removes_test_files():
    """filter_test_nodes excludes test files from graph."""
    from oya.graph.analysis import filter_test_nodes

    G = nx.DiGraph()
    G.add_node(
        "src/api/routes.py::handle",
        name="handle",
        type="function",
        file_path="src/api/routes.py",
        line_start=1,
        line_end=10,
    )
    G.add_node(
        "tests/test_routes.py::test_handle",
        name="test_handle",
        type="function",
        file_path="tests/test_routes.py",
        line_start=1,
        line_end=10,
    )
    G.add_node(
        "src/utils/test_helpers.py::helper",
        name="helper",
        type="function",
        file_path="src/utils/test_helpers.py",
        line_start=1,
        line_end=10,
    )
    G.add_edge(
        "tests/test_routes.py::test_handle",
        "src/api/routes.py::handle",
        type="calls",
        confidence=0.9,
        line=5,
    )

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
    G.add_edge(
        "api/routes.py::handle", "db/queries.py::get_user", type="calls", confidence=0.9, line=10
    )
    G.add_edge(
        "api/handlers.py::process", "db/models.py::User", type="calls", confidence=0.8, line=20
    )

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
    G.add_edge("api/routes.py::handle", "db/models.py::User", type="calls", confidence=0.5, line=10)

    component_graph = get_component_graph(G, min_confidence=0.7)

    # Should have nodes but no edges (confidence too low)
    assert component_graph.has_node("api")
    assert component_graph.has_node("db")
    assert not component_graph.has_edge("api", "db")


def test_select_top_entry_points_by_fanout():
    """select_top_entry_points returns entry points sorted by fan-out."""
    from oya.graph.analysis import select_top_entry_points

    G = nx.DiGraph()
    # Entry point with high fan-out (calls 3 things)
    G.add_node("api/main.py::handle_request", file_path="api/main.py")
    G.add_node("db/query.py::query", file_path="db/query.py")
    G.add_node("cache/redis.py::get", file_path="cache/redis.py")
    G.add_node("log/logger.py::log", file_path="log/logger.py")
    G.add_edge(
        "api/main.py::handle_request", "db/query.py::query", type="calls", confidence=0.9, line=10
    )
    G.add_edge(
        "api/main.py::handle_request", "cache/redis.py::get", type="calls", confidence=0.9, line=15
    )
    G.add_edge(
        "api/main.py::handle_request", "log/logger.py::log", type="calls", confidence=0.9, line=20
    )

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
    G.add_edge(
        "tests/test_main.py::test_handle",
        "api/main.py::handle",
        type="calls",
        confidence=0.9,
        line=5,
    )

    top = select_top_entry_points(G, n=5)

    # Should only return production entry point
    assert len(top) == 1
    assert top[0] == "api/main.py::handle"


def test_component_graph_to_mermaid():
    """component_graph_to_mermaid generates valid Mermaid diagram."""
    from oya.graph.analysis import get_component_graph, component_graph_to_mermaid

    G = nx.DiGraph()
    G.add_node("api/routes.py::handle", file_path="api/routes.py")
    G.add_node("db/models.py::User", file_path="db/models.py")
    G.add_node("llm/client.py::generate", file_path="llm/client.py")
    G.add_edge("api/routes.py::handle", "db/models.py::User", type="calls", confidence=0.9, line=10)
    G.add_edge(
        "api/routes.py::handle", "llm/client.py::generate", type="calls", confidence=0.8, line=15
    )

    component_graph = get_component_graph(G)
    mermaid = component_graph_to_mermaid(component_graph)

    assert mermaid.startswith("flowchart")
    assert "api" in mermaid
    assert "db" in mermaid
    assert "llm" in mermaid
    assert "-->" in mermaid
