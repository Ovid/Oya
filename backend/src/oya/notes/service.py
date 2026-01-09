"""Notes service for managing corrections."""

import re
from datetime import datetime, UTC
from pathlib import Path
from typing import Optional

from oya.db.connection import Database
from oya.notes.schemas import Note, NoteCreate, NoteScope


def _slugify(text: str) -> str:
    """Convert text to URL-safe slug."""
    # Replace path separators and non-alphanumeric chars
    slug = re.sub(r"[/\\]", "-", text)
    slug = re.sub(r"[^a-zA-Z0-9-]", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    return slug.strip("-").lower()


class NotesService:
    """Service for managing correction notes."""

    def __init__(self, notes_path: Path, db: Database) -> None:
        """Initialize notes service.

        Args:
            notes_path: Path to .oyawiki/notes directory.
            db: Database connection.
        """
        self._notes_path = notes_path
        self._db = db
        # Ensure notes directory exists
        self._notes_path.mkdir(parents=True, exist_ok=True)

    def _generate_filename(self, scope: NoteScope, target: str) -> str:
        """Generate filename for a new note.

        Format: {ISO-timestamp}-{scope}-{slug}.md
        """
        timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H-%M-%S")
        slug = _slugify(target) if target else "general"
        return f"{timestamp}-{scope.value}-{slug}.md"

    def _write_note_file(
        self,
        filepath: str,
        scope: NoteScope,
        target: str,
        content: str,
        author: Optional[str],
        created_at: datetime,
    ) -> None:
        """Write note file with YAML frontmatter."""
        frontmatter_lines = [
            "---",
            f"scope: {scope.value}",
            f"target: {target}",
        ]
        if author:
            frontmatter_lines.append(f"author: {author}")
        frontmatter_lines.extend([
            f"created_at: {created_at.isoformat()}",
            "---",
        ])

        full_content = "\n".join(frontmatter_lines) + "\n" + content

        note_file = self._notes_path / filepath
        note_file.write_text(full_content)

    def _read_note_content(self, filepath: str) -> Optional[str]:
        """Read content from note file (excluding frontmatter)."""
        note_file = self._notes_path / filepath
        if not note_file.exists():
            return None

        content = note_file.read_text()

        # Skip frontmatter
        if content.startswith("---"):
            # Find end of frontmatter
            end_idx = content.find("---", 3)
            if end_idx != -1:
                content = content[end_idx + 3:].strip()

        return content

    def create(self, note_data: NoteCreate) -> Note:
        """Create a new correction note.

        Args:
            note_data: Note creation request.

        Returns:
            Created note with ID.
        """
        created_at = datetime.now(UTC)
        filepath = self._generate_filename(note_data.scope, note_data.target)

        # Write file
        self._write_note_file(
            filepath=filepath,
            scope=note_data.scope,
            target=note_data.target,
            content=note_data.content,
            author=note_data.author,
            created_at=created_at,
        )

        # Insert into database
        sql = """
            INSERT INTO notes (filepath, scope, target, content, author, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """
        cursor = self._db.execute(
            sql,
            (
                filepath,
                note_data.scope.value,
                note_data.target,
                note_data.content,
                note_data.author,
                created_at.isoformat(),
            ),
        )
        note_id = cursor.lastrowid

        return Note(
            id=note_id,
            filepath=filepath,
            scope=note_data.scope,
            target=note_data.target,
            content=note_data.content,
            author=note_data.author,
            created_at=created_at,
        )

    def list_by_target(self, target: Optional[str]) -> list[Note]:
        """List notes, optionally filtered by target.

        Args:
            target: Optional target path to filter by.

        Returns:
            List of notes.
        """
        if target:
            sql = """
                SELECT id, filepath, scope, target, content, author, created_at
                FROM notes
                WHERE target = ?
                ORDER BY created_at DESC
            """
            cursor = self._db.execute(sql, (target,))
        else:
            sql = """
                SELECT id, filepath, scope, target, content, author, created_at
                FROM notes
                ORDER BY created_at DESC
            """
            cursor = self._db.execute(sql)

        notes = []
        for row in cursor.fetchall():
            notes.append(Note(
                id=row["id"],
                filepath=row["filepath"],
                scope=NoteScope(row["scope"]),
                target=row["target"],
                content=row["content"],
                author=row["author"],
                created_at=datetime.fromisoformat(row["created_at"]),
            ))

        return notes

    def get(self, note_id: int) -> Optional[Note]:
        """Get a note by ID.

        Args:
            note_id: Note database ID.

        Returns:
            Note if found, None otherwise.
        """
        sql = """
            SELECT id, filepath, scope, target, content, author, created_at
            FROM notes
            WHERE id = ?
        """
        cursor = self._db.execute(sql, (note_id,))
        row = cursor.fetchone()

        if not row:
            return None

        return Note(
            id=row["id"],
            filepath=row["filepath"],
            scope=NoteScope(row["scope"]),
            target=row["target"],
            content=row["content"],
            author=row["author"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    def delete(self, note_id: int) -> bool:
        """Delete a note by ID.

        Args:
            note_id: Note database ID.

        Returns:
            True if deleted, False if not found.
        """
        # First get the note to find the filepath
        note = self.get(note_id)
        if not note:
            return False

        # Delete the file
        note_file = self._notes_path / note.filepath
        if note_file.exists():
            note_file.unlink()

        # Delete from database
        sql = "DELETE FROM notes WHERE id = ?"
        self._db.execute(sql, (note_id,))

        return True
