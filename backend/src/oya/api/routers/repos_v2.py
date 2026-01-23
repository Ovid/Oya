"""Repository management API v2 - multi-repo support."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from oya.config import load_settings
from oya.db.repo_registry import RepoRegistry


router = APIRouter(prefix="/api/v2/repos", tags=["repos-v2"])


class RepoResponse(BaseModel):
    """Single repo in API response."""

    id: int
    origin_url: str
    source_type: str
    local_path: str
    display_name: str
    head_commit: Optional[str]
    branch: Optional[str]
    created_at: Optional[datetime]
    last_pulled: Optional[datetime]
    last_generated: Optional[datetime]
    generation_duration_secs: Optional[float]
    files_processed: Optional[int]
    pages_generated: Optional[int]
    status: str
    error_message: Optional[str]

    model_config = ConfigDict(from_attributes=True)


class RepoListResponse(BaseModel):
    """Response for list repos endpoint."""

    repos: list[RepoResponse]
    total: int


def get_registry() -> RepoRegistry:
    """Get the repo registry."""
    settings = load_settings()
    return RepoRegistry(settings.repos_db_path)


@router.get("", response_model=RepoListResponse)
async def list_repos() -> RepoListResponse:
    """List all repositories."""
    registry = get_registry()
    try:
        repos = registry.list_all()
        return RepoListResponse(
            repos=[
                RepoResponse(
                    id=r.id,
                    origin_url=r.origin_url,
                    source_type=r.source_type,
                    local_path=r.local_path,
                    display_name=r.display_name,
                    head_commit=r.head_commit,
                    branch=r.branch,
                    created_at=r.created_at,
                    last_pulled=r.last_pulled,
                    last_generated=r.last_generated,
                    generation_duration_secs=r.generation_duration_secs,
                    files_processed=r.files_processed,
                    pages_generated=r.pages_generated,
                    status=r.status,
                    error_message=r.error_message,
                )
                for r in repos
            ],
            total=len(repos),
        )
    finally:
        registry.close()
