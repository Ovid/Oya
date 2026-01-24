"""Search endpoints."""

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from oya.api.deps import get_db
from oya.config import ConfigError, load_settings
from oya.db.connection import Database

router = APIRouter(prefix="/api/search", tags=["search"])


class SearchResult(BaseModel):
    """Individual search result."""

    title: str
    path: str
    snippet: str
    type: str
    score: float = 0.0


class SearchResponse(BaseModel):
    """Search response with results."""

    query: str
    results: list[SearchResult]
    total: int


@router.get("", response_model=SearchResponse)
async def search(
    q: str = Query(..., min_length=1, description="Search query"),
    type: str | None = Query(None, description="Filter by type: wiki, note"),
    limit: int = Query(20, ge=1, le=100),
    db: Database = Depends(get_db),
) -> SearchResponse:
    """Search wiki content and notes using full-text search."""
    # Build FTS5 query
    # Escape special characters and add prefix matching
    search_terms = q.replace('"', '""')
    fts_query = f'"{search_terms}"*'

    # Build SQL with optional type filter
    sql = """
        SELECT content, title, path, type,
               bm25(fts_content) as score
        FROM fts_content
        WHERE fts_content MATCH ?
    """
    params: list = [fts_query]

    if type:
        sql += " AND type = ?"
        params.append(type)

    sql += " ORDER BY score LIMIT ?"
    params.append(limit)

    cursor = db.execute(sql, tuple(params))

    results = []
    for row in cursor.fetchall():
        # Create snippet from content
        content = row["content"] or ""
        snippet = _create_snippet(content, q)

        results.append(
            SearchResult(
                title=row["title"] or "",
                path=row["path"] or "",
                snippet=snippet,
                type=row["type"] or "wiki",
                score=abs(row["score"]) if row["score"] else 0.0,
            )
        )

    return SearchResponse(
        query=q,
        results=results,
        total=len(results),
    )


def _create_snippet(content: str, query: str, max_length: int | None = None) -> str:
    """Create a snippet around the query terms."""
    if max_length is None:
        try:
            settings = load_settings()
            max_length = settings.search.snippet_max_length
        except (ValueError, OSError, ConfigError):
            # Settings not available
            max_length = 200  # Default from CONFIG_SCHEMA
    lower_content = content.lower()
    lower_query = query.lower()

    # Find position of query in content
    pos = lower_content.find(lower_query)

    if pos == -1:
        # Query not found, return start of content
        return content[:max_length] + ("..." if len(content) > max_length else "")

    # Calculate start and end positions for snippet
    start = max(0, pos - 50)
    end = min(len(content), pos + len(query) + 150)

    snippet = content[start:end]

    # Add ellipsis if needed
    if start > 0:
        snippet = "..." + snippet
    if end < len(content):
        snippet = snippet + "..."

    return snippet
