# Full Regeneration Option Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add an incremental/full toggle to the generation modal so users can force a complete wiki rebuild.

**Architecture:** A radio group in IndexingPreviewModal selects the mode. The mode flows through the store and API client to a new `mode` body parameter on `POST /api/repos/init`. On the backend, `mode=full` deletes the production `.oyawiki` directory before the existing pipeline runs, forcing a clean rebuild. `.oyaignore` lives outside `.oyawiki` (at `meta/.oyaignore`) so it's unaffected.

**Tech Stack:** React/TypeScript (frontend), FastAPI/Pydantic (backend), Zustand (state management)

---

### Task 1: Backend — Accept `mode` parameter on `/init` endpoint

**Files:**
- Modify: `backend/src/oya/api/schemas.py`
- Modify: `backend/src/oya/api/routers/repos.py`

**Step 1: Add `InitRepoRequest` schema**

In `backend/src/oya/api/schemas.py`, add after the `OyaignoreUpdateResponse` class:

```python
class InitRepoRequest(BaseModel):
    mode: str = "incremental"  # "incremental" or "full"
```

**Step 2: Update `init_repo` endpoint to accept request body**

In `backend/src/oya/api/routers/repos.py`, modify the `init_repo` function signature to accept the new body model. Add `Body` import and the request parameter:

```python
from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException, Body
```

Change the function signature:
```python
@router.post("/init", response_model=JobCreated, status_code=202)
async def init_repo(
    background_tasks: BackgroundTasks,
    mode: str = Body("incremental", embed=True),
    repo: GitRepo = Depends(get_repo),
    db: Database = Depends(get_db),
    paths: RepoPaths = Depends(get_active_repo_paths),
    settings: Settings = Depends(get_settings),
) -> JobCreated:
```

Note: Use `Body(..., embed=True)` so the request body is `{"mode": "incremental"}`. This avoids needing a separate Pydantic model for a single field.

Pass mode to `_run_generation`:
```python
background_tasks.add_task(_run_generation, job_id, repo, db, paths, settings, repo_id, mode)
```

**Step 3: Update `_run_generation` to accept and handle `mode`**

Add `mode` parameter to `_run_generation`:
```python
async def _run_generation(
    job_id: str,
    repo: GitRepo,
    db: Database,
    paths: RepoPaths,
    settings: Settings,
    repo_id: int,
    mode: str = "incremental",
) -> None:
```

Add `shutil` import at top of file (already imported? check — no, `shutil` is imported in `staging.py` but not `repos.py`):
```python
import shutil
```

Insert this block right after the sync phase succeeds and before `prepare_staging_directory()` — specifically after the `"UPDATE generations SET current_phase = '0:starting'"` block (around line 463), before line 466 (`prepare_staging_directory`):

```python
        # Full regeneration: wipe production directory to force clean rebuild
        # .oyaignore lives at meta/.oyaignore (outside .oyawiki), so it's unaffected
        if mode == "full" and production_path.exists():
            shutil.rmtree(production_path)
            logger.info("Full regeneration: wiped production directory %s", production_path)
```

**Step 4: Run backend tests**

Run: `cd /Users/poecurt/projects/oya/backend && python -m pytest tests/ -x -q`
Expected: All existing tests pass (no behavior change for default `mode="incremental"`)

**Step 5: Commit**

```
feat(backend): accept generation mode parameter on /init endpoint

Support "incremental" (default) and "full" mode. Full mode wipes
the production .oyawiki directory before staging, forcing a complete
rebuild.
```

---

### Task 2: Frontend — Add `mode` parameter through API client and store

