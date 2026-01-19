# Up-to-Date Modal Design

## Problem

When clicking "Regenerate" and nothing has changed, the page flashes briefly and nothing visible happens. Users have no feedback that regeneration completed successfully with no changes.

**Root cause:** Race condition - the job completes so quickly (no LLM calls needed) that by the time the frontend fetches job status, it's already `completed`. The GenerationProgress component only renders when `status === 'running'`, so users never see it.

## Solution

Show a modal dialog when regeneration completes with no actual changes: "Wiki is up-to-date".

## Backend Changes

### 1. Database Schema

Add column to `generations` table:

```sql
ALTER TABLE generations ADD COLUMN changes_made BOOLEAN DEFAULT TRUE;
```

**File:** `backend/src/oya/db/schema.sql`

### 2. Generation Result

Modify `GenerationResult` dataclass to expose regeneration info:

**File:** `backend/src/oya/generation/orchestrator.py`

```python
@dataclass
class GenerationResult:
    job_id: str
    synthesis_map: SynthesisMap
    analysis_symbols: list[dict]
    file_imports: dict[str, list[str]] | None
    files_regenerated: bool = False      # NEW
    directories_regenerated: bool = False # NEW
```

Update `run()` to populate these fields (values already computed internally).

### 3. Store Result

**File:** `backend/src/oya/api/routers/repos.py`

After `orchestrator.run()` completes, store `changes_made`:

```python
changes_made = generation_result.files_regenerated or generation_result.directories_regenerated

db.execute(
    """
    UPDATE generations
    SET status = 'completed', completed_at = datetime('now'), changes_made = ?
    WHERE id = ?
    """,
    (changes_made, job_id),
)
```

### 4. API Response

**File:** `backend/src/oya/api/routers/jobs.py`

Add field to `JobStatus` model and query:

```python
class JobStatus(BaseModel):
    job_id: str
    type: str
    status: str
    started_at: datetime | None = None
    completed_at: datetime | None = None
    cancelled_at: datetime | None = None
    current_phase: str | None = None
    total_phases: int | None = None
    error_message: str | None = None
    changes_made: bool | None = None  # NEW - None for old jobs
```

## Frontend Changes

### 1. Types

**File:** `frontend/src/types.ts`

```typescript
interface JobStatus {
  // ... existing fields ...
  changes_made?: boolean | null
}
```

### 2. New Component: UpToDateModal

**File:** `frontend/src/components/UpToDateModal.tsx`

```tsx
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
          <svg className="w-6 h-6 text-green-600 dark:text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
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

### 3. AppContext State

**File:** `frontend/src/context/AppContext.tsx`

Add to state:
```typescript
interface AppState {
  // ... existing fields ...
  showUpToDateModal: boolean
}
```

Add action:
```typescript
type Action =
  // ... existing actions ...
  | { type: 'SET_UP_TO_DATE_MODAL'; payload: boolean }
```

Add to reducer:
```typescript
case 'SET_UP_TO_DATE_MODAL':
  return { ...state, showUpToDateModal: action.payload }
```

Modify `startGeneration()`:
```typescript
const startGeneration = async (): Promise<string | null> => {
  try {
    dispatch({ type: 'SET_LOADING', payload: true })
    dispatch({ type: 'SET_GENERATION_STATUS', payload: null })
    const result = await api.initRepo()
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

Add dismiss function:
```typescript
const dismissUpToDateModal = () => {
  dispatch({ type: 'SET_UP_TO_DATE_MODAL', payload: false })
}
```

### 4. Render Modal

**File:** `frontend/src/components/Layout.tsx`

```tsx
import { UpToDateModal } from './UpToDateModal'

// In component:
const { state, dismissUpToDateModal } = useApp()

// In JSX:
<UpToDateModal
  isOpen={state.showUpToDateModal}
  onClose={dismissUpToDateModal}
/>
```

## Files to Modify

| File | Change |
|------|--------|
| `backend/src/oya/db/schema.sql` | Add `changes_made` column |
| `backend/src/oya/generation/orchestrator.py` | Add fields to `GenerationResult`, populate in `run()` |
| `backend/src/oya/api/routers/repos.py` | Store `changes_made` after generation |
| `backend/src/oya/api/routers/jobs.py` | Add `changes_made` to `JobStatus` model and queries |
| `frontend/src/types.ts` | Add `changes_made` to `JobStatus` type |
| `frontend/src/components/UpToDateModal.tsx` | New file |
| `frontend/src/context/AppContext.tsx` | Add state, action, modal logic |
| `frontend/src/components/Layout.tsx` | Render `UpToDateModal` |
