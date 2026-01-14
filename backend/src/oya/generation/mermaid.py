"""Mermaid diagram generators for architecture documentation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from oya.generation.mermaid_validator import sanitize_label, sanitize_node_id

if TYPE_CHECKING:
    from oya.generation.summaries import SynthesisMap


class LayerDiagramGenerator:
    """Generates layer architecture diagrams from SynthesisMap.

    Creates a flowchart showing architectural layers as subgraphs
    with key components inside and dependency arrows between layers.
    """

    def generate(self, synthesis_map: SynthesisMap) -> str:
        """Generate a layer diagram from SynthesisMap.

        Args:
            synthesis_map: SynthesisMap with layers, components, and dependencies.

        Returns:
            Mermaid flowchart diagram string.
        """
        lines = ["flowchart TB"]

        if not synthesis_map.layers:
            lines.append("    NoLayers[No layers detected]")
            return "\n".join(lines)

        # Create subgraph for each layer
        for layer_name, layer_info in synthesis_map.layers.items():
            layer_id = sanitize_node_id(layer_name)
            layer_label = sanitize_label(f"{layer_name}: {layer_info.purpose}", max_length=50)

            lines.append(f'    subgraph {layer_id}["{layer_label}"]')

            # Add components belonging to this layer
            layer_components = [
                c for c in synthesis_map.key_components if c.layer == layer_name
            ]

            if layer_components:
                for comp in layer_components[:5]:  # Limit to 5 per layer
                    comp_id = sanitize_node_id(f"{layer_name}_{comp.name}")
                    comp_label = sanitize_label(comp.name)
                    lines.append(f'        {comp_id}["{comp_label}"]')
            else:
                # Add placeholder if no components
                placeholder_id = sanitize_node_id(f"{layer_name}_placeholder")
                lines.append(f"        {placeholder_id}[...]")

            lines.append("    end")

        # Add dependency arrows between layers
        for source, targets in synthesis_map.dependency_graph.items():
            source_id = sanitize_node_id(source)
            if isinstance(targets, list):
                for target in targets:
                    target_id = sanitize_node_id(target)
                    if source_id != target_id:
                        lines.append(f"    {source_id} --> {target_id}")

        return "\n".join(lines)


class DependencyGraphGenerator:
    """Generates file dependency graphs from import analysis.

    Creates a flowchart showing which files import from which other files.
    """

    def __init__(self, max_nodes: int = 30):
        """Initialize the generator.

        Args:
            max_nodes: Maximum number of nodes to include (prevents huge diagrams).
        """
        self.max_nodes = max_nodes

    def generate(self, file_imports: dict[str, list[str]]) -> str:
        """Generate a dependency graph from file imports.

        Args:
            file_imports: Dict mapping file paths to list of imported file paths.

        Returns:
            Mermaid flowchart diagram string.
        """
        lines = ["flowchart LR"]

        if not file_imports:
            lines.append("    NoFiles[No files analyzed]")
            return "\n".join(lines)

        # Collect all unique files and limit
        all_files = set(file_imports.keys())
        for imports in file_imports.values():
            all_files.update(imports)

        # Sort by number of connections (most connected first)
        file_connections = {}
        for f in all_files:
            incoming = sum(1 for imports in file_imports.values() if f in imports)
            outgoing = len(file_imports.get(f, []))
            file_connections[f] = incoming + outgoing

        sorted_files = sorted(all_files, key=lambda f: file_connections[f], reverse=True)
        included_files = set(sorted_files[: self.max_nodes])

        # Create nodes for included files
        for file_path in sorted(included_files):
            node_id = sanitize_node_id(file_path)
            # Use just the filename for label
            filename = file_path.split("/")[-1]
            label = sanitize_label(filename, max_length=30)
            lines.append(f'    {node_id}["{label}"]')

        # Add edges for imports between included files
        for source, imports in file_imports.items():
            if source not in included_files:
                continue
            source_id = sanitize_node_id(source)
            for target in imports:
                if target in included_files:
                    target_id = sanitize_node_id(target)
                    lines.append(f"    {source_id} --> {target_id}")

        return "\n".join(lines)
