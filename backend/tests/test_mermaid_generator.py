"""Tests for Mermaid diagram generators."""

import pytest

from oya.generation.mermaid import LayerDiagramGenerator
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
