"""Q&A request and response schemas."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class QAMode(str, Enum):
    """Q&A mode for evidence gating."""

    GATED = "gated"
    LOOSE = "loose"


class Citation(BaseModel):
    """Citation reference in an answer."""

    path: str = Field(..., description="File path of the cited source")
    title: str = Field(..., description="Display title for the citation")
    lines: str | None = Field(None, description="Line range if applicable (e.g., '10-20')")


class QARequest(BaseModel):
    """Request for Q&A endpoint."""

    question: str = Field(..., min_length=1, description="The question to answer")
    context: dict[str, Any] | None = Field(
        None,
        description="Optional page context (page_type, slug)",
    )
    mode: QAMode = Field(
        QAMode.GATED,
        description="Evidence mode: 'gated' (default) or 'loose'",
    )


class QAResponse(BaseModel):
    """Response from Q&A endpoint."""

    answer: str = Field(..., description="The generated answer (empty if insufficient evidence)")
    citations: list[Citation] = Field(
        default_factory=list,
        description="Citations referenced in the answer",
    )
    evidence_sufficient: bool = Field(
        ...,
        description="Whether sufficient evidence was found",
    )
    disclaimer: str = Field(
        ...,
        description="Mandatory disclaimer about AI-generated content",
    )
