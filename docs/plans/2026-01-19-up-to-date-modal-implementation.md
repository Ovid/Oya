# Up-to-Date Modal Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Show a modal when regeneration completes with no changes, fixing the "flash and nothing happens" UX issue.

**Architecture:** Backend tracks whether files/directories were regenerated via new `changes_made` column. Frontend detects instant completion with no changes and shows an "Up-to-date" modal instead of flashing.

**Tech Stack:** Python/FastAPI backend, React/TypeScript frontend, SQLite database

---

## Task 1: Add changes_made Column to Database Schema

**Files:**
- Modify: `backend/src/oya/db/migrations.py:6` (version), `:17-30` (schema), `:134-142` (migrations)

**Step 1: Update schema version**

In `migrations.py`, change line 6:

```python
SCHEMA_VERSION = 5
```

**Step 2: Add column to SCHEMA_SQL**

In `migrations.py`, modify the generations table definition (lines 17-30). Add after line 29 (`metadata TEXT`):

```python
    metadata TEXT,  -- JSON for additional data
    changes_made INTEGER  -- Boolean: whether any content was regenerated
```

**Step 3: Add migration for existing databases**

In `migrations.py`, add after the version 3 migration block (after line 142):

```python
        # Version 5 migration: Add changes_made column to generations table
        if current_version >= 1 and current_version < 5:
            try:
                db.execute("ALTER TABLE generations ADD COLUMN changes_made INTEGER")
                db.commit()
            except Exception:
                # Column may already exist if schema was recreated
                pass
```

**Step 4: Run backend tests to verify schema change**

Run: `cd /Users/poecurt/projects/oya/backend && source .venv/bin/activate && pytest tests/test_db_migrations.py -v`

Expected: PASS (tests should still pass with new schema)

**Step 5: Commit**

```bash
git add backend/src/oya/db/migrations.py
git commit -m "feat(db): add changes_made column to generations table"
```

---

## Task 2: Add Regeneration Tracking to GenerationResult

**Files:**
- Modify: `backend/src/oya/generation/orchestrator.py:87-102` (GenerationResult), `:640-645` (return statement)

**Step 1: Add fields to GenerationResult dataclass**

In `orchestrator.py`, modify the GenerationResult class (lines 99-102). Add new fields:

```python
    job_id: str
    synthesis_map: SynthesisMap | None = None
    analysis_symbols: list[dict[str, Any]] | None = None
    file_imports: dict[str, list[str]] | None = None
    files_regenerated: bool = False
    directories_regenerated: bool = False
```

**Step 2: Update docstring attributes**

Update the Attributes docstring (lines 92-96):

```python
    Attributes:
        job_id: Unique identifier for this generation run.
        synthesis_map: The synthesis map with layers, entry points, etc.
        analysis_symbols: List of parsed symbol dicts from code analysis.
        file_imports: Mapping of file paths to their imports.
        files_regenerated: Whether any files were regenerated.
        directories_regenerated: Whether any directories were regenerated.
```

**Step 3: Update return statement in run()**

In `orchestrator.py`, modify the return statement (lines 640-645):

```python
        return GenerationResult(
            job_id=job_id,
            synthesis_map=synthesis_map,
            analysis_symbols=analysis_symbols,
            file_imports=analysis.get("file_imports"),
            files_regenerated=files_regenerated,
            directories_regenerated=directories_regenerated,
        )
```

**Step 4: Run backend tests**

Run: `cd /Users/poecurt/projects/oya/backend && source .venv/bin/activate && pytest tests/test_orchestrator.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/oya/generation/orchestrator.py
git commit -m "feat(generation): expose files/directories regenerated in GenerationResult"
```

---

## Task 3: Store changes_made After Generation

**Files:**
- Modify: `backend/src/oya/api/routers/repos.py:507-514`

**Step 1: Compute and store changes_made**

In `repos.py`, replace lines 507-514:

```python
        # Compute whether any changes were made
        changes_made = (
            generation_result.files_regenerated or generation_result.directories_regenerated
        )

        # Update status to completed BEFORE promoting staging
        # (promotion deletes .oyawiki which contains the database file)
        db.execute(
            """
            UPDATE generations
            SET status = 'completed', completed_at = datetime('now'), changes_made = ?
            WHERE id = ?
            """,
            (changes_made, job_id),
        )
        db.commit()
```

**Step 2: Run backend tests**

Run: `cd /Users/poecurt/projects/oya/backend && source .venv/bin/activate && pytest tests/test_repos_api.py -v`

