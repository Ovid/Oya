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
class CallSite:
    """Location where a symbol is called from."""

    caller_file: str  # File containing the call
    caller_symbol: str  # Function/method making the call
    line: int  # Exact line of the call
    target_symbol: str  # What's being called


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

    def to_context(self) -> str:
        """Format subgraph as text for LLM consumption."""
        lines = ["## Code Graph Context\n"]

        # Describe nodes
        lines.append("### Entities\n")
        for node in self.nodes:
            node_desc = (
                f"- **{node.name}** ({node.node_type.value}) "
                f"in `{node.file_path}` (lines {node.line_start}-{node.line_end})"
            )
            if node.docstring:
                node_desc += f"\n  > {node.docstring}"
            lines.append(node_desc)

        # Describe relationships
        if self.edges:
            lines.append("\n### Relationships\n")
            for edge in self.edges:
                source_name = edge.source.split("::")[-1] if "::" in edge.source else edge.source
                target_name = edge.target.split("::")[-1] if "::" in edge.target else edge.target
                lines.append(
                    f"- `{source_name}` **{edge.edge_type.value}** `{target_name}` "
                    f"(confidence: {edge.confidence:.0%})"
                )

        return "\n".join(lines)

    def to_mermaid(self) -> str:
        """Generate deterministic Mermaid flowchart from subgraph."""
        lines = ["flowchart TD"]

        # Create stable node IDs (sanitize for Mermaid)
        def sanitize_id(node_id: str) -> str:
            return node_id.replace("/", "_").replace("::", "_").replace(".", "_").replace("-", "_")

        # Sort for determinism
        sorted_nodes = sorted(self.nodes, key=lambda n: n.id)
        sorted_edges = sorted(self.edges, key=lambda e: (e.source, e.target))

        # Add node definitions with shapes based on type
        for node in sorted_nodes:
            safe_id = sanitize_id(node.id)
            if node.node_type == NodeType.CLASS:
                lines.append(f"    {safe_id}[{node.name}]")
            elif node.node_type == NodeType.FUNCTION:
                lines.append(f"    {safe_id}({node.name})")
            elif node.node_type == NodeType.METHOD:
                lines.append(f"    {safe_id}({node.name})")
            else:
                lines.append(f"    {safe_id}[{node.name}]")

        # Add edges with appropriate arrow styles
        edge_styles = {
            EdgeType.CALLS: "-->",
            EdgeType.INSTANTIATES: "-.->",
            EdgeType.INHERITS: "-->|inherits|",
            EdgeType.IMPORTS: "-.->|imports|",
        }
        for edge in sorted_edges:
            source_id = sanitize_id(edge.source)
            target_id = sanitize_id(edge.target)
            arrow = edge_styles.get(edge.edge_type, "-->")
            lines.append(f"    {source_id} {arrow} {target_id}")

        return "\n".join(lines)
