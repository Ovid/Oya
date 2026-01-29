# Persistent Generation Timing Design

## Problem

When regenerating the wiki, the UI shows durations for all generation stages. If the user refreshes the page, all counters reset to 0s because timing is tracked entirely in React component state.

## Goal

Persist stage durations so that page refresh shows accurate timing for:
- Completed phases (exact durations)
- In-progress phase (calculated from stored start timestamp)

## Approach

Use localStorage to persist timing data keyed by job ID. Store timestamps rather than running counters so duration can be calculated at any time.

## Data Structure

```typescript
// Key: `oya-generation-timing-${jobId}`
interface GenerationTiming {
  jobId: string;
  jobStartedAt: number;           // Unix timestamp (ms)
  phases: {
    [phaseName: string]: {
      startedAt: number;          // Unix timestamp (ms)
      completedAt?: number;       // Set when phase finishes
      duration?: number;          // Calculated on completion (seconds)
    }
  }
}
```

### Why timestamps over durations

`duration = now - startedAt` always gives correct value, even after refresh. No need to "pause" and "resume" counters.

### Why store duration for completed phases

Avoids recalculating `completedAt - startedAt` repeatedly. Captures exact duration at completion time.

## Read/Write Timing

### Writes

| Event | Action |
|-------|--------|
| Job starts (first SSE event) | Create entry with `jobStartedAt`, first phase's `startedAt` |
| Phase changes | Set previous phase's `completedAt` + `duration`, new phase's `startedAt` |
| Job completes/fails/cancels | Delete the localStorage entry |

### Reads

| Event | Action |
|-------|--------|
| Component mounts with active `jobId` | Load timing data, restore completed phase durations |
| SSE reconnects | Validate current phase matches, calculate in-progress duration from `startedAt` |

## Cleanup Strategy

1. **On job completion/failure/cancel:** Delete localStorage entry for that job ID
2. **On component mount:** If job doesn't exist or is already completed, delete localStorage entry
3. **On app load (opportunistic):** Scan for `oya-generation-timing-*` keys older than 24 hours and delete them

## Implementation

### New file: `frontend/src/utils/generationTiming.ts`

```typescript
const TIMING_KEY_PREFIX = 'oya-generation-timing-';

export function savePhaseTiming(jobId: string, timing: GenerationTiming): void
export function loadPhaseTiming(jobId: string): GenerationTiming | null
export function clearPhaseTiming(jobId: string): void
export function cleanupStaleTiming(maxAgeMs?: number): void  // Default 24h
```

### Changes to `frontend/src/components/GenerationProgress.tsx`

1. **On mount:** Call `loadPhaseTiming(jobId)`. If data exists:
   - Populate `phaseElapsedTimes` with completed phase durations
   - Set `phaseStartTimesRef` for current phase from stored `startedAt`
   - Calculate `startTime` from stored `jobStartedAt`

2. **On phase change:** Call `savePhaseTiming()` with updated data

3. **On job end:** Call `clearPhaseTiming(jobId)`

4. **On app load (once):** Call `cleanupStaleTiming()` to remove orphans

## Edge Cases

### localStorage unavailable (private browsing)
Wrap localStorage calls in try/catch. Fallback to current behavior (durations reset on refresh). Graceful degradation with no user-visible error.

### Corrupted/invalid data
If `JSON.parse()` fails or data shape is wrong, delete the entry and start fresh. Log warning to console.

### Phase mismatch on reconnect
If SSE says phase 5 but localStorage only has phases 1-2, mark phases 3-4 as completed with `duration: null` (display as "—").

### Job ID changes
Each job has unique ID, so old timing data is keyed separately. Cleanup function removes stale entries.

### Multiple tabs
localStorage is shared across tabs. Both write to same key - last write wins. Acceptable since both tabs show same generation.

## Files Changed

- `frontend/src/utils/generationTiming.ts` (new)
- `frontend/src/components/GenerationProgress.tsx` (modify)

## Not Changed

- Backend API
- SSE streaming
- Database schema
