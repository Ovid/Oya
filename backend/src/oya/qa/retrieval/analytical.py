"""Analytical mode retrieval for architectural analysis."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from oya.db.code_index import CodeIndexQuery, CodeIndexEntry
    from oya.vectorstore.issues import IssuesStore

from oya.qa.retrieval.diagnostic import RetrievalResult


def extract_scope(query: str) -> str | None:
    """Extract the scope being analyzed from a query."""
    patterns = [
        r"(?:flaws?|problems?|issues?)\s+(?:in|with)\s+(?:the\s+)?(\w+)",
        r"analyze\s+(?:the\s+)?(\w+)",
        r"what'?s\s+wrong\s+with\s+(?:the\s+)?(\w+)",
        r"(\w+)\s+(?:structure|architecture|design)",
    ]

    for pattern in patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            scope = match.group(1).lower()
            if scope not in ("the", "a", "an", "this", "code"):
                return scope

    return None


class AnalyticalRetriever:
    """Retrieves context for analytical (architecture/flaw) queries."""

    HIGH_FAN_OUT = 15
    HIGH_FAN_IN = 20

    def __init__(self, code_index: CodeIndexQuery, issues_store: IssuesStore | None = None):
        self.code_index = code_index
        self.issues_store = issues_store

    async def retrieve(self, query: str, budget: int = 2000) -> list[RetrievalResult]:
        """Retrieve context for architectural analysis.

        Args:
            query: The user's analytical question
            budget: Token budget for results (TODO: implement token-aware truncation)
        """
        results: list[RetrievalResult] = []
        scope = extract_scope(query)

        if not scope:
            return results

        # 1. Get entries for scope
        entries = self.code_index.find_by_file(scope)

        # 2. Compute structural metrics and find issues
        god_functions: list[tuple[CodeIndexEntry, int]] = []
        hotspots: list[tuple[CodeIndexEntry, int]] = []

        for entry in entries:
            fan_out = len(entry.calls)
            fan_in = len(entry.called_by)

            if fan_out > self.HIGH_FAN_OUT:
                god_functions.append((entry, fan_out))
            if fan_in > self.HIGH_FAN_IN:
                hotspots.append((entry, fan_in))

        # 3. Query issues store if available
        issues: list[dict] = []
        if self.issues_store and scope:
            issues = self.issues_store.query_issues(query=scope, limit=10)

        # 4. Build results
        # Add god functions
        for entry, fan_out in sorted(god_functions, key=lambda x: -x[1])[:3]:
            results.append(
                RetrievalResult(
                    content=self._format_entry(entry),
                    source="code_index",
                    path=entry.file_path,
                    line_range=(entry.line_start, entry.line_end),
                    relevance=f"High fan-out ({fan_out} calls) - potential god function",
                )
            )

        # Add hotspots
        for entry, fan_in in sorted(hotspots, key=lambda x: -x[1])[:3]:
            results.append(
                RetrievalResult(
                    content=self._format_entry(entry),
                    source="code_index",
                    path=entry.file_path,
                    line_range=(entry.line_start, entry.line_end),
                    relevance=f"High fan-in ({fan_in} callers) - potential hotspot",
                )
            )

        # Add issues from issues store
        for issue in issues[:5]:
            results.append(
                RetrievalResult(
                    content=str(issue.get("content", issue)),
                    source="issues_store",
                    path=issue.get("file_path", ""),
                    relevance=f"Pre-computed issue: {issue.get('category', 'unknown')}",
                )
            )

        return results

    def _format_entry(self, entry: CodeIndexEntry) -> str:
        """Format a code index entry for context."""
        lines = [
            f"# {entry.file_path}:{entry.line_start}-{entry.line_end}",
            f"# {entry.signature}" if entry.signature else "",
            f"# Fan-out: {len(entry.calls)} calls",
            f"# Fan-in: {len(entry.called_by)} callers",
            f"# Mutates: {', '.join(entry.mutates)}" if entry.mutates else "",
            "",
            f"[Source code would be fetched here for {entry.symbol_name}]",
        ]
        return "\n".join(line for line in lines if line)
