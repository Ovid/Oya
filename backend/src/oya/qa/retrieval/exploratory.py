"""Exploratory mode retrieval for tracing code flows."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from oya.db.code_index import CodeIndexQuery, CodeIndexEntry

from oya.qa.retrieval.diagnostic import RetrievalResult


def extract_trace_subject(query: str) -> str | None:
    """Extract the subject being traced from a query."""
    patterns = [
        r"trace\s+(?:the\s+)?(\w+)",
        r"(\w+)\s+flow",
        r"how\s+does\s+(\w+)",
        r"walk\s+through\s+(?:the\s+)?(\w+)",
        r"(\w+)\s+path",
    ]

    for pattern in patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            subject = match.group(1).lower()
            if subject not in ("the", "a", "an", "this", "that", "code", "it"):
                return subject

    return None


class ExploratoryRetriever:
    """Retrieves context for exploratory (flow tracing) queries."""

    def __init__(self, code_index: CodeIndexQuery):
        self.code_index = code_index

    async def retrieve(self, query: str, budget: int = 2500) -> list[RetrievalResult]:
        """Retrieve context for tracing a code flow.

        Args:
            query: The user's exploratory question
            budget: Token budget for results (TODO: implement token-aware truncation)
        """
        results: list[RetrievalResult] = []
        subject = extract_trace_subject(query)

        if not subject:
            return results

        # 1. Find entry points matching subject
        entry_points = self._find_entry_points(subject)

        if not entry_points:
            return results

        # 2. Walk call graph forward from entry points
        flow_entries: list[tuple[CodeIndexEntry, int]] = []
        visited = set()

        for entry in entry_points[:2]:
            self._walk_forward(entry, 0, 3, flow_entries, visited)

        # 3. Build flow representation
        if flow_entries:
            flow_text = self._build_flow_text(flow_entries)
            results.append(
                RetrievalResult(
                    content=flow_text,
                    source="code_index",
                    path="<flow diagram>",
                    relevance=f"Execution flow for {subject}",
                )
            )

        # 4. Add key function details
        for entry, depth in flow_entries[:5]:
            results.append(
                RetrievalResult(
                    content=self._format_entry(entry),
                    source="code_index",
                    path=entry.file_path,
                    line_range=(entry.line_start, entry.line_end),
                    relevance=f"Flow step at depth {depth}",
                )
            )

        return results

    def _find_entry_points(self, subject: str) -> list[CodeIndexEntry]:
        """Find functions that could be entry points for the subject."""
        entries = self.code_index.find_by_symbol(subject)

        def priority(e: CodeIndexEntry) -> int:
            if "route" in e.symbol_type.lower():
                return 0
            if e.symbol_type == "function":
                return 1
            return 2

        return sorted(entries, key=priority)

    def _walk_forward(
        self,
        entry: CodeIndexEntry,
        depth: int,
        max_depth: int,
        results: list[tuple[CodeIndexEntry, int]],
        visited: set[str],
    ) -> None:
        """Walk call graph forward from entry."""
        if depth > max_depth:
            return
        if entry.symbol_name in visited:
            return

        visited.add(entry.symbol_name)
        results.append((entry, depth))

        callees = self.code_index.get_callees(entry.symbol_name)
        for callee in callees[:3]:
            self._walk_forward(callee, depth + 1, max_depth, results, visited)

    def _build_flow_text(self, entries: list[tuple[CodeIndexEntry, int]]) -> str:
        """Build a textual flow representation."""
        lines = ["# Execution Flow", ""]

        for entry, depth in entries:
            indent = "  " * depth
            arrow = "-> " if depth > 0 else ""
            lines.append(f"{indent}{arrow}{entry.symbol_name}()")

        return "\n".join(lines)

    def _format_entry(self, entry: CodeIndexEntry) -> str:
        """Format a code index entry for context."""
        lines = [
            f"# {entry.file_path}:{entry.line_start}-{entry.line_end}",
            f"# {entry.signature}" if entry.signature else "",
            f"# Calls: {', '.join(entry.calls[:5])}" if entry.calls else "",
            "",
            f"[Source code would be fetched here for {entry.symbol_name}]",
        ]
        return "\n".join(line for line in lines if line)
