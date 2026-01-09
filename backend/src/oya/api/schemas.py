"""Pydantic schemas for API requests and responses."""

from datetime import datetime
from pydantic import BaseModel, Field


class RepoStatus(BaseModel):
    """Repository status response."""
    path: str
    head_commit: str | None
    head_message: str | None
    branch: str | None
    initialized: bool
    last_generation: datetime | None = None
    generation_status: str | None = None


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
