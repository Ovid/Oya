"""Tests for Mermaid diagram generators."""

import pytest

from oya.generation.mermaid import DependencyGraphGenerator, LayerDiagramGenerator
from oya.generation.mermaid_validator import validate_mermaid
from oya.generation.summaries import ComponentInfo, LayerInfo, SynthesisMap


class TestLayerDiagramGenerator:
    """Tests for LayerDiagramGenerator."""

    @pytest.fixture
    def sample_synthesis_map(self) -> SynthesisMap:
        """Create a sample SynthesisMap for testing."""
        return SynthesisMap(
            layers={
                "api": LayerInfo(
                    name="api",
                    purpose="HTTP endpoints",
                    directories=["src/api"],
                    files=["src/api/routes.py", "src/api/schemas.py"],
                ),
                "domain": LayerInfo(
                    name="domain",
                    purpose="Business logic",
                    directories=["src/domain"],
                    files=["src/domain/service.py"],
                ),
            },
            key_components=[
                ComponentInfo(name="Router", file="src/api/routes.py", role="HTTP routing", layer="api"),
                ComponentInfo(name="Service", file="src/domain/service.py", role="Core logic", layer="domain"),
            ],
            dependency_graph={"api": ["domain"]},
        )

    def test_generates_valid_mermaid(self, sample_synthesis_map):
        """Generated diagram passes Mermaid validation."""
        generator = LayerDiagramGenerator()
        diagram = generator.generate(sample_synthesis_map)

        result = validate_mermaid(diagram)
        assert result.valid, f"Invalid diagram: {result.errors}"

    def test_includes_all_layers(self, sample_synthesis_map):
        """All layers appear as subgraphs."""
        generator = LayerDiagramGenerator()
        diagram = generator.generate(sample_synthesis_map)

        assert "subgraph" in diagram.lower()
        assert "api" in diagram.lower()
        assert "domain" in diagram.lower()

    def test_includes_key_components(self, sample_synthesis_map):
        """Key components appear in the diagram."""
        generator = LayerDiagramGenerator()
        diagram = generator.generate(sample_synthesis_map)

        assert "Router" in diagram
        assert "Service" in diagram

    def test_includes_dependencies(self, sample_synthesis_map):
        """Layer dependencies are shown as arrows."""
        generator = LayerDiagramGenerator()
        diagram = generator.generate(sample_synthesis_map)

        # Should have an arrow showing api depends on domain
        assert "-->" in diagram

    def test_empty_synthesis_map_returns_minimal_diagram(self):
        """Empty input produces valid minimal diagram."""
        generator = LayerDiagramGenerator()
        diagram = generator.generate(SynthesisMap())

        result = validate_mermaid(diagram)
        assert result.valid


class TestDependencyGraphGenerator:
    """Tests for DependencyGraphGenerator."""

    @pytest.fixture
    def sample_file_imports(self) -> dict[str, list[str]]:
        """Sample file_imports dict from analysis."""
        return {
            "src/api/routes.py": ["src/domain/service.py", "src/config.py"],
            "src/domain/service.py": ["src/db/connection.py"],
            "src/config.py": [],
            "src/db/connection.py": [],
        }

    def test_generates_valid_mermaid(self, sample_file_imports):
        """Generated diagram passes Mermaid validation."""
        generator = DependencyGraphGenerator()
        diagram = generator.generate(sample_file_imports)

        result = validate_mermaid(diagram)
        assert result.valid, f"Invalid diagram: {result.errors}"

    def test_shows_import_relationships(self, sample_file_imports):
        """Import relationships appear as arrows."""
        generator = DependencyGraphGenerator()
        diagram = generator.generate(sample_file_imports)

        assert "-->" in diagram

    def test_includes_all_files(self, sample_file_imports):
        """All files appear in the diagram."""
        generator = DependencyGraphGenerator()
        diagram = generator.generate(sample_file_imports)

        assert "routes" in diagram.lower()
        assert "service" in diagram.lower()

    def test_empty_imports_returns_minimal_diagram(self):
        """Empty input produces valid minimal diagram."""
        generator = DependencyGraphGenerator()
        diagram = generator.generate({})

        result = validate_mermaid(diagram)
        assert result.valid

    def test_limits_nodes_for_large_graphs(self):
        """Large graphs are limited to prevent overwhelming diagrams."""
        large_imports = {f"file{i}.py": [f"file{i+1}.py"] for i in range(100)}
        generator = DependencyGraphGenerator(max_nodes=20)
        diagram = generator.generate(large_imports)

        # Should still be valid
        result = validate_mermaid(diagram)
        assert result.valid
