"""Tests for NetworkX graph construction."""

from oya.parsing.models import ParsedFile, ParsedSymbol, SymbolType, Reference, ReferenceType


def test_build_graph_from_parsed_files():
    """Builder creates NetworkX graph with nodes and edges."""
    from oya.graph.builder import build_graph

    file1 = ParsedFile(
        path="auth/utils.py",
        language="python",
        symbols=[
            ParsedSymbol(
                name="verify", symbol_type=SymbolType.FUNCTION, start_line=10, end_line=20
            ),
        ],
    )
    file2 = ParsedFile(
        path="auth/handler.py",
        language="python",
        symbols=[
            ParsedSymbol(name="login", symbol_type=SymbolType.FUNCTION, start_line=5, end_line=25),
        ],
        references=[
            Reference(
                source="auth/handler.py::login",
                target="auth/utils.py::verify",
                reference_type=ReferenceType.CALLS,
                confidence=0.9,
                line=15,
                target_resolved=True,
            ),
        ],
    )

    graph = build_graph([file1, file2])

    # Should have nodes for both functions
    assert graph.has_node("auth/utils.py::verify")
    assert graph.has_node("auth/handler.py::login")

    # Should have edge from login to verify
    assert graph.has_edge("auth/handler.py::login", "auth/utils.py::verify")

    # Edge should have attributes
    edge_data = graph.edges["auth/handler.py::login", "auth/utils.py::verify"]
    assert edge_data["type"] == "calls"
    assert edge_data["confidence"] == 0.9


def test_build_graph_node_attributes():
    """Graph nodes have correct attributes."""
    from oya.graph.builder import build_graph

    file = ParsedFile(
        path="models/user.py",
        language="python",
        symbols=[
            ParsedSymbol(
                name="User",
                symbol_type=SymbolType.CLASS,
                start_line=5,
                end_line=50,
                docstring="A user entity.",
            ),
        ],
    )

    graph = build_graph([file])

    node_data = graph.nodes["models/user.py::User"]
    assert node_data["name"] == "User"
    assert node_data["type"] == "class"
    assert node_data["file_path"] == "models/user.py"
    assert node_data["line_start"] == 5
    assert node_data["line_end"] == 50
    assert node_data["docstring"] == "A user entity."


def test_propagates_is_entry_point_to_node():
    """Graph nodes include is_entry_point metadata from symbols."""
    from oya.graph.builder import build_graph

    files = [
        ParsedFile(
            path="api/routes.py",
            language="python",
            symbols=[
                ParsedSymbol(
                    name="get_users",
                    symbol_type=SymbolType.ROUTE,
                    start_line=10,
                    end_line=20,
                    metadata={"is_entry_point": True},
                ),
                ParsedSymbol(
                    name="helper",
                    symbol_type=SymbolType.FUNCTION,
                    start_line=25,
                    end_line=30,
                    metadata={},  # Not an entry point
                ),
            ],
            references=[],
        )
    ]

    G = build_graph(files)

    # Entry point should have is_entry_point=True
    entry_node = G.nodes["api/routes.py::get_users"]
    assert entry_node.get("is_entry_point") is True

    # Regular function should have is_entry_point=False
    helper_node = G.nodes["api/routes.py::helper"]
    assert helper_node.get("is_entry_point", False) is False
