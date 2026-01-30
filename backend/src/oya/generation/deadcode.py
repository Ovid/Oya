"""Dead code detection for wiki generation.

Analyzes the code graph to identify symbols with no incoming references,
categorizing them as "probably unused" (zero edges) or "possibly unused"
(only low-confidence edges).
"""

import re
from dataclasses import dataclass, field


@dataclass
class UnusedSymbol:
    """A symbol identified as potentially unused."""

    name: str
    file_path: str
    line: int
    symbol_type: str  # "function", "class", "method", or "variable"


@dataclass
class DeadcodeReport:
    """Report of potentially unused code symbols.

    Attributes:
        probably_unused_functions: Functions with no incoming edges.
        probably_unused_classes: Classes with no incoming edges.
        possibly_unused_functions: Functions with only low-confidence edges.
        possibly_unused_classes: Classes with only low-confidence edges.
        possibly_unused_variables: Variables with only low-confidence edges.
    """

    probably_unused_functions: list[UnusedSymbol] = field(default_factory=list)
    probably_unused_classes: list[UnusedSymbol] = field(default_factory=list)
    possibly_unused_functions: list[UnusedSymbol] = field(default_factory=list)
    possibly_unused_classes: list[UnusedSymbol] = field(default_factory=list)
    possibly_unused_variables: list[UnusedSymbol] = field(default_factory=list)


# Patterns for symbols that should never be flagged as dead code
EXCLUDED_PATTERNS = [
    re.compile(r"^test_"),  # Test functions (prefix)
    re.compile(r"_test$"),  # Test functions (suffix)
    re.compile(r"^__.*__$"),  # Python dunders
    re.compile(r"^main$"),  # Entry points
    re.compile(r"^app$"),  # FastAPI/Flask app
    re.compile(r"^_"),  # Private by convention
]


def is_excluded(name: str) -> bool:
    """Check if a symbol name should be excluded from dead code detection.

    Args:
        name: Symbol name to check.

    Returns:
        True if the symbol should be excluded.
    """
    return any(pattern.search(name) for pattern in EXCLUDED_PATTERNS)
