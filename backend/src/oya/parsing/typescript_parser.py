"""TypeScript/JavaScript parser using tree-sitter."""

from pathlib import Path

import tree_sitter_javascript as ts_js
import tree_sitter_typescript as ts_typescript
from tree_sitter import Language, Parser

from oya.parsing.base import BaseParser
from oya.parsing.models import (
    ParsedFile,
    ParsedSymbol,
    ParseResult,
    SymbolType,
    Reference,
    ReferenceType,
)

# Built-in types that should not create type annotation references
TS_BUILTIN_TYPES = frozenset(
    {
        # Primitives
        "string",
        "number",
        "boolean",
        "void",
        "null",
        "undefined",
        "any",
        "unknown",
        "never",
        "object",
        "symbol",
        "bigint",
        # Capitalized primitives
        "String",
        "Number",
        "Boolean",
        "Object",
        "Symbol",
        "BigInt",
        # Built-in objects
        "Array",
        "Promise",
        "Map",
        "Set",
        "WeakMap",
        "WeakSet",
        "Date",
        "RegExp",
        "Error",
        "Function",
        # Utility types
        "Record",
        "Partial",
        "Required",
        "Readonly",
        "Pick",
        "Omit",
        "Exclude",
        "Extract",
        "NonNullable",
        "ReturnType",
        "Parameters",
        "InstanceType",
        "ThisType",
        "Awaited",
        # React types (common enough to exclude)
        "React",
        "ReactNode",
        "ReactElement",
        "JSX",
    }
)


