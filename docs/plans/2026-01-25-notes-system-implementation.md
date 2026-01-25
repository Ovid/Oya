# Notes System Redesign Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix the broken notes system so corrections are actually used during wiki generation, with one editable note per target.

**Architecture:** File-primary storage with DB index. Each target (file/directory/workflow) has at most one note. Notes stored in `.oyawiki/notes/{scope}/{slug}.md`. Orchestrator loads notes and passes to generators during wiki generation.

**Tech Stack:** Python/FastAPI backend, React/TypeScript frontend, SQLite database, pytest for testing

---

## Task 1: Update Database Schema

**Files:**
- Modify: `backend/src/oya/db/migrations.py`

**Step 1: Write the new schema**

Update the `SCHEMA_SQL` constant to replace the notes table. Find the existing notes table definition (lines 48-63) and replace it:

```python
-- Notes registry (human corrections)
-- One note per (scope, target) pair - upsert semantics
CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scope TEXT NOT NULL,  -- 'file', 'directory', 'workflow', 'general'
    target TEXT NOT NULL,  -- Target path or identifier (empty string for general)
    filepath TEXT NOT NULL,  -- Path relative to .oyawiki/notes/
    content TEXT NOT NULL,  -- Note content (markdown)
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    author TEXT,
    UNIQUE(scope, target)
);
```

Also update the index (line 97) from `idx_notes_scope` to:

```python
CREATE INDEX IF NOT EXISTS idx_notes_scope_target ON notes(scope, target);
```

Remove the old `idx_notes_target` index line (line 97).

**Step 2: Increment schema version**

Change line 6 from `SCHEMA_VERSION = 5` to `SCHEMA_VERSION = 6`.

**Step 3: Add migration for version 6**

After the version 5 migration block (around line 152), add:

```python
        # Version 6 migration: Recreate notes table with new schema
        if current_version >= 1 and current_version < 6:
            try:
                db.execute("DROP TABLE IF EXISTS notes")
                db.commit()
            except Exception:
                pass
```

**Step 4: Run tests to verify schema loads**

