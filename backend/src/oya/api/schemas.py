"""Pydantic schemas for API requests and responses."""

from pydantic import BaseModel, Field


class JobCreated(BaseModel):
    """Job creation response."""

    job_id: str
    status: str = "pending"
    message: str = "Job started"


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


class FileList(BaseModel):
    """A list of directories and files."""

    directories: list[str] = Field(default_factory=list)
    files: list[str] = Field(default_factory=list)


class IndexableItems(BaseModel):
    """List of indexable items categorized by exclusion reason.

    Three categories:
    - included: Files that will be indexed
    - excluded_by_oyaignore: Files excluded via .oyaignore (user can re-include)
    - excluded_by_rule: Files excluded via built-in rules (cannot be changed)
    """

    included: FileList
    excluded_by_oyaignore: FileList
    excluded_by_rule: FileList


class OyaignoreUpdateRequest(BaseModel):
    """Request to update .oyaignore with new exclusions and removals."""

    directories: list[str] = Field(default_factory=list)
    files: list[str] = Field(default_factory=list)
    removals: list[str] = Field(
        default_factory=list, description="Patterns to remove from .oyaignore"
    )


class OyaignoreUpdateResponse(BaseModel):
    """Response after updating .oyaignore."""

    added_directories: list[str]
    added_files: list[str]
    removed: list[str]
    total_added: int
    total_removed: int
