# backend/src/oya/parsing/registry.py
"""Parser registry for selecting appropriate parser."""

from pathlib import Path

from oya.parsing.base import BaseParser
from oya.parsing.models import ParseResult
from oya.parsing.python_parser import PythonParser
from oya.parsing.typescript_parser import TypeScriptParser
from oya.parsing.java_parser import JavaParser
from oya.parsing.fallback_parser import FallbackParser


class ParserRegistry:
    """Registry that selects the appropriate parser for a file.

    Parsers are tried in order of specificity, with the fallback
    parser used when no specific parser matches.
    """

    def __init__(self):
        """Initialize registry with all available parsers."""
        self._parsers: list[BaseParser] = [
            PythonParser(),
            TypeScriptParser(),
            JavaParser(),
        ]
        self._fallback = FallbackParser()

    def get_parser(self, file_path: Path) -> BaseParser:
        """Get the appropriate parser for a file.

        Args:
            file_path: Path to file.

        Returns:
            Parser instance that can handle the file.
        """
        for parser in self._parsers:
            if parser.can_parse(file_path):
                return parser
        return self._fallback

    def parse_file(self, file_path: Path, content: str) -> ParseResult:
        """Parse a file using the appropriate parser.

        Args:
            file_path: Path to file.
            content: File content.

        Returns:
            ParseResult from the selected parser.
        """
        parser = self.get_parser(file_path)
        return parser.parse(file_path, content)

    @property
    def supported_languages(self) -> list[str]:
        """Get list of specifically supported languages."""
        return [p.language_name for p in self._parsers]
