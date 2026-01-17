"""Tests for graph data models."""

import pytest


def test_node_model_creation():
    """Node model stores entity metadata."""
    from oya.graph.models import Node, NodeType

    node = Node(
        id="backend/src/oya/api/routers/qa.py::ask_question",
        node_type=NodeType.FUNCTION,
        name="ask_question",
        file_path="backend/src/oya/api/routers/qa.py",
        line_start=45,
        line_end=92,
        docstring="Handle Q&A queries against the wiki...",
    )

    assert node.id == "backend/src/oya/api/routers/qa.py::ask_question"
    assert node.node_type == NodeType.FUNCTION
    assert node.name == "ask_question"
    assert node.file_path == "backend/src/oya/api/routers/qa.py"
    assert node.line_start == 45
    assert node.line_end == 92


def test_node_type_enum():
    """NodeType has expected values."""
    from oya.graph.models import NodeType

    assert NodeType.FUNCTION.value == "function"
    assert NodeType.CLASS.value == "class"
    assert NodeType.METHOD.value == "method"
    assert NodeType.FILE.value == "file"
    assert NodeType.MODULE.value == "module"


def test_edge_model_creation():
    """Edge model stores relationship with confidence."""
    from oya.graph.models import Edge, EdgeType

    edge = Edge(
        source="qa.py::ask_question",
        target="vectorstore/search.py::semantic_search",
        edge_type=EdgeType.CALLS,
        confidence=0.9,
        line=52,
    )

    assert edge.source == "qa.py::ask_question"
    assert edge.target == "vectorstore/search.py::semantic_search"
    assert edge.edge_type == EdgeType.CALLS
    assert edge.confidence == 0.9
    assert edge.line == 52


def test_edge_type_enum():
    """EdgeType has expected values matching ReferenceType."""
    from oya.graph.models import EdgeType

    assert EdgeType.CALLS.value == "calls"
    assert EdgeType.INSTANTIATES.value == "instantiates"
    assert EdgeType.INHERITS.value == "inherits"
    assert EdgeType.IMPORTS.value == "imports"


def test_subgraph_model():
    """Subgraph aggregates nodes and edges."""
    from oya.graph.models import Node, Edge, Subgraph, NodeType, EdgeType

    node1 = Node(
        id="a.py::func_a",
        node_type=NodeType.FUNCTION,
        name="func_a",
        file_path="a.py",
        line_start=1,
        line_end=10,
    )
    node2 = Node(
        id="b.py::func_b",
        node_type=NodeType.FUNCTION,
        name="func_b",
        file_path="b.py",
        line_start=1,
        line_end=5,
    )
    edge = Edge(
        source="a.py::func_a",
        target="b.py::func_b",
        edge_type=EdgeType.CALLS,
        confidence=0.9,
        line=5,
    )

    subgraph = Subgraph(nodes=[node1, node2], edges=[edge])

    assert len(subgraph.nodes) == 2
    assert len(subgraph.edges) == 1


def test_subgraph_to_dict():
    """Subgraph can be serialized to dict for JSON."""
    from oya.graph.models import Node, Edge, Subgraph, NodeType, EdgeType

    node = Node(
        id="a.py::func",
        node_type=NodeType.FUNCTION,
        name="func",
        file_path="a.py",
        line_start=1,
        line_end=10,
    )
    edge = Edge(
        source="a.py::func",
        target="b.py::other",
        edge_type=EdgeType.CALLS,
        confidence=0.85,
        line=5,
    )
    subgraph = Subgraph(nodes=[node], edges=[edge])

    data = subgraph.to_dict()

    assert "nodes" in data
    assert "edges" in data
    assert len(data["nodes"]) == 1
    assert data["nodes"][0]["id"] == "a.py::func"
    assert data["edges"][0]["confidence"] == 0.85


def test_subgraph_to_context():
    """Subgraph formats as text for LLM consumption."""
    from oya.graph.models import Node, Edge, Subgraph, NodeType, EdgeType

    node1 = Node(
        id="auth/handler.py::login",
        node_type=NodeType.FUNCTION,
        name="login",
        file_path="auth/handler.py",
        line_start=10,
        line_end=25,
        docstring="Authenticate user credentials.",
    )
    node2 = Node(
        id="auth/session.py::create_session",
        node_type=NodeType.FUNCTION,
        name="create_session",
        file_path="auth/session.py",
        line_start=5,
        line_end=15,
    )
    edge = Edge(
        source="auth/handler.py::login",
        target="auth/session.py::create_session",
        edge_type=EdgeType.CALLS,
        confidence=0.9,
        line=20,
    )

    subgraph = Subgraph(nodes=[node1, node2], edges=[edge])
    context = subgraph.to_context()

    # Should contain node information
    assert "login" in context
    assert "create_session" in context
    assert "auth/handler.py" in context
    # Should describe relationships
    assert "calls" in context.lower()
