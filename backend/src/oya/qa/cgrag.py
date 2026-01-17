"""CGRAG (Contextually-Guided RAG) core functionality.

Implements iterative retrieval where the LLM identifies gaps in context
and the system fetches missing pieces across multiple passes.
"""

from __future__ import annotations

import re

import networkx as nx

from oya.graph.models import Subgraph
from oya.graph.query import get_neighborhood


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


def is_specific_gap(gap: str) -> bool:
    """Check if a gap request is specific (vs fuzzy).

    Specific gaps can be looked up directly in the graph.
    Fuzzy gaps need vector search.

    Args:
        gap: The gap description from LLM.

    Returns:
        True if gap is specific enough for graph lookup.
    """
    gap_lower = gap.lower()

    # Contains path separator patterns
    if "::" in gap or " in " in gap_lower:
        return True

    # Contains type keyword followed by name
    if any(
        keyword in gap_lower
        for keyword in ["function ", "class ", "method ", "def "]
    ):
        return True

    return False


def graph_lookup(
    gap: str,
    graph: nx.DiGraph,
    hops: int = 1,
) -> Subgraph | None:
    """Look up a specific gap in the code graph.

    Searches for nodes matching the gap description and returns
    the matching node plus its immediate neighborhood.

    Args:
        gap: The gap description (e.g., "verify_token in auth/verify.py").
        graph: The code knowledge graph.
        hops: Number of hops to include in neighborhood.

    Returns:
        Subgraph containing matched node and neighbors, or None if not found.
    """
    # Extract the likely node name from the gap
    node_name = _extract_node_name(gap)
    if not node_name:
        return None

    # Search for matching node
    matching_node_id = None
    for node_id in graph.nodes():
        node_data = graph.nodes[node_id]
        name = node_data.get("name", "")

        # Exact match on node ID
        if node_id == gap or node_id.endswith(f"::{node_name}"):
            matching_node_id = node_id
            break

        # Match on name
        if name == node_name:
            matching_node_id = node_id
            break

    if not matching_node_id:
        return None

    # Get neighborhood
    return get_neighborhood(graph, matching_node_id, hops=hops, min_confidence=0.0)


def _extract_node_name(gap: str) -> str | None:
    """Extract the likely node/function name from a gap description.

    Args:
        gap: The gap description.

    Returns:
        The extracted name, or None if can't extract.
    """
    # Handle "path::name" format
    if "::" in gap:
        return gap.split("::")[-1].strip()

    # Handle "name in path" format (preserve original case)
    if " in " in gap.lower():
        lower_gap = gap.lower()
        in_pos = lower_gap.find(" in ")
        return gap[:in_pos].strip()

    # Handle "function name" format
    for keyword in ["function ", "class ", "method ", "def "]:
        if keyword in gap.lower():
            idx = gap.lower().index(keyword) + len(keyword)
            rest = gap[idx:].strip()
            # Take first word
            return rest.split()[0] if rest else None

    # Fallback: first word that looks like an identifier
    words = gap.split()
    for word in words:
        # Skip common words
        if word.lower() in {"the", "a", "an", "in", "for", "to", "of", "that", "which"}:
            continue
        # Check if looks like identifier (starts with letter, contains only word chars)
        if word[0].isalpha() and word.replace("_", "").isalnum():
            return word

    return None
