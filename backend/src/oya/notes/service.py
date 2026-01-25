"""Notes service for managing corrections."""

import re
from datetime import datetime, UTC
from pathlib import Path
from typing import Optional

import yaml

from oya.db.connection import Database
from oya.notes.schemas import Note, NoteScope


def _slugify_path(path: str) -> str:
    """Convert path to filename-safe slug for filesystem storage.

    Uses double-dash (--) for path separators to enable unambiguous conversion back
    to the original path. This differs from wiki URL slugs (which use single dash),
    but that's intentional:

    - Wiki URL slugs: src-main-py (relies on file extension heuristics to reconstruct)
    - Notes file slugs: src--main.py (unambiguous, preserves dots in filenames)

    This is only used for filesystem storage. API lookups use the actual path stored
    in the database's `target` column, not the slugified version.
    """
    if not path:
        return ""
    # First replace path separators with -- to flatten directory structure
    slug = path.replace("/", "--").replace("\\", "--")
    # Then remove any characters that aren't alphanumeric, dash, dot, or underscore
    slug = re.sub(r"[^a-zA-Z0-9\-._]", "", slug)
    # Collapse runs of 3+ dashes to -- (handles consecutive separators like //)
    slug = re.sub(r"-{3,}", "--", slug)
    return slug.strip("-")


def _get_filepath(scope: NoteScope, target: str) -> str:
    """Get the filesystem path for storing a note's markdown file.

    This is only used for filesystem storage (e.g., .oyawiki/notes/files/src--main.py.md).
    The database stores the actual target path (e.g., src/main.py) for API lookups.

    Returns:
        Path relative to the notes directory.
    """
    if scope == NoteScope.GENERAL:
        return "general.md"

    slug = _slugify_path(target)
    if not slug:
        slug = "unknown"

    # Organize by scope subdirectory (handle irregular plural for "directory")
    subdir = "directories" if scope == NoteScope.DIRECTORY else f"{scope.value}s"
    return f"{subdir}/{slug}.md"


