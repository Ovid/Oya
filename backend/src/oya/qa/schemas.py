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

    path: str = Field(..., description="File path of the cited source")
    title: str = Field(..., description="Display title for the citation")
    lines: str | None = Field(None, description="Line range if applicable (e.g., '10-20')")


class QARequest(BaseModel):
    """Request for Q&A endpoint."""

    question: str = Field(..., min_length=1, description="The question to answer")


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
