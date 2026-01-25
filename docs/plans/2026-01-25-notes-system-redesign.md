# Notes System Redesign

## Problem Statement

The notes system has solid infrastructure but a critical bug: notes trigger regeneration but their content is never passed to the LLM. The `get_notes_for_target()` function exists but is never called. Additionally, the system allows multiple notes per target with no edit functionality, making it confusing to use.

## Design Decisions

| Decision | Choice |
|----------|--------|
| Notes model | One editable note per target |
| Storage | File-primary with DB index |
| File organization | Flat by scope with slugified paths |
| Frontend UI | Inline on wiki pages |
| Migration | Fresh start (no existing data to preserve) |
| Generation integration | Orchestrator loads notes, passes to generators |

## Architecture

### Data Model

```
Note:
  - scope: 'file' | 'directory' | 'workflow' | 'general'
  - target: string (path or identifier, empty for general)
  - content: string (markdown)
  - updated_at: datetime
  - author: string (optional)
```

**Uniqueness:** `(scope, target)` is unique. There is exactly one `general` note (target = "").

### File Structure

```
.oyawiki/notes/
  files/
    src--main.py.md
    src--api--router.py.md
  directories/
    src--api.md
  workflows/
    authentication.md
  general.md
```

Path slugification: `/` becomes `--`, preserving readability while avoiding nested directories.

### Database Schema

```sql
CREATE TABLE notes (
    id INTEGER PRIMARY KEY,
    scope TEXT NOT NULL,
    target TEXT NOT NULL,
    filepath TEXT NOT NULL,
    content TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    author TEXT,
    UNIQUE(scope, target)
);
CREATE INDEX idx_notes_target ON notes(scope, target);
```

## Backend Implementation

### NotesService

Replace the current service with upsert semantics:

**Methods:**
- `get(scope, target) -> Note | None` - Get note for a target
- `upsert(scope, target, content, author?) -> Note` - Create or update note
- `delete(scope, target) -> bool` - Remove note
- `list(scope?) -> list[Note]` - List all notes, optionally filtered by scope
- `rebuild_index()` - Scan files, rebuild DB index

**Key behavior:** `upsert()` writes the markdown file first, then updates the DB. If a note exists, it overwrites.

### File Format

```markdown
---
scope: file
target: src/main.py
updated_at: 2024-01-15T10:30:00Z
author: alice
---

The `initialize()` function is deprecated. Document it as legacy
and note that `setup()` should be used instead.
```

### API Endpoints

```
GET    /api/notes/{scope}/{target}  -> Note | 404
PUT    /api/notes/{scope}/{target}  -> Note (upsert)
DELETE /api/notes/{scope}/{target}  -> 204
GET    /api/notes                   -> list[Note]
GET    /api/notes?scope=file        -> list[Note] (filtered)
```

The `target` in URLs is URL-encoded (e.g., `src%2Fmain.py`).

## Frontend Implementation

### Inline Note Display

On each wiki page (FilePage, DirectoryPage), add a collapsible note section at the top:

```
┌─────────────────────────────────────────────────┐
│  Developer Correction                      [v]  │
├─────────────────────────────────────────────────┤
│ The `initialize()` function is deprecated.      │
│ Document it as legacy and note that `setup()`   │
│ should be used instead.                         │
│                                                 │
│ Updated by alice - Jan 15, 2024   [Edit] [Delete]│
└─────────────────────────────────────────────────┘
```

If no note exists, show a subtle "Add Correction" button instead.

### NoteEditor Changes

Convert from create-only to edit mode:
- When opened for a target with existing note, pre-populate content
- "Save" button performs upsert (creates or updates)
- Remove scope selector when opened from a specific page (scope is known)

### API Client Updates

```typescript
// Replace createNote with upsert
async function saveNote(scope: NoteScope, target: string, content: string): Promise<Note>

// New: get single note
async function getNote(scope: NoteScope, target: string): Promise<Note | null>

// Change delete signature
async function deleteNote(scope: NoteScope, target: string): Promise<void>
```

### State Management

Add to wiki page components (not a separate store):
- Fetch note when page loads via `getNote(scope, target)`
- Local state for edit modal open/closed
- Refetch after save/delete

## Generation Integration

### Orchestrator Changes

In `_run_files()`, before calling the file generator:

```python
notes = get_notes_for_target(self.db, 'file', file_path)

page, file_summary = await self.file_generator.generate(
    file_path=file_path,
    content=content,
    # ... existing params ...
    notes=notes,  # NEW
)
```

Same pattern in `_run_directories()`:

```python
notes = get_notes_for_target(self.db, 'directory', dir_path)

page, directory_summary = await self.directory_generator.generate(
    directory_path=dir_path,
    # ... existing params ...
    notes=notes,  # NEW
)
```

### Generator Changes

**FileGenerator.generate():** Add `notes: list[dict] | None = None` parameter, pass to `get_file_prompt()`.

**DirectoryGenerator.generate():** Add `notes: list[dict] | None = None` parameter, pass to `get_directory_prompt()`.

### Prompt Changes

**get_directory_prompt():** Add `notes` parameter and call `_add_notes_to_prompt()` like `get_file_prompt()` already does.

## Implementation Plan

### Phase 1: Backend Core (Fixes the critical bug)
1. Drop old notes table, create new schema with uniqueness constraint
2. Rewrite `NotesService` with upsert semantics and file-primary storage
3. Update API endpoints to new REST pattern
4. Add `notes` parameter to `DirectoryGenerator.generate()` and `get_directory_prompt()`
5. Wire up orchestrator to load and pass notes to generators

### Phase 2: Frontend
6. Update API client functions to match new endpoints
7. Create `NoteDisplay` component for inline viewing
8. Update `NoteEditor` to support edit mode (pre-populate existing content)
9. Add note section to `FilePage` and `DirectoryPage` components

### Phase 3: Polish
10. Add `rebuild_index()` command for recovering from file/DB desync
11. Update tests for new behavior
12. Remove old migration code and unused schema

### Out of Scope (Future)
- Notes management page (list all notes)
- Workflow notes integration (needs workflow generation changes)
- Orphan detection (notes for deleted files)

## Files to Modify

### Backend
- `backend/src/oya/db/migrations.py` - New schema
- `backend/src/oya/notes/service.py` - Rewrite with upsert semantics
- `backend/src/oya/notes/schemas.py` - Simplify models
- `backend/src/oya/api/routers/notes.py` - New REST endpoints
- `backend/src/oya/generation/orchestrator.py` - Load and pass notes
- `backend/src/oya/generation/file.py` - Add notes parameter
- `backend/src/oya/generation/directory.py` - Add notes parameter
- `backend/src/oya/generation/prompts.py` - Add notes to directory prompt
- `backend/tests/test_notes_service.py` - Update tests
- `backend/tests/test_notes_api.py` - Update tests

### Frontend
- `frontend/src/api/client.ts` - New API functions
- `frontend/src/components/NoteEditor.tsx` - Edit mode support
- `frontend/src/components/NoteDisplay.tsx` - New component
- `frontend/src/components/pages/FilePage.tsx` - Add note section
- `frontend/src/components/pages/DirectoryPage.tsx` - Add note section
- `frontend/src/types/index.ts` - Update types if needed
