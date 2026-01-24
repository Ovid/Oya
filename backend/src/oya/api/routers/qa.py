"""Q&A API endpoints."""

from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from oya.api.deps import (
    get_active_repo_paths,
    get_db,
    get_issues_store,
    get_llm,
    get_vectorstore,
)
from oya.db.connection import Database
from oya.graph.persistence import load_graph
from oya.llm.client import LLMClient
from oya.qa.schemas import QARequest, QAResponse
from oya.qa.service import QAService
from oya.repo.repo_paths import RepoPaths
from oya.vectorstore.issues import IssuesStore
from oya.vectorstore.store import VectorStore


router = APIRouter(prefix="/api/qa", tags=["qa"])


def _get_paths_for_qa(paths: RepoPaths) -> tuple[Path, Path]:
    """Get wiki and source paths for Q&A from the active repo.

    Returns:
        Tuple of (graph_dir, source_path).
    """
    graph_dir = paths.oyawiki / "graph"
    source_path = paths.source
    return graph_dir, source_path


def get_qa_service(
    vectorstore: VectorStore = Depends(get_vectorstore),
    db: Database = Depends(get_db),
    llm: LLMClient = Depends(get_llm),
    issues_store: IssuesStore = Depends(get_issues_store),
    paths: RepoPaths = Depends(get_active_repo_paths),
) -> QAService:
    """Get Q&A service instance."""
    graph_dir, source_path = _get_paths_for_qa(paths)

    # Load graph if available
    graph = None
    if graph_dir.exists():
        try:
            graph = load_graph(graph_dir)
            if graph.number_of_nodes() == 0:
                graph = None
        except Exception:
            # Graph loading failed, proceed without it
            pass

    return QAService(vectorstore, db, llm, issues_store, graph=graph, source_path=source_path)


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
