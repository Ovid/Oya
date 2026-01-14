"""Q&A service with hybrid search and confidence-based answers."""

import re
from typing import Any

from oya.config.qa import (
    HIGH_CONFIDENCE_THRESHOLD,
    MAX_CONTEXT_TOKENS,
    MAX_RESULT_TOKENS,
    MEDIUM_CONFIDENCE_THRESHOLD,
    MIN_STRONG_MATCHES_FOR_HIGH,
    STRONG_MATCH_THRESHOLD,
)
from oya.config.search import DEDUP_HASH_LENGTH, TYPE_PRIORITY
from oya.db.connection import Database
from oya.generation.chunking import estimate_tokens
from oya.llm.client import LLMClient
from oya.qa.schemas import Citation, ConfidenceLevel, QARequest, QAResponse, SearchQuality
from oya.vectorstore.store import VectorStore

QA_SYSTEM_PROMPT = """You are a helpful assistant that answers questions about a codebase.
You have access to documentation, code, and notes from the repository.

When answering:
1. Be concise and accurate
2. Base your answer only on the provided context
3. After your answer, output a JSON block with citations

Format your response as:
<answer>
Your answer here...
</answer>

<citations>
[
  {"path": "files/example-py.md", "relevant_text": "brief quote showing relevance"},
  {"path": "directories/src.md", "relevant_text": "another brief quote"}
]
</citations>

Only cite sources that directly support your answer. Include 1-5 citations.
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
        limit: int = 10,
    ) -> tuple[list[dict[str, Any]], bool, bool]:
        """Perform hybrid search combining semantic and full-text search.

        Args:
            query: Search query.
            limit: Maximum results to return.

        Returns:
            Tuple of (search results, semantic_ok, fts_ok).
        """
        results: list[dict[str, Any]] = []
        seen_paths: set[str] = set()
        semantic_ok = False
        fts_ok = False

        # Semantic search via ChromaDB
        try:
            semantic_results = self._vectorstore.query(
                query_text=query,
                n_results=limit,
            )
            semantic_ok = True

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
            fts_ok = True

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
        results.sort(key=lambda r: (TYPE_PRIORITY.get(r["type"], 3), r["distance"]))

        # Deduplicate similar content
        results = self._deduplicate_results(results)

        return results[:limit], semantic_ok, fts_ok

    def _deduplicate_results(self, results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Remove duplicate/near-duplicate content.

        Args:
            results: Search results to deduplicate.

        Returns:
            Deduplicated results preserving order.
        """
        seen_content_hashes: set[int] = set()
        deduplicated: list[dict[str, Any]] = []

        for r in results:
            content = r.get("content", "")
            # Hash first N chars (covers most duplicates)
            content_hash = hash(content[:DEDUP_HASH_LENGTH].strip().lower())

            if content_hash not in seen_content_hashes:
                seen_content_hashes.add(content_hash)
                deduplicated.append(r)

        return deduplicated

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

        # Count results with good relevance
        strong_matches = sum(
            1 for r in results if r.get("distance", 1.0) < STRONG_MATCH_THRESHOLD
        )

        # Check best result quality
        best_distance = min(r.get("distance", 1.0) for r in results)

        if strong_matches >= MIN_STRONG_MATCHES_FOR_HIGH and best_distance < HIGH_CONFIDENCE_THRESHOLD:
            return ConfidenceLevel.HIGH
        elif strong_matches >= 1 and best_distance < MEDIUM_CONFIDENCE_THRESHOLD:
            return ConfidenceLevel.MEDIUM
        else:
            return ConfidenceLevel.LOW

    def _truncate_at_sentence(self, text: str, max_tokens: int) -> str:
        """Truncate text at sentence boundary within token limit.

        Args:
            text: Text to truncate.
            max_tokens: Maximum tokens allowed.

        Returns:
            Truncated text ending at sentence boundary.
        """
        if estimate_tokens(text) <= max_tokens:
            return text

        # Split into sentences (simple heuristic)
        sentences = text.replace('\n', ' ').split('. ')
        result: list[str] = []
        for sentence in sentences:
            candidate = '. '.join(result + [sentence])
            if estimate_tokens(candidate) > max_tokens:
                break
            result.append(sentence)

        if not result:
            # If no complete sentence fits, truncate by characters
            chars_per_token = 4  # Approximate
            max_chars = max_tokens * chars_per_token
            return text[:max_chars].rsplit(' ', 1)[0] + '...'

        return '. '.join(result) + '.'

    def _build_context_prompt(
        self,
        question: str,
        results: list[dict[str, Any]],
    ) -> tuple[str, int]:
        """Build prompt with token-aware truncation.

        Args:
            question: User's question.
            results: Search results to include as context.

        Returns:
            Tuple of (formatted prompt, number of results used).
        """
        context_parts: list[str] = []
        total_tokens = 0
        results_used = 0

        for r in results:
            source_type = r.get("type", "unknown")
            path = r.get("path", "unknown")
            content = r.get("content", "")

            # Truncate individual result at sentence boundary
            content = self._truncate_at_sentence(content, max_tokens=MAX_RESULT_TOKENS)

            part = f"[{source_type.upper()}] {path}\n{content}"
            part_tokens = estimate_tokens(part)

            if total_tokens + part_tokens > MAX_CONTEXT_TOKENS:
                break

            context_parts.append(part)
            total_tokens += part_tokens
            results_used += 1

        context_str = "\n\n---\n\n".join(context_parts)

        prompt = f"""Based on the following context from the codebase, answer the question.

CONTEXT:
{context_str}

QUESTION: {question}

Answer the question based only on the context provided. Include citations to specific files."""

        return prompt, results_used

    def _extract_citations(
        self,
        response: str,
        results: list[dict[str, Any]],
    ) -> list[Citation]:
        """Extract citations from structured JSON output.

        Args:
            response: LLM response with <citations> block.
            results: Search results for validation.

        Returns:
            Validated citations with URLs.
        """
        import json

        citations: list[Citation] = []

        # Parse JSON citations block
        match = re.search(r'<citations>\s*(\[.*?\])\s*</citations>', response, re.DOTALL)
        if not match:
            # Fall back to legacy [CITATIONS] format for compatibility
            return self._extract_legacy_citations(response, results)

        try:
            raw_citations = json.loads(match.group(1))
        except json.JSONDecodeError:
            return self._fallback_citations(results[:3])

        # Validate each citation exists in search results
        result_paths = {r.get("path") for r in results}
        seen_paths: set[str] = set()

        for cite in raw_citations:
            path = cite.get("path", "")
            if path and path in result_paths and path not in seen_paths:
                seen_paths.add(path)
                title = path
                for r in results:
                    if r.get("path") == path:
                        title = r.get("title") or path
                        break

                citations.append(Citation(
                    path=path,
                    title=title,
                    lines=None,
                    url=self._path_to_url(path),
                ))

        return citations if citations else self._fallback_citations(results[:3])

    def _extract_legacy_citations(
        self,
        answer: str,
        results: list[dict[str, Any]],
    ) -> list[Citation]:
        """Extract citations from legacy [CITATIONS] format.

        Args:
            answer: LLM-generated answer.
            results: Search results used for context.

        Returns:
            List of extracted citations.
        """
        citations: list[Citation] = []
        seen_paths: set[str] = set()

        # Look for [CITATIONS] section in response
        citations_match = re.search(
            r"\[CITATIONS\](.*?)(?:\n\n|$)", answer, re.DOTALL | re.IGNORECASE
        )

        if citations_match:
            citations_text = citations_match.group(1)
            for line in citations_text.strip().split("\n"):
                line = line.strip().lstrip("-").strip()
                if not line:
                    continue

                if ":" in line:
                    parts = line.split(":", 1)
                    path = parts[0].strip()
                    lines = parts[1].strip() if len(parts) > 1 else None
                else:
                    path = line
                    lines = None

                if path and path not in seen_paths:
                    seen_paths.add(path)
                    title = path
                    for r in results:
                        if r.get("path") == path:
                            title = r.get("title") or path
                            break

                    citations.append(Citation(
                        path=path,
                        title=title,
                        lines=lines,
                        url=self._path_to_url(path),
                    ))

        return citations if citations else self._fallback_citations(results[:3])

    def _fallback_citations(self, results: list[dict[str, Any]]) -> list[Citation]:
        """Create citations from top results as fallback.

        Args:
            results: Search results to use for citations.

        Returns:
            Citations from top results.
        """
        citations: list[Citation] = []
        seen_paths: set[str] = set()

        for r in results:
            path = r.get("path", "")
            if path and path not in seen_paths:
                seen_paths.add(path)
                citations.append(Citation(
                    path=path,
                    title=r.get("title") or path,
                    lines=None,
                    url=self._path_to_url(path),
                ))

        return citations

    def _extract_answer(self, response: str) -> str:
        """Extract answer text from structured response.

        Args:
            response: LLM response with <answer> block.

        Returns:
            Extracted answer text.
        """
        match = re.search(r'<answer>\s*(.*?)\s*</answer>', response, re.DOTALL)
        if match:
            return match.group(1).strip()

        # Fall back to legacy format - remove [CITATIONS] section
        cleaned = re.sub(r"\[CITATIONS\].*", "", response, flags=re.DOTALL | re.IGNORECASE)
        # Also remove <citations> block if present without <answer>
        cleaned = re.sub(r"<citations>.*?</citations>", "", cleaned, flags=re.DOTALL)
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
            request: Q&A request with question.

        Returns:
            Q&A response with answer, citations, confidence, and search quality.
        """
        # Perform hybrid search
        results, semantic_ok, fts_ok = await self.search(request.question)

        # Calculate confidence from results
        confidence = self._calculate_confidence(results)

        # Build prompt with token budgeting
        prompt, results_used = self._build_context_prompt(request.question, results)

        try:
            raw_answer = await self._llm.generate(
                prompt=prompt,
                system_prompt=QA_SYSTEM_PROMPT,
                temperature=0.2,  # Lower for factual Q&A
            )
        except Exception as e:
            return QAResponse(
                answer=f"Error generating answer: {str(e)}",
                citations=[],
                confidence=confidence,
                disclaimer="An error occurred while generating the answer.",
                search_quality=SearchQuality(
                    semantic_searched=semantic_ok,
                    fts_searched=fts_ok,
                    results_found=len(results),
                    results_used=results_used,
                ),
            )

        # Extract citations and answer from structured response
        citations = self._extract_citations(raw_answer, results)
        answer = self._extract_answer(raw_answer)

        # Build disclaimer based on confidence
        disclaimers = {
            ConfidenceLevel.HIGH: "Based on strong evidence from the codebase.",
            ConfidenceLevel.MEDIUM: "Based on partial evidence. Verify against source code.",
            ConfidenceLevel.LOW: "Limited evidence found. This answer may be speculative.",
        }

        return QAResponse(
            answer=answer,
            citations=citations,
            confidence=confidence,
            disclaimer=disclaimers[confidence],
            search_quality=SearchQuality(
                semantic_searched=semantic_ok,
                fts_searched=fts_ok,
                results_found=len(results),
                results_used=results_used,
            ),
        )