**Files:**
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/stores/generationStore.ts`

**Step 1: Update `initRepo` in API client**

In `frontend/src/api/client.ts`, change `initRepo` (line 76-78):

```typescript
export async function initRepo(mode: 'incremental' | 'full' = 'incremental'): Promise<JobCreated> {
  return fetchJson<JobCreated>('/api/repos/init', {
    method: 'POST',
    body: JSON.stringify({ mode }),
  })
}
```

**Step 2: Update `startGeneration` in generation store**

In `frontend/src/stores/generationStore.ts`:

Update the `GenerationActions` interface:
```typescript
interface GenerationActions {
  startGeneration: (mode?: 'incremental' | 'full') => Promise<string | null>
  // ... rest unchanged
}
```

Update the implementation:
```typescript
  startGeneration: async (mode: 'incremental' | 'full' = 'incremental') => {
    // Guard against concurrent calls
    const state = get()
    const jobIsActive =
      state.currentJob?.status === 'running' || state.currentJob?.status === 'pending'
    if (state.isLoading || jobIsActive) {
      return null
    }

    set({ isLoading: true, generationStatus: null, error: null })
    try {
      const result = await api.initRepo(mode)
      const job = await api.getJob(result.job_id)
      set({ currentJob: job })
      return result.job_id
    } catch {
      set({ error: 'Failed to start generation' })
      return null
    } finally {
      set({ isLoading: false })
    }
  },
```

**Step 3: Run frontend build check**

Run: `cd /Users/poecurt/projects/oya/frontend && npm run build`
Expected: No TypeScript errors. The TopBar currently calls `startGeneration()` with no args, which defaults to `"incremental"`.

**Step 4: Commit**

```
feat(frontend): thread generation mode through API client and store

initRepo() and startGeneration() now accept an optional mode parameter
("incremental" or "full"), defaulting to "incremental".
```

---

### Task 3: Frontend — Add mode toggle to IndexingPreviewModal

**Files:**
- Modify: `frontend/src/components/IndexingPreviewModal.tsx`
- Modify: `frontend/src/components/TopBar.tsx`

**Step 1: Update `IndexingPreviewModal` props and add mode state**

Change the interface:
```typescript
interface IndexingPreviewModalProps {
  isOpen: boolean
  onClose: () => void
  onGenerate: (mode: 'incremental' | 'full') => void
}
```

Add state inside the component (after the `isSaving` state, around line 40):
```typescript
const [generationMode, setGenerationMode] = useState<'incremental' | 'full'>('incremental')
```

Reset it when modal closes (in the `useEffect` cleanup, add to the reset block around line 53):
```typescript
setGenerationMode('incremental')
```

**Step 2: Update `handleConfirmGenerate` to pass mode**

Change `onGenerate()` to `onGenerate(generationMode)` in `handleConfirmGenerate` (line 294):
```typescript
  const handleConfirmGenerate = async () => {
    setIsSaving(true)
    try {
      if (hasChanges) {
        await api.updateOyaignore({
          directories: Array.from(pendingExclusions.directories),
          files: Array.from(pendingExclusions.files),
          removals: Array.from(pendingInclusions),
        })
      }
      onGenerate(generationMode)
      onClose()
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to save changes'
      setError(message)
    } finally {
      setShowGenerateConfirm(false)
      setIsSaving(false)
    }
  }
