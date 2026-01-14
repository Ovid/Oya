"""Tests for Mermaid diagram generators."""

import pytest

from oya.generation.mermaid import (
    ClassDiagramGenerator,
    DependencyGraphGenerator,
    DiagramGenerator,
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


class TestDiagramGenerator:
    """Tests for DiagramGenerator facade."""

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

    @pytest.fixture
    def sample_file_imports(self) -> dict[str, list[str]]:
        """Sample file_imports dict from analysis."""
        return {
            "src/api/routes.py": ["src/domain/service.py", "src/config.py"],
            "src/domain/service.py": ["src/db/connection.py"],
            "src/config.py": [],
            "src/db/connection.py": [],
        }

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
        ]

    @pytest.fixture
    def sample_data(self, sample_synthesis_map, sample_file_imports, sample_symbols):
        """Combine all sample data."""
        return {
            "synthesis_map": sample_synthesis_map,
            "file_imports": sample_file_imports,
            "symbols": sample_symbols,
        }

    def test_generate_all_returns_dict_of_diagrams(self, sample_data):
        """generate_all returns dict with all diagram types."""
        generator = DiagramGenerator()
        diagrams = generator.generate_all(
            synthesis_map=sample_data["synthesis_map"],
            file_imports=sample_data["file_imports"],
            symbols=sample_data["symbols"],
        )

        assert "layer" in diagrams
        assert "dependency" in diagrams
        assert "class" in diagrams

    def test_all_generated_diagrams_are_valid(self, sample_data):
        """All generated diagrams pass validation."""
        generator = DiagramGenerator()
        diagrams = generator.generate_all(
            synthesis_map=sample_data["synthesis_map"],
            file_imports=sample_data["file_imports"],
            symbols=sample_data["symbols"],
        )

        for name, diagram in diagrams.items():
            result = validate_mermaid(diagram)
            assert result.valid, f"{name} diagram invalid: {result.errors}"

    def test_handles_missing_data_gracefully(self):
        """Missing data produces valid minimal diagrams."""
        generator = DiagramGenerator()
        diagrams = generator.generate_all(
            synthesis_map=None,
            file_imports={},
            symbols=[],
        )

        for name, diagram in diagrams.items():
            result = validate_mermaid(diagram)
            assert result.valid, f"{name} diagram invalid: {result.errors}"


class TestDependencyGraphGeneratorForFile:
    """Tests for single-file dependency diagram generation."""

    @pytest.fixture
    def sample_imports(self) -> dict[str, list[str]]:
        """Create sample import data."""
        return {
            "src/api/routes.py": ["src/domain/service.py", "src/utils/helpers.py"],
            "src/domain/service.py": ["src/db/models.py"],
            "src/utils/helpers.py": [],
            "src/db/models.py": [],
            "src/other/unrelated.py": ["src/other/another.py"],
            "src/isolated/standalone.py": [],  # Isolated file: nothing imports it
        }

    def test_generate_for_file_shows_imports(self, sample_imports):
        """Diagram shows files that target imports."""
        generator = DependencyGraphGenerator()
        diagram = generator.generate_for_file("src/api/routes.py", sample_imports)

        # Should show the file imports
        assert "service" in diagram.lower()
        assert "helpers" in diagram.lower()

    def test_generate_for_file_shows_importers(self, sample_imports):
        """Diagram shows files that import the target."""
        generator = DependencyGraphGenerator()
        diagram = generator.generate_for_file("src/domain/service.py", sample_imports)

        # routes.py imports service.py, so routes should appear
        assert "routes" in diagram.lower()

    def test_generate_for_file_excludes_unrelated(self, sample_imports):
        """Diagram excludes files with no relationship to target."""
        generator = DependencyGraphGenerator()
        diagram = generator.generate_for_file("src/api/routes.py", sample_imports)

        # other/unrelated.py has no relationship to routes.py
        assert "unrelated" not in diagram.lower()
        assert "another" not in diagram.lower()

    def test_generate_for_file_valid_mermaid(self, sample_imports):
        """Generated diagram is valid Mermaid."""
        generator = DependencyGraphGenerator()
        diagram = generator.generate_for_file("src/api/routes.py", sample_imports)

        result = validate_mermaid(diagram)
        assert result.valid, f"Invalid diagram: {result.errors}"

    def test_generate_for_file_shows_importer_only(self, sample_imports):
        """Diagram shows importers even when file has no imports itself."""
        generator = DependencyGraphGenerator()
        # models.py has no imports, but service.py imports it
        diagram = generator.generate_for_file("src/db/models.py", sample_imports)

        # Should show service as an importer of models
        assert "service" in diagram.lower()

    def test_generate_for_file_empty_when_no_deps(self, sample_imports):
        """Returns empty string for file with no dependencies."""
        generator = DependencyGraphGenerator()
        # standalone.py has no imports AND nothing imports it
        diagram = generator.generate_for_file("src/isolated/standalone.py", sample_imports)

        # Should return empty string for files with no relationships
        assert diagram == ""

    def test_generate_for_file_unknown_file(self, sample_imports):
        """Returns empty string for unknown file."""
        generator = DependencyGraphGenerator()
        diagram = generator.generate_for_file("src/unknown/file.py", sample_imports)

        # Should return empty string for unknown files
        assert diagram == ""
