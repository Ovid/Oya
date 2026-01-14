"""Q&A module for evidence-gated question answering."""

from oya.qa.schemas import (
    QARequest,
    QAResponse,
    Citation,
    ConfidenceLevel,
    SearchQuality,
)
from oya.qa.service import QAService

__all__ = [
    "QARequest",
    "QAResponse",
    "Citation",
    "ConfidenceLevel",
    "SearchQuality",
    "QAService",
]