```

**Step 3: Add radio group UI at top of modal content**

In the modal content area, after `{indexableItems ? (` and `<div className="space-y-6">` (line 387-388), add the radio group as the first child:

```tsx
              {/* Generation mode selector */}
              <div className="flex items-center space-x-6">
                <label className="flex items-center space-x-2 cursor-pointer">
                  <input
                    type="radio"
                    name="generationMode"
                    value="incremental"
                    checked={generationMode === 'incremental'}
                    onChange={() => setGenerationMode('incremental')}
                    className="h-4 w-4 text-indigo-600 border-gray-300 focus:ring-indigo-500"
                  />
                  <span className="text-sm text-gray-700 dark:text-gray-300">
                    Incremental
                  </span>
                  <span className="text-xs text-gray-500 dark:text-gray-400">
                    Only regenerate changed files
                  </span>
                </label>
                <label className="flex items-center space-x-2 cursor-pointer">
                  <input
                    type="radio"
                    name="generationMode"
                    value="full"
                    checked={generationMode === 'full'}
                    onChange={() => setGenerationMode('full')}
                    className="h-4 w-4 text-indigo-600 border-gray-300 focus:ring-indigo-500"
                  />
                  <span className="text-sm text-gray-700 dark:text-gray-300">
                    Full
                  </span>
                  <span className="text-xs text-gray-500 dark:text-gray-400">
                    Wipe all data and regenerate from scratch
                  </span>
                </label>
              </div>
```

**Step 4: Conditionally show file tree or warning banner**

When `generationMode === 'full'`, hide the file tree and show a warning instead. Wrap the existing file tree sections (search input through excluded-by-rule section) in a conditional:

After the radio group, add:

```tsx
              {generationMode === 'full' ? (
                <div className="rounded-md bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700 p-4">
                  <div className="flex">
                    <svg className="h-5 w-5 text-amber-400" viewBox="0 0 20 20" fill="currentColor">
                      <path fillRule="evenodd" d="M8.485 2.495c.673-1.167 2.357-1.167 3.03 0l6.28 10.875c.673 1.167-.168 2.625-1.516 2.625H3.72c-1.347 0-2.189-1.458-1.515-2.625L8.485 2.495zM10 6a.75.75 0 01.75.75v3.5a.75.75 0 01-1.5 0v-3.5A.75.75 0 0110 6zm0 9a1 1 0 100-2 1 1 0 000 2z" clipRule="evenodd" />
                    </svg>
                    <div className="ml-3">
                      <h3 className="text-sm font-medium text-amber-800 dark:text-amber-200">
                        Full Regeneration
                      </h3>
                      <p className="mt-1 text-sm text-amber-700 dark:text-amber-300">
                        This will delete all existing wiki data (pages, database, vector store, notes)
                        except .oyaignore. The entire wiki will be regenerated.
                      </p>
                    </div>
                  </div>
                </div>
              ) : (
                <>
                  {/* Search input */}
                  ...existing search, counts, file tree sections...
                </>
              )}
```

Specifically, wrap everything from the `{/* Search input */}` div through the end of `{/* Excluded by rule section */}` in the `<>...</>` fragment inside the `: (` branch.

**Step 5: Update confirmation dialog text for full mode**

Update the ConfirmationDialog content to reflect the mode:

```tsx
        <ConfirmationDialog
          isOpen={showGenerateConfirm}
          title={generationMode === 'full' ? 'Full Regeneration' : 'Generate Wiki'}
          confirmLabel={isSaving ? 'Generating...' : 'Generate'}
          onConfirm={handleConfirmGenerate}
          onCancel={handleCancelGenerateConfirm}
        >
          {generationMode === 'full' ? (
            <p className="text-amber-700 dark:text-amber-300">
              All existing wiki data will be deleted and regenerated from scratch.
            </p>
          ) : (
            <>
              <p className="mb-2">{effectiveCounts.files} files will be indexed</p>
              {hasChanges && (
                <p className="text-gray-500 dark:text-gray-400">.oyaignore will be updated</p>
              )}
            </>
          )}
        </ConfirmationDialog>
```

**Step 6: Update TopBar to pass mode**

In `frontend/src/components/TopBar.tsx`, change the `onGenerate` prop (line 228):

```tsx
      <IndexingPreviewModal
        isOpen={isPreviewModalOpen}
        onClose={() => setIsPreviewModalOpen(false)}
        onGenerate={(mode) => startGeneration(mode)}
      />
```

**Step 7: Run frontend build check**

Run: `cd /Users/poecurt/projects/oya/frontend && npm run build`
Expected: No TypeScript errors.

**Step 8: Commit**

```
feat(frontend): add incremental/full toggle to generation modal

Radio group at top of IndexingPreviewModal lets users choose between
incremental (default) and full regeneration. Full mode hides the file
tree and shows a warning banner about data deletion.
```

---

### Task 4: Update frontend tests

**Files:**
- Modify: `frontend/src/components/IndexingPreviewModal.test.tsx`

**Step 1: Update `onGenerate` mock in all tests**

The `onGenerate` prop now receives `(mode)`. Update the mock setup. In the existing tests, `onGenerate` is a `vi.fn()` — the mock doesn't need changing, but assertions about calls should verify the mode parameter.

Find all places where `onGenerate` is asserted on and update to check for the mode argument. For example, if there's `expect(onGenerate).toHaveBeenCalled()`, it should still pass. If there's `expect(onGenerate).toHaveBeenCalledWith()`, update to `expect(onGenerate).toHaveBeenCalledWith('incremental')`.

**Step 2: Add test for full regeneration mode**

Add a new test:

```typescript
it('should pass full mode when full regeneration is selected', async () => {
  const onGenerate = vi.fn()
  render(<IndexingPreviewModal isOpen={true} onClose={vi.fn()} onGenerate={onGenerate} />)

  await waitFor(() => {
    expect(screen.getByText('Directories')).toBeInTheDocument()
  })

  // Select full regeneration
  const fullRadio = screen.getByLabelText(/Full/i) // or getByRole('radio', { name: /full/i })
  fireEvent.click(fullRadio)

  // File tree should be hidden, warning should show
  expect(screen.queryByText('Directories')).not.toBeInTheDocument()
  expect(screen.getByText(/delete all existing wiki data/i)).toBeInTheDocument()

  // Generate
  fireEvent.click(screen.getByRole('button', { name: /generate wiki/i }))
  // Confirm
  await waitFor(() => {
    expect(screen.getByText(/Full Regeneration/i)).toBeInTheDocument()
  })
  fireEvent.click(screen.getByRole('button', { name: /generate/i }))

  await waitFor(() => {
    expect(onGenerate).toHaveBeenCalledWith('full')
  })
})
```

**Step 3: Add test for incremental mode (default)**

```typescript
it('should pass incremental mode by default', async () => {
  const onGenerate = vi.fn()
  render(<IndexingPreviewModal isOpen={true} onClose={vi.fn()} onGenerate={onGenerate} />)

  await waitFor(() => {
    expect(screen.getByText('Directories')).toBeInTheDocument()
  })

  // Generate without changing mode
  fireEvent.click(screen.getByRole('button', { name: /generate wiki/i }))
  await waitFor(() => {
    expect(screen.getByText('Generate Wiki')).toBeInTheDocument() // confirm dialog title
  })
  fireEvent.click(screen.getByRole('button', { name: /generate/i }))

  await waitFor(() => {
    expect(onGenerate).toHaveBeenCalledWith('incremental')
  })
})
```

**Step 4: Add test that mode resets on close**

```typescript
it('should reset mode to incremental when modal closes and reopens', async () => {
  const { rerender } = render(
    <IndexingPreviewModal isOpen={true} onClose={vi.fn()} onGenerate={vi.fn()} />
  )

  await waitFor(() => {
    expect(screen.getByText('Directories')).toBeInTheDocument()
  })

  // Select full mode
  fireEvent.click(screen.getByDisplayValue('full'))
  expect(screen.getByText(/delete all existing wiki data/i)).toBeInTheDocument()

  // Close and reopen
  rerender(<IndexingPreviewModal isOpen={false} onClose={vi.fn()} onGenerate={vi.fn()} />)
  rerender(<IndexingPreviewModal isOpen={true} onClose={vi.fn()} onGenerate={vi.fn()} />)

  await waitFor(() => {
    expect(screen.getByText('Directories')).toBeInTheDocument()
  })

  // Should be back to incremental (file tree visible)
  expect(screen.queryByText(/delete all existing wiki data/i)).not.toBeInTheDocument()
})
```

**Step 5: Run frontend tests**

Run: `cd /Users/poecurt/projects/oya/frontend && npm run test`
Expected: All tests pass including new ones.

**Step 6: Commit**

```
test(frontend): add tests for generation mode toggle

Tests verify full mode hides file tree and shows warning, incremental
mode is the default, and mode resets when modal closes.
```

---

### Task 5: Final verification

**Step 1: Run full backend test suite**

Run: `cd /Users/poecurt/projects/oya/backend && python -m pytest tests/ -x -q`
Expected: All pass.

**Step 2: Run full frontend build and tests**

Run: `cd /Users/poecurt/projects/oya/frontend && npm run build && npm run test`
Expected: Build succeeds, all tests pass.

**Step 3: Commit any remaining fixes if needed**
