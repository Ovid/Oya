"""Q&A request and response schemas."""

from enum import Enum

from pydantic import BaseModel, Field


class ConfidenceLevel(str, Enum):
    """Confidence level for Q&A answers."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class SearchQuality(BaseModel):
    """Transparency about search execution."""

    semantic_searched: bool = Field(..., description="Did vector search succeed?")
    fts_searched: bool = Field(..., description="Did FTS search succeed?")
    results_found: int = Field(..., description="Total results before dedup")
    results_used: int = Field(..., description="Results after dedup, within token budget")


class Citation(BaseModel):
    """Citation reference in an answer."""

    path: str = Field(..., description="Wiki-relative path of the cited source")
    title: str = Field(..., description="Display title for the citation")
    lines: str | None = Field(None, description="Line range if applicable (e.g., '10-20')")
    url: str = Field(..., description="Frontend route (e.g., '/files/src_main-py')")


class CGRAGMetadata(BaseModel):
    """Metadata about the iterative retrieval process."""

    passes_used: int = Field(..., description="Number of retrieval passes (1-3)")
    gaps_identified: list[str] = Field(
        default_factory=list,
        description="All gaps the LLM requested across passes",
    )
    gaps_resolved: list[str] = Field(
        default_factory=list,
        description="Gaps that were successfully retrieved",
    )
    gaps_unresolved: list[str] = Field(
        default_factory=list,
        description="Gaps that could not be found",
    )
    session_id: str | None = Field(
        None,
        description="Session ID for follow-up questions",
    )
    context_from_cache: bool = Field(
        False,
        description="Whether session cache contributed context",
    )


class QARequest(BaseModel):
    """Request for Q&A endpoint."""

    question: str = Field(..., min_length=1, description="The question to answer")
    use_graph: bool = Field(default=True, description="Whether to use graph expansion")
    session_id: str | None = Field(
        None,
        description="Session ID for CGRAG context continuity",
    )
    quick_mode: bool = Field(
        default=False,
        description="Skip CGRAG iteration for faster responses",
    )
    temperature: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Override the default LLM temperature (0.0-1.0)",
    )


class QAResponse(BaseModel):
    """Response from Q&A endpoint."""

    answer: str = Field(..., description="The generated answer")
    citations: list[Citation] = Field(
        default_factory=list,
        description="Citations referenced in the answer",
    )
    confidence: ConfidenceLevel = Field(
        ...,
        description="Confidence level: high, medium, or low",
    )
    disclaimer: str = Field(
        ...,
        description="Disclaimer about AI-generated content",
    )
    search_quality: SearchQuality = Field(
        ...,
        description="Metrics about search execution",
    )
    cgrag: CGRAGMetadata | None = Field(
        None,
        description="CGRAG iteration metadata (if iterative retrieval was used)",
    )
