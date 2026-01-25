"""Notes API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import Optional

from oya.api.deps import get_db, get_active_repo_paths
from oya.db.connection import Database
from oya.notes.schemas import Note, NoteScope, NoteUpsert
from oya.notes.service import NotesService
from oya.repo.repo_paths import RepoPaths


router = APIRouter(prefix="/api/notes", tags=["notes"])


def get_notes_service(
    paths: RepoPaths = Depends(get_active_repo_paths),
    db: Database = Depends(get_db),
) -> NotesService:
    """Get NotesService instance."""
    return NotesService(paths.notes_dir, db)


@router.get("", response_model=list[Note])
async def list_notes(
    scope: Optional[NoteScope] = Query(None, description="Filter by scope"),
    service: NotesService = Depends(get_notes_service),
) -> list[Note]:
    """List all correction notes.

    Returns all notes, optionally filtered by scope.
    """
    return service.list(scope)


@router.get("/{scope}/{target:path}", response_model=Note)
async def get_note(
    scope: NoteScope,
    target: str,
    service: NotesService = Depends(get_notes_service),
) -> Note:
    """Get a single note by scope and target.

    Target should be URL-encoded if it contains special characters.
    For general notes, use empty string as target.
    """
    note = service.get(scope, target)
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    return note


@router.put("/{scope}/{target:path}", response_model=Note)
async def upsert_note(
    scope: NoteScope,
    target: str,
    data: NoteUpsert,
    service: NotesService = Depends(get_notes_service),
) -> Note:
    """Create or update a correction note.

    Creates a markdown file in .oyawiki/notes/{scope}s/{slug}.md
    and indexes it in the database.
    """
    return service.upsert(
        scope=scope,
        target=target,
        content=data.content,
        author=data.author,
    )


@router.delete("/{scope}/{target:path}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_note(
    scope: NoteScope,
    target: str,
    service: NotesService = Depends(get_notes_service),
) -> None:
    """Delete a note by scope and target.

    Removes both the file and database record.
    """
    if not service.delete(scope, target):
        raise HTTPException(status_code=404, detail="Note not found")
