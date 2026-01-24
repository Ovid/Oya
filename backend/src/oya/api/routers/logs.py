"""API endpoints for accessing repository logs."""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from oya.config import load_settings
from oya.db.repo_registry import RepoRegistry
from oya.repo.repo_paths import RepoPaths

router = APIRouter(prefix="/api/v2/repos", tags=["logs"])


class LogsResponse(BaseModel):
    """Response containing log file content."""

    content: str
    size_bytes: int
    entry_count: int


class DeleteLogsResponse(BaseModel):
    """Response after deleting logs."""

    message: str


def _get_repo_or_404(repo_id: int) -> tuple:
    """Get repo from registry or raise 404."""
    settings = load_settings()
    registry = RepoRegistry(settings.repos_db_path)
    try:
        repo = registry.get(repo_id)
        if repo is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Repository {repo_id} not found",
            )
        return repo, settings
    finally:
        registry.close()


@router.get("/{repo_id}/logs/llm-queries", response_model=LogsResponse)
async def get_llm_logs(repo_id: int) -> LogsResponse:
    """Get the LLM query logs for a repository."""
    repo, settings = _get_repo_or_404(repo_id)
    paths = RepoPaths(settings.data_dir, repo.local_path)
    log_file = paths.oya_logs / "llm-queries.jsonl"

    if not log_file.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No logs found for this repository",
        )

    content = log_file.read_text()
    entry_count = sum(1 for line in content.strip().split("\n") if line.strip())

    return LogsResponse(
        content=content,
        size_bytes=log_file.stat().st_size,
        entry_count=entry_count,
    )


@router.delete("/{repo_id}/logs/llm-queries", response_model=DeleteLogsResponse)
async def delete_llm_logs(repo_id: int) -> DeleteLogsResponse:
    """Delete the LLM query logs for a repository."""
    repo, settings = _get_repo_or_404(repo_id)
    paths = RepoPaths(settings.data_dir, repo.local_path)
    log_file = paths.oya_logs / "llm-queries.jsonl"

    if not log_file.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No logs to delete",
        )

    log_file.unlink()

    return DeleteLogsResponse(message="Logs deleted successfully")
