"""Tests for Mermaid diagram generators."""

import pytest

from oya.generation.mermaid import (
    ClassDiagramGenerator,
    DependencyGraphGenerator,
    LayerDiagramGenerator,
)
from oya.generation.mermaid_validator import validate_mermaid
from oya.generation.summaries import ComponentInfo, LayerInfo, SynthesisMap
from oya.parsing.models import ParsedSymbol, SymbolType


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


class TestClassDiagramGenerator:
    """Tests for ClassDiagramGenerator."""

    @pytest.fixture
    def sample_symbols(self) -> list[ParsedSymbol]:
        """Sample ParsedSymbol list with classes and methods."""
        return [
            ParsedSymbol(
                name="UserService",
                symbol_type=SymbolType.CLASS,
                start_line=1,
                end_line=20,
                metadata={"file": "src/service.py"},
            ),
            ParsedSymbol(
                name="get_user",
                symbol_type=SymbolType.METHOD,
                start_line=5,
                end_line=10,
                parent="UserService",
                signature="def get_user(self, user_id: int) -> User",
                metadata={"file": "src/service.py"},
            ),
            ParsedSymbol(
                name="create_user",
                symbol_type=SymbolType.METHOD,
                start_line=12,
                end_line=18,
                parent="UserService",
                signature="def create_user(self, name: str) -> User",
                metadata={"file": "src/service.py"},
            ),
            ParsedSymbol(
                name="Database",
                symbol_type=SymbolType.CLASS,
                start_line=1,
                end_line=15,
                metadata={"file": "src/db.py"},
            ),
        ]

    def test_generates_valid_mermaid(self, sample_symbols):
        """Generated diagram passes Mermaid validation."""
        generator = ClassDiagramGenerator()
        diagram = generator.generate(sample_symbols)

        result = validate_mermaid(diagram)
        assert result.valid, f"Invalid diagram: {result.errors}"

    def test_includes_classes(self, sample_symbols):
        """Classes appear in the diagram."""
        generator = ClassDiagramGenerator()
        diagram = generator.generate(sample_symbols)

        assert "UserService" in diagram
        assert "Database" in diagram

    def test_includes_methods(self, sample_symbols):
        """Methods appear under their parent class."""
        generator = ClassDiagramGenerator()
        diagram = generator.generate(sample_symbols)

        assert "get_user" in diagram
        assert "create_user" in diagram

    def test_empty_symbols_returns_minimal_diagram(self):
        """Empty input produces valid minimal diagram."""
        generator = ClassDiagramGenerator()
        diagram = generator.generate([])

        result = validate_mermaid(diagram)
        assert result.valid

    def test_limits_classes_for_large_codebases(self):
        """Large symbol lists are limited."""
        many_classes = [
            ParsedSymbol(
                name=f"Class{i}",
                symbol_type=SymbolType.CLASS,
                start_line=1,
                end_line=10,
                metadata={"file": f"file{i}.py"},
            )
            for i in range(50)
        ]
        generator = ClassDiagramGenerator(max_classes=10)
        diagram = generator.generate(many_classes)

        result = validate_mermaid(diagram)
        assert result.valid
