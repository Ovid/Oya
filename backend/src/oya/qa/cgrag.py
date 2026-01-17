"""CGRAG (Contextually-Guided RAG) core functionality.

Implements iterative retrieval where the LLM identifies gaps in context
and the system fetches missing pieces across multiple passes.
"""

from __future__ import annotations

import re


def parse_gaps(response: str) -> list[str]:
    """Parse gap requests from LLM response.

    Extracts the MISSING section and parses each line as a gap request.

    Args:
        response: Raw LLM response with ANSWER and MISSING sections.

    Returns:
        List of gap descriptions (empty if NONE or no section).
    """
    # Find MISSING section
    match = re.search(r"MISSING[^:]*:\s*(.+?)$", response, re.DOTALL | re.IGNORECASE)
    if not match:
        return []

    missing_section = match.group(1).strip()

    # Check for NONE
    if missing_section.upper().startswith("NONE"):
        return []

    # Parse each line as a gap
    gaps = []
    for line in missing_section.split("\n"):
        line = line.strip().lstrip("-").strip()
        if line and not line.upper().startswith("NONE"):
            gaps.append(line)

    return gaps


def parse_answer(response: str) -> str:
    """Extract answer from LLM response.

    Args:
        response: Raw LLM response with ANSWER section.

    Returns:
        The answer text.
    """
    # Find ANSWER section
    match = re.search(r"ANSWER:\s*(.+?)(?=MISSING|$)", response, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()

    # Fallback: return everything before MISSING
    parts = re.split(r"MISSING", response, flags=re.IGNORECASE)
    return parts[0].strip()
