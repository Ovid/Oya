# Analysis of the Notes System

## What's Good ✓

The notes system has solid foundational infrastructure:

1. **Dual Storage System**: Notes are persisted both in the database (`notes` table) and as markdown files in `.oyawiki/notes/` with YAML frontmatter. [1](#0-0) [2](#0-1) 

2. **Regeneration Triggering**: Notes correctly trigger wiki regeneration even when source code hasn't changed. The `_has_new_notes()` method checks for notes created after a page's last generation timestamp. [3](#0-2) [4](#0-3) 

3. **API Completeness**: The backend has endpoints for creating, listing, getting, and deleting notes. [5](#0-4) 

4. **Prompt Integration Infrastructure**: The `get_file_prompt()` function supports a `notes` parameter and has helper functions to format notes as "Developer Corrections (Ground Truth)" in prompts. [6](#0-5) [7](#0-6) 

5. **Multi-Scope Support**: Notes support different scopes (file, directory, workflow, general) for flexible targeting. [8](#0-7) 

## What's Bad ✗

1. **No Uniqueness Constraint**: Multiple notes can be created for the same target with no database constraint preventing duplicates. The TODO indicates this is recognized: "we should have a single note per file, directory, and it can be edited." [9](#0-8) [10](#0-9) 

2. **No Edit Functionality**: The `NoteEditor` component only handles creation, not editing existing notes. There's no `updateNote()` API function either. [11](#0-10) [12](#0-11) 

3. **No Orphan Detection**: There's no validation to check if a note's target still exists when files/directories are deleted. Notes can reference non-existent entities indefinitely. [13](#0-12) 

4. **No Target Validation on Creation**: When creating a note, there's no check to verify that the target path actually exists in the repository. [14](#0-13) 

## What's Missing (Critical Issue) ⚠️

**Notes are NOT actually being integrated into generation prompts!** While the infrastructure exists, the actual implementation is incomplete:

- The `FileGenerator.generate()` method doesn't accept a `notes` parameter and doesn't retrieve notes: [15](#0-14) 

- The orchestrator never passes notes to the generator: [16](#0-15) 

- Similarly, `DirectoryGenerator.generate()` has no notes parameter: [17](#0-16) 

- And the orchestrator doesn't pass notes to directory generation either: [18](#0-17) 

**This means notes trigger regeneration but their content is completely ignored during generation.** The `get_notes_for_target()` function exists but is never called: [19](#0-18) 

## Additional Missing Features

5. **No UI for Viewing Notes**: There's no component to display existing notes, only a creation interface. [20](#0-19) 

6. **No Notes Management Interface**: Users can't see what notes exist, edit them, or manage them beyond individual deletion via API.

7. **Incomplete Scope Coverage**: Only file-level notes have the infrastructure to be added to prompts; directory and workflow notes lack similar integration paths.

## Notes

The notes system has excellent architectural design but **critical implementation gaps**. Most importantly, notes content is not being incorporated into wiki generation despite the presence of triggering logic and formatting functions. This means user corrections are stored and trigger regeneration, but the LLM never sees them, defeating the entire purpose of the correction system. To fix this, the generators need to retrieve notes via `get_notes_for_target()` and pass them to their respective prompt functions.

### Citations

**File:** backend/src/oya/db/migrations.py (L48-63)
```python
-- Notes registry (human corrections)
-- Tracks all correction notes with their scope and targeting
CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filepath TEXT NOT NULL UNIQUE,  -- Path relative to .oyawiki/notes/
    scope TEXT NOT NULL,  -- 'file', 'directory', 'workflow', 'general'
    target TEXT,  -- Target path or identifier
    content TEXT,  -- Note content (for search and display)
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    author TEXT,
    git_branch TEXT,
    git_commit TEXT,
    git_dirty INTEGER DEFAULT 0,  -- Boolean: was repo dirty when note was created
    oya_version TEXT,
    metadata TEXT  -- JSON for additional data
);
```

**File:** backend/src/oya/notes/service.py (L36-43)
```python
    def _generate_filename(self, scope: NoteScope, target: str) -> str:
        """Generate filename for a new note.

        Format: {ISO-timestamp}-{scope}-{slug}.md
        """
        timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H-%M-%S")
        slug = _slugify(target) if target else "general"
        return f"{timestamp}-{scope.value}-{slug}.md"
```

**File:** backend/src/oya/notes/service.py (L45-72)
```python
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
        frontmatter_lines.extend(
            [
                f"created_at: {created_at.isoformat()}",
                "---",
            ]
        )

        full_content = "\n".join(frontmatter_lines) + "\n" + content

        note_file = self._notes_path / filepath
        note_file.write_text(full_content)
```

**File:** backend/src/oya/notes/service.py (L91-141)
```python
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
        if note_id is None:
            raise RuntimeError("Failed to get note ID after insert")

        return Note(
            id=note_id,
            filepath=filepath,
            scope=note_data.scope,
            target=note_data.target,
            content=note_data.content,
            author=note_data.author,
            created_at=created_at,
        )
```

**File:** backend/src/oya/generation/orchestrator.py (L324-348)
```python
    def _has_new_notes(self, target: str, generated_at: str | None) -> bool:
        """Check if there are notes created after the page was generated.

        Args:
            target: Target path to check for notes.
            generated_at: Timestamp when the page was last generated.

        Returns:
            True if there are new notes, False otherwise.
        """
        if not generated_at or not hasattr(self.db, "execute"):
            return False

        try:
            cursor = self.db.execute(
                """
                SELECT COUNT(*) FROM notes
                WHERE target = ? AND created_at > ?
                """,
                (target, generated_at),
            )
            row = cursor.fetchone()
            return row[0] > 0 if row else False
        except Exception:
            return False
```

**File:** backend/src/oya/generation/orchestrator.py (L400-404)
```python
        # Check if there are new notes
        if self._has_new_notes(file_path, existing.get("generated_at")):
            return True, content_hash

        return False, content_hash
```

**File:** backend/src/oya/generation/orchestrator.py (L1201-1209)
```python
            page, directory_summary = await self.directory_generator.generate(
                directory_path=dir_path,
                file_list=direct_files,
                symbols=dir_symbols,
                architecture_context="",
                file_summaries=dir_file_summaries,
                child_summaries=child_summaries,
                project_name=project_name,
            )
```

**File:** backend/src/oya/generation/orchestrator.py (L1403-1414)
```python
            page, file_summary = await self.file_generator.generate(
                file_path=file_path,
                content=content,
                symbols=file_symbols,
                imports=imports,
                architecture_summary="",
                parsed_symbols=file_parsed_symbols,
                file_imports=all_file_imports,
            )
            # Add source hash to the page for storage
            page.source_hash = content_hash
            return page, file_summary
```

**File:** backend/src/oya/api/routers/notes.py (L24-71)
```python
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
```

**File:** backend/src/oya/generation/prompts.py (L1178-1213)
```python
def get_file_prompt(
    file_path: str,
    content: str,
    symbols: list[dict[str, Any]],
    imports: list[str],
    architecture_summary: str,
    language: str = "",
    notes: list[dict[str, Any]] | None = None,
) -> str:
    """Generate a prompt for creating a file documentation page.

    Args:
        file_path: Path to the file.
        content: Content of the file.
        symbols: List of symbol dictionaries defined in the file.
        imports: List of import statements.
        architecture_summary: Summary of how this file fits in the architecture.
        language: Programming language for syntax highlighting.
        notes: Optional list of correction notes affecting this file.

    Returns:
        The rendered prompt string.
    """
    prompt = FILE_TEMPLATE.render(
        file_path=file_path,
        content=content,
        symbols=_format_symbols(symbols),
        imports=_format_imports(imports),
        architecture_summary=architecture_summary or "No architecture context provided.",
        language=language,
    )

    if notes:
        prompt = _add_notes_to_prompt(prompt, notes)

    return prompt
```

**File:** backend/src/oya/generation/prompts.py (L1216-1270)
```python
def _format_notes(notes: list[dict[str, Any]]) -> str:
    """Format notes for inclusion in a prompt.

    Args:
        notes: List of note dictionaries with content, author, created_at.

    Returns:
        Formatted string representation of notes.
    """
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
        created_at = note.get("created_at", "")

        lines.append(f"### Correction {i}")
        if author:
            lines.append(f"*From: {author}*")
        if created_at:
            lines.append(f"*Date: {created_at}*")
        lines.append("")
        lines.append(content)
        lines.append("")

    return "\n".join(lines)


def _add_notes_to_prompt(prompt: str, notes: list[dict[str, Any]]) -> str:
    """Add notes section to a prompt.

    Args:
        prompt: Original prompt.
        notes: List of correction notes.

    Returns:
        Prompt with notes section added.
    """
    notes_section = _format_notes(notes)
    if notes_section:
        # Insert notes before the "---" separator
        if "---" in prompt:
            parts = prompt.split("---", 1)
            return parts[0] + notes_section + "\n---" + parts[1]
        else:
            return prompt + "\n\n" + notes_section

    return prompt
```

**File:** backend/src/oya/generation/prompts.py (L1273-1310)
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
    # Query notes by scope and target
    sql = """
        SELECT content, author, created_at
        FROM notes
        WHERE (scope = ? AND target = ?)
           OR scope = 'general'
        ORDER BY created_at DESC
    """

    try:
        cursor = db.execute(sql, (scope, target))
        notes = []
        for row in cursor.fetchall():
            notes.append(
                {
                    "content": row["content"],
                    "author": row["author"],
                    "created_at": row["created_at"],
                }
            )
        return notes
    except Exception:
        return []
```

**File:** TODO.md (L64-65)
```markdown
    - Notes: we should have a single note per file, directory, and it can be
      edited.
```

**File:** frontend/src/components/NoteEditor.tsx (L1-10)
```typescript
import { useState, useEffect } from 'react'
import { createNote } from '../api/client'
import { useNoteEditorStore } from '../stores'
import type { NoteScope, Note } from '../types'

interface NoteEditorProps {
  isOpen: boolean
  onClose: () => void
  onNoteCreated?: (note: Note) => void
  defaultScope?: NoteScope
```

**File:** frontend/src/components/NoteEditor.tsx (L28-59)
```typescript
  // Reset state when editor opens
  useEffect(() => {
    if (isOpen) {
      setScope(defaultScope)
      setTarget(defaultTarget)
      setContent('')
      setError(null)
    }
  }, [isOpen, defaultScope, defaultTarget])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!content.trim()) return

    setIsSubmitting(true)
    setError(null)

    try {
      const note = await createNote({
        scope,
        target: scope === 'general' ? '' : target,
        content: content.trim(),
      })
      onNoteCreated?.(note)
      onClose()
      setContent('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save note')
    } finally {
      setIsSubmitting(false)
    }
  }
```

**File:** frontend/src/api/client.ts (L252-271)
```typescript
// Notes endpoints
export async function createNote(note: NoteCreate): Promise<Note> {
  return fetchJson<Note>('/api/notes', {
    method: 'POST',
    body: JSON.stringify(note),
  })
}

export async function listNotes(target?: string): Promise<Note[]> {
  const params = target ? `?target=${encodeURIComponent(target)}` : ''
  return fetchJson<Note[]>(`/api/notes${params}`)
}

export async function getNote(noteId: number): Promise<Note> {
  return fetchJson<Note>(`/api/notes/${noteId}`)
}

export async function deleteNote(noteId: number): Promise<void> {
  await fetch(`${API_BASE}/api/notes/${noteId}`, { method: 'DELETE' })
}
```

**File:** backend/src/oya/generation/file.py (L59-92)
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
    ) -> tuple[GeneratedPage, FileSummary]:
        """Generate documentation for a file.

        Args:
            file_path: Path to the file being documented.
            content: Content of the file.
            symbols: List of symbol dictionaries defined in the file.
            imports: List of import statements.
            architecture_summary: Summary of how this file fits in the architecture.
            parsed_symbols: Optional list of ParsedSymbol objects for class diagrams.
            file_imports: Optional dict of all file imports for dependency diagrams.

        Returns:
            Tuple of (GeneratedPage with file documentation, FileSummary extracted from output).
        """
        language = self._detect_language(file_path)

        prompt = get_file_prompt(
            file_path=file_path,
            content=content,
            symbols=symbols,
            imports=imports,
            architecture_summary=architecture_summary,
            language=language,
        )
```

**File:** backend/src/oya/generation/directory.py (L28-64)
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
    ) -> tuple[GeneratedPage, DirectorySummary]:
        """Generate directory documentation and extract summary.

        Args:
            directory_path: Path to the directory (empty string for root).
            file_list: List of files in the directory.
            symbols: List of symbol dictionaries defined in the directory.
            architecture_context: Summary of how this directory fits in the architecture.
            file_summaries: Optional list of FileSummary objects for files in the directory.
            child_summaries: Optional list of DirectorySummary objects for child directories.
            project_name: Optional project name for breadcrumb (defaults to repo name).

        Returns:
            A tuple of (GeneratedPage, DirectorySummary).
        """
        repo_name = self.repo.path.name
        proj_name = project_name or repo_name

        prompt = get_directory_prompt(
            repo_name=repo_name,
            directory_path=directory_path,
            file_list=file_list,
            symbols=symbols,
            architecture_context=architecture_context,
            file_summaries=file_summaries or [],
            subdirectory_summaries=child_summaries or [],
            project_name=proj_name,
        )
```

