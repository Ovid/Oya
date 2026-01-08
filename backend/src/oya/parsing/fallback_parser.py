"""Fallback regex-based parser for unsupported languages.

This parser uses regex patterns to detect common constructs across multiple
programming languages. It never fails and always returns a successful ParseResult,
making it suitable as a fallback when dedicated parsers are unavailable.
"""

import re
from pathlib import Path

from oya.parsing.base import BaseParser
from oya.parsing.models import ParsedFile, ParsedSymbol, ParseResult, SymbolType


# Extension to language name mapping
EXTENSION_LANGUAGES = {
    ".go": "go",
    ".rs": "rust",
    ".rb": "ruby",
    ".pl": "perl",
    ".pm": "perl",
    ".lua": "lua",
    ".sh": "shell",
    ".bash": "shell",
    ".zsh": "shell",
    ".fish": "shell",
    ".php": "php",
    ".scala": "scala",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".swift": "swift",
    ".r": "r",
    ".R": "r",
    ".m": "objective-c",
    ".mm": "objective-c++",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".hpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".cs": "csharp",
    ".fs": "fsharp",
    ".clj": "clojure",
    ".cljs": "clojurescript",
    ".ex": "elixir",
    ".exs": "elixir",
    ".erl": "erlang",
    ".hrl": "erlang",
    ".hs": "haskell",
    ".ml": "ocaml",
    ".mli": "ocaml",
    ".nim": "nim",
    ".zig": "zig",
    ".v": "v",
    ".d": "d",
    ".dart": "dart",
    ".groovy": "groovy",
    ".gradle": "gradle",
}

# Regex patterns for common language constructs
# Each pattern is: (pattern, symbol_type, name_group_index)
FUNCTION_PATTERNS = [
    # Go: func name(...)
    (re.compile(r"^\s*func\s+(\w+)\s*\(", re.MULTILINE), SymbolType.FUNCTION),
    # Go method: func (receiver) name(...)
    (re.compile(r"^\s*func\s+\([^)]+\)\s+(\w+)\s*\(", re.MULTILINE), SymbolType.METHOD),
    # Rust: fn name(...)
    (re.compile(r"^\s*(?:pub\s+)?fn\s+(\w+)\s*[<(]", re.MULTILINE), SymbolType.FUNCTION),
    # Ruby/Python: def name
    (re.compile(r"^\s*def\s+(\w+)", re.MULTILINE), SymbolType.FUNCTION),
    # Perl: sub name
    (re.compile(r"^\s*sub\s+(\w+)", re.MULTILINE), SymbolType.FUNCTION),
    # JavaScript/PHP/etc: function name(...)
    (re.compile(r"^\s*function\s+(\w+)\s*\(", re.MULTILINE), SymbolType.FUNCTION),
    # Lua: function name(...)
    (re.compile(r"^\s*(?:local\s+)?function\s+(\w+)\s*\(", re.MULTILINE), SymbolType.FUNCTION),
    # C/C++/Java-like: type name(...) - simplified
    (
        re.compile(
            r"^\s*(?:public|private|protected|static|virtual|override|async|extern)?\s*"
            r"(?:void|int|float|double|char|bool|string|auto|var)\s+"
            r"(\w+)\s*\(",
            re.MULTILINE,
        ),
        SymbolType.FUNCTION,
    ),
    # Shell: name() { or function name
    (re.compile(r"^\s*(\w+)\s*\(\s*\)\s*\{", re.MULTILINE), SymbolType.FUNCTION),
    (re.compile(r"^\s*function\s+(\w+)", re.MULTILINE), SymbolType.FUNCTION),
]

CLASS_PATTERNS = [
    # class Name
    (re.compile(r"^\s*(?:public\s+|private\s+)?class\s+(\w+)", re.MULTILINE), SymbolType.CLASS),
    # struct Name
    (
        re.compile(r"^\s*(?:pub\s+)?(?:type\s+)?struct\s+(\w+)", re.MULTILINE),
        SymbolType.CLASS,
    ),
    # trait Name (Rust)
    (re.compile(r"^\s*(?:pub\s+)?trait\s+(\w+)", re.MULTILINE), SymbolType.INTERFACE),
    # interface Name
    (
        re.compile(r"^\s*(?:public\s+)?interface\s+(\w+)", re.MULTILINE),
        SymbolType.INTERFACE,
    ),
    # enum Name
    (
        re.compile(r"^\s*(?:pub\s+)?(?:public\s+)?enum\s+(\w+)", re.MULTILINE),
        SymbolType.ENUM,
    ),
    # module Name (Ruby, etc.)
    (re.compile(r"^\s*module\s+(\w+)", re.MULTILINE), SymbolType.CLASS),
    # type Name (Go)
    (re.compile(r"^\s*type\s+(\w+)\s+(?:struct|interface)", re.MULTILINE), SymbolType.CLASS),
    # impl Name (Rust)
    (re.compile(r"^\s*impl(?:\s*<[^>]*>)?\s+(\w+)", re.MULTILINE), SymbolType.CLASS),
]


