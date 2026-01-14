"""Search and vector store configuration.

These settings control hybrid search (semantic + full-text) used by Q&A
and the search API. Hybrid search combines ChromaDB vector similarity
with SQLite FTS5 full-text search, then merges and ranks results.
"""

# =============================================================================
# Result Limits
# =============================================================================
# Default number of results to return from search operations. Higher values
# provide more context but increase processing time and token usage.

DEFAULT_SEARCH_LIMIT = 10
SNIPPET_MAX_LENGTH = 200

# =============================================================================
# Result Prioritization
# =============================================================================
# When ranking combined results, content type affects ordering. Human-written
# notes are prioritized over code, which is prioritized over generated wiki
# content. Lower numbers = higher priority.

TYPE_PRIORITY = {"note": 0, "code": 1, "wiki": 2}

# =============================================================================
# Deduplication
# =============================================================================
# Search results from different sources may contain duplicate content.
# We hash the first N characters of each result to detect near-duplicates.

DEDUP_HASH_LENGTH = 500
