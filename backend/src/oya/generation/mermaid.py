"""Mermaid diagram generators for architecture documentation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from oya.generation.mermaid_validator import sanitize_label, sanitize_node_id

if TYPE_CHECKING:
    from oya.generation.summaries import SynthesisMap
    from oya.parsing.models import ParsedSymbol


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
