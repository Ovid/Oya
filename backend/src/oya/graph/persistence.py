"""Persist graph to JSON files in .oyawiki/graph/."""

import json
from datetime import datetime, timezone
from pathlib import Path

import networkx as nx


def save_graph(graph: nx.DiGraph, output_dir: Path) -> None:
    """Save graph to JSON files.

    Creates:
        - nodes.json: All node definitions
        - edges.json: All edges with confidence
        - metadata.json: Build timestamp and stats

    Args:
        graph: NetworkX directed graph to persist.
        output_dir: Directory to write files to (e.g., .oyawiki/graph/).
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Serialize nodes
    nodes = []
    for node_id, attrs in graph.nodes(data=True):
        nodes.append({
            "id": node_id,
            "name": attrs.get("name"),
            "type": attrs.get("type"),
            "file_path": attrs.get("file_path"),
            "line_start": attrs.get("line_start"),
            "line_end": attrs.get("line_end"),
            "docstring": attrs.get("docstring"),
            "signature": attrs.get("signature"),
            "parent": attrs.get("parent"),
        })

    # Sort for determinism
    nodes.sort(key=lambda n: n["id"])

    with open(output_dir / "nodes.json", "w") as f:
        json.dump(nodes, f, indent=2)

    # Serialize edges
    edges = []
    for source, target, attrs in graph.edges(data=True):
        edges.append({
            "source": source,
            "target": target,
            "type": attrs.get("type"),
            "confidence": attrs.get("confidence"),
            "line": attrs.get("line"),
        })

    # Sort for determinism
    edges.sort(key=lambda e: (e["source"], e["target"]))

    with open(output_dir / "edges.json", "w") as f:
        json.dump(edges, f, indent=2)

    # Write metadata
    metadata = {
        "build_timestamp": datetime.now(timezone.utc).isoformat(),
        "node_count": graph.number_of_nodes(),
        "edge_count": graph.number_of_edges(),
    }

    with open(output_dir / "metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)