Expected: PASS

**Step 3: Commit**

```bash
git add backend/src/oya/api/routers/repos.py
git commit -m "feat(api): store changes_made when generation completes"
```

---

## Task 4: Add changes_made to JobStatus API

**Files:**
- Modify: `backend/src/oya/api/routers/jobs.py:16-28` (model), `:44-67` (list_jobs), `:79-102` (get_job)

**Step 1: Add field to JobStatus model**

In `jobs.py`, add to JobStatus class after line 27:

```python
class JobStatus(BaseModel):
    """Job status response."""

    job_id: str
    type: str
    status: str
    started_at: datetime | None = None
    completed_at: datetime | None = None
    cancelled_at: datetime | None = None
    current_phase: str | None = None
    total_phases: int | None = None
    error_message: str | None = None
    changes_made: bool | None = None
```

**Step 2: Update list_jobs query and response**

In `jobs.py`, update the SQL query in list_jobs (lines 44-52):

```python
    cursor = db.execute(
        """
        SELECT id, type, status, started_at, completed_at,
               current_phase, total_phases, error_message, changes_made
        FROM generations
        ORDER BY started_at DESC
        LIMIT ?
        """,
        (limit,),
    )
```

Update the JobStatus construction (lines 57-67):

```python
        jobs.append(
            JobStatus(
                job_id=row["id"],
                type=row["type"],
                status=row["status"],
                started_at=_parse_datetime(row["started_at"]),
                completed_at=_parse_datetime(row["completed_at"]),
                current_phase=row["current_phase"],
                total_phases=row["total_phases"],
                error_message=row["error_message"],
                changes_made=bool(row["changes_made"]) if row["changes_made"] is not None else None,
            )
        )
```

**Step 3: Update get_job query and response**

In `jobs.py`, update the SQL query in get_job (lines 79-87):

```python
    cursor = db.execute(
        """
        SELECT id, type, status, started_at, completed_at,
               current_phase, total_phases, error_message, changes_made
        FROM generations
        WHERE id = ?
        """,
        (job_id,),
    )
```

Update the JobStatus construction (lines 93-102):

```python
    return JobStatus(
        job_id=row["id"],
        type=row["type"],
        status=row["status"],
        started_at=_parse_datetime(row["started_at"]),
        completed_at=_parse_datetime(row["completed_at"]),
        current_phase=row["current_phase"],
        total_phases=row["total_phases"],
        error_message=row["error_message"],
        changes_made=bool(row["changes_made"]) if row["changes_made"] is not None else None,
    )
```

**Step 4: Run backend tests**

Run: `cd /Users/poecurt/projects/oya/backend && source .venv/bin/activate && pytest tests/test_jobs_api.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/oya/api/routers/jobs.py
git commit -m "feat(api): include changes_made in job status responses"
```

---

## Task 5: Add changes_made to Frontend Types

**Files:**
- Modify: `frontend/src/types/index.ts:30-39`

**Step 1: Add field to JobStatus interface**

In `types/index.ts`, add after line 38 (`error_message`):

```typescript
export interface JobStatus {
  job_id: string
  type: string
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'
  started_at: string | null
  completed_at: string | null
  current_phase: string | null
  total_phases: number | null
  error_message: string | null
  changes_made?: boolean | null
}
```

**Step 2: Run frontend type check**

Run: `cd /Users/poecurt/projects/oya/.worktrees/up-to-date-modal/frontend && npm run build`

Expected: Build succeeds with no type errors

**Step 3: Commit**

```bash
git add frontend/src/types/index.ts
git commit -m "feat(types): add changes_made to JobStatus interface"
```

---

## Task 6: Create UpToDateModal Component

**Files:**
- Create: `frontend/src/components/UpToDateModal.tsx`
- Create: `frontend/src/components/UpToDateModal.test.tsx`

**Step 1: Write the test file**

Create `frontend/src/components/UpToDateModal.test.tsx`:

