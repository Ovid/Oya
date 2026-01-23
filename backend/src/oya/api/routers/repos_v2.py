"""Repository management API v2 - multi-repo support."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict

from oya.config import load_settings
from oya.db.repo_registry import RepoRegistry
from oya.repo.url_parser import parse_repo_url
from oya.repo.git_operations import clone_repo, GitCloneError
from oya.repo.repo_paths import RepoPaths


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


class CreateRepoRequest(BaseModel):
    """Request to create/add a new repository."""

    url: str
    display_name: Optional[str] = None


class CreateRepoResponse(BaseModel):
    """Response after creating a repository."""

    id: int
    origin_url: str
    source_type: str
    local_path: str
    display_name: str
    status: str


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


@router.get("/{repo_id}", response_model=RepoResponse)
async def get_repo(repo_id: int) -> RepoResponse:
    """
    Get a repository by ID.

    Returns 404 if not found.
    """
    registry = get_registry()
    try:
        repo = registry.get(repo_id)
        if not repo:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Repository {repo_id} not found",
            )
        return RepoResponse(
            id=repo.id,
            origin_url=repo.origin_url,
            source_type=repo.source_type,
            local_path=repo.local_path,
            display_name=repo.display_name,
            head_commit=repo.head_commit,
            branch=repo.branch,
            created_at=repo.created_at,
            last_pulled=repo.last_pulled,
            last_generated=repo.last_generated,
            generation_duration_secs=repo.generation_duration_secs,
            files_processed=repo.files_processed,
            pages_generated=repo.pages_generated,
            status=repo.status,
            error_message=repo.error_message,
        )
    finally:
        registry.close()


@router.delete("/{repo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_repo(repo_id: int) -> None:
    """
    Delete a repository by ID.

    Deletes both the registry entry and all files on disk.

    Returns 204 on success, 404 if not found, 409 if repo is generating.
    """
    settings = load_settings()
    registry = get_registry()
    try:
        repo = registry.get(repo_id)
        if not repo:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Repository {repo_id} not found",
            )

        if repo.status == "generating":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot delete repository while generating",
            )

        # Delete files on disk
        repo_paths = RepoPaths(settings.data_dir, repo.local_path)
        repo_paths.delete_all()

        # Delete from registry
        registry.delete(repo_id)
    finally:
        registry.close()


@router.post("", response_model=CreateRepoResponse, status_code=status.HTTP_201_CREATED)
async def create_repo(request: CreateRepoRequest) -> CreateRepoResponse:
    """
    Create a new repository by cloning from a URL or local path.

    Returns 201 on success, 409 if the repository already exists.
    """
    settings = load_settings()

    # Parse the URL to determine source type and local path
    try:
        parsed = parse_repo_url(request.url)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    # Check for duplicates
    registry = get_registry()
    try:
        existing = registry.find_by_origin_url(parsed.original_url)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Repository already exists with ID {existing.id}",
            )

        # Create directory structure
        repo_paths = RepoPaths(settings.data_dir, parsed.local_path)
        repo_paths.create_structure()

        # Clone the repository
        try:
            clone_repo(parsed.original_url, repo_paths.source)
        except GitCloneError as e:
            # Clean up on failure
            repo_paths.delete_all()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=e.message,
            )

        # Determine display name
        display_name = request.display_name or parsed.repo

        # Add to registry
        repo_id = registry.add(
            origin_url=parsed.original_url,
            source_type=parsed.source_type,
            local_path=parsed.local_path,
            display_name=display_name,
        )

        # Update status to ready
        registry.update(repo_id, status="ready")

        return CreateRepoResponse(
            id=repo_id,
            origin_url=parsed.original_url,
            source_type=parsed.source_type,
            local_path=str(repo_paths.source),
            display_name=display_name,
            status="ready",
        )
    finally:
        registry.close()
