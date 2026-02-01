"""Build NetworkX graph from parsed code files."""

import networkx as nx

from oya.parsing.models import ParsedFile, ParsedSymbol
from oya.graph.resolver import SymbolTable, resolve_references


def build_graph(parsed_files: list[ParsedFile]) -> nx.DiGraph:
    """Build a directed graph from parsed files.

    Args:
        parsed_files: List of parsed files with symbols and references.

    Returns:
        NetworkX directed graph with code entities as nodes and relationships as edges.
    """
    G = nx.DiGraph()

    # Build symbol table and resolve references
    symbol_table = SymbolTable.from_parsed_files(parsed_files)
    all_resolved_refs = []
    for file in parsed_files:
        resolved = resolve_references([file], symbol_table)
        all_resolved_refs.extend(resolved)

    # Add nodes for all symbols
    for file in parsed_files:
        for symbol in file.symbols:
            node_id = _make_node_id(file.path, symbol)
            G.add_node(
                node_id,
                name=symbol.name,
                type=symbol.symbol_type.value,
                file_path=file.path,
                line_start=symbol.start_line,
                line_end=symbol.end_line,
                docstring=symbol.docstring,
                signature=symbol.signature,
                parent=symbol.parent,
                is_entry_point=symbol.metadata.get("is_entry_point", False),
            )

    # Add edges for all resolved references
    for ref in all_resolved_refs:
        if ref.target_resolved:
            # Only add edges for resolved references where both nodes exist
            if G.has_node(ref.source) and G.has_node(ref.target):
                G.add_edge(
                    ref.source,
                    ref.target,
                    type=ref.reference_type.value,
                    confidence=ref.confidence,
                    line=ref.line,
                )
            elif G.has_node(ref.source):
                # Target node doesn't exist but reference is resolved
                # This can happen for external dependencies
                G.add_edge(
                    ref.source,
                    ref.target,
                    type=ref.reference_type.value,
                    confidence=ref.confidence,
                    line=ref.line,
                )

    return G


def _make_node_id(file_path: str, symbol: ParsedSymbol) -> str:
    """Create a unique node ID for a symbol."""
    if symbol.parent:
        return f"{file_path}::{symbol.parent}.{symbol.name}"
    return f"{file_path}::{symbol.name}"