```typescript
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { UpToDateModal } from './UpToDateModal'

describe('UpToDateModal', () => {
  it('renders nothing when closed', () => {
    const { container } = render(<UpToDateModal isOpen={false} onClose={() => {}} />)
    expect(container.firstChild).toBeNull()
  })

  it('renders modal content when open', () => {
    render(<UpToDateModal isOpen={true} onClose={() => {}} />)
    expect(screen.getByText('Wiki is up-to-date')).toBeInTheDocument()
    expect(screen.getByText('No changes detected since last generation.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Got it' })).toBeInTheDocument()
  })

  it('calls onClose when button is clicked', () => {
    const onClose = vi.fn()
    render(<UpToDateModal isOpen={true} onClose={onClose} />)
    fireEvent.click(screen.getByRole('button', { name: 'Got it' }))
    expect(onClose).toHaveBeenCalledOnce()
  })

  it('calls onClose when backdrop is clicked', () => {
    const onClose = vi.fn()
    render(<UpToDateModal isOpen={true} onClose={onClose} />)
    // The backdrop is the first fixed div with bg-black/50
    const backdrop = document.querySelector('.bg-black\\/50')
    fireEvent.click(backdrop!)
    expect(onClose).toHaveBeenCalledOnce()
  })
})
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/poecurt/projects/oya/.worktrees/up-to-date-modal/frontend && npm test -- --run src/components/UpToDateModal.test.tsx`

Expected: FAIL with "Cannot find module './UpToDateModal'"

**Step 3: Create the component**

Create `frontend/src/components/UpToDateModal.tsx`:

```typescript
interface UpToDateModalProps {
  isOpen: boolean
  onClose: () => void
}

export function UpToDateModal({ isOpen, onClose }: UpToDateModalProps) {
  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="fixed inset-0 bg-black/50" onClick={onClose} />
      <div className="relative bg-white dark:bg-gray-800 rounded-lg shadow-xl p-6 max-w-xs mx-4 text-center">
        <div className="mx-auto w-12 h-12 bg-green-100 dark:bg-green-900 rounded-full flex items-center justify-center mb-4">
          <svg
            className="w-6 h-6 text-green-600 dark:text-green-400"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M5 13l4 4L19 7"
            />
          </svg>
        </div>
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
          Wiki is up-to-date
        </h3>
        <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
          No changes detected since last generation.
        </p>
        <button
          onClick={onClose}
          className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 rounded-md"
        >
          Got it
        </button>
      </div>
    </div>
  )
}
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/poecurt/projects/oya/.worktrees/up-to-date-modal/frontend && npm test -- --run src/components/UpToDateModal.test.tsx`

Expected: PASS (4 tests)

**Step 5: Commit**

```bash
git add frontend/src/components/UpToDateModal.tsx frontend/src/components/UpToDateModal.test.tsx
git commit -m "feat(ui): add UpToDateModal component"
```

---

## Task 7: Add State and Logic to AppContext

**Files:**
- Modify: `frontend/src/context/AppContext.tsx:20-31` (state), `:33-45` (actions), `:78-121` (reducer), `:163-181` (startGeneration), `:123-136` (context interface), `:287-300` (context value)

**Step 1: Add showUpToDateModal to AppState interface**

In `AppContext.tsx`, add to AppState interface (around line 30):

```typescript
interface AppState {
  repoStatus: RepoStatus | null
  wikiTree: WikiTree | null
  currentPage: WikiPage | null
  currentJob: JobStatus | null
  isLoading: boolean
  error: string | null
  noteEditor: NoteEditorState
  darkMode: boolean
  generationStatus: GenerationStatus | null
  askPanelOpen: boolean
  showUpToDateModal: boolean
}
```

**Step 2: Add action type**

In `AppContext.tsx`, add to Action type (around line 45):

```typescript
  | { type: 'SET_ASK_PANEL_OPEN'; payload: boolean }
  | { type: 'SET_UP_TO_DATE_MODAL'; payload: boolean }
```

**Step 3: Add initial state**

In `AppContext.tsx`, add to initialState (around line 76):

```typescript
  askPanelOpen: getInitialAskPanelOpen(),
  showUpToDateModal: false,
}
```

**Step 4: Add reducer case**

In `AppContext.tsx`, add to appReducer switch (around line 117):

```typescript
    case 'SET_ASK_PANEL_OPEN':
      return { ...state, askPanelOpen: action.payload }
    case 'SET_UP_TO_DATE_MODAL':
      return { ...state, showUpToDateModal: action.payload }
    default:
```

**Step 5: Modify startGeneration function**

In `AppContext.tsx`, replace startGeneration (lines 163-181):

