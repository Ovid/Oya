"""Python AST parser using the built-in ast module."""

import ast
from pathlib import Path

from oya.parsing.base import BaseParser
from oya.parsing.models import ParsedFile, ParsedSymbol, ParseResult, Reference, ReferenceType, SymbolType


# HTTP methods commonly used in web frameworks for route definitions
ROUTE_DECORATORS = frozenset({"get", "post", "put", "patch", "delete", "head", "options"})


class PythonParser(BaseParser):
    """Parser for Python source files using the ast module."""

    @property
    def supported_extensions(self) -> list[str]:
        """File extensions this parser handles."""
        return [".py", ".pyi"]

    @property
    def language_name(self) -> str:
        """Human-readable language name."""
        return "Python"

    def parse(self, file_path: Path, content: str) -> ParseResult:
        """Parse Python file content and extract symbols.

        Args:
            file_path: Path to the file (for error messages).
            content: File content as string.

        Returns:
            ParseResult with extracted symbols or error.
        """
        try:
            tree = ast.parse(content, filename=str(file_path))
        except SyntaxError as e:
            return ParseResult.failure(str(file_path), f"Syntax error: {e}")

        symbols: list[ParsedSymbol] = []
        imports: list[str] = []
        references: list[Reference] = []

        # Process top-level nodes
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                symbols.append(self._parse_function(node, parent=None))
                scope = f"{file_path}::{node.name}"
                references.extend(self._extract_calls(node, scope))
            elif isinstance(node, ast.ClassDef):
                symbols.extend(self._parse_class(node))
                # Extract inheritance
                references.extend(self._extract_inheritance(node, str(file_path)))
                # Extract calls from methods
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        scope = f"{file_path}::{node.name}.{item.name}"
                        references.extend(self._extract_calls(item, scope))
            elif isinstance(node, ast.Import):
                imports.extend(self._parse_import(node))
            elif isinstance(node, ast.ImportFrom):
                imports.extend(self._parse_import_from(node))
            elif isinstance(node, ast.Assign):
                symbols.extend(self._parse_assignment(node))

        parsed_file = ParsedFile(
            path=str(file_path),
            language="python",
            symbols=symbols,
            imports=imports,
            references=references,
            raw_content=content,
            line_count=content.count("\n") + 1,
        )

        return ParseResult.success(parsed_file)

    def parse_string(self, code: str, filename: str = "<string>") -> ParseResult:
        """Convenience method to parse a string of Python code.

        Args:
            code: Python source code as string.
            filename: Filename to use in error messages.

        Returns:
            ParseResult with extracted symbols or error.
        """
        return self.parse(Path(filename), code)

    def _parse_function(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        parent: str | None,
    ) -> ParsedSymbol:
        """Parse a function or async function definition.

        Args:
            node: The AST function node.
            parent: Name of the parent class, if any.

        Returns:
            ParsedSymbol representing the function.
        """
        decorators = self._extract_decorators(node)
        is_route = self._is_route_handler(decorators)

        # Determine symbol type
        if is_route:
            symbol_type = SymbolType.ROUTE
        elif parent is not None:
            symbol_type = SymbolType.METHOD
        else:
            symbol_type = SymbolType.FUNCTION

        return ParsedSymbol(
            name=node.name,
            symbol_type=symbol_type,
            start_line=node.lineno,
            end_line=node.end_lineno or node.lineno,
            docstring=ast.get_docstring(node),
            signature=self._build_signature(node),
            decorators=decorators,
            parent=parent,
        )

    def _parse_class(self, node: ast.ClassDef) -> list[ParsedSymbol]:
        """Parse a class definition and its methods.

        Args:
            node: The AST class node.

        Returns:
            List of symbols (class + methods).
        """
        symbols = []

        # Add the class itself
        class_symbol = ParsedSymbol(
            name=node.name,
            symbol_type=SymbolType.CLASS,
            start_line=node.lineno,
            end_line=node.end_lineno or node.lineno,
            docstring=ast.get_docstring(node),
            signature=self._build_class_signature(node),
            decorators=self._extract_decorators(node),
        )
        symbols.append(class_symbol)

        # Process methods
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                symbols.append(self._parse_function(item, parent=node.name))

        return symbols

    def _parse_import(self, node: ast.Import) -> list[str]:
        """Parse an import statement.

        Args:
            node: The AST import node.

        Returns:
            List of imported module names.
        """
        return [alias.name for alias in node.names]

    def _parse_import_from(self, node: ast.ImportFrom) -> list[str]:
        """Parse a from...import statement.

        Args:
            node: The AST import-from node.

        Returns:
            List of fully qualified import names.
        """
        module = node.module or ""
        return [f"{module}.{alias.name}" if module else alias.name for alias in node.names]

    def _parse_assignment(self, node: ast.Assign) -> list[ParsedSymbol]:
        """Parse a module-level assignment.

        Args:
            node: The AST assignment node.

        Returns:
            List of variable/constant symbols.
        """
        symbols = []

        for target in node.targets:
            if isinstance(target, ast.Name):
                name = target.id
                # Convention: UPPER_CASE names are constants
                is_constant = name.isupper()
                symbol_type = SymbolType.CONSTANT if is_constant else SymbolType.VARIABLE

                symbols.append(
                    ParsedSymbol(
                        name=name,
                        symbol_type=symbol_type,
                        start_line=node.lineno,
                        end_line=node.end_lineno or node.lineno,
                    )
                )

        return symbols

    def _extract_decorators(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef
    ) -> list[str]:
        """Extract decorator names from a decorated node.

        Args:
            node: The AST node with decorators.

        Returns:
            List of decorator names as strings.
        """
        decorators = []

        for dec in node.decorator_list:
            if isinstance(dec, ast.Name):
                # Simple decorator: @decorator
                decorators.append(dec.id)
            elif isinstance(dec, ast.Attribute):
                # Attribute decorator: @obj.decorator
                decorators.append(self._get_attribute_name(dec))
            elif isinstance(dec, ast.Call):
                # Called decorator: @decorator(...) or @obj.decorator(...)
                if isinstance(dec.func, ast.Name):
                    decorators.append(dec.func.id)
                elif isinstance(dec.func, ast.Attribute):
                    decorators.append(self._get_attribute_name(dec.func))

        return decorators

    def _get_attribute_name(self, node: ast.Attribute) -> str:
        """Get the full dotted name from an Attribute node.

        Args:
            node: The AST attribute node.

        Returns:
            Dotted name string (e.g., 'app.route').
        """
        parts = []
        current: ast.expr = node

        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value

        if isinstance(current, ast.Name):
            parts.append(current.id)

        return ".".join(reversed(parts))

    def _is_route_handler(self, decorators: list[str]) -> bool:
        """Check if decorators indicate a route handler.

        Args:
            decorators: List of decorator names.

        Returns:
            True if this looks like a route handler.
        """
        for dec in decorators:
            # Check for patterns like: app.get, router.post, etc.
            parts = dec.split(".")
            if len(parts) >= 2 and parts[-1].lower() in ROUTE_DECORATORS:
                return True

        return False

    def _build_signature(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
        """Build a human-readable function signature.

        Args:
            node: The AST function node.

        Returns:
            Function signature string.
        """
        args = node.args
        params = []

        # Regular positional args
        num_defaults = len(args.defaults)
        num_args = len(args.args)
        first_default_idx = num_args - num_defaults

        for i, arg in enumerate(args.args):
            param = self._format_arg(arg)
            if i >= first_default_idx:
                default_idx = i - first_default_idx
                default = self._format_default(args.defaults[default_idx])
                param = f"{param}={default}"
            params.append(param)

        # *args
        if args.vararg:
            params.append(f"*{self._format_arg(args.vararg)}")

        # Keyword-only args
        num_kw_defaults = len(args.kw_defaults)
        for i, arg in enumerate(args.kwonlyargs):
            param = self._format_arg(arg)
            if i < num_kw_defaults and args.kw_defaults[i] is not None:
                default = self._format_default(args.kw_defaults[i])
                param = f"{param}={default}"
            params.append(param)

        # **kwargs
        if args.kwarg:
            params.append(f"**{self._format_arg(args.kwarg)}")

        # Build signature
        prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
        params_str = ", ".join(params)
        sig = f"{prefix} {node.name}({params_str})"

        # Add return annotation
        if node.returns:
            sig += f" -> {self._format_annotation(node.returns)}"

        return sig

    def _format_arg(self, arg: ast.arg) -> str:
        """Format a function argument with optional type annotation.

        Args:
            arg: The AST arg node.

        Returns:
            Formatted argument string.
        """
        if arg.annotation:
            return f"{arg.arg}: {self._format_annotation(arg.annotation)}"
        return arg.arg

    def _format_annotation(self, node: ast.expr) -> str:
        """Format a type annotation.

        Args:
            node: The AST annotation node.

        Returns:
            Annotation as string.
        """
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Constant):
            return repr(node.value)
        elif isinstance(node, ast.Attribute):
            return self._get_attribute_name(node)
        elif isinstance(node, ast.Subscript):
            return ast.unparse(node)
        else:
            return ast.unparse(node)

    def _format_default(self, node: ast.expr | None) -> str:
        """Format a default value.

        Args:
            node: The AST default value node.

        Returns:
            Default value as string.
        """
        if node is None:
            return "None"
        return ast.unparse(node)

    def _build_class_signature(self, node: ast.ClassDef) -> str:
        """Build a class signature including base classes.

        Args:
            node: The AST class node.

        Returns:
            Class signature string.
        """
        bases = [ast.unparse(base) for base in node.bases]
        keywords = [f"{kw.arg}={ast.unparse(kw.value)}" for kw in node.keywords]

        all_parts = bases + keywords
        if all_parts:
            return f"class {node.name}({', '.join(all_parts)})"
        return f"class {node.name}"

    def _extract_inheritance(self, node: ast.ClassDef, file_path: str) -> list[Reference]:
        """Extract inheritance relationships from a class definition.

        Args:
            node: The ClassDef AST node.
            file_path: Path to the file being parsed.

        Returns:
            List of Reference objects for inheritance.
        """
        references = []
        class_scope = f"{file_path}::{node.name}"

        for base in node.bases:
            if isinstance(base, ast.Name):
                references.append(Reference(
                    source=class_scope,
                    target=base.id,
                    reference_type=ReferenceType.INHERITS,
                    confidence=0.95,  # High confidence for direct name
                    line=node.lineno,
                ))
            elif isinstance(base, ast.Attribute):
                target = self._get_attribute_name(base)
                references.append(Reference(
                    source=class_scope,
                    target=target,
                    reference_type=ReferenceType.INHERITS,
                    confidence=0.9,  # Slightly lower for dotted names
                    line=node.lineno,
                ))

        return references

    def _extract_calls(self, node: ast.AST, current_scope: str) -> list[Reference]:
        """Extract function/method calls from an AST node.

        Args:
            node: The AST node to analyze.
            current_scope: The current function/method name for source.

        Returns:
            List of Reference objects for calls found.
        """
        references = []

        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                target, confidence, ref_type = self._resolve_call_target(child)
                if target:
                    references.append(Reference(
                        source=current_scope,
                        target=target,
                        reference_type=ref_type,
                        confidence=confidence,
                        line=child.lineno,
                    ))

        return references

    def _resolve_call_target(self, node: ast.Call) -> tuple[str | None, float, ReferenceType]:
        """Resolve the target of a call expression.

        Args:
            node: The Call AST node.

        Returns:
            Tuple of (target_name, confidence, reference_type).
        """
        func = node.func

        if isinstance(func, ast.Name):
            name = func.id
            # Convention: CapitalCase names are likely classes (instantiation)
            if name and name[0].isupper():
                return name, 0.85, ReferenceType.INSTANTIATES
            return name, 0.9, ReferenceType.CALLS
        elif isinstance(func, ast.Attribute):
            attr_name = self._get_attribute_name(func)
            # Check if final component is CapitalCase
            parts = attr_name.split(".")
            if parts and parts[-1][0].isupper():
                return attr_name, 0.75, ReferenceType.INSTANTIATES
            return attr_name, 0.7, ReferenceType.CALLS

        return None, 0.0, ReferenceType.CALLS
