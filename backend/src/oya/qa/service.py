"""Q&A service with hybrid search and confidence-based answers."""

from __future__ import annotations

import json
import re
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, Any

import networkx as nx

from oya.constants.issues import ISSUE_QUERY_KEYWORDS
from oya.constants.qa import (
    GRAPH_EXPANSION_CONFIDENCE_THRESHOLD,
    GRAPH_EXPANSION_HOPS,
    HIGH_CONFIDENCE_THRESHOLD,
    MAX_CONTEXT_TOKENS,
    MAX_RESULT_TOKENS,
    MEDIUM_CONFIDENCE_THRESHOLD,
    MIN_STRONG_MATCHES_FOR_HIGH,
    STRONG_MATCH_THRESHOLD,
)
from oya.constants.search import DEDUP_HASH_LENGTH, TYPE_PRIORITY
from oya.db.connection import Database
from oya.generation.chunking import estimate_tokens
from oya.generation.prompts import format_graph_qa_context
from oya.graph.models import Subgraph
from oya.llm.client import LLMClient
from oya.qa.graph_retrieval import (
    build_graph_context,
    expand_with_graph,
    map_search_results_to_node_ids,
    prioritize_nodes,
)
from oya.qa.cgrag import run_cgrag_loop, CGRAGResult
from oya.qa.ranking import RRFRanker
from oya.qa.schemas import (
    CGRAGMetadata,
    Citation,
    ConfidenceLevel,
    QARequest,
    QAResponse,
    SearchQuality,
)
from oya.qa.session import SessionStore
from oya.vectorstore.store import VectorStore

if TYPE_CHECKING:
    from oya.vectorstore.issues import IssuesStore

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

# Module-level session store for CGRAG
_session_store = SessionStore()


