"""Mermaid diagram syntax validation."""

import re
from dataclasses import dataclass, field


@dataclass
class ValidationResult:
    """Result of Mermaid diagram validation.

    Attributes:
        valid: True if the diagram syntax is valid.
        errors: List of human-readable error messages.
        line_numbers: Lines where errors were found.
    """

    valid: bool
    errors: list[str] = field(default_factory=list)
    line_numbers: list[int] = field(default_factory=list)


# Valid Mermaid diagram types
VALID_DIAGRAM_TYPES = frozenset([
    "flowchart",
    "graph",
    "sequencediagram",
    "classdiagram",
    "statediagram",
    "statediagram-v2",
    "erdiagram",
    "journey",
    "gantt",
    "pie",
    "quadrantchart",
    "requirementdiagram",
    "gitgraph",
    "mindmap",
    "timeline",
    "zenuml",
])


def validate_mermaid(content: str) -> ValidationResult:
    """Validate Mermaid diagram syntax.

    Performs structural validation including:
    - Diagram type declaration present
    - Balanced brackets [], (), {}
    - Subgraph/end pairing

    Args:
        content: Mermaid diagram content to validate.

    Returns:
        ValidationResult with validity status and any errors.
    """
    errors: list[str] = []
    line_numbers: list[int] = []

    lines = content.strip().split("\n")
    if not lines:
        return ValidationResult(valid=False, errors=["Empty diagram"], line_numbers=[0])

    # Check diagram type declaration
    first_line = lines[0].strip().lower()
    has_valid_type = any(first_line.startswith(dt) for dt in VALID_DIAGRAM_TYPES)
    if not has_valid_type:
        errors.append(
            "Missing or invalid diagram type. Must start with one of: flowchart, classDiagram, etc."
        )
        line_numbers.append(1)

    # Check balanced brackets
    bracket_pairs = [("[", "]"), ("(", ")"), ("{", "}")]
    for open_char, close_char in bracket_pairs:
        open_count = content.count(open_char)
        close_count = content.count(close_char)
        if open_count != close_count:
            errors.append(
                f"Unbalanced brackets: {open_count} '{open_char}' vs {close_count} '{close_char}'"
            )

    # Check subgraph/end pairing
    subgraph_count = len(re.findall(r"^\s*subgraph\b", content, re.MULTILINE | re.IGNORECASE))
    end_count = len(re.findall(r"^\s*end\b", content, re.MULTILINE | re.IGNORECASE))
    if subgraph_count != end_count:
        errors.append(f"Unmatched subgraph/end: {subgraph_count} subgraphs vs {end_count} ends")

    return ValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        line_numbers=line_numbers,
    )


def sanitize_label(text: str, max_length: int = 40) -> str:
    """Make text safe for Mermaid node labels.

    Handles problematic characters and truncates long labels.

    Args:
        text: Raw text to sanitize.
        max_length: Maximum length before truncation.

    Returns:
        Sanitized label safe for Mermaid diagrams.
    """
    # Replace newlines with spaces
    result = text.replace("\n", " ").replace("\r", "")

    # Remove or escape problematic characters
    # Brackets in labels need special handling
    result = result.replace("[", "(").replace("]", ")")
    result = result.replace("{", "(").replace("}", ")")
    result = result.replace('"', "'")
    result = result.replace("<", "").replace(">", "")

    # Collapse multiple spaces
    result = " ".join(result.split())

    # Truncate if too long
    if len(result) > max_length:
        result = result[: max_length - 3] + "..."

    return result


def sanitize_node_id(text: str) -> str:
    """Make text safe for Mermaid node IDs.

    Node IDs should only contain alphanumeric, underscore, and hyphen.

    Args:
        text: Raw text to convert to node ID.

    Returns:
        Valid Mermaid node ID.
    """
    # Replace common separators with underscores
    result = text.replace(".", "_").replace("/", "_").replace("-", "_")

    # Remove any remaining special characters
    result = re.sub(r"[^a-zA-Z0-9_]", "", result)

    # Collapse multiple underscores
    result = re.sub(r"_+", "_", result)

    # Ensure it doesn't start with a number
    if result and result[0].isdigit():
        result = "n" + result

    return result.strip("_")
