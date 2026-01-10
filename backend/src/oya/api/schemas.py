"""Pydantic schemas for API requests and responses."""

from datetime import datetime
from pydantic import BaseModel, Field


class EmbeddingMetadata(BaseModel):
    """Metadata about the embedding model used for indexing."""
    provider: str
    model: str
    indexed_at: str


class RepoStatus(BaseModel):
    """Repository status response."""
    path: str
    head_commit: str | None
    head_message: str | None
    branch: str | None
    initialized: bool
    is_docker: bool = False
    last_generation: datetime | None = None
    generation_status: str | None = None
    embedding_metadata: EmbeddingMetadata | None = None
    current_provider: str | None = None
    current_model: str | None = None
    embedding_mismatch: bool = False


class JobCreated(BaseModel):
    """Job creation response."""
    job_id: str
    status: str = "pending"
    message: str = "Job started"


class WorkspaceSwitch(BaseModel):
    """Request to switch workspace."""
    path: str = Field(..., description="Absolute path to the new workspace directory")


class WorkspaceSwitchResponse(BaseModel):
    """Response after switching workspace."""
    status: RepoStatus
    message: str


class DirectoryEntry(BaseModel):
    """A directory entry for the directory browser."""
    name: str
    path: str
    is_dir: bool


class DirectoryListing(BaseModel):
    """Response for directory listing."""
    path: str
    parent: str | None
    entries: list[DirectoryEntry]


class IndexableItems(BaseModel):
    """List of indexable directories and files for preview."""
    directories: list[str]
    files: list[str]
    total_directories: int
    total_files: int