class NotesService:
    """Service for managing correction notes.

    File-primary storage with database index.
    Each (scope, target) pair has at most one note.
    """

    def __init__(self, notes_path: Path, db: Database) -> None:
        """Initialize notes service.

        Args:
            notes_path: Path to .oyawiki/notes directory.
            db: Database connection.
        """
        self._notes_path = notes_path
        self._db = db
        # Ensure notes directory and subdirectories exist
        self._notes_path.mkdir(parents=True, exist_ok=True)
        for subdir in ["files", "directories", "workflows"]:
            (self._notes_path / subdir).mkdir(exist_ok=True)

    def _write_note_file(
        self,
        filepath: str,
        scope: NoteScope,
        target: str,
        content: str,
        author: Optional[str],
        updated_at: datetime,
    ) -> None:
        """Write note file with YAML frontmatter."""
        frontmatter_lines = [
            "---",
            f"scope: {scope.value}",
            f"target: {target}",
        ]
        if author:
            frontmatter_lines.append(f"author: {author}")
        frontmatter_lines.extend(
            [
                f"updated_at: {updated_at.isoformat()}",
                "---",
                "",
            ]
        )

        full_content = "\n".join(frontmatter_lines) + content

        note_file = self._notes_path / filepath
        note_file.parent.mkdir(parents=True, exist_ok=True)
        note_file.write_text(full_content)

    def get(self, scope: NoteScope, target: str) -> Optional[Note]:
        """Get a note by scope and target.

        Args:
            scope: Note scope.
            target: Target path (empty string for general).

        Returns:
            Note if found, None otherwise.
        """
        sql = """
            SELECT id, scope, target, filepath, content, author, updated_at
            FROM notes
            WHERE scope = ? AND target = ?
        """
        cursor = self._db.execute(sql, (scope.value, target))
        row = cursor.fetchone()

        if not row:
            return None

        return Note(
            id=row["id"],
            scope=NoteScope(row["scope"]),
            target=row["target"],
            content=row["content"],
            author=row["author"],
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def upsert(
        self,
        scope: NoteScope,
        target: str,
        content: str,
        author: Optional[str] = None,
    ) -> Note:
        """Create or update a note.

        Args:
            scope: Note scope.
            target: Target path (empty string for general).
            content: Markdown content.
            author: Optional author.

        Returns:
            The created or updated note.
        """
        updated_at = datetime.now(UTC)
        filepath = _get_filepath(scope, target)

        # Write file first (source of truth)
        self._write_note_file(
            filepath=filepath,
            scope=scope,
            target=target,
            content=content,
            author=author,
            updated_at=updated_at,
        )

        # Upsert into database
        sql = """
            INSERT INTO notes (scope, target, filepath, content, author, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(scope, target) DO UPDATE SET
                filepath = excluded.filepath,
                content = excluded.content,
                author = excluded.author,
                updated_at = excluded.updated_at
        """
        self._db.execute(
            sql,
            (
                scope.value,
                target,
                filepath,
                content,
                author,
                updated_at.isoformat(),
            ),
        )

        # Get the note ID (either newly inserted or existing)
        note = self.get(scope, target)
        if note is None:
            raise RuntimeError("Failed to get note after upsert")

        return note

    def delete(self, scope: NoteScope, target: str) -> bool:
        """Delete a note by scope and target.

        Args:
            scope: Note scope.
            target: Target path.

        Returns:
            True if deleted, False if not found.
        """
        # First get the note to find the filepath
        note = self.get(scope, target)
        if not note:
            return False

        filepath = _get_filepath(scope, target)

        # Delete the file
        note_file = self._notes_path / filepath
        if note_file.exists():
            note_file.unlink()

        # Delete from database
        sql = "DELETE FROM notes WHERE scope = ? AND target = ?"
        self._db.execute(sql, (scope.value, target))

        return True

    def list(self, scope: Optional[NoteScope] = None) -> list[Note]:
        """List notes, optionally filtered by scope.

        Args:
            scope: Optional scope to filter by.

        Returns:
            List of notes.
        """
        if scope:
            sql = """
                SELECT id, scope, target, filepath, content, author, updated_at
                FROM notes
                WHERE scope = ?
                ORDER BY updated_at DESC
            """
            cursor = self._db.execute(sql, (scope.value,))
        else:
            sql = """
                SELECT id, scope, target, filepath, content, author, updated_at
                FROM notes
                ORDER BY updated_at DESC
            """
            cursor = self._db.execute(sql)

        notes = []
        for row in cursor.fetchall():
            notes.append(
                Note(
                    id=row["id"],
                    scope=NoteScope(row["scope"]),
                    target=row["target"],
                    content=row["content"],
                    author=row["author"],
                    updated_at=datetime.fromisoformat(row["updated_at"]),
                )
            )

        return notes

    def rebuild_index(self) -> int:
        """Rebuild database index from files on disk.

        Scans .oyawiki/notes/ for markdown files and syncs DB.

        Returns:
            Number of notes indexed.
        """
        count = 0

        # Clear existing notes
        self._db.execute("DELETE FROM notes")

        # Scan all markdown files
        for md_file in self._notes_path.rglob("*.md"):
            try:
                content = md_file.read_text()

                # Parse frontmatter
                if not content.startswith("---"):
                    continue

                end_idx = content.find("---", 3)
                if end_idx == -1:
                    continue

                frontmatter = content[3:end_idx].strip()
                body = content[end_idx + 3 :].strip()

                meta = yaml.safe_load(frontmatter)
                if not meta:
                    continue

                scope = NoteScope(meta.get("scope", "general"))
                target = meta.get("target", "")
                author = meta.get("author")
                updated_at = meta.get("updated_at", datetime.now(UTC).isoformat())

                filepath = str(md_file.relative_to(self._notes_path))

                # Insert into database
                sql = """
                    INSERT OR REPLACE INTO notes
                    (scope, target, filepath, content, author, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """
                self._db.execute(
                    sql,
                    (scope.value, target, filepath, body, author, updated_at),
                )
                count += 1

            except Exception:
                # Skip malformed files
                continue

        self._db.commit()
        return count