class TypeScriptParser(BaseParser):
    """Parser for TypeScript and JavaScript files using tree-sitter."""

    def __init__(self) -> None:
        """Initialize parsers for different file types."""
        # Create language instances
        self._ts_language = Language(ts_typescript.language_typescript())
        self._tsx_language = Language(ts_typescript.language_tsx())
        self._js_language = Language(ts_js.language())

        # Create parsers for each language
        self._ts_parser: Parser = Parser(self._ts_language)
        self._tsx_parser: Parser = Parser(self._tsx_language)
        self._js_parser: Parser = Parser(self._js_language)

    @property
    def supported_extensions(self) -> list[str]:
        """File extensions this parser handles."""
        return [".ts", ".tsx", ".js", ".jsx"]

    @property
    def language_name(self) -> str:
        """Human-readable language name."""
        return "TypeScript"

    def _get_parser_for_extension(self, extension: str) -> Parser:
        """Get the appropriate parser for a file extension.

        Args:
            extension: File extension (e.g., '.ts', '.tsx').

        Returns:
            The appropriate tree-sitter parser.
        """
        extension = extension.lower()
        if extension == ".tsx":
            return self._tsx_parser
        elif extension == ".ts":
            return self._ts_parser
        else:
            # .js and .jsx use the JavaScript parser
            return self._js_parser

    def parse(self, file_path: Path, content: str) -> ParseResult:
        """Parse TypeScript/JavaScript file content and extract symbols.

        Args:
            file_path: Path to the file (for error messages).
            content: File content as string.

        Returns:
            ParseResult with extracted symbols or error.
        """
        try:
            parser = self._get_parser_for_extension(file_path.suffix)
            tree = parser.parse(content.encode("utf-8"))

            symbols: list[ParsedSymbol] = []
            imports: list[str] = []
            exports: list[str] = []
            references: list[Reference] = []

            # Walk the AST
            self._walk_tree(
                tree.root_node,
                symbols,
                imports,
                exports,
                content,
                parent_class=None,
                references=references,
                file_path=str(file_path),
            )

            parsed_file = ParsedFile(
                path=str(file_path),
                language="typescript" if file_path.suffix in [".ts", ".tsx"] else "javascript",
                symbols=symbols,
                imports=imports,
                exports=exports,
                references=references,
                raw_content=content,
                line_count=content.count("\n") + 1,
            )

            return ParseResult.success(parsed_file)

        except Exception as e:
            return ParseResult.failure(str(file_path), f"Parse error: {e}")

    def parse_string(self, code: str, filename: str = "<string>") -> ParseResult:
        """Convenience method to parse a string of TypeScript/JavaScript code.

        Args:
            code: Source code as string.
            filename: Filename to use for extension detection and error messages.

        Returns:
            ParseResult with extracted symbols or error.
        """
        return self.parse(Path(filename), code)

    def _walk_tree(
        self,
        node,
        symbols: list[ParsedSymbol],
        imports: list[str],
        exports: list[str],
        content: str,
        parent_class: str | None = None,
        references: list[Reference] | None = None,
        file_path: str = "",
    ) -> None:
        """Walk the tree-sitter AST and extract symbols.

        Args:
            node: Current tree-sitter node.
            symbols: List to append extracted symbols.
            imports: List to append import strings.
            exports: List to append export names.
            content: Original source content.
            parent_class: Name of parent class if inside a class body.
            references: List to append references to.
            file_path: Path to the file being parsed.
        """
        node_type = node.type

        # Track node types that are fully processed and shouldn't recurse into children
        skip_children = False

        # Handle different node types
        if node_type == "function_declaration":
            self._extract_function(node, symbols, content, parent_class, references, file_path)
            skip_children = True
        elif node_type == "lexical_declaration":
            # Could contain arrow functions or constants
            self._extract_lexical_declaration(
                node, symbols, exports, content, references, file_path
            )
            skip_children = True
        elif node_type == "class_declaration":
            self._extract_class(node, symbols, content, references, file_path)
            skip_children = True  # Methods are already extracted in _extract_class
        elif node_type == "interface_declaration":
            self._extract_interface(node, symbols, content)
            skip_children = True
        elif node_type == "type_alias_declaration":
            self._extract_type_alias(node, symbols, content)
            skip_children = True
        elif node_type == "enum_declaration":
            self._extract_enum(node, symbols, content)
            skip_children = True
        elif node_type == "import_statement":
            self._extract_import(node, imports, content)
            skip_children = True
        elif node_type == "export_statement":
            self._extract_export(node, symbols, exports, content, references, file_path)
            skip_children = True
        elif node_type == "method_definition":
            self._extract_method(node, symbols, content, parent_class, references, file_path)
            skip_children = True

        # Recurse into children unless already fully processed
        if not skip_children:
            for child in node.children:
                self._walk_tree(
                    child, symbols, imports, exports, content, parent_class, references, file_path
                )

    def _extract_function(
        self,
        node,
        symbols: list[ParsedSymbol],
        content: str,
        parent_class: str | None = None,
        references: list[Reference] | None = None,
        file_path: str = "",
    ) -> None:
        """Extract a function declaration.

        Args:
            node: The function_declaration node.
            symbols: List to append the symbol.
            content: Original source content.
            parent_class: Parent class name if any.
            references: List to append references to.
            file_path: Path to the file being parsed.
        """
        name_node = node.child_by_field_name("name")
        if not name_node:
            return

        name = self._get_node_text(name_node, content)
        start_line = node.start_point[0] + 1
        end_line = node.end_point[0] + 1

        symbols.append(
            ParsedSymbol(
                name=name,
                symbol_type=SymbolType.METHOD if parent_class else SymbolType.FUNCTION,
                start_line=start_line,
                end_line=end_line,
                parent=parent_class,
            )
        )

        # Extract calls if references list provided
        if references is not None:
            scope = (
                f"{file_path}::{parent_class}.{name}" if parent_class else f"{file_path}::{name}"
            )
            body_node = node.child_by_field_name("body")
            if body_node:
                self._extract_calls_from_node(body_node, references, content, scope)

        # Extract type annotations
        if references is not None:
            references.extend(self._extract_type_annotation_references(node, content, file_path))

    def _extract_lexical_declaration(
        self,
        node,
        symbols: list[ParsedSymbol],
        exports: list[str],
        content: str,
        references: list[Reference] | None = None,
        file_path: str = "",
    ) -> None:
        """Extract variables/constants from a lexical declaration (const, let).

        Also detects arrow function assignments.

        Args:
            node: The lexical_declaration node.
            symbols: List to append symbols.
            exports: List to append export names (if part of export).
            content: Original source content.
            references: List to append references to.
            file_path: Path to the file being parsed.
        """
        for child in node.children:
            if child.type == "variable_declarator":
                name_node = child.child_by_field_name("name")
                value_node = child.child_by_field_name("value")

                if name_node:
                    name = self._get_node_text(name_node, content)
                    start_line = child.start_point[0] + 1
                    end_line = child.end_point[0] + 1

                    # Check if value is an arrow function
                    if value_node and value_node.type == "arrow_function":
                        symbols.append(
                            ParsedSymbol(
                                name=name,
                                symbol_type=SymbolType.FUNCTION,
                                start_line=start_line,
                                end_line=end_line,
                            )
                        )
                        # Extract calls from arrow function body
                        if references is not None:
                            scope = f"{file_path}::{name}"
                            body_node = value_node.child_by_field_name("body")
                            if body_node:
                                self._extract_calls_from_node(body_node, references, content, scope)
                        # Extract type annotations from arrow function
                        if references is not None:
                            references.extend(
                                self._extract_type_annotation_references(
                                    value_node, content, file_path
                                )
                            )
                    else:
                        # Regular variable/constant
                        is_const = any(
                            c.type == "const" for c in node.children if hasattr(c, "type")
                        )
                        symbol_type = SymbolType.CONSTANT if is_const else SymbolType.VARIABLE
                        symbols.append(
                            ParsedSymbol(
                                name=name,
                                symbol_type=symbol_type,
                                start_line=start_line,
                                end_line=end_line,
                            )
                        )

    def _extract_class(
        self,
        node,
        symbols: list[ParsedSymbol],
        content: str,
        references: list[Reference] | None = None,
        file_path: str = "",
    ) -> None:
        """Extract a class declaration and its methods.

        Args:
            node: The class_declaration node.
            symbols: List to append symbols.
            content: Original source content.
            references: List to append references to.
            file_path: Path to the file being parsed.
        """
        name_node = node.child_by_field_name("name")
        if not name_node:
            return

        class_name = self._get_node_text(name_node, content)
        start_line = node.start_point[0] + 1
        end_line = node.end_point[0] + 1
        class_scope = f"{file_path}::{class_name}"

        symbols.append(
            ParsedSymbol(
                name=class_name,
                symbol_type=SymbolType.CLASS,
                start_line=start_line,
                end_line=end_line,
            )
        )

        # Extract inheritance (extends clause)
        if references is not None:
            for child in node.children:
                if child.type == "class_heritage":
                    for heritage_child in child.children:
                        if heritage_child.type == "extends_clause":
                            # Get the class being extended
                            for ext_child in heritage_child.children:
                                if ext_child.type in ("identifier", "type_identifier"):
                                    target = self._get_node_text(ext_child, content)
                                    references.append(
                                        Reference(
                                            source=class_scope,
                                            target=target,
                                            reference_type=ReferenceType.INHERITS,
                                            confidence=0.95,
                                            line=start_line,
                                        )
                                    )

        # Process class body for methods
        body_node = node.child_by_field_name("body")
        if body_node:
            for child in body_node.children:
                if child.type == "method_definition":
                    self._extract_method(child, symbols, content, class_name, references, file_path)

    def _extract_method(
        self,
        node,
        symbols: list[ParsedSymbol],
        content: str,
        parent_class: str | None,
        references: list[Reference] | None = None,
        file_path: str = "",
    ) -> None:
        """Extract a method from a class.

        Args:
            node: The method_definition node.
            symbols: List to append the symbol.
            content: Original source content.
            parent_class: Name of the containing class.
            references: List to append references to.
            file_path: Path to the file being parsed.
        """
        name_node = node.child_by_field_name("name")
        if not name_node:
            return

        name = self._get_node_text(name_node, content)
        start_line = node.start_point[0] + 1
        end_line = node.end_point[0] + 1

        symbols.append(
            ParsedSymbol(
                name=name,
                symbol_type=SymbolType.METHOD,
                start_line=start_line,
                end_line=end_line,
                parent=parent_class,
            )
        )

        # Extract calls if references list provided
        if references is not None:
            scope = (
                f"{file_path}::{parent_class}.{name}" if parent_class else f"{file_path}::{name}"
            )
            body_node = node.child_by_field_name("body")
            if body_node:
                self._extract_calls_from_node(body_node, references, content, scope)

        # Extract type annotations
        if references is not None:
            references.extend(self._extract_type_annotation_references(node, content, file_path))

    def _extract_interface(
        self,
        node,
        symbols: list[ParsedSymbol],
        content: str,
    ) -> None:
        """Extract a TypeScript interface declaration.

        Args:
            node: The interface_declaration node.
            symbols: List to append the symbol.
            content: Original source content.
        """
        name_node = node.child_by_field_name("name")
        if not name_node:
            return

        name = self._get_node_text(name_node, content)
        start_line = node.start_point[0] + 1
        end_line = node.end_point[0] + 1

        symbols.append(
            ParsedSymbol(
                name=name,
                symbol_type=SymbolType.INTERFACE,
                start_line=start_line,
                end_line=end_line,
            )
        )

    def _extract_type_alias(
        self,
        node,
        symbols: list[ParsedSymbol],
        content: str,
    ) -> None:
        """Extract a TypeScript type alias declaration.

        Args:
            node: The type_alias_declaration node.
            symbols: List to append the symbol.
            content: Original source content.
        """
        name_node = node.child_by_field_name("name")
        if not name_node:
            return

        name = self._get_node_text(name_node, content)
        start_line = node.start_point[0] + 1
        end_line = node.end_point[0] + 1

        symbols.append(
            ParsedSymbol(
                name=name,
                symbol_type=SymbolType.TYPE_ALIAS,
                start_line=start_line,
                end_line=end_line,
            )
        )

    def _extract_enum(
        self,
        node,
        symbols: list[ParsedSymbol],
        content: str,
    ) -> None:
        """Extract a TypeScript enum declaration.

        Args:
            node: The enum_declaration node.
            symbols: List to append the symbol.
            content: Original source content.
        """
        name_node = node.child_by_field_name("name")
        if not name_node:
            return

        name = self._get_node_text(name_node, content)
        start_line = node.start_point[0] + 1
        end_line = node.end_point[0] + 1

        symbols.append(
            ParsedSymbol(
                name=name,
                symbol_type=SymbolType.ENUM,
                start_line=start_line,
                end_line=end_line,
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
            node: The import_statement node.
            imports: List to append import strings.
            content: Original source content.
        """
        # Find the source (module being imported from)
        source_node = node.child_by_field_name("source")
        if source_node:
            source = self._get_node_text(source_node, content)
            # Remove quotes
            source = source.strip("'\"")
            imports.append(source)

    def _extract_export(
        self,
        node,
        symbols: list[ParsedSymbol],
        exports: list[str],
        content: str,
        references: list[Reference] | None = None,
        file_path: str = "",
    ) -> None:
        """Extract export statement and its contents.

        Args:
            node: The export_statement node.
            symbols: List to append symbols for exported declarations.
            exports: List to append export names.
            content: Original source content.
            references: List to append references to.
            file_path: Path to the file being parsed.
        """
        # Process the declaration within the export
        for child in node.children:
            if child.type == "function_declaration":
                name_node = child.child_by_field_name("name")
                if name_node:
                    name = self._get_node_text(name_node, content)
                    exports.append(name)
                    self._extract_function(child, symbols, content, None, references, file_path)
            elif child.type == "lexical_declaration":
                # Export const/let
                for declarator in child.children:
                    if declarator.type == "variable_declarator":
                        name_node = declarator.child_by_field_name("name")
                        if name_node:
                            name = self._get_node_text(name_node, content)
                            exports.append(name)
                self._extract_lexical_declaration(
                    child, symbols, exports, content, references, file_path
                )
            elif child.type == "class_declaration":
                name_node = child.child_by_field_name("name")
                if name_node:
                    name = self._get_node_text(name_node, content)
                    exports.append(name)
                self._extract_class(child, symbols, content, references, file_path)
            elif child.type == "interface_declaration":
                name_node = child.child_by_field_name("name")
                if name_node:
                    name = self._get_node_text(name_node, content)
                    exports.append(name)
                self._extract_interface(child, symbols, content)
            elif child.type == "type_alias_declaration":
                name_node = child.child_by_field_name("name")
                if name_node:
                    name = self._get_node_text(name_node, content)
                    exports.append(name)
                self._extract_type_alias(child, symbols, content)
            elif child.type == "enum_declaration":
                name_node = child.child_by_field_name("name")
                if name_node:
                    name = self._get_node_text(name_node, content)
                    exports.append(name)
                self._extract_enum(child, symbols, content)

    def _get_node_text(self, node, content: str) -> str:
        """Get the text content of a tree-sitter node.

        Args:
            node: Tree-sitter node.
            content: Original source content.

        Returns:
            The text content of the node.
        """
        return content[node.start_byte : node.end_byte]

    def _extract_calls_from_node(
        self,
        node,
        references: list[Reference],
        content: str,
        current_scope: str,
    ) -> None:
        """Recursively extract function calls from a tree-sitter node.

        Args:
            node: Current tree-sitter node.
            references: List to append references to.
            content: Original source content.
            current_scope: Current function/method scope.
        """
        if node.type == "call_expression":
            func_node = node.child_by_field_name("function")
            if func_node:
                target, confidence, ref_type = self._resolve_ts_call_target(func_node, content)
                if target:
                    references.append(
                        Reference(
                            source=current_scope,
                            target=target,
                            reference_type=ref_type,
                            confidence=confidence,
                            line=node.start_point[0] + 1,
                        )
                    )
        elif node.type == "new_expression":
            # new ClassName(...)
            constructor_node = node.child_by_field_name("constructor")
            if constructor_node:
                target = self._get_node_text(constructor_node, content)
                references.append(
                    Reference(
                        source=current_scope,
                        target=target,
                        reference_type=ReferenceType.INSTANTIATES,
                        confidence=0.95,
                        line=node.start_point[0] + 1,
                    )
                )

        # Recurse into children
        for child in node.children:
            self._extract_calls_from_node(child, references, content, current_scope)

    def _resolve_ts_call_target(
        self, func_node, content: str
    ) -> tuple[str | None, float, ReferenceType]:
        """Resolve the target of a TypeScript call expression.

        Args:
            func_node: The function node of the call_expression.
            content: Original source content.

        Returns:
            Tuple of (target_name, confidence, reference_type).
        """
        node_type = func_node.type

        if node_type == "identifier":
            name = self._get_node_text(func_node, content)
            # CapitalCase = likely class instantiation
            if name and name[0].isupper():
                return name, 0.85, ReferenceType.INSTANTIATES
            return name, 0.9, ReferenceType.CALLS
        elif node_type == "member_expression":
            # obj.method()
            text = self._get_node_text(func_node, content)
            return text, 0.7, ReferenceType.CALLS

        return None, 0.0, ReferenceType.CALLS

    def _extract_types_from_ts_annotation(self, node, content: str) -> list[str]:
        """Recursively extract type names from a tree-sitter type annotation node.

        Args:
            node: Tree-sitter node representing a type.
            content: Original source content.

        Returns:
            List of type names found (excluding built-ins).
        """
        types: list[str] = []
        node_type = node.type

        if node_type == "type_identifier":
            name = self._get_node_text(node, content)
            if name not in TS_BUILTIN_TYPES:
                types.append(name)

        elif node_type == "generic_type":
            for child in node.children:
                if child.type == "type_identifier":
                    name = self._get_node_text(child, content)
                    if name not in TS_BUILTIN_TYPES:
                        types.append(name)
                elif child.type == "type_arguments":
                    for arg in child.children:
                        types.extend(self._extract_types_from_ts_annotation(arg, content))

        elif node_type == "union_type":
            for child in node.children:
                if child.type != "|":
                    types.extend(self._extract_types_from_ts_annotation(child, content))

        elif node_type == "intersection_type":
            for child in node.children:
                if child.type != "&":
                    types.extend(self._extract_types_from_ts_annotation(child, content))

        elif node_type == "array_type":
            for child in node.children:
                types.extend(self._extract_types_from_ts_annotation(child, content))

        elif node_type == "parenthesized_type":
            for child in node.children:
                types.extend(self._extract_types_from_ts_annotation(child, content))

        elif node_type == "type_annotation":
            for child in node.children:
                if child.type != ":":
                    types.extend(self._extract_types_from_ts_annotation(child, content))

        elif node_type == "function_type":
            # Function type: (x: A, y: B) => C
            # Only extract types from type annotations, not parameter names
            for child in node.children:
                if child.type == "formal_parameters":
                    for param in child.children:
                        if param.type in ("required_parameter", "optional_parameter"):
                            for param_child in param.children:
                                if param_child.type == "type_annotation":
                                    types.extend(
                                        self._extract_types_from_ts_annotation(param_child, content)
                                    )
                elif child.type == "type_annotation":
                    # Return type annotation
                    types.extend(self._extract_types_from_ts_annotation(child, content))
                elif child.type == "type_identifier":
                    # Direct return type
                    name = self._get_node_text(child, content)
                    if name not in TS_BUILTIN_TYPES:
                        types.append(name)

        else:
            for child in node.children:
                types.extend(self._extract_types_from_ts_annotation(child, content))

        return types

    def _extract_type_annotation_references(
        self, node, content: str, file_path: str
    ) -> list[Reference]:
        """Extract type annotation references from a function or method node.

        Args:
            node: The function_declaration or method_definition node.
            content: Original source content.
            file_path: Path to the file being parsed.

        Returns:
            List of Reference objects for type annotations.
        """
        references: list[Reference] = []
        file_scope = str(file_path)

        # Find parameters node
        params_node = node.child_by_field_name("parameters")
        if params_node:
            for child in params_node.children:
                if child.type in ("required_parameter", "optional_parameter"):
                    for param_child in child.children:
                        if param_child.type == "type_annotation":
                            line = param_child.start_point[0] + 1
                            for type_name in self._extract_types_from_ts_annotation(
                                param_child, content
                            ):
                                references.append(
                                    Reference(
                                        source=file_scope,
                                        target=type_name,
                                        reference_type=ReferenceType.TYPE_ANNOTATION,
                                        confidence=0.9,
                                        line=line,
                                    )
                                )

        # Find return type annotation
        return_type = node.child_by_field_name("return_type")
        if return_type:
            line = return_type.start_point[0] + 1
            for type_name in self._extract_types_from_ts_annotation(return_type, content):
                references.append(
                    Reference(
                        source=file_scope,
                        target=type_name,
                        reference_type=ReferenceType.TYPE_ANNOTATION,
                        confidence=0.9,
                        line=line,
                    )
                )

        return references