```typescript
  const startGeneration = async (): Promise<string | null> => {
    try {
      dispatch({ type: 'SET_LOADING', payload: true })
      // Clear any previous interrupted status when starting a new generation
      dispatch({ type: 'SET_GENERATION_STATUS', payload: null })
      const result = await api.initRepo()

      // Start polling job status
      const job = await api.getJob(result.job_id)

      // Check if job completed instantly with no changes
      if (job.status === 'completed' && job.changes_made === false) {
        dispatch({ type: 'SET_UP_TO_DATE_MODAL', payload: true })
        return null
      }

      dispatch({ type: 'SET_CURRENT_JOB', payload: job })

      return result.job_id
    } catch {
      dispatch({ type: 'SET_ERROR', payload: 'Failed to start generation' })
      return null
    } finally {
      dispatch({ type: 'SET_LOADING', payload: false })
    }
  }
```

**Step 6: Add dismissUpToDateModal function**

In `AppContext.tsx`, add after dismissGenerationStatus (around line 285):

```typescript
  const dismissGenerationStatus = () => {
    dispatch({ type: 'SET_GENERATION_STATUS', payload: null })
  }

  const dismissUpToDateModal = () => {
    dispatch({ type: 'SET_UP_TO_DATE_MODAL', payload: false })
  }
```

**Step 7: Update context interface**

In `AppContext.tsx`, add to AppContextValue interface (around line 134):

```typescript
  dismissGenerationStatus: () => void
  setAskPanelOpen: (open: boolean) => void
  dismissUpToDateModal: () => void
}
```

**Step 8: Update context value**

In `AppContext.tsx`, add to contextValue (around line 299):

```typescript
    dismissGenerationStatus,
    setAskPanelOpen,
    dismissUpToDateModal,
  }
```

**Step 9: Run frontend tests**

Run: `cd /Users/poecurt/projects/oya/.worktrees/up-to-date-modal/frontend && npm test -- --run`

Expected: All tests PASS

**Step 10: Commit**

```bash
git add frontend/src/context/AppContext.tsx
git commit -m "feat(context): add up-to-date modal state and instant completion detection"
```

---

## Task 8: Render Modal in Layout

**Files:**
- Modify: `frontend/src/components/Layout.tsx:1-8` (imports), `:28` (useApp), `:135-143` (JSX)

**Step 1: Add import**

In `Layout.tsx`, add import after line 6:

```typescript
import { NoteEditor } from './NoteEditor'
import { UpToDateModal } from './UpToDateModal'
import { InterruptedGenerationBanner } from './InterruptedGenerationBanner'
```

**Step 2: Destructure dismissUpToDateModal from useApp**

In `Layout.tsx`, update line 28:

```typescript
  const { state, closeNoteEditor, refreshTree, setAskPanelOpen, dismissUpToDateModal } = useApp()
  const { noteEditor, askPanelOpen, showUpToDateModal } = state
```

**Step 3: Render UpToDateModal**

In `Layout.tsx`, add after NoteEditor (after line 142):

```typescript
      {/* Note Editor */}
      <NoteEditor
        isOpen={noteEditor.isOpen}
        onClose={closeNoteEditor}
        onNoteCreated={() => refreshTree()}
        defaultScope={noteEditor.defaultScope}
        defaultTarget={noteEditor.defaultTarget}
      />

      {/* Up-to-date Modal */}
      <UpToDateModal isOpen={showUpToDateModal} onClose={dismissUpToDateModal} />
    </div>
```

**Step 4: Run all frontend tests**

Run: `cd /Users/poecurt/projects/oya/.worktrees/up-to-date-modal/frontend && npm test -- --run`

Expected: All tests PASS

**Step 5: Build to verify no type errors**

Run: `cd /Users/poecurt/projects/oya/.worktrees/up-to-date-modal/frontend && npm run build`

Expected: Build succeeds

**Step 6: Commit**

```bash
git add frontend/src/components/Layout.tsx
git commit -m "feat(ui): render UpToDateModal in Layout"
```

---

## Task 9: Final Integration Test

**Step 1: Run all backend tests**

Run: `cd /Users/poecurt/projects/oya/backend && source .venv/bin/activate && pytest -v`

Expected: All tests PASS

**Step 2: Run all frontend tests**

Run: `cd /Users/poecurt/projects/oya/.worktrees/up-to-date-modal/frontend && npm test -- --run`

Expected: All tests PASS

**Step 3: Run frontend lint**

Run: `cd /Users/poecurt/projects/oya/.worktrees/up-to-date-modal/frontend && npm run lint`

Expected: No errors

**Step 4: Commit final state**

If any fixes were needed:

```bash
git add -A
git commit -m "fix: address test/lint issues"
```