Run: `cd /Users/poecurt/projects/oya/.worktrees/fix-notes-system/backend && source .venv/bin/activate && pytest tests/test_migrations.py -v`
Expected: PASS (if test exists) or no test file (that's ok)

**Step 5: Commit**

```bash
git add backend/src/oya/db/migrations.py
git commit -m "feat(notes): update schema for one-note-per-target model"
```

---

## Task 2: Update Notes Schemas

**Files:**
- Modify: `backend/src/oya/notes/schemas.py`

**Step 1: Update the Note model**

Replace `created_at` with `updated_at` and remove `filepath` from the public API (it's internal):

```python
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
        description="Markdown content of the correction",
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
```

**Step 2: Commit**

```bash
git add backend/src/oya/notes/schemas.py
git commit -m "feat(notes): simplify schemas for upsert model"
```

---

## Task 3: Rewrite NotesService

**Files:**
- Modify: `backend/src/oya/notes/service.py`

**Step 1: Write the new service implementation**

Replace the entire file with:

```python
"""Notes service for managing corrections."""

import re
from datetime import datetime, UTC
from pathlib import Path
from typing import Optional

from oya.db.connection import Database
from oya.notes.schemas import Note, NoteScope


def _slugify_path(path: str) -> str:
    """Convert path to filename-safe slug.

    Replaces / with -- to avoid nested directories.
    """
    if not path:
        return ""
    # Replace path separators with --
    slug = path.replace("/", "--").replace("\\", "--")
    # Remove any characters that aren't alphanumeric, dash, dot, or underscore
    slug = re.sub(r"[^a-zA-Z0-9\-._]", "-", slug)
    # Collapse multiple dashes
    slug = re.sub(r"-+", "-", slug)
    return slug.strip("-")


def _get_filepath(scope: NoteScope, target: str) -> str:
    """Get the filepath for a note based on scope and target.

    Returns path relative to notes directory.
    """
    if scope == NoteScope.GENERAL:
        return "general.md"

    slug = _slugify_path(target)
    if not slug:
        slug = "unknown"

    # Organize by scope subdirectory
    return f"{scope.value}s/{slug}.md"


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
        cursor = self._db.execute(
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
        import yaml

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
                body = content[end_idx + 3:].strip()

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
```

**Step 2: Commit**

```bash
git add backend/src/oya/notes/service.py
git commit -m "feat(notes): rewrite service with upsert semantics and file-primary storage"
```

---

## Task 4: Update Notes API Endpoints

**Files:**
- Modify: `backend/src/oya/api/routers/notes.py`

**Step 1: Write new REST endpoints**

Replace the entire file with:

```python
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
```

**Step 2: Commit**

```bash
git add backend/src/oya/api/routers/notes.py
git commit -m "feat(notes): update API to REST pattern with scope/target paths"
```

---

## Task 5: Update prompts.py for Directory Notes

**Files:**
- Modify: `backend/src/oya/generation/prompts.py`

**Step 1: Add notes parameter to get_directory_prompt**

Find the `get_directory_prompt` function (around line 1130) and add `notes` parameter:

```python
def get_directory_prompt(
    repo_name: str,
    directory_path: str,
    file_list: list[str],
    symbols: list[dict[str, Any]],
    architecture_context: str,
    file_summaries: list[Any] | None = None,
    subdirectory_summaries: list[Any] | None = None,
    project_name: str | None = None,
    notes: list[dict[str, Any]] | None = None,  # ADD THIS
) -> str:
```

**Step 2: Add notes to the returned prompt**

At the end of the function (before the return), add notes handling. Find where `DIRECTORY_TEMPLATE.render(...)` is called and after it, add:

```python
    prompt = DIRECTORY_TEMPLATE.render(
        # ... existing params ...
    )

    if notes:
        prompt = _add_notes_to_prompt(prompt, notes)

    return prompt
```

**Step 3: Update get_notes_for_target to use updated_at**

Find `get_notes_for_target` function (around line 1273) and change `created_at` to `updated_at`:

```python
def get_notes_for_target(
    db: Any,
    scope: str,
    target: str,
) -> list[dict[str, Any]]:
    """Load notes that affect a specific target.

    Args:
        db: Database connection.
        scope: Note scope ('file', 'directory', 'workflow', 'general').
        target: Target path.

    Returns:
        List of note dictionaries.
    """
    sql = """
        SELECT content, author, updated_at
        FROM notes
        WHERE (scope = ? AND target = ?)
           OR scope = 'general'
        ORDER BY updated_at DESC
    """

    try:
        cursor = db.execute(sql, (scope, target))
        notes = []
        for row in cursor.fetchall():
            notes.append(
                {
                    "content": row["content"],
                    "author": row["author"],
                    "updated_at": row["updated_at"],
                }
            )
        return notes
    except Exception:
        return []
```

**Step 4: Update _format_notes to use updated_at**

Find `_format_notes` function and change `created_at` to `updated_at`:

```python
def _format_notes(notes: list[dict[str, Any]]) -> str:
    """Format notes for inclusion in a prompt."""
    if not notes:
        return ""

    lines = ["## Developer Corrections (Ground Truth)", ""]
    lines.append(
        "The following corrections have been provided by developers and MUST be incorporated:"
    )
    lines.append("")

    for i, note in enumerate(notes, 1):
        content = note.get("content", "")
        author = note.get("author", "Unknown")
        updated_at = note.get("updated_at", "")

        lines.append(f"### Correction {i}")
        if author:
            lines.append(f"*From: {author}*")
        if updated_at:
            lines.append(f"*Updated: {updated_at}*")
        lines.append("")
        lines.append(content)
        lines.append("")

    return "\n".join(lines)
```

**Step 5: Commit**

```bash
git add backend/src/oya/generation/prompts.py
git commit -m "feat(notes): add notes support to directory prompts"
```

---

## Task 6: Add Notes Parameter to FileGenerator

**Files:**
- Modify: `backend/src/oya/generation/file.py`

**Step 1: Add notes parameter to generate method**

Update the `generate` method signature (around line 34):

```python
    async def generate(
        self,
        file_path: str,
        content: str,
        symbols: list[dict],
        imports: list[str],
        architecture_summary: str,
        parsed_symbols: list[ParsedSymbol] | None = None,
        file_imports: dict[str, list[str]] | None = None,
        notes: list[dict] | None = None,  # ADD THIS
    ) -> tuple[GeneratedPage, FileSummary]:
```

**Step 2: Pass notes to get_file_prompt**

Update the `get_file_prompt` call (around line 60):

```python
        prompt = get_file_prompt(
            file_path=file_path,
            content=content,
            symbols=symbols,
            imports=imports,
            architecture_summary=architecture_summary,
            language=language,
            notes=notes,  # ADD THIS
        )
```

**Step 3: Commit**

```bash
git add backend/src/oya/generation/file.py
git commit -m "feat(notes): add notes parameter to FileGenerator"
```

---

## Task 7: Add Notes Parameter to DirectoryGenerator

**Files:**
- Modify: `backend/src/oya/generation/directory.py`

**Step 1: Add notes parameter to generate method**

Update the `generate` method signature (around line 28):

```python
    async def generate(
        self,
        directory_path: str,
        file_list: list[str],
        symbols: list[dict],
        architecture_context: str,
        file_summaries: list[FileSummary] | None = None,
        child_summaries: list[DirectorySummary] | None = None,
        project_name: str | None = None,
        notes: list[dict] | None = None,  # ADD THIS
    ) -> tuple[GeneratedPage, DirectorySummary]:
```

**Step 2: Pass notes to get_directory_prompt**

Update the `get_directory_prompt` call (around line 55):

```python
        prompt = get_directory_prompt(
            repo_name=repo_name,
            directory_path=directory_path,
            file_list=file_list,
            symbols=symbols,
            architecture_context=architecture_context,
            file_summaries=file_summaries or [],
            subdirectory_summaries=child_summaries or [],
            project_name=proj_name,
            notes=notes,  # ADD THIS
        )
```

**Step 3: Commit**

```bash
git add backend/src/oya/generation/directory.py
git commit -m "feat(notes): add notes parameter to DirectoryGenerator"
```

---

## Task 8: Wire Up Orchestrator to Pass Notes

**Files:**
- Modify: `backend/src/oya/generation/orchestrator.py`

**Step 1: Add import for get_notes_for_target**

At the top of the file, find the imports from `prompts` and add `get_notes_for_target`:

```python
from oya.generation.prompts import (
    SYSTEM_PROMPT,
    get_notes_for_target,  # ADD THIS
    # ... other imports
)
```

**Step 2: Update file generation to pass notes**

Find where `file_generator.generate()` is called (around line 1403). Before the call, add:

```python
            # Load notes for this file
            notes = get_notes_for_target(self.db, "file", file_path)

            page, file_summary = await self.file_generator.generate(
                file_path=file_path,
                content=content,
                symbols=file_symbols,
                imports=imports,
                architecture_summary="",
                parsed_symbols=file_parsed_symbols,
                file_imports=all_file_imports,
                notes=notes,  # ADD THIS
            )
```

**Step 3: Update directory generation to pass notes**

Find where `directory_generator.generate()` is called (around line 1201). Before the call, add:

```python
            # Load notes for this directory
            notes = get_notes_for_target(self.db, "directory", dir_path)

            page, directory_summary = await self.directory_generator.generate(
                directory_path=dir_path,
                file_list=direct_files,
                symbols=dir_symbols,
                architecture_context="",
                file_summaries=dir_file_summaries,
                child_summaries=child_summaries,
                project_name=project_name,
                notes=notes,  # ADD THIS
            )
```

**Step 4: Update _has_new_notes to use updated_at**

Find the `_has_new_notes` method and change `created_at` to `updated_at`:

```python
    def _has_new_notes(self, target: str, generated_at: str | None) -> bool:
        """Check if there are notes updated after the page was generated."""
        if not generated_at or not hasattr(self.db, "execute"):
            return False

        try:
            cursor = self.db.execute(
                """
                SELECT COUNT(*) FROM notes
                WHERE target = ? AND updated_at > ?
                """,
                (target, generated_at),
            )
            row = cursor.fetchone()
            return row[0] > 0 if row else False
        except Exception:
            return False
```

**Step 5: Commit**

```bash
git add backend/src/oya/generation/orchestrator.py
git commit -m "feat(notes): wire up orchestrator to load and pass notes to generators"
```

---

## Task 9: Update Backend Tests

**Files:**
- Modify: `backend/tests/test_notes_service.py`
- Modify: `backend/tests/test_notes_api.py`

**Step 1: Rewrite test_notes_service.py**

Replace the entire file with:

```python
"""Notes service tests."""

import pytest
from unittest.mock import MagicMock

from oya.notes.service import NotesService, _slugify_path, _get_filepath
from oya.notes.schemas import NoteScope


class TestSlugifyPath:
    """Tests for path slugification."""

    def test_replaces_slashes_with_double_dash(self):
        assert _slugify_path("src/main.py") == "src--main.py"

    def test_handles_nested_paths(self):
        assert _slugify_path("src/api/routers/notes.py") == "src--api--routers--notes.py"

    def test_empty_path_returns_empty(self):
        assert _slugify_path("") == ""

    def test_removes_special_characters(self):
        assert _slugify_path("src/[test]/file.py") == "src--test--file.py"


class TestGetFilepath:
    """Tests for filepath generation."""

    def test_general_scope_returns_general_md(self):
        assert _get_filepath(NoteScope.GENERAL, "") == "general.md"

    def test_file_scope_uses_files_subdirectory(self):
        assert _get_filepath(NoteScope.FILE, "src/main.py") == "files/src--main.py.md"

    def test_directory_scope_uses_directories_subdirectory(self):
        assert _get_filepath(NoteScope.DIRECTORY, "src/api") == "directorys/src--api.md"

    def test_workflow_scope_uses_workflows_subdirectory(self):
        assert _get_filepath(NoteScope.WORKFLOW, "auth") == "workflows/auth.md"


@pytest.fixture
def tmp_workspace(tmp_path):
    """Create temporary workspace with notes directory."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    notes_path = workspace / ".oyawiki" / "notes"
    notes_path.mkdir(parents=True)
    return workspace


@pytest.fixture
def mock_db():
    """Mock database for testing."""
    db = MagicMock()
    # Setup for upsert returning the note
    db.execute.return_value.fetchone.return_value = {
        "id": 1,
        "scope": "file",
        "target": "src/main.py",
        "filepath": "files/src--main.py.md",
        "content": "Test content",
        "author": None,
        "updated_at": "2024-01-01T00:00:00+00:00",
    }
    return db


@pytest.fixture
def notes_service(tmp_workspace, mock_db):
    """Create notes service for testing."""
    notes_path = tmp_workspace / ".oyawiki" / "notes"
    return NotesService(notes_path, mock_db)


class TestNotesServiceUpsert:
    """Tests for note upsert."""

    def test_creates_note_file(self, notes_service, tmp_workspace):
        """Upserting a note creates file on disk."""
        notes_service.upsert(
            scope=NoteScope.FILE,
            target="src/main.py",
            content="This function should use async/await pattern.",
        )

        # Check file exists in correct location
        notes_path = tmp_workspace / ".oyawiki" / "notes"
        note_file = notes_path / "files" / "src--main.py.md"
        assert note_file.exists()

        # Check content
        content = note_file.read_text()
        assert "scope: file" in content
        assert "target: src/main.py" in content
        assert "async/await pattern" in content

    def test_includes_frontmatter_metadata(self, notes_service, tmp_workspace):
        """Note file includes YAML frontmatter with metadata."""
        notes_service.upsert(
            scope=NoteScope.WORKFLOW,
            target="authentication",
            content="Auth flow needs two-factor support.",
            author="test@example.com",
        )

        notes_path = tmp_workspace / ".oyawiki" / "notes"
        note_file = notes_path / "workflows" / "authentication.md"
        content = note_file.read_text()

        assert content.startswith("---")
        assert "scope: workflow" in content
        assert "target: authentication" in content
        assert "author: test@example.com" in content
        assert "updated_at:" in content

    def test_upserts_to_database(self, notes_service, mock_db):
        """Upserting inserts or updates database record."""
        notes_service.upsert(
            scope=NoteScope.FILE,
            target="src/api.py",
            content="API needs rate limiting.",
        )

        mock_db.execute.assert_called()
        # Should use INSERT...ON CONFLICT
        call_sql = mock_db.execute.call_args_list[0][0][0].lower()
        assert "insert" in call_sql
        assert "on conflict" in call_sql

    def test_returns_note_object(self, notes_service):
        """Upsert returns Note with all fields."""
        note = notes_service.upsert(
            scope=NoteScope.GENERAL,
            target="",
            content="General project guidelines.",
        )

        assert note.id is not None
        assert note.scope == NoteScope.FILE  # From mock
        assert note.content == "Test content"  # From mock


class TestNotesServiceGet:
    """Tests for getting notes."""

    def test_gets_note_by_scope_and_target(self, notes_service, mock_db):
        """Gets note by scope and target."""
        note = notes_service.get(NoteScope.FILE, "src/main.py")

        assert note is not None
        assert note.id == 1
        assert note.content == "Test content"

    def test_returns_none_when_not_found(self, notes_service, mock_db):
        """Returns None when note doesn't exist."""
        mock_db.execute.return_value.fetchone.return_value = None

        note = notes_service.get(NoteScope.FILE, "nonexistent.py")

        assert note is None


class TestNotesServiceDelete:
    """Tests for deleting notes."""

    def test_deletes_note_file(self, notes_service, tmp_workspace, mock_db):
        """Deleting a note removes the file."""
        # Create a note file
        notes_path = tmp_workspace / ".oyawiki" / "notes"
        files_dir = notes_path / "files"
        files_dir.mkdir(exist_ok=True)
        note_file = files_dir / "src--main.py.md"
        note_file.write_text("Test content")

        mock_db.execute.return_value.fetchone.return_value = {
            "id": 1,
            "scope": "file",
            "target": "src/main.py",
            "filepath": "files/src--main.py.md",
            "content": "Test",
            "author": None,
            "updated_at": "2024-01-01T00:00:00",
        }

        result = notes_service.delete(NoteScope.FILE, "src/main.py")

        assert result is True
        assert not note_file.exists()

    def test_returns_false_when_not_found(self, notes_service, mock_db):
        """Returns False when note doesn't exist."""
        mock_db.execute.return_value.fetchone.return_value = None

        result = notes_service.delete(NoteScope.FILE, "nonexistent.py")

        assert result is False


class TestNotesServiceList:
    """Tests for listing notes."""

    def test_lists_all_notes(self, notes_service, mock_db):
        """Lists all notes when no scope filter."""
        mock_db.execute.return_value.fetchall.return_value = [
            {
                "id": 1,
                "scope": "file",
                "target": "src/a.py",
                "filepath": "files/src--a.py.md",
                "content": "A",
                "author": None,
                "updated_at": "2024-01-01T00:00:00",
            },
            {
                "id": 2,
                "scope": "directory",
                "target": "src/utils",
                "filepath": "directories/src--utils.md",
                "content": "B",
                "author": None,
                "updated_at": "2024-01-02T00:00:00",
            },
        ]

        notes = notes_service.list()

        assert len(notes) == 2

    def test_filters_by_scope(self, notes_service, mock_db):
        """Lists notes filtered by scope."""
        mock_db.execute.return_value.fetchall.return_value = [
            {
                "id": 1,
                "scope": "file",
                "target": "src/a.py",
                "filepath": "files/src--a.py.md",
                "content": "A",
                "author": None,
                "updated_at": "2024-01-01T00:00:00",
            },
        ]

        notes = notes_service.list(NoteScope.FILE)

        # Verify scope was passed to query
        call_args = mock_db.execute.call_args[0]
        assert "file" in call_args[1]
```

**Step 2: Rewrite test_notes_api.py**

Replace the entire file with:

```python
"""Notes API endpoint tests."""

import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from oya.main import app
from oya.notes.schemas import Note, NoteScope


@pytest.fixture
def client():
    """Test client."""
    return TestClient(app)


@pytest.fixture
def mock_notes_service():
    """Mock NotesService."""
    with patch("oya.api.routers.notes.get_notes_service") as mock:
        service = MagicMock()
        mock.return_value = service
        yield service


class TestListNotes:
    """Tests for GET /api/notes."""

    def test_returns_all_notes(self, client, mock_notes_service):
        """Returns list of all notes."""
        mock_notes_service.list.return_value = [
            Note(
                id=1,
                scope=NoteScope.FILE,
                target="src/main.py",
                content="Content 1",
                author=None,
                updated_at="2024-01-01T00:00:00",
            ),
        ]

        response = client.get("/api/notes")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["target"] == "src/main.py"

    def test_filters_by_scope(self, client, mock_notes_service):
        """Filters by scope query parameter."""
        mock_notes_service.list.return_value = []

        client.get("/api/notes?scope=file")

        mock_notes_service.list.assert_called_once_with(NoteScope.FILE)


class TestGetNote:
    """Tests for GET /api/notes/{scope}/{target}."""

    def test_returns_note(self, client, mock_notes_service):
        """Returns note by scope and target."""
        mock_notes_service.get.return_value = Note(
            id=1,
            scope=NoteScope.FILE,
            target="src/main.py",
            content="Test content",
            author="alice",
            updated_at="2024-01-01T00:00:00",
        )

        response = client.get("/api/notes/file/src/main.py")

        assert response.status_code == 200
        data = response.json()
        assert data["content"] == "Test content"
        assert data["author"] == "alice"

    def test_returns_404_when_not_found(self, client, mock_notes_service):
        """Returns 404 when note doesn't exist."""
        mock_notes_service.get.return_value = None

        response = client.get("/api/notes/file/nonexistent.py")

        assert response.status_code == 404


class TestUpsertNote:
    """Tests for PUT /api/notes/{scope}/{target}."""

    def test_creates_note(self, client, mock_notes_service):
        """Creates new note."""
        mock_notes_service.upsert.return_value = Note(
            id=1,
            scope=NoteScope.FILE,
            target="src/main.py",
            content="New content",
            author=None,
            updated_at="2024-01-01T00:00:00",
        )

        response = client.put(
            "/api/notes/file/src/main.py",
            json={"content": "New content"},
        )

        assert response.status_code == 200
        mock_notes_service.upsert.assert_called_once()

    def test_updates_existing_note(self, client, mock_notes_service):
        """Updates existing note."""
        mock_notes_service.upsert.return_value = Note(
            id=1,
            scope=NoteScope.FILE,
            target="src/main.py",
            content="Updated content",
            author="bob",
            updated_at="2024-01-02T00:00:00",
        )

        response = client.put(
            "/api/notes/file/src/main.py",
            json={"content": "Updated content", "author": "bob"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["content"] == "Updated content"


class TestDeleteNote:
    """Tests for DELETE /api/notes/{scope}/{target}."""

    def test_deletes_note(self, client, mock_notes_service):
        """Deletes note successfully."""
        mock_notes_service.delete.return_value = True

        response = client.delete("/api/notes/file/src/main.py")

        assert response.status_code == 204

    def test_returns_404_when_not_found(self, client, mock_notes_service):
        """Returns 404 when note doesn't exist."""
        mock_notes_service.delete.return_value = False

        response = client.delete("/api/notes/file/nonexistent.py")

        assert response.status_code == 404
```

**Step 3: Run the tests**

Run: `cd /Users/poecurt/projects/oya/.worktrees/fix-notes-system/backend && source .venv/bin/activate && pytest tests/test_notes_service.py tests/test_notes_api.py -v`
Expected: All tests pass

**Step 4: Commit**

```bash
git add backend/tests/test_notes_service.py backend/tests/test_notes_api.py
git commit -m "test(notes): update tests for new upsert-based API"
```

---

## Task 10: Update Frontend API Client

**Files:**
- Modify: `frontend/src/api/client.ts`

**Step 1: Replace notes API functions**

Find the notes endpoints section (around line 252) and replace with:

```typescript
// Notes endpoints
export async function getNote(scope: NoteScope, target: string): Promise<Note | null> {
  try {
    const encodedTarget = encodeURIComponent(target)
    return await fetchJson<Note>(`/api/notes/${scope}/${encodedTarget}`)
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) {
      return null
    }
    throw err
  }
}

export async function saveNote(
  scope: NoteScope,
  target: string,
  content: string,
  author?: string
): Promise<Note> {
  const encodedTarget = encodeURIComponent(target)
  return fetchJson<Note>(`/api/notes/${scope}/${encodedTarget}`, {
    method: 'PUT',
    body: JSON.stringify({ content, author }),
  })
}

export async function deleteNote(scope: NoteScope, target: string): Promise<void> {
  const encodedTarget = encodeURIComponent(target)
  await fetch(`${API_BASE}/api/notes/${scope}/${encodedTarget}`, { method: 'DELETE' })
}

export async function listNotes(scope?: NoteScope): Promise<Note[]> {
  const params = scope ? `?scope=${scope}` : ''
  return fetchJson<Note[]>(`/api/notes${params}`)
}
```

**Step 2: Remove old createNote function**

Delete the old `createNote` function if it still exists.

**Step 3: Commit**

```bash
git add frontend/src/api/client.ts
git commit -m "feat(notes): update API client for new REST endpoints"
```

---

## Task 11: Update Frontend Types

**Files:**
- Modify: `frontend/src/types/index.ts`

**Step 1: Update Note interface**

Find the Note interface (around line 122) and update:

```typescript
export interface Note {
  id: number
  scope: NoteScope
  target: string
  content: string
  author: string | null
  updated_at: string  // Changed from created_at
}
```

**Step 2: Remove NoteCreate interface**

Delete the `NoteCreate` interface since we now use inline parameters for `saveNote`.

**Step 3: Commit**

```bash
git add frontend/src/types/index.ts
git commit -m "feat(notes): update types for new note model"
```

---

## Task 12: Create NoteDisplay Component

**Files:**
- Create: `frontend/src/components/NoteDisplay.tsx`

**Step 1: Write the component**

```typescript
import { useState } from 'react'
import { deleteNote } from '../api/client'
import type { Note, NoteScope } from '../types'

interface NoteDisplayProps {
  note: Note
  scope: NoteScope
  target: string
  onEdit: () => void
  onDeleted: () => void
}

export function NoteDisplay({ note, scope, target, onEdit, onDeleted }: NoteDisplayProps) {
  const [isDeleting, setIsDeleting] = useState(false)
  const [isExpanded, setIsExpanded] = useState(true)

  const handleDelete = async () => {
    if (!confirm('Delete this correction? This cannot be undone.')) return

    setIsDeleting(true)
    try {
      await deleteNote(scope, target)
      onDeleted()
    } catch (err) {
      console.error('Failed to delete note:', err)
    } finally {
      setIsDeleting(false)
    }
  }

  const formatDate = (isoString: string) => {
    const date = new Date(isoString)
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    })
  }

  return (
    <div className="mb-6 border border-amber-200 dark:border-amber-800 rounded-lg bg-amber-50 dark:bg-amber-900/20">
      {/* Header */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full px-4 py-3 flex items-center justify-between text-left hover:bg-amber-100 dark:hover:bg-amber-900/30 rounded-t-lg"
      >
        <div className="flex items-center gap-2">
          <svg
            className="w-5 h-5 text-amber-600 dark:text-amber-400"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"
            />
          </svg>
          <span className="font-medium text-amber-800 dark:text-amber-200">
            Developer Correction
          </span>
        </div>
        <svg
          className={`w-5 h-5 text-amber-600 dark:text-amber-400 transition-transform ${
            isExpanded ? 'rotate-180' : ''
          }`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {/* Content */}
      {isExpanded && (
        <div className="px-4 pb-4">
          <div className="prose prose-sm dark:prose-invert max-w-none text-gray-800 dark:text-gray-200">
            {note.content.split('\n').map((line, i) => (
              <p key={i} className="my-2">
                {line || '\u00A0'}
              </p>
            ))}
          </div>

          {/* Footer */}
          <div className="mt-4 pt-3 border-t border-amber-200 dark:border-amber-800 flex items-center justify-between text-sm">
            <div className="text-amber-700 dark:text-amber-300">
              {note.author && <span>Updated by {note.author} &middot; </span>}
              <span>{formatDate(note.updated_at)}</span>
            </div>
            <div className="flex gap-2">
              <button
                onClick={onEdit}
                className="px-3 py-1 text-amber-700 dark:text-amber-300 hover:bg-amber-200 dark:hover:bg-amber-800 rounded"
              >
                Edit
              </button>
              <button
                onClick={handleDelete}
                disabled={isDeleting}
                className="px-3 py-1 text-red-600 dark:text-red-400 hover:bg-red-100 dark:hover:bg-red-900/30 rounded disabled:opacity-50"
              >
                {isDeleting ? 'Deleting...' : 'Delete'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
```

**Step 2: Commit**

```bash
git add frontend/src/components/NoteDisplay.tsx
git commit -m "feat(notes): create NoteDisplay component for inline viewing"
```

---

## Task 13: Update NoteEditor for Edit Mode

**Files:**
- Modify: `frontend/src/components/NoteEditor.tsx`

**Step 1: Rewrite NoteEditor**

Replace the entire file:

```typescript
import { useState, useEffect } from 'react'
import { saveNote } from '../api/client'
import { useNoteEditorStore } from '../stores'
import type { NoteScope, Note } from '../types'

interface NoteEditorProps {
  isOpen: boolean
  onClose: () => void
  onSaved: (note: Note) => void
  scope: NoteScope
  target: string
  existingContent?: string
}

export function NoteEditor({
  isOpen,
  onClose,
  onSaved,
  scope,
  target,
  existingContent = '',
}: NoteEditorProps) {
  const setDirty = useNoteEditorStore((s) => s.setDirty)
  const [content, setContent] = useState(existingContent)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const isEditing = !!existingContent

  // Reset state when editor opens
  useEffect(() => {
    if (isOpen) {
      setContent(existingContent)
      setError(null)
    }
  }, [isOpen, existingContent])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!content.trim()) return

    setIsSubmitting(true)
    setError(null)

    try {
      const note = await saveNote(scope, target, content.trim())
      setDirty(false)
      onSaved(note)
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save correction')
    } finally {
      setIsSubmitting(false)
    }
  }

  if (!isOpen) return null

  const scopeLabel =
    scope === 'file'
      ? 'File'
      : scope === 'directory'
        ? 'Directory'
        : scope === 'workflow'
          ? 'Workflow'
          : 'General'

  return (
    <div className="fixed inset-0 z-50 overflow-hidden">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black bg-opacity-50" onClick={onClose} />

      {/* Slide-over panel */}
      <div className="absolute inset-y-0 right-0 max-w-lg w-full bg-white dark:bg-gray-800 shadow-xl">
        <form onSubmit={handleSubmit} className="h-full flex flex-col">
          {/* Header */}
          <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
              {isEditing ? 'Edit Correction' : 'Add Correction'}
            </h2>
            <button
              type="button"
              onClick={onClose}
              className="text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M6 18L18 6M6 6l12 12"
                />
              </svg>
            </button>
          </div>

          {/* Body */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {/* Target info */}
            <div className="p-3 bg-gray-100 dark:bg-gray-700 rounded-lg">
              <div className="text-sm text-gray-500 dark:text-gray-400">{scopeLabel}</div>
              <div className="font-mono text-sm text-gray-900 dark:text-white">
                {target || '(general)'}
              </div>
            </div>

            {/* Content editor */}
            <div className="flex-1">
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Correction (Markdown supported)
              </label>
              <textarea
                value={content}
                onChange={(e) => {
                  setContent(e.target.value)
                  setDirty(!!e.target.value.trim() && e.target.value !== existingContent)
                }}
                placeholder="Describe the correction. This will be shown to the LLM during wiki generation..."
                rows={12}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono text-sm"
                autoFocus
              />
              <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                This correction will be included in the LLM prompt when regenerating documentation
                for this {scope}.
              </p>
            </div>

            {/* Error message */}
            {error && (
              <div className="p-3 bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 rounded-lg text-sm">
                {error}
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="px-4 py-3 border-t border-gray-200 dark:border-gray-700 flex justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting || !content.trim()}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isSubmitting ? 'Saving...' : 'Save Correction'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
```

**Step 2: Commit**

```bash
git add frontend/src/components/NoteEditor.tsx
git commit -m "feat(notes): update NoteEditor for edit mode with fixed scope/target"
```

---

## Task 14: Add Note Section to PageLoader

**Files:**
- Modify: `frontend/src/components/PageLoader.tsx`

**Step 1: Import dependencies**

Add imports at the top:

```typescript
import { useEffect, useState, useCallback } from 'react'
import type { WikiPage, Note, NoteScope } from '../types'
import { WikiContent } from './WikiContent'
import { NotFound } from './NotFound'
import { NoteDisplay } from './NoteDisplay'
import { NoteEditor } from './NoteEditor'
import { useWikiStore, useGenerationStore } from '../stores'
import { ApiError, getNote } from '../api/client'
import { GenerationProgress } from './GenerationProgress'
```

**Step 2: Add props for note support**

Update the interface:

```typescript
interface PageLoaderProps {
  loadPage: () => Promise<WikiPage>
  noteScope?: NoteScope
  noteTarget?: string
}
```

**Step 3: Add note state and loading**

Inside the component, after existing state declarations, add:

```typescript
  // Note state
  const [note, setNote] = useState<Note | null>(null)
  const [noteLoading, setNoteLoading] = useState(false)
  const [editorOpen, setEditorOpen] = useState(false)

  // Load note when target changes
  useEffect(() => {
    if (!noteScope || noteTarget === undefined) {
      setNote(null)
      return
    }

    let cancelled = false
    setNoteLoading(true)

    getNote(noteScope, noteTarget)
      .then((n) => {
        if (!cancelled) setNote(n)
      })
      .catch(() => {
        if (!cancelled) setNote(null)
      })
      .finally(() => {
        if (!cancelled) setNoteLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [noteScope, noteTarget])

  const handleNoteSaved = (savedNote: Note) => {
    setNote(savedNote)
  }

  const handleNoteDeleted = () => {
    setNote(null)
  }
```

**Step 4: Update the return statement**

Before `return <WikiContent page={page} />`, add note rendering:

```typescript
  // Render note section + content
  const noteSection = noteScope && noteTarget !== undefined && !noteLoading && (
    <div className="mb-4">
      {note ? (
        <NoteDisplay
          note={note}
          scope={noteScope}
          target={noteTarget}
          onEdit={() => setEditorOpen(true)}
          onDeleted={handleNoteDeleted}
        />
      ) : (
        <button
          onClick={() => setEditorOpen(true)}
          className="text-sm text-blue-600 dark:text-blue-400 hover:underline flex items-center gap-1"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 4v16m8-8H4"
            />
          </svg>
          Add Correction
        </button>
      )}
      {noteScope && (
        <NoteEditor
          isOpen={editorOpen}
          onClose={() => setEditorOpen(false)}
          onSaved={handleNoteSaved}
          scope={noteScope}
          target={noteTarget}
          existingContent={note?.content}
        />
      )}
    </div>
  )

  return (
    <>
      {noteSection}
      <WikiContent page={page} />
    </>
  )
```

**Step 5: Commit**

```bash
git add frontend/src/components/PageLoader.tsx
git commit -m "feat(notes): add inline note section to PageLoader"
```

---

## Task 15: Update FilePage and DirectoryPage

**Files:**
- Modify: `frontend/src/components/pages/FilePage.tsx`
- Modify: `frontend/src/components/pages/DirectoryPage.tsx`

**Step 1: Update FilePage**

Replace with:

```typescript
import { useCallback } from 'react'
import { useParams } from 'react-router-dom'
import { PageLoader } from '../PageLoader'
import { getFile } from '../../api/client'

export function FilePage() {
  const { slug } = useParams<{ slug: string }>()
  const loadPage = useCallback(() => getFile(slug!), [slug])

  // Convert slug back to file path for note lookup
  // Slugs use -- for path separators, so src--main.py -> src/main.py
  const filePath = slug?.replace(/--/g, '/').replace(/\.md$/, '') || ''

  return (
    <PageLoader
      loadPage={loadPage}
      noteScope="file"
      noteTarget={filePath}
    />
  )
}
```

**Step 2: Update DirectoryPage**

First read the current DirectoryPage to understand its structure, then update similarly:

```typescript
import { useCallback } from 'react'
import { useParams } from 'react-router-dom'
import { PageLoader } from '../PageLoader'
import { getDirectory } from '../../api/client'

export function DirectoryPage() {
  const { slug } = useParams<{ slug: string }>()
  const loadPage = useCallback(() => getDirectory(slug!), [slug])

  // Convert slug back to directory path
  // Handle 'root' specially
  const dirPath = slug === 'root' ? '' : (slug?.replace(/--/g, '/') || '')

  return (
    <PageLoader
      loadPage={loadPage}
      noteScope="directory"
      noteTarget={dirPath}
    />
  )
}
```

**Step 3: Commit**

```bash
git add frontend/src/components/pages/FilePage.tsx frontend/src/components/pages/DirectoryPage.tsx
git commit -m "feat(notes): pass note scope/target to PageLoader in file and directory pages"
```

---

## Task 16: Run Full Test Suite

**Step 1: Run backend tests**

Run: `cd /Users/poecurt/projects/oya/.worktrees/fix-notes-system/backend && source .venv/bin/activate && pytest -v`
Expected: All tests pass

**Step 2: Run frontend tests**

Run: `cd /Users/poecurt/projects/oya/.worktrees/fix-notes-system/frontend && npm run test`
Expected: All tests pass

**Step 3: Run frontend build**

Run: `cd /Users/poecurt/projects/oya/.worktrees/fix-notes-system/frontend && npm run build`
Expected: Build succeeds

**Step 4: Fix any issues**

If tests fail, fix issues and commit fixes.

---

## Task 17: Final Cleanup

**Files:**
- Review: `frontend/src/stores/noteEditorStore.ts`

**Step 1: Check if noteEditorStore is still needed**

The store may still be useful for the `isDirty` state to warn before closing with unsaved changes. If so, keep it. If not, it can be removed later.

**Step 2: Create final commit**

```bash
git add -A
git commit -m "chore: cleanup and finalize notes system redesign"
```

---

## Summary

After completing all tasks:

1. **Database**: New schema with `UNIQUE(scope, target)` constraint
2. **Service**: Upsert semantics, file-primary storage in `.oyawiki/notes/{scope}s/{slug}.md`
3. **API**: REST pattern with `PUT /api/notes/{scope}/{target}` for upsert
4. **Generators**: Accept `notes` parameter and pass to prompts
5. **Orchestrator**: Loads notes via `get_notes_for_target()` and passes to generators
6. **Frontend**: Inline note display on wiki pages with edit/delete functionality

The critical bug is fixed: notes are now passed to the LLM during generation.
