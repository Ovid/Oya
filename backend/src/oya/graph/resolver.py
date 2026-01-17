"""Cross-file reference resolution using symbol tables."""

from dataclasses import dataclass, field
from oya.parsing.models import ParsedFile, ParsedSymbol, Reference


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


def resolve_references(
    files: list[ParsedFile],
    symbol_table: SymbolTable,
) -> list[Reference]:
    """Resolve references against the symbol table.

    Args:
        files: Parsed files containing unresolved references.
        symbol_table: Symbol table built from all parsed files.

    Returns:
        List of resolved (or attempted) references.
    """
    resolved = []

    for file in files:
        for ref in file.references:
            if ref.target_resolved:
                # Already resolved
                resolved.append(ref)
                continue

            # Look up target in symbol table
            candidates = symbol_table.lookup(ref.target)

            if len(candidates) == 1:
                # Exact match - high confidence
                resolved.append(
                    Reference(
                        source=ref.source,
                        target=candidates[0],
                        reference_type=ref.reference_type,
                        confidence=ref.confidence,  # Maintain original confidence
                        line=ref.line,
                        target_resolved=True,
                    )
                )
            elif len(candidates) > 1:
                # Ambiguous - create multiple refs with reduced confidence
                for candidate in candidates:
                    resolved.append(
                        Reference(
                            source=ref.source,
                            target=candidate,
                            reference_type=ref.reference_type,
                            confidence=ref.confidence * 0.5,  # Reduce confidence
                            line=ref.line,
                            target_resolved=True,
                        )
                    )
            else:
                # No match - keep unresolved with low confidence
                resolved.append(
                    Reference(
                        source=ref.source,
                        target=ref.target,
                        reference_type=ref.reference_type,
                        confidence=ref.confidence * 0.3,  # Significantly reduce
                        line=ref.line,
                        target_resolved=False,
                    )
                )

    return resolved
