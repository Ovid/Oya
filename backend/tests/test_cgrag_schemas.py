"""Tests for CGRAG schema additions."""


def test_cgrag_metadata_creation():
    """CGRAGMetadata can be created with all fields."""
    from oya.qa.schemas import CGRAGMetadata

    metadata = CGRAGMetadata(
        passes_used=2,
        gaps_identified=["verify_token", "get_user"],
        gaps_resolved=["verify_token"],
        gaps_unresolved=["get_user"],
        session_id="abc-123",
        context_from_cache=True,
    )

    assert metadata.passes_used == 2
    assert len(metadata.gaps_identified) == 2
    assert len(metadata.gaps_resolved) == 1
    assert len(metadata.gaps_unresolved) == 1
    assert metadata.session_id == "abc-123"
    assert metadata.context_from_cache is True


def test_cgrag_metadata_defaults():
    """CGRAGMetadata has sensible defaults."""
    from oya.qa.schemas import CGRAGMetadata

    metadata = CGRAGMetadata(passes_used=1)

    assert metadata.passes_used == 1
    assert metadata.gaps_identified == []
    assert metadata.gaps_resolved == []
    assert metadata.gaps_unresolved == []
    assert metadata.session_id is None
    assert metadata.context_from_cache is False


def test_qa_request_has_session_id():
    """QARequest has optional session_id field."""
    from oya.qa.schemas import QARequest

    # Without session_id
    request = QARequest(question="How does X work?")
    assert request.session_id is None

    # With session_id
    request = QARequest(question="How does X work?", session_id="abc-123")
    assert request.session_id == "abc-123"


def test_qa_response_has_cgrag():
    """QAResponse has optional cgrag field."""
    from oya.qa.schemas import QAResponse, CGRAGMetadata, ConfidenceLevel, SearchQuality

    response = QAResponse(
        answer="The answer",
        citations=[],
        confidence=ConfidenceLevel.HIGH,
        disclaimer="Test",
        search_quality=SearchQuality(
            semantic_searched=True,
            fts_searched=True,
            results_found=5,
            results_used=3,
        ),
        cgrag=CGRAGMetadata(passes_used=2),
    )

    assert response.cgrag is not None
    assert response.cgrag.passes_used == 2
