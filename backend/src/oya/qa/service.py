"""Q&A service with hybrid search and evidence gating."""

import re
from typing import Any

from oya.db.connection import Database
from oya.llm.client import LLMClient
from oya.qa.schemas import Citation, ConfidenceLevel, QARequest, QAResponse, SearchQuality
from oya.vectorstore.store import VectorStore


# Minimum number of results required for evidence to be considered sufficient
MIN_EVIDENCE_RESULTS = 2

# Minimum relevance score (lower distance = more relevant)
MAX_DISTANCE_THRESHOLD = 0.8

QA_SYSTEM_PROMPT = """You are a helpful assistant that answers questions about a codebase.
You have access to documentation, code, and notes from the repository.

When answering:
1. Be concise and accurate
2. Reference specific files and line numbers when possible
3. If you cite sources, list them at the end in the format [CITATIONS] followed by bullet points
4. Only answer based on the provided context - do not make up information

Format citations like:
[CITATIONS]
- path/to/file.py:10-20
- docs/readme.md
"""


class QAService:
    """Service for evidence-gated Q&A over codebase."""

    def __init__(
        self,
        vectorstore: VectorStore,
        db: Database,
        llm: LLMClient,
    ) -> None:
        """Initialize Q&A service.

        Args:
            vectorstore: ChromaDB vector store for semantic search.
            db: SQLite database for full-text search.
            llm: LLM client for answer generation.
        """
        self._vectorstore = vectorstore
        self._db = db
        self._llm = llm

    async def search(
        self,
        query: str,
        context: dict[str, Any] | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Perform hybrid search combining semantic and full-text search.

        Args:
            query: Search query.
            context: Optional page context for filtering.
            limit: Maximum results to return.

        Returns:
            Combined and deduplicated search results.
        """
        results: list[dict[str, Any]] = []
        seen_paths: set[str] = set()

        # Semantic search via ChromaDB
        where_filter = None
        if context and context.get("page_type"):
            # Could filter by type if needed
            pass

        try:
            semantic_results = self._vectorstore.query(
                query_text=query,
                n_results=limit,
                where=where_filter,
            )

            for i, doc_id in enumerate(semantic_results.get("ids", [[]])[0]):
                documents = semantic_results.get("documents", [[]])[0]
                metadatas = semantic_results.get("metadatas", [[]])[0]
                distances = semantic_results.get("distances", [[]])[0]

                if i < len(documents):
                    path = metadatas[i].get("path", "") if i < len(metadatas) else ""
                    if path and path not in seen_paths:
                        seen_paths.add(path)
                        results.append({
                            "id": doc_id,
                            "content": documents[i],
                            "path": path,
                            "title": metadatas[i].get("title", "") if i < len(metadatas) else "",
                            "type": metadatas[i].get("type", "wiki") if i < len(metadatas) else "wiki",
                            "distance": distances[i] if i < len(distances) else 1.0,
                            "source": "semantic",
                        })
        except Exception:
            # If semantic search fails, continue with FTS only
            pass

        # Full-text search via SQLite FTS5
        try:
            search_terms = query.replace('"', '""')
            fts_query = f'"{search_terms}"*'

            sql = """
                SELECT content, title, path, type, bm25(fts_content) as score
                FROM fts_content
                WHERE fts_content MATCH ?
                ORDER BY score
                LIMIT ?
            """

            cursor = self._db.execute(sql, (fts_query, limit))

            for row in cursor.fetchall():
                path = row["path"] or ""
                if path and path not in seen_paths:
                    seen_paths.add(path)
                    results.append({
                        "id": f"fts_{path}",
                        "content": row["content"] or "",
                        "path": path,
                        "title": row["title"] or "",
                        "type": row["type"] or "wiki",
                        "distance": 1.0 - min(abs(row["score"]) / 10, 1.0) if row["score"] else 0.5,
                        "source": "fts",
                    })
        except Exception:
            # If FTS fails, use whatever semantic results we have
            pass

        # Sort by type (notes first) then by distance
        type_priority = {"note": 0, "code": 1, "wiki": 2}
        results.sort(key=lambda r: (type_priority.get(r["type"], 3), r["distance"]))

        return results[:limit]

    def _evaluate_evidence(self, results: list[dict[str, Any]]) -> bool:
        """Evaluate if search results provide sufficient evidence.

        Args:
            results: Search results to evaluate.

        Returns:
            True if evidence is sufficient for answering.
        """
        if len(results) < MIN_EVIDENCE_RESULTS:
            return False

        # Check if at least some results are relevant (low distance)
        relevant_count = sum(
            1 for r in results
            if r.get("distance", 1.0) < MAX_DISTANCE_THRESHOLD
        )

        return relevant_count >= MIN_EVIDENCE_RESULTS

    def _calculate_confidence(self, results: list[dict[str, Any]]) -> ConfidenceLevel:
        """Calculate confidence level from search results.

        Args:
            results: Search results with distance scores.

        Returns:
            HIGH if 3+ strong matches and best < 0.3
            MEDIUM if 1+ decent match and best < 0.6
            LOW otherwise
        """
        if not results:
            return ConfidenceLevel.LOW

        # Count results with good relevance (distance < 0.5)
        strong_matches = sum(1 for r in results if r.get("distance", 1.0) < 0.5)

        # Check best result quality
        best_distance = min(r.get("distance", 1.0) for r in results)

        if strong_matches >= 3 and best_distance < 0.3:
            return ConfidenceLevel.HIGH
        elif strong_matches >= 1 and best_distance < 0.6:
            return ConfidenceLevel.MEDIUM
        else:
            return ConfidenceLevel.LOW

    def _build_context_prompt(self, question: str, results: list[dict[str, Any]]) -> str:
        """Build prompt with search results as context.

        Args:
            question: User's question.
            results: Search results to include as context.

        Returns:
            Formatted prompt string.
        """
        context_parts = []

        for r in results:
            source_type = r.get("type", "unknown")
            path = r.get("path", "unknown")
            content = r.get("content", "")[:2000]  # Limit content length

            context_parts.append(f"[{source_type.upper()}] {path}\n{content}")

        context_str = "\n\n---\n\n".join(context_parts)

        return f"""Based on the following context from the codebase, answer the question.

CONTEXT:
{context_str}

QUESTION: {question}

Answer the question based only on the context provided. Include citations to specific files."""

    def _extract_citations(
        self,
        answer: str,
        results: list[dict[str, Any]],
    ) -> list[Citation]:
        """Extract citations from LLM response.

        Args:
            answer: LLM-generated answer.
            results: Search results used for context.

        Returns:
            List of extracted citations.
        """
        citations: list[Citation] = []
        seen_paths: set[str] = set()

        # Look for [CITATIONS] section in response
        citations_match = re.search(r"\[CITATIONS\](.*?)(?:\n\n|$)", answer, re.DOTALL | re.IGNORECASE)

        if citations_match:
            citations_text = citations_match.group(1)
            # Parse bullet points
            for line in citations_text.strip().split("\n"):
                line = line.strip().lstrip("-").strip()
                if not line:
                    continue

                # Parse path:lines format
                if ":" in line:
                    parts = line.split(":", 1)
                    path = parts[0].strip()
                    lines = parts[1].strip() if len(parts) > 1 else None
                else:
                    path = line
                    lines = None

                if path and path not in seen_paths:
                    seen_paths.add(path)
                    # Find title from results
                    title = path
                    for r in results:
                        if r.get("path") == path:
                            title = r.get("title") or path
                            break

                    citations.append(Citation(path=path, title=title, lines=lines))

        # If no explicit citations, use top results
        if not citations:
            for r in results[:3]:
                path = r.get("path", "")
                if path and path not in seen_paths:
                    seen_paths.add(path)
                    citations.append(Citation(
                        path=path,
                        title=r.get("title") or path,
                        lines=None,
                    ))

        return citations

    def _clean_answer(self, answer: str) -> str:
        """Remove citations section from answer text.

        Args:
            answer: Raw LLM response.

        Returns:
            Cleaned answer without citations block.
        """
        # Remove [CITATIONS] section - match from [CITATIONS] to end of string
        # since citations should always be at the end
        cleaned = re.sub(r"\[CITATIONS\].*", "", answer, flags=re.DOTALL | re.IGNORECASE)
        return cleaned.strip()

    def _path_to_url(self, wiki_path: str) -> str:
        """Convert wiki path to frontend route.

        Args:
            wiki_path: Path relative to wiki (e.g., 'files/src_main-py.md')

        Returns:
            Frontend route (e.g., '/files/src_main-py')
        """
        route = wiki_path.removesuffix(".md")

        if route == "overview":
            return "/"
        elif route == "architecture":
            return "/architecture"
        else:
            return f"/{route}"

    async def ask(self, request: QARequest) -> QAResponse:
        """Answer a question about the codebase.

        Args:
            request: Q&A request with question, context, and mode.

        Returns:
            Q&A response with answer, citations, and disclaimer.
        """
        # Perform hybrid search
        results = await self.search(
            request.question,
            context=request.context,
        )

        # Evaluate evidence
        evidence_sufficient = self._evaluate_evidence(results)

        # In gated mode, refuse to answer if evidence insufficient
        if request.mode == QAMode.GATED and not evidence_sufficient:
            return QAResponse(
                answer="",
                citations=[],
                evidence_sufficient=False,
                disclaimer="Unable to answer: insufficient evidence in the codebase. Try rephrasing your question or switching to loose mode.",
            )

        # Build prompt and generate answer
        prompt = self._build_context_prompt(request.question, results)

        try:
            raw_answer = await self._llm.generate(
                prompt=prompt,
                system_prompt=QA_SYSTEM_PROMPT,
                temperature=0.5,
            )
        except Exception as e:
            return QAResponse(
                answer="",
                citations=[],
                evidence_sufficient=evidence_sufficient,
                disclaimer=f"Error generating answer: {str(e)}",
            )

        # Extract citations and clean answer
        citations = self._extract_citations(raw_answer, results)
        answer = self._clean_answer(raw_answer)

        # Build disclaimer based on mode and evidence
        if request.mode == QAMode.LOOSE and not evidence_sufficient:
            disclaimer = "AI-generated answer with limited evidence. This response may be speculative. Please verify against the codebase."
        else:
            disclaimer = "AI-generated; may contain errors. Please verify against the codebase."

        return QAResponse(
            answer=answer,
            citations=citations,
            evidence_sufficient=evidence_sufficient,
            disclaimer=disclaimer,
        )
