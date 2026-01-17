"""Tests for CGRAG core functionality."""

import networkx as nx


def _make_test_graph() -> nx.DiGraph:
    """Create a test graph with known structure."""
    G = nx.DiGraph()

    nodes = [
        ("auth/handler.py::login", {"name": "login", "type": "function",
            "file_path": "auth/handler.py", "line_start": 10, "line_end": 30}),
        ("auth/verify.py::verify_token", {"name": "verify_token", "type": "function",
            "file_path": "auth/verify.py", "line_start": 5, "line_end": 25}),
        ("db/users.py::get_user", {"name": "get_user", "type": "function",
            "file_path": "db/users.py", "line_start": 20, "line_end": 40}),
    ]
    for node_id, attrs in nodes:
        G.add_node(node_id, **attrs)

    edges = [
        ("auth/handler.py::login", "auth/verify.py::verify_token",
            {"type": "calls", "confidence": 0.9, "line": 15}),
        ("auth/verify.py::verify_token", "db/users.py::get_user",
            {"type": "calls", "confidence": 0.8, "line": 10}),
    ]
    for source, target, attrs in edges:
        G.add_edge(source, target, **attrs)

    return G


class TestIsSpecificGap:
    """Tests for is_specific_gap function."""

    def test_specific_with_path(self):
        """Gap with 'in path' is specific."""
        from oya.qa.cgrag import is_specific_gap

        assert is_specific_gap("verify_token in auth/verify.py")

    def test_specific_with_double_colon(self):
        """Gap with :: is specific."""
        from oya.qa.cgrag import is_specific_gap

        assert is_specific_gap("auth/verify.py::verify_token")

    def test_fuzzy_description(self):
        """Descriptive gap is fuzzy."""
        from oya.qa.cgrag import is_specific_gap

        assert not is_specific_gap("the database connection handler")

    def test_specific_with_function_keyword(self):
        """Gap with 'function X' is specific."""
        from oya.qa.cgrag import is_specific_gap

        assert is_specific_gap("function verify_token")


class TestGraphLookup:
    """Tests for graph_lookup function."""

    def test_lookup_by_name(self):
        """Finds node by function name."""
        from oya.qa.cgrag import graph_lookup

        graph = _make_test_graph()

        result = graph_lookup("verify_token", graph)

        assert result is not None
        assert len(result.nodes) >= 1
        node_names = {n.name for n in result.nodes}
        assert "verify_token" in node_names

    def test_lookup_by_path_and_name(self):
        """Finds node by path::name format."""
        from oya.qa.cgrag import graph_lookup

        graph = _make_test_graph()

        result = graph_lookup("auth/verify.py::verify_token", graph)

        assert result is not None
        node_ids = {n.id for n in result.nodes}
        assert "auth/verify.py::verify_token" in node_ids

    def test_lookup_not_found(self):
        """Returns None for non-existent node."""
        from oya.qa.cgrag import graph_lookup

        graph = _make_test_graph()

        result = graph_lookup("nonexistent_function", graph)

        assert result is None

    def test_lookup_includes_neighborhood(self):
        """Result includes 1-hop neighborhood."""
        from oya.qa.cgrag import graph_lookup

        graph = _make_test_graph()

        result = graph_lookup("verify_token", graph)

        # verify_token connects to login and get_user
        node_names = {n.name for n in result.nodes}
        assert "verify_token" in node_names
        # Should include at least one neighbor
        assert len(node_names) > 1


class TestParseGaps:
    """Tests for parse_gaps function."""

    def test_parse_gaps_none(self):
        """NONE in response returns empty list."""
        from oya.qa.cgrag import parse_gaps

        response = """ANSWER:
The auth system works by...

MISSING (or "NONE" if nothing needed):
NONE"""

        gaps = parse_gaps(response)

        assert gaps == []

    def test_parse_gaps_single(self):
        """Single gap is parsed correctly."""
        from oya.qa.cgrag import parse_gaps

        response = """ANSWER:
The auth system works by...

MISSING (or "NONE" if nothing needed):
- verify_token in auth/verify.py"""

        gaps = parse_gaps(response)

        assert len(gaps) == 1
        assert "verify_token" in gaps[0]

    def test_parse_gaps_multiple(self):
        """Multiple gaps are parsed correctly."""
        from oya.qa.cgrag import parse_gaps

        response = """ANSWER:
The auth system works by...

MISSING (or "NONE" if nothing needed):
- verify_token in auth/verify.py
- UserModel in models/user.py
- the database connection handler"""

        gaps = parse_gaps(response)

        assert len(gaps) == 3
        assert "verify_token" in gaps[0]
        assert "UserModel" in gaps[1]
        assert "database connection" in gaps[2]

    def test_parse_gaps_no_section(self):
        """Missing MISSING section returns empty list."""
        from oya.qa.cgrag import parse_gaps

        response = """ANSWER:
The auth system works by calling various functions."""

        gaps = parse_gaps(response)

        assert gaps == []

    def test_parse_answer(self):
        """Answer is extracted correctly."""
        from oya.qa.cgrag import parse_answer

        response = """ANSWER:
The auth system works by verifying tokens
and checking user permissions.

MISSING (or "NONE" if nothing needed):
NONE"""

        answer = parse_answer(response)

        assert "auth system works" in answer
        assert "verifying tokens" in answer
        assert "MISSING" not in answer
