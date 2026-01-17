"""Integration tests for graph-based architecture generation."""

import pytest
from pathlib import Path

from oya.parsing import PythonParser
from oya.graph import build_graph, save_graph, load_graph
from oya.generation.graph_architecture import GraphArchitectureGenerator


class TestGraphArchitectureIntegration:
    """Test graph architecture generation on real code."""

    @pytest.fixture
    def parsed_oya_files(self):
        """Parse Oya's own graph module."""
        parser = PythonParser()
        files = []

        graph_dir = Path(__file__).parent.parent / "src" / "oya" / "graph"
        for py_file in graph_dir.glob("*.py"):
            if py_file.name != "__init__.py":
                content = py_file.read_text()
                result = parser.parse(py_file, content)
                if result.ok:
                    files.append(result.file)

        return files

    @pytest.fixture
    def oya_graph(self, parsed_oya_files):
        """Build graph from Oya code."""
        return build_graph(parsed_oya_files)

    @pytest.mark.asyncio
    async def test_generates_architecture_from_oya_graph(self, oya_graph):
        """Can generate architecture page from Oya's own code graph."""
        from unittest.mock import AsyncMock

        mock_llm = AsyncMock()
        mock_llm.generate.return_value = """# Architecture

The graph module provides code analysis capabilities.

## Components

The module is organized into several sub-components for different concerns.
"""

        generator = GraphArchitectureGenerator(mock_llm)

        page = await generator.generate(
            repo_name="oya",
            graph=oya_graph,
            component_summaries={},
        )

        # Verify output structure
        assert page.page_type == "architecture"
        assert "```mermaid" in page.content
        assert "flowchart" in page.content

    def test_graph_persistence_for_architecture(self, oya_graph, tmp_path):
        """Graph can be saved and loaded for architecture generation."""
        graph_dir = tmp_path / "graph"
        save_graph(oya_graph, graph_dir)

        loaded = load_graph(graph_dir)

        assert loaded.number_of_nodes() == oya_graph.number_of_nodes()
        assert loaded.number_of_edges() == oya_graph.number_of_edges()