class QAService:
    """Service for evidence-gated Q&A over codebase."""

    def __init__(
        self,
        vectorstore: VectorStore,
        db: Database,
        llm: LLMClient,
        issues_store: IssuesStore | None = None,
        graph: nx.DiGraph | None = None,
    ) -> None:
        """Initialize Q&A service.

        Args:
            vectorstore: ChromaDB vector store for semantic search.
            db: SQLite database for full-text search.
            llm: LLM client for answer generation.
            issues_store: Optional IssuesStore for issue-aware Q&A.
            graph: Optional code graph for graph-augmented retrieval.
        """
        self._vectorstore = vectorstore
        self._db = db
        self._llm = llm
        self._issues_store = issues_store
        self._graph = graph
        self._ranker = RRFRanker(k=60)

    async def search(
        self,
        query: str,
        limit: int = 10,
    ) -> tuple[list[dict[str, Any]], bool, bool]:
        """Perform hybrid search combining semantic and full-text search.

        Uses RRF (Reciprocal Rank Fusion) to merge results from both sources,
        boosting documents that appear in both lists.

        Args:
            query: Search query.
            limit: Maximum results to return.

        Returns:
            Tuple of (search results, semantic_ok, fts_ok).
        """
        semantic_results: list[dict[str, Any]] = []
        fts_results: list[dict[str, Any]] = []
        semantic_ok = False
        fts_ok = False

        # Semantic search via ChromaDB
        try:
            raw_semantic = self._vectorstore.query(
                query_text=query,
                n_results=limit,
            )
            semantic_ok = True

            for i, doc_id in enumerate(raw_semantic.get("ids", [[]])[0]):
                documents = raw_semantic.get("documents", [[]])[0]
                metadatas = raw_semantic.get("metadatas", [[]])[0]
                distances = raw_semantic.get("distances", [[]])[0]

                if i < len(documents):
                    path = metadatas[i].get("path", "") if i < len(metadatas) else ""
                    if path:
                        semantic_results.append(
                            {
                                "id": doc_id,
                                "content": documents[i],
                                "path": path,
                                "title": metadatas[i].get("title", "")
                                if i < len(metadatas)
                                else "",
                                "type": metadatas[i].get("type", "wiki")
                                if i < len(metadatas)
                                else "wiki",
                                "distance": distances[i] if i < len(distances) else 1.0,
                                "source": "semantic",
                            }
                        )
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
                if path:
                    # Use path-based ID for FTS results to enable RRF matching
                    # with semantic results that may have different chunk IDs
                    fts_results.append(
                        {
                            "id": path,  # Use path as ID for cross-source matching
                            "content": row["content"] or "",
                            "path": path,
                            "title": row["title"] or "",
                            "type": row["type"] or "wiki",
                            "distance": 1.0 - min(abs(row["score"]) / 10, 1.0)
                            if row["score"]
                            else 0.5,
                            "source": "fts",
                        }
                    )
        except Exception:
            # If FTS fails, use whatever semantic results we have
            pass

        # Normalize semantic result IDs to paths for RRF matching
        for result in semantic_results:
            result["id"] = result["path"]

        # Merge results using RRF ranking
        merged = self._ranker.merge(semantic_results, fts_results)

        # Sort by type priority first (notes > file > directory > overview), then by RRF score
        merged.sort(key=lambda r: (TYPE_PRIORITY.get(r["type"], 3), -r.get("rrf_score", 0)))

        # Deduplicate similar content
        results = self._deduplicate_results(merged)

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
        strong_matches = sum(1 for r in results if r.get("distance", 1.0) < STRONG_MATCH_THRESHOLD)

        # Check best result quality
        best_distance = min(r.get("distance", 1.0) for r in results)

        if (
            strong_matches >= MIN_STRONG_MATCHES_FOR_HIGH
            and best_distance < HIGH_CONFIDENCE_THRESHOLD
        ):
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
        sentences = text.replace("\n", " ").split(". ")
        result: list[str] = []
        for sentence in sentences:
            candidate = ". ".join(result + [sentence])
            if estimate_tokens(candidate) > max_tokens:
                break
            result.append(sentence)

        if not result:
            # If no complete sentence fits, truncate by characters
            chars_per_token = 4  # Approximate
            max_chars = max_tokens * chars_per_token
            return text[:max_chars].rsplit(" ", 1)[0] + "..."

        return ". ".join(result) + "."

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

    def _build_graph_context(self, results: list[dict[str, Any]]) -> str:
        """Build graph-augmented context from search results.

        Args:
            results: Search results from hybrid search.

        Returns:
            Formatted graph context string, or empty string if no graph data.
        """
        if self._graph is None:
            return ""

        # Map search results to graph node IDs
        node_ids = map_search_results_to_node_ids(results, self._graph)

        if not node_ids:
            return ""

        # Expand via graph traversal
        subgraph = expand_with_graph(
            node_ids,
            self._graph,
            hops=GRAPH_EXPANSION_HOPS,
            min_confidence=GRAPH_EXPANSION_CONFIDENCE_THRESHOLD,
        )

        if not subgraph.nodes:
            return ""

        # Prioritize nodes
        prioritized = prioritize_nodes(subgraph.nodes, self._graph)
        subgraph = Subgraph(nodes=prioritized, edges=subgraph.edges)

        # Build context with budget
        # Reserve some budget for graph context (1/3 of total)
        graph_budget = MAX_CONTEXT_TOKENS // 3
        mermaid, code = build_graph_context(subgraph, token_budget=graph_budget)

        return format_graph_qa_context(mermaid, code)

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
        match = re.search(r"<citations>\s*(\[.*?\])\s*</citations>", response, re.DOTALL)
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

                citations.append(
                    Citation(
                        path=path,
                        title=title,
                        lines=None,
                        url=self._path_to_url(path),
                    )
                )

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

                    citations.append(
                        Citation(
                            path=path,
                            title=title,
                            lines=lines,
                            url=self._path_to_url(path),
                        )
                    )

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
                citations.append(
                    Citation(
                        path=path,
                        title=r.get("title") or path,
                        lines=None,
                        url=self._path_to_url(path),
                    )
                )

        return citations

    def _extract_answer(self, response: str) -> str:
        """Extract answer text from structured response.

        Args:
            response: LLM response with <answer> block.

        Returns:
            Extracted answer text.
        """
        match = re.search(r"<answer>\s*(.*?)\s*</answer>", response, re.DOTALL)
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

    def _is_issue_query(self, question: str) -> bool:
        """Check if question is asking about code issues.

        Args:
            question: User's question.

        Returns:
            True if question contains issue-related keywords.
        """
        question_lower = question.lower()
        return any(keyword in question_lower for keyword in ISSUE_QUERY_KEYWORDS)

    async def ask(self, request: QARequest) -> QAResponse:
        """Answer a question about the codebase.

        Args:
            request: Q&A request with question.

        Returns:
            Q&A response with answer, citations, confidence, and search quality.
        """
        # Check if this is an issue-related query
        if self._is_issue_query(request.question) and self._issues_store:
            return await self._ask_with_issues(request)

        return await self._ask_normal(request)

    async def _ask_with_issues(self, request: QARequest) -> QAResponse:
        """Answer an issue-related question using pre-computed issues.

        Args:
            request: Q&A request with question.

        Returns:
            Q&A response based on pre-computed issues.
        """
        assert self._issues_store is not None  # Caller verifies this
        # Query issues collection
        issues = self._issues_store.query_issues(query=request.question, limit=20)

        if not issues:
            # Fall back to normal search by calling the regular flow
            return await self._ask_normal(request)

        # Build context from issues
        context_parts = []
        for issue in issues:
            file_path = issue.get("file_path", "unknown")
            category = issue.get("category", "")
            severity = issue.get("severity", "")
            title = issue.get("title", "")
            content = issue.get("content", "")
            part = f"[{severity.upper()}] {category} issue in {file_path}\n{title}\n{content}"
            context_parts.append(part)

        context_str = "\n\n---\n\n".join(context_parts)

        prompt = f"""Based on the following code issues identified during analysis, answer the question.

IDENTIFIED ISSUES:
{context_str}

QUESTION: {request.question}

Analyze these issues and identify any systemic patterns. Are there architectural or process problems causing multiple similar issues?
Format your response with:
1. A summary of the issues found
2. Any patterns across issues
3. Recommendations for addressing them"""

        try:
            raw_answer = await self._llm.generate(
                prompt=prompt,
                system_prompt=QA_SYSTEM_PROMPT,
                temperature=0.2,
            )
        except Exception as e:
            return QAResponse(
                answer=f"Error: {e}",
                citations=[],
                confidence=ConfidenceLevel.LOW,
                disclaimer="Error generating answer.",
                search_quality=SearchQuality(
                    semantic_searched=False,
                    fts_searched=False,
                    results_found=len(issues),
                    results_used=len(issues),
                ),
                cgrag=None,
            )

        answer = self._extract_answer(raw_answer)

        # Create citations from issues
        citations = []
        seen_paths: set[str] = set()
        for issue in issues[:5]:
            path = issue.get("file_path", "")
            if path and path not in seen_paths:
                seen_paths.add(path)
                citations.append(
                    Citation(
                        path=path,
                        title=issue.get("title", path),
                        lines=None,
                        url=self._path_to_url(
                            f"files/{path.replace('/', '-').replace('.', '-')}.md"
                        ),
                    )
                )

        return QAResponse(
            answer=answer,
            citations=citations,
            confidence=ConfidenceLevel.HIGH if len(issues) >= 3 else ConfidenceLevel.MEDIUM,
            disclaimer="Based on issues detected during wiki generation.",
            search_quality=SearchQuality(
                semantic_searched=True,
                fts_searched=False,
                results_found=len(issues),
                results_used=min(len(issues), 20),
            ),
            cgrag=None,
        )

    async def _ask_normal(self, request: QARequest) -> QAResponse:
        """Answer a question, routing to quick or CGRAG mode.

        Args:
            request: Q&A request with question.

        Returns:
            Q&A response with answer, citations, confidence, and search quality.
        """
        # Perform hybrid search
        results, semantic_ok, fts_ok = await self.search(request.question)

        # Calculate confidence from results
        confidence = self._calculate_confidence(results)

        # Build initial context with token budgeting
        initial_context, results_used = self._build_context_prompt(request.question, results)

        # Add graph context if available and enabled
        if self._graph is not None and request.use_graph and results:
            graph_context = self._build_graph_context(results)
            if graph_context:
                initial_context = graph_context + "\n\n" + initial_context

        # Route to quick or CGRAG mode
        if request.quick_mode:
            return await self._ask_quick(
                request=request,
                context=initial_context,
                results=results,
                confidence=confidence,
                semantic_ok=semantic_ok,
                fts_ok=fts_ok,
                results_used=results_used,
            )
        else:
            return await self._ask_with_cgrag(
                request=request,
                initial_context=initial_context,
                results=results,
                confidence=confidence,
                semantic_ok=semantic_ok,
                fts_ok=fts_ok,
                results_used=results_used,
            )

    async def _ask_quick(
        self,
        request: QARequest,
        context: str,
        results: list[dict[str, Any]],
        confidence: ConfidenceLevel,
        semantic_ok: bool,
        fts_ok: bool,
        results_used: int,
    ) -> QAResponse:
        """Answer a question with a single LLM call (no CGRAG iteration).

        Args:
            request: Q&A request with question.
            context: Pre-built context from search results.
            results: Search results for citations.
            confidence: Calculated confidence level.
            semantic_ok: Whether semantic search succeeded.
            fts_ok: Whether FTS search succeeded.
            results_used: Number of results included in context.

        Returns:
            Q&A response with answer, citations, and confidence.
        """
        # Build prompt for single-pass answer
        prompt = f"""{context}

QUESTION: {request.question}

Answer the question based only on the context provided. Include citations to specific files."""

        try:
            # Use request temperature if provided, otherwise use default
            generate_kwargs: dict[str, Any] = {
                "prompt": prompt,
                "system_prompt": QA_SYSTEM_PROMPT,
            }
            if request.temperature is not None:
                generate_kwargs["temperature"] = request.temperature

            raw_answer = await self._llm.generate(**generate_kwargs)
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
                cgrag=None,
            )

        # Extract answer and citations
        answer = self._extract_answer(raw_answer)
        citations = self._extract_citations(raw_answer, results)

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
            cgrag=None,
        )

    async def _ask_with_cgrag(
        self,
        request: QARequest,
        initial_context: str,
        results: list[dict[str, Any]],
        confidence: ConfidenceLevel,
        semantic_ok: bool,
        fts_ok: bool,
        results_used: int,
    ) -> QAResponse:
        """Answer a question using CGRAG iterative retrieval.

        Args:
            request: Q&A request with question.
            initial_context: Pre-built context from search results.
            results: Search results for citations.
            confidence: Calculated confidence level.
            semantic_ok: Whether semantic search succeeded.
            fts_ok: Whether FTS search succeeded.
            results_used: Number of results included in context.

        Returns:
            Q&A response with answer, citations, confidence, and CGRAG metadata.
        """
        # Get or create CGRAG session
        session = _session_store.get_or_create(request.session_id)
        context_from_cache = bool(session.cached_nodes) and request.session_id is not None

        try:
            # Run CGRAG iterative loop
            cgrag_result: CGRAGResult = await run_cgrag_loop(
                question=request.question,
                initial_context=initial_context,
                session=session,
                llm=self._llm,
                graph=self._graph,
                vectorstore=self._vectorstore,
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
                cgrag=CGRAGMetadata(
                    passes_used=0,
                    gaps_identified=[],
                    gaps_resolved=[],
                    gaps_unresolved=[],
                    session_id=session.id,
                    context_from_cache=context_from_cache,
                ),
            )

        # Extract answer from CGRAG result
        answer = cgrag_result.answer

        # Use fallback citations from search results since CGRAG uses different format
        citations = self._fallback_citations(results[:5])

        # Build CGRAG metadata
        cgrag_metadata = CGRAGMetadata(
            passes_used=cgrag_result.passes_used,
            gaps_identified=cgrag_result.gaps_identified,
            gaps_resolved=cgrag_result.gaps_resolved,
            gaps_unresolved=cgrag_result.gaps_unresolved,
            session_id=session.id,
            context_from_cache=context_from_cache,
        )

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
            cgrag=cgrag_metadata,
        )

    async def ask_stream(self, request: QARequest) -> AsyncGenerator[str, None]:
        """Stream Q&A response as SSE events.

        Yields SSE-formatted event strings:
        - event: token, data: {"text": "..."}
        - event: status, data: {"stage": "...", "pass": N}
        - event: done, data: {"citations": [...], "confidence": "...", "session_id": "...", "disclaimer": "..."}
        - event: error, data: {"message": "..."}
        """
        # Issue 1 fix: Emit "searching" status BEFORE performing search
        yield f"event: status\ndata: {json.dumps({'stage': 'searching', 'pass': 1})}\n\n"

        # Perform hybrid search
        results, semantic_ok, fts_ok = await self.search(request.question)
        confidence = self._calculate_confidence(results)
        initial_context, results_used = self._build_context_prompt(request.question, results)

        # Add graph context if available
        if self._graph is not None and request.use_graph and results:
            graph_context = self._build_graph_context(results)
            if graph_context:
                initial_context = graph_context + "\n\n" + initial_context

        # Issue 1 fix: Emit "generating" status AFTER search completes
        yield f"event: status\ndata: {json.dumps({'stage': 'generating', 'pass': 1})}\n\n"

        temperature = request.temperature if request.temperature is not None else 0.7
        accumulated_response = ""

        # Issue 3 fix: Get session once for CGRAG mode (reuse later instead of second lookup)
        session = None
        if not request.quick_mode:
            session = _session_store.get_or_create(request.session_id)

        try:
            if request.quick_mode:
                # Issue 5 fix: Match prompt format from _ask_quick()
                prompt = f"""{initial_context}

QUESTION: {request.question}

Answer the question based only on the context provided. Include citations to specific files."""

                # Single pass streaming
                async for token in self._llm.generate_stream(
                    prompt=prompt,
                    system_prompt=QA_SYSTEM_PROMPT,
                    temperature=temperature,
                ):
                    accumulated_response += token
                    yield f"event: token\ndata: {json.dumps({'text': token})}\n\n"
            else:
                # CGRAG mode - run iteration first, then send answer
                assert session is not None  # Guaranteed by check at line 941
                cgrag_result = await run_cgrag_loop(
                    question=request.question,
                    initial_context=initial_context,
                    session=session,
                    llm=self._llm,
                    graph=self._graph,
                    vectorstore=self._vectorstore,
                )
                # Issue 2 fix: Stream in word chunks instead of character-by-character
                # Split by spaces to yield words with trailing space, batching for efficiency
                words = cgrag_result.answer.split(" ")
                for i, word in enumerate(words):
                    # Add space back except for last word
                    chunk = word + (" " if i < len(words) - 1 else "")
                    yield f"event: token\ndata: {json.dumps({'text': chunk})}\n\n"
                accumulated_response = cgrag_result.answer

        except Exception as e:
            yield f"event: error\ndata: {json.dumps({'message': str(e)})}\n\n"
            return

        # Extract citations from the accumulated response
        if "<citations>" in accumulated_response:
            citations = self._extract_citations(accumulated_response, results)
        else:
            citations = self._fallback_citations(results[:5])

        # Issue 3 fix: Reuse session variable from earlier lookup (no duplicate lookup)
        session_id = session.id if session is not None else None

        # Issue 4 fix: Add disclaimer to done event based on confidence level
        disclaimers = {
            ConfidenceLevel.HIGH: "Based on strong evidence from the codebase.",
            ConfidenceLevel.MEDIUM: "Based on partial evidence. Verify against source code.",
            ConfidenceLevel.LOW: "Limited evidence found. This answer may be speculative.",
        }

        done_data = {
            "citations": [c.model_dump() for c in citations],
            "confidence": confidence.value,
            "session_id": session_id,
            "disclaimer": disclaimers[confidence],
            "search_quality": {
                "semantic_searched": semantic_ok,
                "fts_searched": fts_ok,
                "results_found": len(results),
                "results_used": results_used,
            },
        }
        yield f"event: done\ndata: {json.dumps(done_data)}\n\n"
