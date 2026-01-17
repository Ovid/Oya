"""Tests for graph persistence to JSON."""

import json
import pytest
from pathlib import Path
import networkx as nx


def test_save_graph_creates_files(tmp_path):
    """save_graph creates nodes.json, edges.json, and metadata.json."""
    from oya.graph.persistence import save_graph

    G = nx.DiGraph()
    G.add_node("a.py::func", name="func", type="function", file_path="a.py",
               line_start=1, line_end=10, docstring=None, signature=None, parent=None)
    G.add_edge("a.py::func", "b.py::other", type="calls", confidence=0.9, line=5)

    output_dir = tmp_path / ".oyawiki" / "graph"
    save_graph(G, output_dir)

    assert (output_dir / "nodes.json").exists()
    assert (output_dir / "edges.json").exists()
    assert (output_dir / "metadata.json").exists()


def test_save_graph_nodes_format(tmp_path):
    """nodes.json contains correct node data."""
    from oya.graph.persistence import save_graph

    G = nx.DiGraph()
    G.add_node("models/user.py::User", name="User", type="class",
               file_path="models/user.py", line_start=5, line_end=50,
               docstring="A user entity.", signature=None, parent=None)

    output_dir = tmp_path / "graph"
    save_graph(G, output_dir)

    with open(output_dir / "nodes.json") as f:
        nodes = json.load(f)

    assert len(nodes) == 1
    assert nodes[0]["id"] == "models/user.py::User"
    assert nodes[0]["name"] == "User"
    assert nodes[0]["type"] == "class"
    assert nodes[0]["docstring"] == "A user entity."


def test_save_graph_edges_format(tmp_path):
    """edges.json contains correct edge data."""
    from oya.graph.persistence import save_graph

    G = nx.DiGraph()
    G.add_node("a.py::func", name="func", type="function", file_path="a.py",
               line_start=1, line_end=10, docstring=None, signature=None, parent=None)
    G.add_node("b.py::other", name="other", type="function", file_path="b.py",
               line_start=1, line_end=5, docstring=None, signature=None, parent=None)
    G.add_edge("a.py::func", "b.py::other", type="calls", confidence=0.85, line=7)

    output_dir = tmp_path / "graph"
    save_graph(G, output_dir)

    with open(output_dir / "edges.json") as f:
        edges = json.load(f)

    assert len(edges) == 1
    assert edges[0]["source"] == "a.py::func"
    assert edges[0]["target"] == "b.py::other"
    assert edges[0]["type"] == "calls"
    assert edges[0]["confidence"] == 0.85


def test_save_graph_metadata(tmp_path):
    """metadata.json contains build information."""
    from oya.graph.persistence import save_graph

    G = nx.DiGraph()
    G.add_node("a.py::func", name="func", type="function", file_path="a.py",
               line_start=1, line_end=10, docstring=None, signature=None, parent=None)

    output_dir = tmp_path / "graph"
    save_graph(G, output_dir)

    with open(output_dir / "metadata.json") as f:
        metadata = json.load(f)

    assert "build_timestamp" in metadata
    assert metadata["node_count"] == 1
    assert metadata["edge_count"] == 0


def test_load_graph_roundtrip(tmp_path):
    """load_graph reconstructs the saved graph."""
    from oya.graph.persistence import save_graph, load_graph

    G = nx.DiGraph()
    G.add_node("a.py::func", name="func", type="function", file_path="a.py",
               line_start=1, line_end=10, docstring="A function.", signature="def func():", parent=None)
    G.add_node("b.py::other", name="other", type="function", file_path="b.py",
               line_start=1, line_end=5, docstring=None, signature=None, parent=None)
    G.add_edge("a.py::func", "b.py::other", type="calls", confidence=0.85, line=7)

    output_dir = tmp_path / "graph"
    save_graph(G, output_dir)

    loaded = load_graph(output_dir)

    # Same nodes
    assert set(loaded.nodes()) == set(G.nodes())
    # Same edges
    assert set(loaded.edges()) == set(G.edges())
    # Node attributes preserved
    assert loaded.nodes["a.py::func"]["docstring"] == "A function."
    # Edge attributes preserved
    assert loaded.edges["a.py::func", "b.py::other"]["confidence"] == 0.85


def test_load_graph_missing_dir_returns_empty():
    """load_graph returns empty graph for missing directory."""
    from oya.graph.persistence import load_graph

    loaded = load_graph(Path("/nonexistent/path"))

    assert loaded.number_of_nodes() == 0
    assert loaded.number_of_edges() == 0
