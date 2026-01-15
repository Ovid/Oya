"""Tests for metadata extraction."""

from oya.indexing.metadata import MetadataExtractor
from oya.generation.summaries import SynthesisMap, LayerInfo, EntryPointInfo


class TestMetadataExtractor:
    """Tests for MetadataExtractor."""

    def test_extracts_layer_from_synthesis_map(self):
        """Maps source file to architectural layer."""
        synthesis_map = SynthesisMap(
            layers={
                "api": LayerInfo(name="api", purpose="HTTP endpoints", files=["src/api/routes.py"]),
                "domain": LayerInfo(name="domain", purpose="Business logic", files=["src/auth/service.py"]),
            },
        )

        extractor = MetadataExtractor(synthesis_map=synthesis_map)
        layer = extractor.get_layer_for_file("src/auth/service.py")

        assert layer == "domain"

    def test_extracts_symbols_from_analysis(self):
        """Gets symbols for source file from analysis data."""
        analysis_symbols = [
            {"name": "authenticate", "type": "function", "file": "src/auth/service.py"},
            {"name": "User", "type": "class", "file": "src/auth/service.py"},
            {"name": "other_func", "type": "function", "file": "src/other.py"},
        ]

        extractor = MetadataExtractor(symbols=analysis_symbols)
        symbols = extractor.get_symbols_for_file("src/auth/service.py")

        assert "authenticate" in symbols
        assert "User" in symbols
        assert "other_func" not in symbols

    def test_filters_symbols_to_chunk_content(self):
        """Only includes symbols that appear in chunk text."""
        analysis_symbols = [
            {"name": "authenticate", "type": "function", "file": "src/auth/service.py"},
            {"name": "User", "type": "class", "file": "src/auth/service.py"},
            {"name": "validate", "type": "function", "file": "src/auth/service.py"},
        ]

        extractor = MetadataExtractor(symbols=analysis_symbols)
        chunk_content = "The authenticate function handles login."
        symbols = extractor.get_symbols_in_content("src/auth/service.py", chunk_content)

        assert "authenticate" in symbols
        assert "User" not in symbols  # Not mentioned in content
        assert "validate" not in symbols

    def test_extracts_imports_from_analysis(self):
        """Gets imports for source file."""
        file_imports = {
            "src/auth/service.py": ["bcrypt", "src/models/user.py"],
            "src/other.py": ["requests"],
        }

        extractor = MetadataExtractor(file_imports=file_imports)
        imports = extractor.get_imports_for_file("src/auth/service.py")

        assert "bcrypt" in imports
        assert "src/models/user.py" in imports
        assert "requests" not in imports

    def test_extracts_entry_points(self):
        """Gets entry points for source file."""
        synthesis_map = SynthesisMap(
            entry_points=[
                EntryPointInfo(name="login", entry_type="api_route", file="src/auth/routes.py", description="/login"),
                EntryPointInfo(name="logout", entry_type="api_route", file="src/auth/routes.py", description="/logout"),
                EntryPointInfo(name="health", entry_type="api_route", file="src/health.py", description="/health"),
            ],
        )

        extractor = MetadataExtractor(synthesis_map=synthesis_map)
        entry_points = extractor.get_entry_points_for_file("src/auth/routes.py")

        assert len(entry_points) == 2
