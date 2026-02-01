"""Dead code detection for wiki generation.

Analyzes the code graph to identify symbols with no incoming references,
categorizing them as "probably unused" (zero edges) or "possibly unused"
(only low-confidence edges).
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path


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
# Note: Test code is primarily filtered at the file level via is_test_file(),
# but we keep test name patterns here for defense in depth
EXCLUDED_NAME_PATTERNS = [
    re.compile(r"^test_"),  # Test functions (prefix)
    re.compile(r"_test$"),  # Test functions (suffix)
    re.compile(r"^__.*__$"),  # Python dunders
    re.compile(r"^main$"),  # Entry points
    re.compile(r"^app$"),  # FastAPI/Flask app
    re.compile(r"^_"),  # Private by convention
]

# Patterns for identifying test files (language-agnostic)
# These patterns match against the full file path
TEST_PATH_PATTERNS = [
    re.compile(r"[/\\]tests?[/\\]"),  # /test/ or /tests/ directory
    re.compile(r"[/\\]__tests__[/\\]"),  # /__tests__/ (Jest convention)
    re.compile(r"[/\\]specs?[/\\]"),  # /spec/ or /specs/ directory
    re.compile(r"[/\\]test_[^/\\]+$"),  # /test_*.py etc
    re.compile(r"[/\\][^/\\]+_test\.[^/\\]+$"),  # /*_test.py, /*_test.go etc
    re.compile(r"[/\\][^/\\]+\.test\.[^/\\]+$"),  # /*.test.ts, /*.test.js etc
    re.compile(r"[/\\][^/\\]+\.spec\.[^/\\]+$"),  # /*.spec.ts, /*.spec.js etc
    re.compile(r"[/\\][^/\\]+_spec\.[^/\\]+$"),  # /*_spec.rb etc
]


def is_test_file(file_path: str) -> bool:
    """Check if a file path represents a test file.

    Uses language-agnostic patterns to identify test files:
    - Files in test/tests/__tests__/spec/specs directories
    - Files named test_*, *_test.*, *.test.*, *.spec.*

    Args:
        file_path: Path to the file (can be relative or absolute).

    Returns:
        True if the file appears to be a test file.
    """
    # Normalize path separators for consistent matching
    normalized = file_path.replace("\\", "/")
    return any(pattern.search(normalized) for pattern in TEST_PATH_PATTERNS)


def is_excluded(name: str) -> bool:
    """Check if a symbol name should be excluded from dead code detection.

    Args:
        name: Symbol name to check.

    Returns:
        True if the symbol should be excluded.
    """
    return any(pattern.search(name) for pattern in EXCLUDED_NAME_PATTERNS)


CONFIDENCE_THRESHOLD = 0.7


def _get_file_path_from_node_id(node_id: str) -> str:
    """Extract file path from a node ID like 'path/to/file.py::symbol_name'."""
    if "::" in node_id:
        return node_id.split("::")[0]
    return node_id


def analyze_deadcode(graph_dir: Path) -> DeadcodeReport:
    """Analyze graph data to find potentially unused symbols.

    Args:
        graph_dir: Directory containing nodes.json and edges.json.

    Returns:
        DeadcodeReport with categorized unused symbols.
    """
    graph_dir = Path(graph_dir)

    # Load nodes
    nodes_file = graph_dir / "nodes.json"
    if not nodes_file.exists():
        return DeadcodeReport()

    with open(nodes_file) as f:
        nodes = json.load(f)

    # Load edges
    edges_file = graph_dir / "edges.json"
    edges = []
    if edges_file.exists():
        with open(edges_file) as f:
            edges = json.load(f)

    # Build sets of targets by confidence level
    # IMPORTANT: Only count edges from non-test code as "usage"
    # Code that is only called by tests is effectively dead from production perspective
    high_confidence_targets: set[str] = set()
    low_confidence_targets: set[str] = set()

    for edge in edges:
        source = edge.get("source", "")
        target = edge.get("target", "")
        confidence = edge.get("confidence", 0.0)

        # Skip edges from test files - test calls don't count as production usage
        source_file = _get_file_path_from_node_id(source)
        if is_test_file(source_file):
            continue

        if confidence >= CONFIDENCE_THRESHOLD:
            high_confidence_targets.add(target)
        else:
            low_confidence_targets.add(target)

    # Categorize nodes
    report = DeadcodeReport()

    for node in nodes:
        node_id = node.get("id", "")
        name = node.get("name", "")
        node_type = node.get("type", "")
        file_path = node.get("file_path", "")
        line = node.get("line_start", 0)

        # Skip symbols in test files - we don't analyze test code for deadness
        if is_test_file(file_path):
            continue

        # Skip excluded names
        if is_excluded(name):
            continue

        # Check if this node has incoming edges (from non-test code)
        has_high_conf = node_id in high_confidence_targets
        has_low_conf = node_id in low_confidence_targets

        if has_high_conf:
            # Used with high confidence - not dead code
            continue

        symbol = UnusedSymbol(
            name=name,
            file_path=file_path,
            line=line,
            symbol_type=node_type,
        )

        if has_low_conf:
            # Only low-confidence edges - possibly unused
            if node_type in ("function", "method"):
                report.possibly_unused_functions.append(symbol)
            elif node_type == "class":
                report.possibly_unused_classes.append(symbol)
            elif node_type == "variable":
                report.possibly_unused_variables.append(symbol)
        else:
            # No edges at all - probably unused
            # Variables only go to possibly (design decision)
            if node_type == "variable":
                report.possibly_unused_variables.append(symbol)
            elif node_type in ("function", "method"):
                report.probably_unused_functions.append(symbol)
            elif node_type == "class":
                report.probably_unused_classes.append(symbol)

    return report


def generate_deadcode_page(report: DeadcodeReport) -> str:
    """Generate markdown content for the Code Health wiki page.

    Args:
        report: DeadcodeReport with categorized unused symbols.

    Returns:
        Markdown string for the wiki page.
    """
    lines = [
        "# Code Health: Potential Dead Code",
        "",
        "This page lists symbols where static analysis found no callers.",
        "**Many of these are false positives.** Review each carefully before removing.",
        "",
        "## Common False Positives",
        "",
        "Before removing anything, consider whether the symbol is:",
        "",
        "- **Test code** - pytest discovers `Test*` classes and `test_*` functions",
        "- **Entry points** - CLI commands, route handlers, event listeners",
        "- **Framework hooks** - `__init__`, lifecycle methods, signal handlers",
        "- **Public API** - Symbols intended for external consumers",
        "- **Dynamic calls** - Code invoked via `getattr()` or reflection",
        "",
    ]

    # Review Candidates section
    lines.append("## Review Candidates")
    lines.append("")
    lines.append(
        "The following symbols have no detected callers. This does NOT mean they are unused."
    )
    lines.append("")

    # Combine probably and possibly into single lists (less judgmental)
    all_functions = report.probably_unused_functions + report.possibly_unused_functions
    all_classes = report.probably_unused_classes + report.possibly_unused_classes
    all_variables = report.possibly_unused_variables

    _add_symbol_section(lines, "Functions", all_functions)
    _add_symbol_section(lines, "Classes", all_classes)
    _add_symbol_section(lines, "Variables", all_variables)

    return "\n".join(lines)


def _add_symbol_section(lines: list[str], title: str, symbols: list[UnusedSymbol]) -> None:
    """Add a section for a category of symbols.

    Args:
        lines: List of lines to append to.
        title: Section title (e.g., "Functions").
        symbols: List of unused symbols.
    """
    count = len(symbols)
    lines.append(f"### {title} ({count})")
    lines.append("")

    if not symbols:
        lines.append("None detected.")
        lines.append("")
        return

    # Table header
    lines.append("| Name | File | Line |")
    lines.append("|------|------|------|")

    # Sort by file path, then line for determinism
    sorted_symbols = sorted(symbols, key=lambda s: (s.file_path, s.line))

    for symbol in sorted_symbols:
        # Link to file page with line anchor
        link = f"[{symbol.name}](files/{symbol.file_path}#L{symbol.line})"
        lines.append(f"| {link} | {symbol.file_path} | {symbol.line} |")

    lines.append("")
