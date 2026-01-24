"""Notes API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import Optional

from oya.api.deps import get_db, get_active_repo_paths
from oya.db.connection import Database
from oya.notes.schemas import Note, NoteCreate
from oya.notes.service import NotesService
from oya.repo.repo_paths import RepoPaths


router = APIRouter(prefix="/api/notes", tags=["notes"])


def get_notes_service(
    paths: RepoPaths = Depends(get_active_repo_paths),
    db: Database = Depends(get_db),
) -> NotesService:
    """Get NotesService instance."""
    return NotesService(paths.notes_dir, db)


@router.post("", response_model=Note, status_code=status.HTTP_201_CREATED)
async def create_note(
    note_data: NoteCreate,
    service: NotesService = Depends(get_notes_service),
) -> Note:
    """Create a new correction note.

    Creates a markdown file in .oyawiki/notes/ with frontmatter metadata
    and registers the note in the database.
    """
    return service.create(note_data)


@router.get("", response_model=list[Note])
async def list_notes(
    target: Optional[str] = Query(None, description="Filter by target path"),
    service: NotesService = Depends(get_notes_service),
) -> list[Note]:
    """List correction notes.

    Returns all notes, optionally filtered by target path.
    """
    return service.list_by_target(target)


@router.get("/{note_id}", response_model=Note)
async def get_note(
    note_id: int,
    service: NotesService = Depends(get_notes_service),
) -> Note:
    """Get a single note by ID."""
    note = service.get(note_id)
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    return note


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_note(
    note_id: int,
    service: NotesService = Depends(get_notes_service),
) -> None:
    """Delete a note by ID.

    Removes both the file and database record.
    """
    if not service.delete(note_id):
        raise HTTPException(status_code=404, detail="Note not found")
