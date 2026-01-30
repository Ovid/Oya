"""Data models for code parsing."""

from dataclasses import dataclass, field
from enum import Enum


class ReferenceType(Enum):
    """Types of references between code entities."""

    CALLS = "calls"
    INSTANTIATES = "instantiates"
    INHERITS = "inherits"
    IMPORTS = "imports"
    TYPE_ANNOTATION = "type_annotation"  # Types used in annotations


class SymbolType(Enum):
    """Types of code symbols that can be extracted."""

    FUNCTION = "function"
    CLASS = "class"
    METHOD = "method"
    IMPORT = "import"
    EXPORT = "export"
    VARIABLE = "variable"
    CONSTANT = "constant"
    INTERFACE = "interface"  # TypeScript
    TYPE_ALIAS = "type_alias"  # TypeScript
    ENUM = "enum"
    DECORATOR = "decorator"
    ROUTE = "route"  # API route handlers
    CLI_COMMAND = "cli_command"  # CLI entry points


@dataclass
class ParsedSymbol:
    """A parsed code symbol (function, class, etc.)."""

    name: str
    symbol_type: SymbolType
    start_line: int
    end_line: int
    docstring: str | None = None
    signature: str | None = None
    decorators: list[str] = field(default_factory=list)
    parent: str | None = None  # For methods, the class name
    metadata: dict = field(default_factory=dict)


@dataclass
class ParsedFile:
    """Result of parsing a single file."""

    path: str
    language: str
    symbols: list[ParsedSymbol]
    imports: list[str] = field(default_factory=list)
    exports: list[str] = field(default_factory=list)
    references: list["Reference"] = field(default_factory=list)
    raw_content: str | None = None
    line_count: int = 0
    metadata: dict = field(default_factory=dict)
    synopsis: str | None = None  # Extracted synopsis code


@dataclass
class ParseResult:
    """Result of a parse operation (success or failure)."""

    ok: bool
    file: ParsedFile | None
    error: str | None
    path: str | None = None

    @classmethod
    def success(cls, parsed_file: ParsedFile) -> "ParseResult":
        """Create a successful parse result."""
        return cls(ok=True, file=parsed_file, error=None, path=parsed_file.path)

    @classmethod
    def failure(cls, path: str, error: str) -> "ParseResult":
        """Create a failed parse result."""
        return cls(ok=False, file=None, error=error, path=path)


@dataclass
class Reference:
    """A reference from one code entity to another."""

    source: str  # e.g., "auth/handler.py::login"
    target: str  # e.g., "auth/session.py::create_session" or unresolved name
    reference_type: ReferenceType
    confidence: float  # 0.0 to 1.0
    line: int  # Line number where reference occurs
    target_resolved: bool = False  # True if target is a full path, False if just a name
