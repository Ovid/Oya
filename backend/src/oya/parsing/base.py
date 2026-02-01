"""Base parser interface."""

import re
from abc import ABC, abstractmethod
from pathlib import Path

from oya.parsing.decorator_patterns import (
    ENTRY_POINT_PATTERNS,
    REFERENCE_PATTERNS,
    EntryPointPattern,
    ReferencePattern,
)
from oya.parsing.models import ParseResult


class BaseParser(ABC):
    """Abstract base class for language-specific parsers."""

    @property
    @abstractmethod
    def supported_extensions(self) -> list[str]:
        """File extensions this parser handles (e.g., ['.py'])."""
        pass

    @property
    @abstractmethod
    def language_name(self) -> str:
        """Human-readable language name."""
        pass

    @abstractmethod
    def parse(self, file_path: Path, content: str) -> ParseResult:
        """Parse file content and extract symbols.

        Args:
            file_path: Path to the file (for error messages).
            content: File content as string.

        Returns:
            ParseResult with extracted symbols or error.
        """
        pass

    def can_parse(self, file_path: Path) -> bool:
        """Check if this parser can handle the given file.

        Args:
            file_path: Path to check.

        Returns:
            True if this parser supports the file extension.
        """
        return file_path.suffix.lower() in self.supported_extensions

    def _get_reference_patterns(self) -> list[ReferencePattern]:
        """Get reference patterns for this parser's language."""
        return REFERENCE_PATTERNS.get(self.language_name.lower(), [])

    def _get_entry_point_patterns(self) -> list[EntryPointPattern]:
        """Get entry point patterns for this parser's language."""
        return ENTRY_POINT_PATTERNS.get(self.language_name.lower(), [])

    def _matches_decorator_pattern(
        self,
        decorator_name: str,
        object_name: str | None,
        pattern: ReferencePattern | EntryPointPattern,
    ) -> bool:
        """Check if decorator matches pattern.

        Args:
            decorator_name: The decorator's method/function name (e.g., "get" in router.get).
            object_name: The object the decorator is called on (e.g., "router"), or None.
            pattern: The pattern to match against.

        Returns:
            True if the decorator matches the pattern.
        """
        # Decorator name must match
        if not re.match(pattern.decorator_name, decorator_name):
            return False

        # If pattern specifies an object, it must match
        if pattern.object_name is not None:
            if object_name is None:
                return False
            if not re.match(pattern.object_name, object_name):
                return False

        return True
