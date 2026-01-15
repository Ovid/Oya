"""Java parser using tree-sitter."""

from pathlib import Path

import tree_sitter_java as ts_java
from tree_sitter import Language, Parser

from oya.parsing.base import BaseParser
from oya.parsing.models import ParsedFile, ParsedSymbol, ParseResult, SymbolType


# Spring MVC annotations that indicate route handlers
SPRING_ROUTE_ANNOTATIONS = frozenset(
    {
        "GetMapping",
        "PostMapping",
        "PutMapping",
        "DeleteMapping",
        "PatchMapping",
        "RequestMapping",
    }
)


class JavaParser(BaseParser):
    """Parser for Java source files using tree-sitter."""

    def __init__(self):
        """Initialize the Java parser."""
        self._language = Language(ts_java.language())
        self._parser = Parser(self._language)

    @property
    def supported_extensions(self) -> list[str]:
        """File extensions this parser handles."""
        return [".java"]

    @property
    def language_name(self) -> str:
        """Human-readable language name."""
        return "Java"

    def parse(self, file_path: Path, content: str) -> ParseResult:
        """Parse Java file content and extract symbols.

        Args:
            file_path: Path to the file (for error messages).
            content: File content as string.

        Returns:
            ParseResult with extracted symbols or error.
        """
        try:
            tree = self._parser.parse(content.encode("utf-8"))

            symbols: list[ParsedSymbol] = []
            imports: list[str] = []

            # Walk the AST
            self._walk_tree(tree.root_node, symbols, imports, content)

            parsed_file = ParsedFile(
                path=str(file_path),
                language="java",
                symbols=symbols,
                imports=imports,
                raw_content=content,
                line_count=content.count("\n") + 1,
            )

            return ParseResult.success(parsed_file)

        except Exception as e:
            return ParseResult.failure(str(file_path), f"Parse error: {e}")

    def parse_string(self, code: str, filename: str = "<string>") -> ParseResult:
        """Convenience method to parse a string of Java code.

        Args:
            code: Java source code as string.
            filename: Filename to use in error messages.

        Returns:
            ParseResult with extracted symbols or error.
        """
        return self.parse(Path(filename), code)

    def _walk_tree(
        self,
        node,
        symbols: list[ParsedSymbol],
        imports: list[str],
        content: str,
        parent_class: str | None = None,
    ) -> None:
        """Walk the tree-sitter AST and extract symbols.

        Args:
            node: Current tree-sitter node.
            symbols: List to append extracted symbols.
            imports: List to append import strings.
            content: Original source content.
            parent_class: Name of parent class if inside a class body.
        """
        node_type = node.type

        # Track node types that are fully processed and shouldn't recurse into children
        skip_children = False

        if node_type == "class_declaration":
            self._extract_class(node, symbols, content)
            skip_children = True
        elif node_type == "interface_declaration":
            self._extract_interface(node, symbols, content)
            skip_children = True
        elif node_type == "enum_declaration":
            self._extract_enum(node, symbols, content)
            skip_children = True
        elif node_type == "import_declaration":
            self._extract_import(node, imports, content)
            skip_children = True

        # Recurse into children unless already fully processed
        if not skip_children:
            for child in node.children:
                self._walk_tree(child, symbols, imports, content, parent_class)

    def _extract_class(
        self,
        node,
        symbols: list[ParsedSymbol],
        content: str,
    ) -> None:
        """Extract a class declaration and its methods.

        Args:
            node: The class_declaration node.
            symbols: List to append symbols.
            content: Original source content.
        """
        name_node = node.child_by_field_name("name")
        if not name_node:
            return

        class_name = self._get_node_text(name_node, content)
        start_line = node.start_point[0] + 1
        end_line = node.end_point[0] + 1

        # Extract class-level annotations
        decorators = self._extract_annotations(node, content)

        symbols.append(
            ParsedSymbol(
                name=class_name,
                symbol_type=SymbolType.CLASS,
                start_line=start_line,
                end_line=end_line,
                decorators=decorators,
            )
        )

        # Process class body for methods
        body_node = node.child_by_field_name("body")
        if body_node:
            self._extract_class_members(body_node, symbols, content, class_name)

    def _extract_interface(
        self,
        node,
        symbols: list[ParsedSymbol],
        content: str,
    ) -> None:
        """Extract an interface declaration.

        Args:
            node: The interface_declaration node.
            symbols: List to append symbols.
            content: Original source content.
        """
        name_node = node.child_by_field_name("name")
        if not name_node:
            return

        name = self._get_node_text(name_node, content)
        start_line = node.start_point[0] + 1
        end_line = node.end_point[0] + 1

        decorators = self._extract_annotations(node, content)

        symbols.append(
            ParsedSymbol(
                name=name,
                symbol_type=SymbolType.INTERFACE,
                start_line=start_line,
                end_line=end_line,
                decorators=decorators,
            )
        )

    def _extract_enum(
        self,
        node,
        symbols: list[ParsedSymbol],
        content: str,
    ) -> None:
        """Extract an enum declaration.

        Args:
            node: The enum_declaration node.
            symbols: List to append symbols.
            content: Original source content.
        """
        name_node = node.child_by_field_name("name")
        if not name_node:
            return

        name = self._get_node_text(name_node, content)
        start_line = node.start_point[0] + 1
        end_line = node.end_point[0] + 1

        decorators = self._extract_annotations(node, content)

        symbols.append(
            ParsedSymbol(
                name=name,
                symbol_type=SymbolType.ENUM,
                start_line=start_line,
                end_line=end_line,
                decorators=decorators,
            )
        )

    def _extract_class_members(
        self,
        body_node,
        symbols: list[ParsedSymbol],
        content: str,
        class_name: str,
    ) -> None:
        """Extract methods and other members from a class body.

        Args:
            body_node: The class_body node.
            symbols: List to append symbols.
            content: Original source content.
            class_name: Name of the containing class.
        """
        for child in body_node.children:
            if child.type == "method_declaration":
                self._extract_method(child, symbols, content, class_name)
            elif child.type == "constructor_declaration":
                self._extract_method(child, symbols, content, class_name, is_constructor=True)

    def _extract_method(
        self,
        node,
        symbols: list[ParsedSymbol],
        content: str,
        parent_class: str,
        is_constructor: bool = False,
    ) -> None:
        """Extract a method from a class.

        Args:
            node: The method_declaration node.
            symbols: List to append the symbol.
            content: Original source content.
            parent_class: Name of the containing class.
            is_constructor: Whether this is a constructor.
        """
        name_node = node.child_by_field_name("name")
        if not name_node:
            return

        name = self._get_node_text(name_node, content)
        start_line = node.start_point[0] + 1
        end_line = node.end_point[0] + 1

        # Extract method-level annotations
        decorators = self._extract_annotations(node, content)

        # Check if this is a Spring route handler
        is_route = any(dec in SPRING_ROUTE_ANNOTATIONS for dec in decorators)

        symbols.append(
            ParsedSymbol(
                name=name,
                symbol_type=SymbolType.ROUTE if is_route else SymbolType.METHOD,
                start_line=start_line,
                end_line=end_line,
                decorators=decorators,
                parent=parent_class,
            )
        )

    def _extract_import(
        self,
        node,
        imports: list[str],
        content: str,
    ) -> None:
        """Extract import statement information.

        Args:
            node: The import_declaration node.
            imports: List to append import strings.
            content: Original source content.
        """
        # Get the full import text, excluding 'import' keyword and semicolon
        import_text = self._get_node_text(node, content)
        # Remove 'import', 'static' keyword if present, and clean up
        import_text = import_text.replace("import ", "").replace("static ", "").rstrip(";").strip()
        imports.append(import_text)

    def _extract_annotations(self, node, content: str) -> list[str]:
        """Extract annotation names from a node.

        Annotations in Java appear as siblings before the declaration,
        or as modifiers children.

        Args:
            node: The tree-sitter node.
            content: Original source content.

        Returns:
            List of annotation names (without the @ symbol).
        """
        annotations = []

        # Find the modifiers node by iterating over children
        # (child_by_field_name doesn't work reliably for modifiers)
        modifiers = None
        for child in node.children:
            if child.type == "modifiers":
                modifiers = child
                break

        if modifiers:
            for child in modifiers.children:
                if child.type == "marker_annotation":
                    # Simple annotation like @Service
                    # The name is stored in an identifier child node
                    for subchild in child.children:
                        if subchild.type == "identifier":
                            annotations.append(self._get_node_text(subchild, content))
                            break
                elif child.type == "annotation":
                    # Annotation with arguments like @GetMapping("/users")
                    # The name is stored in an identifier child node
                    for subchild in child.children:
                        if subchild.type == "identifier":
                            annotations.append(self._get_node_text(subchild, content))
                            break

        return annotations

    def _get_node_text(self, node, content: str) -> str:
        """Get the text content of a tree-sitter node.

        Args:
            node: Tree-sitter node.
            content: Original source content.

        Returns:
            The text content of the node.
        """
        return content[node.start_byte : node.end_byte]
