"""Q&A API endpoints."""

from fastapi import APIRouter, Depends

from oya.api.deps import get_db, get_vectorstore, get_llm
from oya.db.connection import Database
from oya.llm.client import LLMClient
from oya.qa.schemas import QARequest, QAResponse
from oya.qa.service import QAService
from oya.vectorstore.store import VectorStore


router = APIRouter(prefix="/api/qa", tags=["qa"])


def get_qa_service(
    vectorstore: VectorStore = Depends(get_vectorstore),
    db: Database = Depends(get_db),
    llm: LLMClient = Depends(get_llm),
) -> QAService:
    """Get Q&A service instance."""
    return QAService(vectorstore, db, llm)


@router.post("/ask", response_model=QAResponse)
async def ask_question(
    request: QARequest,
    service: QAService = Depends(get_qa_service),
) -> QAResponse:
    """Ask a question about the codebase.

    Performs hybrid search (semantic + full-text) and generates an answer
    with citations. Returns a confidence level (high/medium/low) based on
    search result quality.
    """
    return await service.ask(request)
