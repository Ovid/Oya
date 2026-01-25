"""Notes schemas for corrections and annotations."""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class NoteScope(str, Enum):
    """Scope of a correction note."""

    FILE = "file"
    DIRECTORY = "directory"
    WORKFLOW = "workflow"
    GENERAL = "general"


class NoteUpsert(BaseModel):
    """Request to create or update a note."""

    content: str = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="Markdown content of the correction (max 10,000 characters)",
    )
    author: Optional[str] = Field(
        None,
        description="Optional author name or email",
    )


class Note(BaseModel):
    """A correction note."""

    model_config = {"from_attributes": True}

    id: int = Field(..., description="Database ID")
    scope: NoteScope = Field(..., description="Scope of the correction")
    target: str = Field(..., description="Target path")
    content: str = Field(..., description="Markdown content")
    author: Optional[str] = Field(None, description="Author")
    updated_at: datetime = Field(..., description="Last update timestamp")
