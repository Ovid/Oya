"""Search result ranking with Reciprocal Rank Fusion."""

from typing import Any


class RRFRanker:
    """Combines semantic and full-text search results using RRF.

    Reciprocal Rank Fusion scores documents based on their ranks in
    multiple result lists. Documents appearing in both lists get
    boosted scores.

    RRF_score(doc) = sum(1 / (k + rank_i)) for each list i
    """

    def __init__(self, k: int = 60, missing_rank: int = 1000) -> None:
        """Initialize RRF ranker.

        Args:
            k: Ranking constant (default 60, standard for RRF).
            missing_rank: Rank assigned to documents not in a list.
        """
        self._k = k
        self._missing_rank = missing_rank

    def merge(
        self,
        semantic_results: list[dict[str, Any]],
        fts_results: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Merge semantic and FTS results using RRF scoring.

        Args:
            semantic_results: Results from semantic/vector search.
            fts_results: Results from full-text search.

        Returns:
            Merged results sorted by RRF score (highest first).
        """
        # Build rank maps
        semantic_ranks: dict[str, int] = {}
        for rank, doc in enumerate(semantic_results):
            doc_id = doc.get("id", "")
            if doc_id:
                semantic_ranks[doc_id] = rank

        fts_ranks: dict[str, int] = {}
        for rank, doc in enumerate(fts_results):
            doc_id = doc.get("id", "")
            if doc_id:
                fts_ranks[doc_id] = rank

        # Build document lookup (prefer semantic version, fall back to FTS)
        docs_by_id: dict[str, dict[str, Any]] = {}
        for doc in fts_results:
            doc_id = doc.get("id", "")
            if doc_id:
                docs_by_id[doc_id] = doc
        for doc in semantic_results:
            doc_id = doc.get("id", "")
            if doc_id:
                docs_by_id[doc_id] = doc

        # Calculate RRF scores
        all_ids = set(semantic_ranks.keys()) | set(fts_ranks.keys())
        scores: dict[str, float] = {}

        for doc_id in all_ids:
            sem_rank = semantic_ranks.get(doc_id, self._missing_rank)
            fts_rank = fts_ranks.get(doc_id, self._missing_rank)

            rrf_score = 1 / (self._k + sem_rank + 1) + 1 / (self._k + fts_rank + 1)
            scores[doc_id] = rrf_score

        # Sort by score and build result list
        sorted_ids = sorted(scores.keys(), key=lambda x: -scores[x])

        results: list[dict[str, Any]] = []
        for doc_id in sorted_ids:
            doc = docs_by_id.get(doc_id, {})
            if doc:
                result = dict(doc)
                result["rrf_score"] = scores[doc_id]
                results.append(result)

        return results
