"""Pydantic schemas for API requests and responses."""

from datetime import datetime
from pydantic import BaseModel


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
