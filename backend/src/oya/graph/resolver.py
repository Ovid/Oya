"""Cross-file reference resolution using symbol tables."""

from dataclasses import dataclass, field
from oya.parsing.models import ParsedFile, ParsedSymbol


@dataclass
class SymbolTable:
    """Index of all code definitions for reference resolution."""

    # Maps simple name -> list of fully qualified IDs
    _by_name: dict[str, list[str]] = field(default_factory=dict)
    # Maps qualified name (e.g., "User.save") -> list of fully qualified IDs
    _by_qualified: dict[str, list[str]] = field(default_factory=dict)
    # Maps full ID -> symbol metadata
    _symbols: dict[str, ParsedSymbol] = field(default_factory=dict)
    # Maps full ID -> file path
    _file_paths: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_parsed_files(cls, files: list[ParsedFile]) -> "SymbolTable":
        """Build symbol table from parsed files."""
        table = cls()

        for file in files:
            for symbol in file.symbols:
                # Build fully qualified ID
                if symbol.parent:
                    full_id = f"{file.path}::{symbol.parent}.{symbol.name}"
                    qualified_name = f"{symbol.parent}.{symbol.name}"
                else:
                    full_id = f"{file.path}::{symbol.name}"
                    qualified_name = symbol.name

                # Index by simple name
                if symbol.name not in table._by_name:
                    table._by_name[symbol.name] = []
                table._by_name[symbol.name].append(full_id)

                # Index by qualified name
                if qualified_name not in table._by_qualified:
                    table._by_qualified[qualified_name] = []
                table._by_qualified[qualified_name].append(full_id)

                # Store symbol and file path
                table._symbols[full_id] = symbol
                table._file_paths[full_id] = file.path

        return table

    def lookup(self, name: str) -> list[str]:
        """Look up symbol by name, returning all matching full IDs."""
        # Try qualified name first
        if name in self._by_qualified:
            return self._by_qualified[name]
        # Fall back to simple name
        return self._by_name.get(name, [])
