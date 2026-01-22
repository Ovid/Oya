"""CGRAG (Contextually-Guided RAG) core functionality.

Implements iterative retrieval where the LLM identifies gaps in context
and the system fetches missing pieces across multiple passes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import networkx as nx

from oya.config import ConfigError, load_settings
from oya.generation.prompts import format_cgrag_prompt
from oya.graph.models import Subgraph
from oya.graph.query import get_neighborhood

if TYPE_CHECKING:
    from oya.llm.client import LLMClient
    from oya.qa.session import CGRAGSession
    from oya.vectorstore.store import VectorStore


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
    # Find ANSWER section - match until "MISSING" appears at start of line (section header)
    # The section header format is: MISSING (or "NONE" if nothing needed):
    # Use \n to ensure we only match "MISSING" as a section header, not within text
    match = re.search(
        r"ANSWER:\s*(.+?)(?=\nMISSING\s*[\(:]|$)", response, re.DOTALL | re.IGNORECASE
    )
    if match:
        return match.group(1).strip()

    # Fallback: return everything before MISSING section header (at start of line)
    parts = re.split(r"\nMISSING\s*[\(:]", response, flags=re.IGNORECASE)
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
    if any(keyword in gap_lower for keyword in ["function ", "class ", "method ", "def "]):
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


@dataclass
class CGRAGResult:
    """Result from CGRAG iteration loop."""

    answer: str
    passes_used: int
    gaps_identified: list[str] = field(default_factory=list)
    gaps_resolved: list[str] = field(default_factory=list)
    gaps_unresolved: list[str] = field(default_factory=list)
    context_from_cache: bool = False


async def run_cgrag_loop(
    question: str,
    initial_context: str,
    session: CGRAGSession,
    llm: LLMClient,
    graph: nx.DiGraph | None,
    vectorstore: VectorStore | None,
) -> CGRAGResult:
    """Run the CGRAG iterative retrieval loop.

    Repeatedly asks the LLM to answer and identify gaps, then retrieves
    missing context until no more gaps or max passes reached.

    Args:
        question: The user's question.
        initial_context: Starting context from initial retrieval.
        session: CGRAG session for caching across passes.
        llm: LLM client for generating answers.
        graph: Optional code graph for targeted retrieval.
        vectorstore: Optional vector store for fuzzy retrieval.

    Returns:
        CGRAGResult with final answer and iteration metadata.
    """
    try:
        settings = load_settings()
        max_passes = settings.ask.cgrag_max_passes
    except (ValueError, OSError, ConfigError):
        # Settings not available (e.g., WORKSPACE_PATH not set in tests)
        max_passes = 3  # Default from CONFIG_SCHEMA

    context = initial_context
    all_gaps_identified: list[str] = []
    gaps_resolved: list[str] = []
    gaps_unresolved: list[str] = []
    answer = ""

    for pass_num in range(1, max_passes + 1):
        # Format prompt and get LLM response
        prompt = format_cgrag_prompt(question, context)
        response = await llm.generate(prompt)

        # Parse answer and gaps
        answer = parse_answer(response)
        gaps = parse_gaps(response)

        # If no gaps, we're done
        if not gaps:
            return CGRAGResult(
                answer=answer,
                passes_used=pass_num,
                gaps_identified=all_gaps_identified,
                gaps_resolved=gaps_resolved,
                gaps_unresolved=gaps_unresolved,
            )

        # Track all gaps identified
        for gap in gaps:
            if gap not in all_gaps_identified:
                all_gaps_identified.append(gap)

        # Check if all gaps were already not found (stop condition)
        new_gaps = [g for g in gaps if g not in session.not_found]
        if not new_gaps:
            # All gaps were already tried and not found
            for gap in gaps:
                if gap not in gaps_unresolved:
                    gaps_unresolved.append(gap)
            return CGRAGResult(
                answer=answer,
                passes_used=pass_num,
                gaps_identified=all_gaps_identified,
                gaps_resolved=gaps_resolved,
                gaps_unresolved=gaps_unresolved,
            )

        # Try to retrieve context for each gap
        new_context_parts: list[str] = []
        for gap in new_gaps:
            retrieved = await _retrieve_for_gap(gap, graph, vectorstore, session)
            if retrieved:
                new_context_parts.append(retrieved)
                if gap not in gaps_resolved:
                    gaps_resolved.append(gap)
            else:
                session.add_not_found(gap)
                if gap not in gaps_unresolved:
                    gaps_unresolved.append(gap)

        # Append new context
        if new_context_parts:
            context = context + "\n\n" + "\n\n".join(new_context_parts)

    # Hit max passes
    return CGRAGResult(
        answer=answer,
        passes_used=max_passes,
        gaps_identified=all_gaps_identified,
        gaps_resolved=gaps_resolved,
        gaps_unresolved=gaps_unresolved,
    )


async def _retrieve_for_gap(
    gap: str,
    graph: nx.DiGraph | None,
    vectorstore: VectorStore | None,
    session: CGRAGSession,
) -> str | None:
    """Retrieve context for a single gap.

    Tries graph lookup first for specific gaps, then falls back to vector search.

    Args:
        gap: The gap description from LLM.
        graph: Optional code graph for targeted retrieval.
        vectorstore: Optional vector store for fuzzy retrieval.
        session: CGRAG session for caching nodes.

    Returns:
        Retrieved context as a string, or None if not found.
    """
    # Try graph lookup for specific gaps
    if graph is not None and is_specific_gap(gap):
        subgraph = graph_lookup(gap, graph)
        if subgraph and subgraph.nodes:
            # Cache nodes in session
            session.add_nodes(subgraph.nodes)
            return _format_subgraph_context(subgraph)

    # Try vector search for fuzzy gaps
    if vectorstore is not None:
        try:
            settings = load_settings()
            top_k = settings.ask.cgrag_targeted_top_k
        except (ValueError, OSError, ConfigError):
            # Settings not available (e.g., WORKSPACE_PATH not set in tests)
            top_k = 3  # Default from CONFIG_SCHEMA
        raw_results = vectorstore.query(query_text=gap, n_results=top_k)
        documents = raw_results.get("documents", [[]])[0]
        metadatas = raw_results.get("metadatas", [[]])[0]
        if documents:
            context_parts = []
            for i, doc in enumerate(documents):
                file_path = metadatas[i].get("path", "Unknown") if i < len(metadatas) else "Unknown"
                context_parts.append(f"### {file_path}\n{doc}")
            return "\n\n".join(context_parts)

    return None


def _format_subgraph_context(subgraph: Subgraph) -> str:
    """Format a subgraph as context text for the LLM.

    Args:
        subgraph: The subgraph containing nodes and edges.

    Returns:
        Formatted context string.
    """
    return subgraph.to_context()
