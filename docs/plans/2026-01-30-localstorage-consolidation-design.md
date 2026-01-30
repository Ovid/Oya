# localStorage Consolidation Design

## Problem

Oya uses multiple localStorage keys (`oya-dark-mode`, `oya-ask-panel-open`, etc.) which clutters the storage namespace. Keys also use inconsistent casing (camelCase in some places).

## Solution

Consolidate all Oya data under a single `oya` localStorage key with snake_case for all property names.

## Storage Structure

```typescript
interface OyaStorage {
  dark_mode: boolean
  ask_panel_open: boolean
  sidebar_left_width: number
  sidebar_right_width: number
  current_job: {
    job_id: string
    type: string
    status: string
    started_at: string | null
    completed_at: string | null
    current_phase: string | null
    total_phases: number | null
    error_message: string | null
  } | null
  qa_settings: {
    quick_mode: boolean
    temperature: number
    timeout_minutes: number
  }
  generation_timing: {
    [job_id: string]: {
      job_id: string
      job_started_at: number
      phases: {
        [phase_name: string]: {
          started_at: number
          completed_at?: number
          duration?: number
        }
      }
    }
  }
}
```

## API Design

New module `frontend/src/utils/storage.ts`:

```typescript
// Read/write the entire storage object
function loadStorage(): OyaStorage
function saveStorage(data: OyaStorage): void

// Convenience helpers for common operations
function getStorageValue<K extends keyof OyaStorage>(key: K): OyaStorage[K]
function setStorageValue<K extends keyof OyaStorage>(key: K, value: OyaStorage[K]): void

// Timing-specific (nested under generation_timing)
function getTimingForJob(jobId: string): GenerationTiming | null
function setTimingForJob(jobId: string, timing: GenerationTiming): void
function clearTimingForJob(jobId: string): void
function cleanupStaleTiming(maxAgeMs: number): void
```

Internal TypeScript types remain camelCase (JS convention). Conversion between snake_case (storage) and camelCase (runtime) happens at the storage boundary.

## Migration Strategy

When `loadStorage()` finds no `oya` key but detects old keys:

1. Read all old keys (`oya-dark-mode`, `oya-ask-panel-open`, etc.)
2. Convert to new structure with snake_case
3. Save to single `oya` key
4. Delete old keys

Migration is transparent to the app.

## Files to Change

### New files
- `frontend/src/utils/storage.ts` - consolidated storage module
- `frontend/src/utils/storage.test.ts` - tests including migration

### Modified files
- `frontend/src/config/storage.ts` - remove old key constants
- `frontend/src/config/qa.ts` - remove `QA_STORAGE_KEY`
- `frontend/src/stores/uiStore.ts` - use storage helpers
- `frontend/src/stores/generationStore.ts` - use storage helpers
- `frontend/src/hooks/useResizablePanel.ts` - use storage helpers
- `frontend/src/components/AskPanel.tsx` - use storage helpers
- `frontend/src/utils/generationTiming.ts` - remove (absorbed into storage.ts)
- `frontend/src/stores/initialize.ts` - trigger migration on startup

### Test files to update
- `frontend/src/stores/uiStore.test.ts`
- `frontend/src/utils/generationTiming.test.ts` - remove or repurpose
- `frontend/src/hooks/useResizablePanel.test.ts`
- `frontend/src/stores/generationStore.test.ts`

### Documentation
- `CLAUDE.md` - add snake_case localStorage standard

## Test Strategy

Each feature must have tests verifying:
1. Loading from storage (correct value, defaults when missing)
2. Saving to storage (correct key/value)
3. Invalid data handling (corrupted JSON, wrong shape)

New `storage.test.ts` covers:
- Migration from old keys
- snake_case ↔ camelCase conversion
- Partial storage handling
- Timing cleanup logic
