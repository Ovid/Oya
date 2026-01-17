"""Code graph construction and querying."""

from oya.graph.models import (
    Node,
    NodeType,
    Edge,
    EdgeType,
    Subgraph,
)
from oya.graph.builder import build_graph
from oya.graph.resolver import SymbolTable, resolve_references
from oya.graph.persistence import save_graph, load_graph
from oya.graph.query import (
    get_calls,
    get_callers,
    get_neighborhood,
    trace_flow,
    get_entry_points,
    get_leaf_nodes,
)

__all__ = [
    # Models
    "Node",
    "NodeType",
    "Edge",
    "EdgeType",
    "Subgraph",
    # Builder
    "build_graph",
    # Resolver
    "SymbolTable",
    "resolve_references",
    # Persistence
    "save_graph",
    "load_graph",
    # Query
    "get_calls",
    "get_callers",
    "get_neighborhood",
    "trace_flow",
    "get_entry_points",
    "get_leaf_nodes",
]
