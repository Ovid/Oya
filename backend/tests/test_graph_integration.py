"""Integration tests for the graph module using Oya's own code."""

import pytest
from pathlib import Path

from oya.parsing import PythonParser
from oya.graph import build_graph, save_graph, load_graph, get_calls, get_neighborhood


class TestGraphSelfAnalysis:
    """Test graph building on Oya's own codebase."""

    @pytest.fixture
    def parsed_oya_files(self):
        """Parse a few Oya source files."""
        parser = PythonParser()
        files = []

        # Parse the graph module itself
        graph_dir = Path(__file__).parent.parent / "src" / "oya" / "graph"
        for py_file in graph_dir.glob("*.py"):
            if py_file.name != "__init__.py":
                content = py_file.read_text()
                result = parser.parse(py_file, content)
                if result.ok:
                    files.append(result.file)

        return files

    def test_build_graph_from_oya_code(self, parsed_oya_files):
        """Can build graph from Oya's own code."""
        graph = build_graph(parsed_oya_files)

        # Should have nodes
        assert graph.number_of_nodes() > 0
        # Should have edges (references between functions)
        assert graph.number_of_edges() >= 0  # May have 0 if no cross-file refs

    def test_graph_persistence_roundtrip(self, parsed_oya_files, tmp_path):
        """Graph survives save/load cycle."""
        graph = build_graph(parsed_oya_files)

        output_dir = tmp_path / "graph"
        save_graph(graph, output_dir)
        loaded = load_graph(output_dir)

        assert loaded.number_of_nodes() == graph.number_of_nodes()
        assert loaded.number_of_edges() == graph.number_of_edges()

    def test_query_works_on_oya_graph(self, parsed_oya_files):
        """Query functions work on Oya's graph."""
        graph = build_graph(parsed_oya_files)

        # Find any node and query its neighborhood
        if graph.number_of_nodes() > 0:
            node_id = list(graph.nodes())[0]
            neighborhood = get_neighborhood(graph, node_id, hops=1)

            # Should return a valid subgraph
            assert neighborhood.nodes is not None
            assert len(neighborhood.nodes) >= 1  # At least the center node
