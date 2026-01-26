"""Utilities for building and parsing YAML frontmatter in wiki pages.

Frontmatter provides metadata for each wiki page including:
- source: The source file/directory path (optional for overview pages)
- type: Page type (file, directory, overview, etc.)
- commit: Git commit hash when page was generated
- generated: ISO timestamp of generation
- layer: Architecture layer (optional)

This metadata enables detection of orphaned pages during cleanup.
"""

from datetime import datetime

import yaml


def build_frontmatter(
    source: str | None,
    page_type: str,
    commit: str,
    generated: datetime,
    layer: str | None = None,
) -> str:
    """Build YAML frontmatter string for a wiki page.

    Args:
        source: Source file/directory path (None for overview pages)
        page_type: Type of page (file, directory, overview, etc.)
        commit: Git commit hash when page was generated
        generated: Datetime when page was generated
        layer: Architecture layer (optional)

    Returns:
        YAML frontmatter string starting with --- and ending with ---
        followed by a blank line.
    """
    metadata: dict[str, str] = {}

    if source is not None:
        metadata["source"] = source

    metadata["type"] = page_type
    metadata["generated"] = generated.isoformat()
    metadata["commit"] = commit

    if layer is not None:
        metadata["layer"] = layer

    # Build YAML with explicit string formatting to control order
    lines = ["---"]
    for key, value in metadata.items():
        lines.append(f"{key}: {value}")
    lines.append("---")
    lines.append("")  # Blank line after frontmatter

    return "\n".join(lines) + "\n"


def parse_frontmatter(content: str) -> tuple[dict | None, str]:
    """Parse YAML frontmatter from wiki page content.

    Args:
        content: Full page content that may start with frontmatter

    Returns:
        Tuple of (metadata_dict, remaining_content).
        If no valid frontmatter found, returns (None, original_content).
    """
    if not content.startswith("---\n"):
        return None, content

    # Find the closing delimiter
    # Start searching after the opening "---\n"
    end_pos = content.find("\n---\n", 4)
    if end_pos == -1:
        # Check for closing delimiter at end of content
        if content.rstrip().endswith("\n---"):
            end_pos = content.rstrip().rfind("\n---")
        else:
            return None, content

    # Extract the YAML content between delimiters
    yaml_content = content[4:end_pos]

    try:
        metadata = yaml.safe_load(yaml_content)
        if not isinstance(metadata, dict):
            return None, content
    except yaml.YAMLError:
        return None, content

    # Calculate where remaining content starts
    # After closing "---\n", skip optional blank line
    remaining_start = end_pos + 5  # len("\n---\n")

    # Skip one blank line if present
    if remaining_start < len(content) and content[remaining_start] == "\n":
        remaining_start += 1

    remaining_content = content[remaining_start:]

    return metadata, remaining_content
