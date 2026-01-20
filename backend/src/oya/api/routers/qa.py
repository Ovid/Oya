"""Q&A API endpoints."""

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from oya.api.deps import get_db, get_issues_store, get_llm, get_settings, get_vectorstore
from oya.config import Settings
from oya.graph.persistence import load_graph
from oya.db.connection import Database
from oya.llm.client import LLMClient
from oya.qa.schemas import QARequest, QAResponse
from oya.qa.service import QAService
from oya.vectorstore.issues import IssuesStore
from oya.vectorstore.store import VectorStore


router = APIRouter(prefix="/api/qa", tags=["qa"])


def get_qa_service(
    vectorstore: VectorStore = Depends(get_vectorstore),
    db: Database = Depends(get_db),
    llm: LLMClient = Depends(get_llm),
    issues_store: IssuesStore = Depends(get_issues_store),
    settings: Settings = Depends(get_settings),
) -> QAService:
    """Get Q&A service instance."""
    # Load graph if available
    graph_dir = settings.oyawiki_path / "graph"
    graph = None
    if graph_dir.exists():
        try:
            graph = load_graph(graph_dir)
            if graph.number_of_nodes() == 0:
                graph = None
        except Exception:
            # Graph loading failed, proceed without it
            pass

    return QAService(vectorstore, db, llm, issues_store, graph=graph)


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


@router.post("/ask/stream")
async def ask_question_stream(
    request: QARequest,
    service: QAService = Depends(get_qa_service),
) -> StreamingResponse:
    """Stream Q&A response as Server-Sent Events."""
    return StreamingResponse(
        service.ask_stream(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
