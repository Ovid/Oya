"""Mermaid diagram generators for architecture documentation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from oya.generation.mermaid_validator import sanitize_label, sanitize_node_id
from oya.parsing.models import ParsedSymbol, SymbolType

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


class ClassDiagramGenerator:
    """Generates class diagrams from parsed symbols.

    Creates a classDiagram showing classes and their methods.
    """

    def __init__(self, max_classes: int = 15, max_methods_per_class: int = 5):
        """Initialize the generator.

        Args:
            max_classes: Maximum number of classes to include.
            max_methods_per_class: Maximum methods to show per class.
        """
        self.max_classes = max_classes
        self.max_methods_per_class = max_methods_per_class

    def generate(self, symbols: list[ParsedSymbol]) -> str:
        """Generate a class diagram from parsed symbols.

        Args:
            symbols: List of ParsedSymbol objects from parsing.

        Returns:
            Mermaid classDiagram string.
        """
        lines = ["classDiagram"]

        # Extract classes and their methods
        classes = [s for s in symbols if s.symbol_type == SymbolType.CLASS]
        methods = [s for s in symbols if s.symbol_type == SymbolType.METHOD]

        if not classes:
            lines.append("    class NoClasses {")
            lines.append("        No classes found")
            lines.append("    }")
            return "\n".join(lines)

        # Group methods by parent class
        methods_by_class: dict[str, list[ParsedSymbol]] = {}
        for method in methods:
            if method.parent:
                methods_by_class.setdefault(method.parent, []).append(method)

        # Generate class definitions (limited)
        for cls in classes[: self.max_classes]:
            class_name = sanitize_node_id(cls.name)
            lines.append(f"    class {class_name} {{")

            # Add methods for this class
            cls_methods = methods_by_class.get(cls.name, [])
            for method in cls_methods[: self.max_methods_per_class]:
                method_name = sanitize_label(method.name, max_length=30)
                # Extract simple signature if available
                if method.signature:
                    # Simplify signature for display
                    sig = method.signature.replace("def ", "").replace("self, ", "")
                    sig = sanitize_label(sig, max_length=40)
                    lines.append(f"        +{sig}")
                else:
                    lines.append(f"        +{method_name}()")

            if not cls_methods:
                lines.append("        ...")

            lines.append("    }")

        return "\n".join(lines)


class DiagramGenerator:
    """Facade for generating all diagram types.

    Provides a single interface to generate layer, dependency,
    and class diagrams from analysis data.
    """

    def __init__(self):
        """Initialize with default sub-generators."""
        self.layer_generator = LayerDiagramGenerator()
        self.dependency_generator = DependencyGraphGenerator()
        self.class_generator = ClassDiagramGenerator()

    def generate_all(
        self,
        synthesis_map: SynthesisMap | None = None,
        file_imports: dict[str, list[str]] | None = None,
        symbols: list[ParsedSymbol] | None = None,
    ) -> dict[str, str]:
        """Generate all diagram types from available data.

        Args:
            synthesis_map: SynthesisMap for layer diagram (optional).
            file_imports: File import dict for dependency diagram (optional).
            symbols: ParsedSymbol list for class diagram (optional).

        Returns:
            Dict mapping diagram name to Mermaid content.
        """
        from oya.generation.summaries import SynthesisMap as SynthesisMapClass

        diagrams = {}

        # Layer diagram
        if synthesis_map is not None:
            diagrams["layer"] = self.layer_generator.generate(synthesis_map)
        else:
            diagrams["layer"] = self.layer_generator.generate(SynthesisMapClass())

        # Dependency diagram
        diagrams["dependency"] = self.dependency_generator.generate(file_imports or {})

        # Class diagram
        diagrams["class"] = self.class_generator.generate(symbols or [])

        return diagrams
