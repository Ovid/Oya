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
