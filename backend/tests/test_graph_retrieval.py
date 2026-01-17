"""Tests for graph-augmented Q&A retrieval."""

import networkx as nx


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
        (
            "auth/handler.py::login",
            {
                "name": "login",
                "type": "function",
                "file_path": "auth/handler.py",
                "line_start": 10,
                "line_end": 30,
            },
        ),
        (
            "auth/verify.py::verify_token",
            {
                "name": "verify_token",
                "type": "function",
                "file_path": "auth/verify.py",
                "line_start": 5,
                "line_end": 25,
            },
        ),
        (
            "db/users.py::get_user",
            {
                "name": "get_user",
                "type": "function",
                "file_path": "db/users.py",
                "line_start": 20,
                "line_end": 40,
            },
        ),
        (
            "db/query.py::db_query",
            {
                "name": "db_query",
                "type": "function",
                "file_path": "db/query.py",
                "line_start": 1,
                "line_end": 15,
            },
        ),
        (
            "auth/session.py::save_session",
            {
                "name": "save_session",
                "type": "function",
                "file_path": "auth/session.py",
                "line_start": 10,
                "line_end": 20,
            },
        ),
    ]
    for node_id, attrs in nodes:
        G.add_node(node_id, **attrs)

    # Add edges with confidence
    edges = [
        (
            "auth/handler.py::login",
            "auth/verify.py::verify_token",
            {"type": "calls", "confidence": 0.9, "line": 15},
        ),
        (
            "auth/verify.py::verify_token",
            "db/users.py::get_user",
            {"type": "calls", "confidence": 0.8, "line": 10},
        ),
        (
            "auth/verify.py::verify_token",
            "auth/session.py::save_session",
            {"type": "calls", "confidence": 0.7, "line": 20},
        ),
        (
            "db/users.py::get_user",
            "db/query.py::db_query",
            {"type": "calls", "confidence": 0.6, "line": 25},
        ),
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


class TestPrioritizeNodes:
    """Tests for prioritize_nodes function."""

    def test_prioritize_by_centrality(self):
        """Nodes with more connections rank higher."""
        from oya.qa.graph_retrieval import prioritize_nodes
        from oya.graph.models import Node, NodeType

        # verify_token has more connections than db_query
        nodes = [
            Node(
                id="db/query.py::db_query",
                node_type=NodeType.FUNCTION,
                name="db_query",
                file_path="db/query.py",
                line_start=1,
                line_end=15,
            ),
            Node(
                id="auth/verify.py::verify_token",
                node_type=NodeType.FUNCTION,
                name="verify_token",
                file_path="auth/verify.py",
                line_start=5,
                line_end=25,
            ),
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
            Node(
                id="a",
                node_type=NodeType.FUNCTION,
                name="a",
                file_path="a.py",
                line_start=1,
                line_end=10,
            ),
            Node(
                id="b",
                node_type=NodeType.FUNCTION,
                name="b",
                file_path="b.py",
                line_start=1,
                line_end=10,
            ),
        ]

        graph = nx.DiGraph()  # Empty graph
        prioritized = prioritize_nodes(nodes, graph)

        assert len(prioritized) == 2
        names = {n.name for n in prioritized}
        assert names == {"a", "b"}


class TestBuildGraphContext:
    """Tests for build_graph_context function."""

    def test_includes_mermaid_diagram(self):
        """Output includes Mermaid diagram."""
        from oya.qa.graph_retrieval import build_graph_context
        from oya.graph.models import Node, Edge, NodeType, EdgeType, Subgraph

        subgraph = Subgraph(
            nodes=[
                Node(
                    id="a.py::func_a",
                    node_type=NodeType.FUNCTION,
                    name="func_a",
                    file_path="a.py",
                    line_start=1,
                    line_end=10,
                ),
                Node(
                    id="b.py::func_b",
                    node_type=NodeType.FUNCTION,
                    name="func_b",
                    file_path="b.py",
                    line_start=1,
                    line_end=10,
                ),
            ],
            edges=[
                Edge(
                    source="a.py::func_a",
                    target="b.py::func_b",
                    edge_type=EdgeType.CALLS,
                    confidence=0.9,
                    line=5,
                ),
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
                Node(
                    id="auth/handler.py::login",
                    node_type=NodeType.FUNCTION,
                    name="login",
                    file_path="auth/handler.py",
                    line_start=10,
                    line_end=30,
                    docstring="Handle user login.",
                ),
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
            Node(
                id=f"file{i}.py::func{i}",
                node_type=NodeType.FUNCTION,
                name=f"func{i}",
                file_path=f"file{i}.py",
                line_start=1,
                line_end=100,
                docstring="A" * 500,
            )  # Long docstring
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
