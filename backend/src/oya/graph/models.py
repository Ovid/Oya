"""Data models for the code knowledge graph."""

from dataclasses import dataclass, field
from enum import Enum


class NodeType(Enum):
    """Types of nodes in the code graph."""

    FUNCTION = "function"
    CLASS = "class"
    METHOD = "method"
    FILE = "file"
    MODULE = "module"


@dataclass
class Node:
    """A node in the code graph representing a code entity."""

    id: str  # Unique identifier, e.g., "path/to/file.py::ClassName.method_name"
    node_type: NodeType
    name: str
    file_path: str
    line_start: int
    line_end: int
    docstring: str | None = None
    signature: str | None = None
    metadata: dict = field(default_factory=dict)


class EdgeType(Enum):
    """Types of edges (relationships) in the code graph."""

    CALLS = "calls"
    INSTANTIATES = "instantiates"
    INHERITS = "inherits"
    IMPORTS = "imports"


@dataclass
class Edge:
    """An edge in the code graph representing a relationship."""

    source: str  # Source node ID
    target: str  # Target node ID
    edge_type: EdgeType
    confidence: float  # 0.0 to 1.0
    line: int  # Line number where relationship occurs
    metadata: dict = field(default_factory=dict)


@dataclass
class Subgraph:
    """A subset of the code graph (nodes and edges)."""

    nodes: list[Node]
    edges: list[Edge]

    def to_dict(self) -> dict:
        """Serialize to dictionary for JSON output."""
        return {
            "nodes": [
                {
                    "id": n.id,
                    "type": n.node_type.value,
                    "name": n.name,
                    "file_path": n.file_path,
                    "line_start": n.line_start,
                    "line_end": n.line_end,
                    "docstring": n.docstring,
                    "signature": n.signature,
                    "metadata": n.metadata,
                }
                for n in self.nodes
            ],
            "edges": [
                {
                    "source": e.source,
                    "target": e.target,
                    "type": e.edge_type.value,
                    "confidence": e.confidence,
                    "line": e.line,
                    "metadata": e.metadata,
                }
                for e in self.edges
            ],
        }
