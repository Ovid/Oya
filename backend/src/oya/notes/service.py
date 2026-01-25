"""Notes service for managing corrections."""

import hashlib
import logging
import re
import threading
from datetime import datetime, UTC
from pathlib import Path
from typing import Optional

import yaml

from oya.db.connection import Database
from oya.notes.schemas import Note, NoteScope

logger = logging.getLogger(__name__)


# Max filename length before falling back to hash (most filesystems limit to 255 bytes)
# Use 200 to leave room for .md extension and be safe across all filesystems
MAX_SLUG_LENGTH = 200

# Mapping from scope to subdirectory name (handles irregular plurals)
SCOPE_SUBDIRS: dict[NoteScope, str] = {
    NoteScope.FILE: "files",
    NoteScope.DIRECTORY: "directories",
    NoteScope.WORKFLOW: "workflows",
}


def _slugify_path(path: str) -> str:
    """Convert path to filename-safe slug for filesystem storage.

    Uses double-dash (--) for path separators to enable unambiguous conversion back
    to the original path. This differs from wiki URL slugs (which use single dash),
    but that's intentional:

    - Wiki URL slugs: src-main-py (relies on file extension heuristics to reconstruct)
    - Notes file slugs: src--main.py (unambiguous, preserves dots in filenames)

    Special characters are percent-encoded to avoid collisions. For example:
    - file(test).py  -> file%28test%29.py
    - file[test].py  -> file%5Btest%5D.py

    If the resulting slug exceeds MAX_SLUG_LENGTH bytes (e.g., paths with many
    Unicode characters), falls back to a SHA-256 hash prefix for the filename.

    This is only used for filesystem storage. API lookups use the actual path stored
    in the database's `target` column, not the slugified version.
    """
    if not path:
        return ""
    # First replace path separators with -- to flatten directory structure
    slug = path.replace("/", "--").replace("\\", "--")
    # Percent-encode special characters to avoid collisions
    # Keep alphanumeric, dash, dot, and underscore as-is
    result = []
    for char in slug:
        if char.isalnum() or char in "-._":
            result.append(char)
        else:
            # Percent-encode the character as UTF-8 bytes (e.g., '(' -> '%28', 'é' -> '%C3%A9')
            result.append("".join(f"%{b:02X}" for b in char.encode("utf-8")))
    slug = "".join(result)
    # Collapse runs of 3+ dashes to -- (handles consecutive separators like //)
    slug = re.sub(r"-{3,}", "--", slug)
    slug = slug.strip("-")

    # If slug is too long, fall back to hash-based filename
    if len(slug.encode("utf-8")) > MAX_SLUG_LENGTH:
        hash_digest = hashlib.sha256(path.encode("utf-8")).hexdigest()[:16]
        # Keep a short prefix for human readability, then add hash
        prefix = slug[:40] if len(slug) > 40 else slug
        # Preserve file extension for readability (e.g., ".py")
        ext = Path(path).suffix
        slug = f"{prefix}--{hash_digest}{ext}"

    return slug


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

    subdir = SCOPE_SUBDIRS[scope]
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
        # Lock for thread-safe upsert/delete operations (protects file + DB atomicity)
        self._lock = threading.Lock()
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

    def _get_stored_filepath(self, scope: NoteScope, target: str) -> Optional[str]:
        """Get the stored filepath from the database for an existing note.

        Returns None if no note exists for this scope/target.
        """
        sql = "SELECT filepath FROM notes WHERE scope = ? AND target = ?"
        cursor = self._db.execute(sql, (scope.value, target))
        row = cursor.fetchone()
        return row["filepath"] if row else None

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

        # Use lock to ensure atomicity of file + DB operations
        with self._lock:
            # Check if note exists with a different filepath (e.g., slug algorithm changed)
            # and delete the old file to avoid orphans
            old_filepath = self._get_stored_filepath(scope, target)
            if old_filepath and old_filepath != filepath:
                old_file = self._notes_path / old_filepath
                if old_file.exists():
                    old_file.unlink()

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
            self._db.commit()

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
        # Use lock to ensure atomicity of file + DB operations
        with self._lock:
            # Get stored filepath from database (not recalculated, in case algorithm changed)
            filepath = self._get_stored_filepath(scope, target)
            if not filepath:
                return False

            # Delete the file
            note_file = self._notes_path / filepath
            if note_file.exists():
                note_file.unlink()

            # Delete from database
            sql = "DELETE FROM notes WHERE scope = ? AND target = ?"
            self._db.execute(sql, (scope.value, target))
            self._db.commit()

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
        Uses transaction rollback on critical errors to avoid leaving DB empty.

        Returns:
            Number of notes indexed.

        Raises:
            RuntimeError: If a critical error occurs during rebuild.
        """
        count = 0

        try:
            # Start explicit transaction so DELETE + INSERTs are atomic
            # This ensures rollback can restore the original data if rebuild fails
            self._db.execute("BEGIN IMMEDIATE")

            # Clear existing notes (within transaction)
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

                except Exception as e:
                    # Log and skip malformed files so admins can identify problems
                    logger.warning(f"Failed to parse note file {md_file}: {e}")
                    continue

            # Only commit after all files processed successfully
            self._db.commit()
            return count

        except Exception as e:
            # Rollback to preserve existing data on critical errors
            logger.error(f"Critical error during rebuild_index, rolling back: {e}")
            try:
                self._db.rollback()
            except Exception as rollback_error:
                # Defensive: rollback may fail if no transaction is active
                logger.error(f"Failed to rollback transaction: {rollback_error}")
            raise RuntimeError(f"Failed to rebuild notes index: {e}") from e
