"""CGRAG (Contextually-Guided RAG) core functionality.

Implements iterative retrieval where the LLM identifies gaps in context
and the system fetches missing pieces across multiple passes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import networkx as nx

from oya.config import ConfigError, EXTENSION_LANGUAGES, load_settings
from oya.generation.prompts import format_cgrag_prompt
from oya.graph.models import Subgraph
from oya.graph.query import get_neighborhood

if TYPE_CHECKING:
    from oya.llm.client import LLMClient
    from oya.qa.session import CGRAGSession
    from oya.vectorstore.store import VectorStore


def parse_gaps(response: str) -> list[str]:
    """Parse gap requests from LLM response.

    Extracts the <missing> section and parses each line as a gap request.

    Args:
        response: Raw LLM response with <answer> and <missing> sections.

    Returns:
        List of gap descriptions (empty if NONE or no section).
    """
    # Find <missing> section (XML tags are unambiguous)
    match = re.search(r"<missing>\s*(.+?)\s*</missing>", response, re.DOTALL | re.IGNORECASE)
    if not match:
        # Fallback: try legacy MISSING: format for backwards compatibility
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
        response: Raw LLM response with <answer> section.

    Returns:
        The answer text.
    """
    # Find <answer> section (XML tags are unambiguous)
    match = re.search(r"<answer>\s*(.+?)\s*</answer>", response, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()

    # Fallback: try legacy ANSWER: format for backwards compatibility
    match = re.search(
        r"ANSWER:\s*(.+?)(?=\n<missing>|\nMISSING\s*[\(:]|$)", response, re.DOTALL | re.IGNORECASE
    )
    if match:
        return match.group(1).strip()

    # Last resort: return the whole response
    return response.strip()


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


@dataclass
class GapReferences:
    """Extracted references from a gap description."""

    file_path: str | None = None
    function_name: str | None = None


def extract_references_from_gap(gap: str) -> GapReferences:
    """Extract file and function references from a gap description."""
    refs = GapReferences()

    # Strip backticks that LLMs often use for code references
    gap = gap.replace("`", "")

    # Common file extensions pattern (longer extensions first to avoid partial matches)
    _EXT_PATTERN = (
        r"\.(?:pyi|py|tsx|ts|jsx|js|java|go|rs|rb|cpp|hpp|cs|swift|kt|scala|php|vue|svelte|c|h)"
    )

    # Pattern: "func_name() in path/to/file.py" - function with parens before "in"
    func_in_file = re.search(rf"(\w+)\(\)\s+in\s+([\w/.-]+{_EXT_PATTERN})", gap)
    if func_in_file:
        refs.function_name = func_in_file.group(1)
        refs.file_path = func_in_file.group(2)
        return refs

    # Pattern: "func_name in path/to/file.py" - simple identifier before "in" + path
    simple_in_file = re.search(rf"\b(\w+)\s+in\s+([\w/.-]+{_EXT_PATTERN})", gap)
    if simple_in_file:
        refs.function_name = simple_in_file.group(1)
        refs.file_path = simple_in_file.group(2)
        return refs

    # Pattern: explicit file path
    file_match = re.search(rf"([\w/.-]+{_EXT_PATTERN})", gap)
    if file_match:
        refs.file_path = file_match.group(1)

    # Pattern: function_name() or function_name
    func_match = re.search(r"\b(\w+)\(\)", gap)
    if func_match:
        refs.function_name = func_match.group(1)
    elif not refs.function_name:
        # Try to find a function-like name
        func_match = re.search(r"(?:function|method|implementation of)\s+(\w+)", gap, re.IGNORECASE)
        if func_match:
            refs.function_name = func_match.group(1)

    return refs


async def run_cgrag_loop(
    question: str,
    initial_context: str,
    session: CGRAGSession,
    llm: LLMClient,
    graph: nx.DiGraph | None,
    vectorstore: VectorStore | None,
    source_path: Path | None = None,
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
        source_path: Optional path to source code for reading actual files.

    Returns:
        CGRAGResult with final answer and iteration metadata.
    """
    try:
        settings = load_settings()
        max_passes = settings.ask.cgrag_max_passes
    except (ValueError, OSError, ConfigError):
        # Settings not available
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
            retrieved = await _retrieve_for_gap(gap, graph, vectorstore, session, source_path)
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
    source_path: Path | None = None,
) -> str | None:
    """Retrieve context for a single gap.

    Tries graph lookup first for specific gaps, then falls back to vector search.
    When source_path is available, also reads actual source file content.

    Args:
        gap: The gap description from LLM.
        graph: Optional code graph for targeted retrieval.
        vectorstore: Optional vector store for fuzzy retrieval.
        session: CGRAG session for caching nodes.
        source_path: Optional path to source code directory.

    Returns:
        Retrieved context as a string, or None if not found.
    """
    # Try graph lookup for specific gaps
    if graph is not None and is_specific_gap(gap):
        subgraph = graph_lookup(gap, graph)
        if subgraph and subgraph.nodes:
            # Cache nodes in session
            session.add_nodes(subgraph.nodes)

            # If source_path is available, try to read actual source code
            if source_path is not None:
                source_context = _read_source_for_nodes(subgraph.nodes, source_path)
                if source_context:
                    return source_context

            return _format_subgraph_context(subgraph)

    # Try vector search for fuzzy gaps
    if vectorstore is not None:
        try:
            settings = load_settings()
            top_k = settings.ask.cgrag_targeted_top_k
        except (ValueError, OSError, ConfigError):
            # Settings not available
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


def _read_source_for_nodes(
    nodes: list,
    source_path: Path,
    max_lines_per_file: int = 200,
    max_total_lines: int = 1000,
) -> str | None:
    """Read actual source code for graph nodes.

    Args:
        nodes: List of Node objects with file_path, line_start, line_end.
        source_path: Path to source code directory.
        max_lines_per_file: Maximum lines to read per file.
        max_total_lines: Maximum total lines across all files to prevent context overflow.

    Returns:
        Formatted source code context, or None if no files could be read.
    """
    context_parts: list[str] = []
    seen_files: set[str] = set()
    total_lines = 0

    for node in nodes:
        # Stop if we've hit the total line limit
        if total_lines >= max_total_lines:
            break

        file_path = getattr(node, "file_path", None)
        if not file_path or file_path in seen_files:
            continue

        full_path = source_path / file_path
        if not full_path.exists() or not full_path.is_file():
            continue

        seen_files.add(file_path)
        line_start = getattr(node, "line_start", 1)
        line_end = getattr(node, "line_end", None)

        try:
            with open(full_path, encoding="utf-8", errors="replace") as f:
                lines = f.readlines()

            # Extract relevant lines (1-indexed to 0-indexed)
            start_idx = max(0, line_start - 1)
            if line_end is not None:
                end_idx = min(len(lines), line_end)
            else:
                end_idx = min(len(lines), start_idx + max_lines_per_file)

            # Add some context lines before and after
            context_before = 5
            context_after = 5
            start_idx = max(0, start_idx - context_before)
            end_idx = min(len(lines), end_idx + context_after)

            # Limit to remaining budget
            remaining_lines = max_total_lines - total_lines
            if remaining_lines <= 0:
                break

            snippet_lines = lines[start_idx:end_idx]
            if not snippet_lines:
                continue

            # Truncate if exceeds remaining budget
            if len(snippet_lines) > remaining_lines:
                snippet_lines = snippet_lines[:remaining_lines]
                end_idx = start_idx + len(snippet_lines)

            total_lines += len(snippet_lines)
            snippet = "".join(snippet_lines)

            # Determine language for syntax highlighting hint
            ext = full_path.suffix.lower()
            lang = EXTENSION_LANGUAGES.get(ext, "")

            node_name = getattr(node, "name", "")
            header = f"### {file_path}"
            if node_name:
                header += f" :: {node_name}"
            header += f" (lines {start_idx + 1}-{end_idx})"

            context_parts.append(f"{header}\n```{lang}\n{snippet.rstrip()}\n```")

        except (OSError, UnicodeDecodeError):
            # Skip files that can't be read
            continue

    if not context_parts:
        return None

    return "\n\n".join(context_parts)
