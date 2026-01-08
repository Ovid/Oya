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


class NoteCreate(BaseModel):
    """Request to create a new note."""

    scope: NoteScope = Field(..., description="Scope of the correction")
    target: str = Field(
        "",
        description="Target path (file, directory, or workflow name)",
    )
    content: str = Field(
        ...,
        min_length=1,
        description="Markdown content of the correction",
    )
    author: Optional[str] = Field(
        None,
        description="Optional author email (defaults to git config)",
    )


class Note(BaseModel):
    """A correction note."""

    model_config = {"from_attributes": True}

    id: int = Field(..., description="Database ID")
    filepath: str = Field(..., description="Filename in notes directory")
    scope: NoteScope = Field(..., description="Scope of the correction")
    target: str = Field(..., description="Target path")
    content: str = Field(..., description="Markdown content")
    author: Optional[str] = Field(None, description="Author email")
    created_at: datetime = Field(..., description="Creation timestamp")