class FallbackParser(BaseParser):
    """Regex-based fallback parser for languages without dedicated parsers.

    This parser uses regex patterns to detect common programming constructs
    like functions, classes, structs, etc. It never fails and always returns
    a successful ParseResult, making it suitable as a fallback parser.

    Features:
        - Detects common function patterns (func, fn, def, sub, function)
        - Detects common class/type patterns (class, struct, trait, interface, enum)
        - Guesses language from file extension
        - Never fails - always returns a successful result
    """

    @property
    def supported_extensions(self) -> list[str]:
        """File extensions this parser handles.

        Returns all known extensions, but can_parse() returns True for any file.
        """
        return list(EXTENSION_LANGUAGES.keys())

    @property
    def language_name(self) -> str:
        """Human-readable language name."""
        return "Generic"

    def can_parse(self, file_path: Path) -> bool:
        """Check if this parser can handle the given file.

        The fallback parser accepts any file, making it suitable as a
        last-resort parser for unsupported languages.

        Args:
            file_path: Path to check.

        Returns:
            Always returns True.
        """
        return True

    def parse(self, file_path: Path, content: str) -> ParseResult:
        """Parse file content and extract symbols using regex patterns.

        This method never fails - it always returns a successful ParseResult,
        even if no symbols are found or the content is malformed.

        Args:
            file_path: Path to the file (used for language detection).
            content: File content as string.

        Returns:
            ParseResult with extracted symbols (always successful).
        """
        language = self._detect_language(file_path)
        symbols: list[ParsedSymbol] = []

        # Extract function-like patterns
        for pattern, symbol_type in FUNCTION_PATTERNS:
            for match in pattern.finditer(content):
                name = match.group(1)
                line_num = content[: match.start()].count("\n") + 1

                # Estimate end line (rough approximation)
                end_line = self._estimate_end_line(content, match.start(), line_num)

                symbols.append(
                    ParsedSymbol(
                        name=name,
                        symbol_type=symbol_type,
                        start_line=line_num,
                        end_line=end_line,
                    )
                )

        # Extract class-like patterns
        for pattern, symbol_type in CLASS_PATTERNS:
            for match in pattern.finditer(content):
                name = match.group(1)
                line_num = content[: match.start()].count("\n") + 1

                # Estimate end line
                end_line = self._estimate_end_line(content, match.start(), line_num)

                symbols.append(
                    ParsedSymbol(
                        name=name,
                        symbol_type=symbol_type,
                        start_line=line_num,
                        end_line=end_line,
                    )
                )

        # Remove duplicates (same name and line)
        symbols = self._deduplicate_symbols(symbols)

        # Sort by line number
        symbols.sort(key=lambda s: s.start_line)

        # Count lines
        line_count = content.count("\n")
        if content and not content.endswith("\n"):
            line_count += 1

        parsed_file = ParsedFile(
            path=str(file_path),
            language=language,
            symbols=symbols,
            raw_content=content,
            line_count=line_count,
        )

        return ParseResult.success(parsed_file)

    def parse_string(self, code: str, filename: str = "<string>") -> ParseResult:
        """Convenience method to parse a string of code.

        Args:
            code: Source code as string.
            filename: Filename to use for language detection.

        Returns:
            ParseResult with extracted symbols.
        """
        return self.parse(Path(filename), code)

    def _detect_language(self, file_path: Path) -> str:
        """Detect language from file extension.

        Args:
            file_path: Path to the file.

        Returns:
            Language name (lowercase) or 'unknown'.
        """
        suffix = file_path.suffix.lower()
        return EXTENSION_LANGUAGES.get(suffix, "unknown")

    def _estimate_end_line(self, content: str, start_pos: int, start_line: int) -> int:
        """Estimate the end line of a code block.

        This is a rough approximation that looks for balanced braces
        or indentation-based block ends.

        Args:
            content: Full file content.
            start_pos: Position in content where the symbol starts.
            start_line: Line number where the symbol starts.

        Returns:
            Estimated end line number.
        """
        # Simple heuristic: look for closing brace or end keyword
        # within a reasonable distance
        remaining = content[start_pos:]
        lines = remaining.split("\n")

        # For brace-based languages, try to find matching brace
        brace_count = 0
        found_open_brace = False

        for i, line in enumerate(lines[:100]):  # Limit search
            for char in line:
                if char == "{":
                    brace_count += 1
                    found_open_brace = True
                elif char == "}":
                    brace_count -= 1
                    if found_open_brace and brace_count == 0:
                        return start_line + i

            # Check for end keyword (Ruby, Lua, etc.)
            stripped = line.strip()
            if stripped == "end" and i > 0:
                return start_line + i

        # Default: assume block is about 10 lines
        return min(start_line + 10, start_line + len(lines) - 1)

    def _deduplicate_symbols(self, symbols: list[ParsedSymbol]) -> list[ParsedSymbol]:
        """Remove duplicate symbols (same name and start line).

        Args:
            symbols: List of symbols possibly containing duplicates.

        Returns:
            Deduplicated list of symbols.
        """
        seen: set[tuple[str, int]] = set()
        unique: list[ParsedSymbol] = []

        for symbol in symbols:
            key = (symbol.name, symbol.start_line)
            if key not in seen:
                seen.add(key)
                unique.append(symbol)

        return unique
