"""Mermaid diagram generators for architecture documentation."""

from __future__ import annotations

from oya.generation.mermaid_validator import sanitize_label, sanitize_node_id
from oya.generation.summaries import SynthesisMap
from oya.parsing.models import ParsedSymbol, SymbolType


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
            layer_label = sanitize_label(layer_name.capitalize())

            lines.append(f'    subgraph {layer_id}["{layer_label}"]')

            # Add components belonging to this layer
            layer_components = [c for c in synthesis_map.key_components if c.layer == layer_name]

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

    @staticmethod
    def is_useful(diagram: str) -> bool:
        """Check if a layer diagram adds value.

        Returns False if:
        - Contains "NoLayers" placeholder
        - Has only one subgraph (single layer)
        - Has no edges between layers

        Args:
            diagram: The generated Mermaid diagram string.

        Returns:
            True if the diagram is worth including.
        """
        if "NoLayers" in diagram or "No layers" in diagram:
            return False

        # Count subgraphs - need multiple layers to be useful
        subgraph_count = diagram.lower().count("subgraph ")
        if subgraph_count <= 1:
            return False

        # Must have edges between layers
        return "-->" in diagram


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

    def generate_for_file(self, file_path: str, all_imports: dict[str, list[str]]) -> str:
        """Generate a dependency diagram focused on a single file.

        Shows:
        - What this file imports (outgoing edges)
        - What files import this file (incoming edges)

        Args:
            file_path: The file to focus on.
            all_imports: Dict mapping all file paths to their imports.

        Returns:
            Mermaid diagram string, or empty string if no dependencies.
        """
        if file_path not in all_imports:
            # Check if anything imports this file
            has_importers = any(file_path in imports for imports in all_imports.values())
            if not has_importers:
                return ""

        # Collect related files: imports and importers
        imports = set(all_imports.get(file_path, []))
        importers = {f for f, imp_list in all_imports.items() if file_path in imp_list}

        related_files = imports | importers | {file_path}

        if len(related_files) <= 1:
            return ""

        lines = ["flowchart LR"]

        # Create nodes for all related files
        for fp in sorted(related_files):
            node_id = sanitize_node_id(fp)
            filename = fp.split("/")[-1]
            label = sanitize_label(filename, max_length=30)
            lines.append(f'    {node_id}["{label}"]')

        # Add edges: target imports
        target_id = sanitize_node_id(file_path)
        for imp in imports:
            imp_id = sanitize_node_id(imp)
            lines.append(f"    {target_id} --> {imp_id}")

        # Add edges: files that import target
        for importer in importers:
            importer_id = sanitize_node_id(importer)
            lines.append(f"    {importer_id} --> {target_id}")

        return "\n".join(lines)

    @staticmethod
    def is_useful(diagram: str) -> bool:
        """Check if a dependency diagram adds value.

        Returns False if:
        - Contains "NoFiles" placeholder
        - Has no edges (just nodes, no relationships)

        Args:
            diagram: The generated Mermaid diagram string.

        Returns:
            True if the diagram is worth including.
        """
        if "NoFiles" in diagram or "No files" in diagram:
            return False

        # Must have at least one edge to show relationships
        return "-->" in diagram


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

    @staticmethod
    def is_useful(diagram: str) -> bool:
        """Check if a class diagram adds value.

        Returns False if:
        - Contains "NoClasses" placeholder
        - All classes only have "..." as content (no real methods)

        Args:
            diagram: The generated Mermaid diagram string.

        Returns:
            True if the diagram is worth including.
        """
        if "NoClasses" in diagram:
            return False

        # Check if any class has real content (not just ...)
        lines = diagram.split("\n")
        in_class = False
        has_real_content = False

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("class ") and "{" in stripped:
                in_class = True
            elif in_class and stripped == "}":
                in_class = False
            elif in_class and stripped and stripped != "..." and not stripped.startswith("class "):
                # Found actual content (method signature, etc.)
                has_real_content = True
                break

        return has_real_content


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
        diagrams = {}

        # Layer diagram
        if synthesis_map is not None:
            diagrams["layer"] = self.layer_generator.generate(synthesis_map)
        else:
            diagrams["layer"] = self.layer_generator.generate(SynthesisMap())

        # Dependency diagram
        diagrams["dependency"] = self.dependency_generator.generate(file_imports or {})

        # Class diagram
        diagrams["class"] = self.class_generator.generate(symbols or [])

        return diagrams
