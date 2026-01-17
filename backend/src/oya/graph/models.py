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
