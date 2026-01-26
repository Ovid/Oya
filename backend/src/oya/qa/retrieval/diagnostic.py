"""Diagnostic mode retrieval for error debugging."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from oya.db.code_index import CodeIndexQuery, CodeIndexEntry


@dataclass
class ErrorAnchors:
    """Extracted error information from a query."""

    exception_types: list[str] = field(default_factory=list)
    error_strings: list[str] = field(default_factory=list)
    file_refs: list[str] = field(default_factory=list)
    function_refs: list[str] = field(default_factory=list)


@dataclass
class RetrievalResult:
    """A single retrieval result."""

    content: str
    source: str  # "code_index", "source_file", "wiki"
    path: str
    line_range: tuple[int, int] | None = None
    relevance: str = ""  # Why this was retrieved


def extract_error_anchors(query: str) -> ErrorAnchors:
    """Extract error-related anchors from a query."""
    anchors = ErrorAnchors()

    # Extract exception types: ValueError, TypeError, sqlite3.OperationalError
    exception_pattern = r"\b(\w+\.)?(\w+(?:Error|Exception))\b"
    for match in re.finditer(exception_pattern, query):
        full_match = match.group(0)
        anchors.exception_types.append(full_match)
        # Also add just the exception name without module
        if match.group(2):
            anchors.exception_types.append(match.group(2))

    # Extract quoted strings (likely error messages)
    quoted_pattern = r'["\']([^"\']{5,})["\']'
    for match in re.finditer(quoted_pattern, query):
        anchors.error_strings.append(match.group(1))

    # Extract file references from stack traces
    file_pattern = r'File\s+"([^"]+\.py)"'
    for match in re.finditer(file_pattern, query):
        anchors.file_refs.append(match.group(1))

    # Also catch bare file paths
    path_pattern = r"\b([\w/]+\.(?:py|ts|js|java))\b"
    for match in re.finditer(path_pattern, query):
        if match.group(1) not in anchors.file_refs:
            anchors.file_refs.append(match.group(1))

    # Extract function names from stack traces: "line 45, in get_db"
    # Only match when preceded by line number to avoid false positives like "error in production"
    func_pattern = r"line\s+\d+,?\s+in\s+(\w+)"
    for match in re.finditer(func_pattern, query):
        anchors.function_refs.append(match.group(1))

    # Deduplicate
    anchors.exception_types = list(set(anchors.exception_types))
    anchors.error_strings = list(set(anchors.error_strings))
    anchors.file_refs = list(set(anchors.file_refs))
    anchors.function_refs = list(set(anchors.function_refs))

    return anchors


class DiagnosticRetriever:
    """Retrieves context for diagnostic (error debugging) queries."""

    def __init__(self, code_index: CodeIndexQuery):
        self.code_index = code_index

    async def retrieve(self, query: str, budget: int = 2000) -> list[RetrievalResult]:
        """Retrieve context for diagnosing an error.

        Args:
            query: The user's diagnostic question
            budget: Token budget for results (TODO: implement token-aware truncation)
        """
        results: list[RetrievalResult] = []
        anchors = extract_error_anchors(query)

        # 1. Find functions by exception type
        error_sites: list[CodeIndexEntry] = []
        for exc_type in anchors.exception_types:
            entries = self.code_index.find_by_raises(exc_type)
            error_sites.extend(entries)

        # 2. Find functions by error string
        for err_str in anchors.error_strings:
            entries = self.code_index.find_by_error_string(err_str)
            error_sites.extend(entries)

        # 3. Direct lookup if file/function specified
        for func in anchors.function_refs:
            entries = self.code_index.find_by_symbol(func)
            error_sites.extend(entries)

        # Deduplicate by (file_path, symbol_name)
        seen = set()
        unique_sites = []
        for entry in error_sites:
            key = (entry.file_path, entry.symbol_name)
            if key not in seen:
                seen.add(key)
                unique_sites.append(entry)

        # 4. Walk call graph backward from error sites
        callers_with_mutations: list[CodeIndexEntry] = []
        for site in unique_sites[:5]:  # Limit to top 5 error sites
            callers = self.code_index.get_callers(site.symbol_name)
            for caller in callers:
                if caller.mutates:  # Prioritize callers that mutate state
                    callers_with_mutations.append(caller)

        # 5. Build results
        # Add error sites
        for entry in unique_sites[:3]:
            results.append(
                RetrievalResult(
                    content=self._format_entry(entry),
                    source="code_index",
                    path=entry.file_path,
                    line_range=(entry.line_start, entry.line_end),
                    relevance=f"Error site: raises {entry.raises}",
                )
            )

        # Add callers with mutations
        for entry in callers_with_mutations[:3]:
            results.append(
                RetrievalResult(
                    content=self._format_entry(entry),
                    source="code_index",
                    path=entry.file_path,
                    line_range=(entry.line_start, entry.line_end),
                    relevance=f"Caller that mutates: {entry.mutates}",
                )
            )

        return results

    def _format_entry(self, entry: CodeIndexEntry) -> str:
        """Format a code index entry for context."""
        lines = [
            f"# {entry.file_path}:{entry.line_start}-{entry.line_end}",
            f"# {entry.signature}" if entry.signature else "",
            f"# Raises: {', '.join(entry.raises)}" if entry.raises else "",
            f"# Mutates: {', '.join(entry.mutates)}" if entry.mutates else "",
            "",
            f"[Source code would be fetched here for {entry.symbol_name}]",
        ]
        return "\n".join(line for line in lines if line)
