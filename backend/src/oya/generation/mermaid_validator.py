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
