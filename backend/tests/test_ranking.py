"""Tests for search result ranking."""

from oya.qa.ranking import RRFRanker


class TestRRFRanker:
    """Tests for Reciprocal Rank Fusion ranker."""

    def test_combines_rankings_with_rrf(self):
        """Documents in both lists get higher scores."""
        ranker = RRFRanker(k=60)

        semantic_results = [
            {"id": "doc_a", "content": "A"},
            {"id": "doc_b", "content": "B"},
            {"id": "doc_c", "content": "C"},
        ]
        fts_results = [
            {"id": "doc_b", "content": "B"},
            {"id": "doc_a", "content": "A"},
            {"id": "doc_d", "content": "D"},
        ]

        merged = ranker.merge(semantic_results, fts_results)

        # doc_a and doc_b should be top (in both lists)
        top_ids = [r["id"] for r in merged[:2]]
        assert "doc_a" in top_ids
        assert "doc_b" in top_ids

    def test_handles_disjoint_results(self):
        """Works when lists have no overlap."""
        ranker = RRFRanker(k=60)

        semantic_results = [{"id": "doc_a", "content": "A"}]
        fts_results = [{"id": "doc_b", "content": "B"}]

        merged = ranker.merge(semantic_results, fts_results)

        assert len(merged) == 2
        ids = {r["id"] for r in merged}
        assert ids == {"doc_a", "doc_b"}

    def test_handles_empty_lists(self):
        """Works with empty result lists."""
        ranker = RRFRanker(k=60)

        merged = ranker.merge([], [{"id": "doc_a", "content": "A"}])
        assert len(merged) == 1

        merged = ranker.merge([{"id": "doc_a", "content": "A"}], [])
        assert len(merged) == 1

        merged = ranker.merge([], [])
        assert len(merged) == 0

    def test_preserves_document_fields(self):
        """Merged results contain all original fields."""
        ranker = RRFRanker(k=60)

        semantic_results = [
            {"id": "doc_a", "content": "A", "path": "/a", "title": "Doc A", "type": "file"},
        ]
        fts_results = []

        merged = ranker.merge(semantic_results, fts_results)

        assert merged[0]["path"] == "/a"
        assert merged[0]["title"] == "Doc A"
        assert merged[0]["type"] == "file"

    def test_adds_rrf_score(self):
        """Merged results include RRF score."""
        ranker = RRFRanker(k=60)

        semantic_results = [{"id": "doc_a", "content": "A"}]
        fts_results = [{"id": "doc_a", "content": "A"}]

        merged = ranker.merge(semantic_results, fts_results)

        assert "rrf_score" in merged[0]
        assert merged[0]["rrf_score"] > 0
