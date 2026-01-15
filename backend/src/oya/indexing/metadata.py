"""Metadata extraction for wiki chunks."""

from typing import Any

from oya.generation.summaries import SynthesisMap


class MetadataExtractor:
    """Extracts metadata for wiki chunks from analysis data."""

    def __init__(
        self,
        synthesis_map: SynthesisMap | None = None,
        symbols: list[dict[str, Any]] | None = None,
        file_imports: dict[str, list[str]] | None = None,
    ) -> None:
        self._synthesis_map = synthesis_map
        self._symbols = symbols or []
        self._file_imports = file_imports or {}

        # Build file-to-layer index
        self._file_to_layer: dict[str, str] = {}
        if synthesis_map:
            for layer_name, layer_info in synthesis_map.layers.items():
                for file_path in layer_info.files:
                    self._file_to_layer[file_path] = layer_name

        # Build file-to-symbols index
        self._file_to_symbols: dict[str, list[str]] = {}
        for sym in self._symbols:
            file_path = sym.get("file", "")
            name = sym.get("name", "")
            if file_path and name:
                if file_path not in self._file_to_symbols:
                    self._file_to_symbols[file_path] = []
                self._file_to_symbols[file_path].append(name)

    def get_layer_for_file(self, source_file: str) -> str:
        """Get architectural layer for a source file."""
        return self._file_to_layer.get(source_file, "")

    def get_symbols_for_file(self, source_file: str) -> list[str]:
        """Get all symbols defined in a source file."""
        return self._file_to_symbols.get(source_file, [])

    def get_symbols_in_content(self, source_file: str, content: str) -> list[str]:
        """Get symbols from a file that appear in the given content."""
        file_symbols = self.get_symbols_for_file(source_file)
        return [sym for sym in file_symbols if sym in content]

    def get_imports_for_file(self, source_file: str) -> list[str]:
        """Get imports for a source file."""
        return self._file_imports.get(source_file, [])

    def get_entry_points_for_file(self, source_file: str) -> list[str]:
        """Get entry points defined in a source file."""
        if not self._synthesis_map or not self._synthesis_map.entry_points:
            return []

        entry_points: list[str] = []
        for ep in self._synthesis_map.entry_points:
            if ep.file == source_file:
                if ep.description:
                    entry_points.append(f"{ep.entry_type.upper()} {ep.description}")
                else:
                    entry_points.append(ep.name)

        return entry_points
