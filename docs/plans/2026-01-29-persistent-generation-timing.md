# Persistent Generation Timing Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Persist wiki generation phase durations in localStorage so they survive page refresh.

**Architecture:** Create a utility module for localStorage timing operations. Integrate with GenerationProgress component by loading timing on mount, saving on phase transitions, and clearing on job completion.

**Tech Stack:** React, TypeScript, localStorage, Vitest

---

## Task 1: Create Storage Key Constant

**Files:**
- Modify: `frontend/src/config/storage.ts`

**Step 1: Add the storage key constant**

Add to `frontend/src/config/storage.ts`:

```typescript
export const STORAGE_KEY_GENERATION_TIMING_PREFIX = 'oya-generation-timing-'
```

**Step 2: Verify no lint errors**

Run: `cd /Users/poecurt/projects/oya/.worktrees/persistent-timing/frontend && npm run lint`
Expected: No errors

**Step 3: Commit**

```bash
git add frontend/src/config/storage.ts
git commit -m "config: add generation timing localStorage key prefix"
```

---

## Task 2: Create GenerationTiming Type and Utility Module

**Files:**
- Create: `frontend/src/utils/generationTiming.ts`
- Create: `frontend/src/utils/generationTiming.test.ts`

**Step 1: Write failing tests for the utility functions**

Create `frontend/src/utils/generationTiming.test.ts`:

```typescript
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import {
  GenerationTiming,
  savePhaseTiming,
  loadPhaseTiming,
  clearPhaseTiming,
  cleanupStaleTiming,
} from './generationTiming'
import { STORAGE_KEY_GENERATION_TIMING_PREFIX } from '../config/storage'

describe('generationTiming utilities', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  describe('savePhaseTiming', () => {
    it('should save timing data to localStorage', () => {
      const timing: GenerationTiming = {
        jobId: 'job-123',
        jobStartedAt: 1000000,
        phases: {
          syncing: { startedAt: 1000000, completedAt: 1005000, duration: 5 },
        },
      }

      savePhaseTiming('job-123', timing)

      const stored = localStorage.getItem(`${STORAGE_KEY_GENERATION_TIMING_PREFIX}job-123`)
      expect(stored).not.toBeNull()
      expect(JSON.parse(stored!)).toEqual(timing)
    })

    it('should handle localStorage errors gracefully', () => {
      const timing: GenerationTiming = {
        jobId: 'job-123',
        jobStartedAt: 1000000,
        phases: {},
      }

      // Mock localStorage.setItem to throw
      const originalSetItem = localStorage.setItem
      localStorage.setItem = () => {
        throw new Error('QuotaExceededError')
      }

      // Should not throw
      expect(() => savePhaseTiming('job-123', timing)).not.toThrow()

      localStorage.setItem = originalSetItem
    })
  })

  describe('loadPhaseTiming', () => {
    it('should load timing data from localStorage', () => {
      const timing: GenerationTiming = {
        jobId: 'job-123',
        jobStartedAt: 1000000,
        phases: {
          syncing: { startedAt: 1000000 },
        },
      }
      localStorage.setItem(
        `${STORAGE_KEY_GENERATION_TIMING_PREFIX}job-123`,
        JSON.stringify(timing)
      )

      const loaded = loadPhaseTiming('job-123')
      expect(loaded).toEqual(timing)
    })

    it('should return null if no data exists', () => {
      const loaded = loadPhaseTiming('nonexistent-job')
      expect(loaded).toBeNull()
    })

    it('should return null and clear corrupted data', () => {
      localStorage.setItem(
        `${STORAGE_KEY_GENERATION_TIMING_PREFIX}job-123`,
        'not valid json {'
      )

      const loaded = loadPhaseTiming('job-123')
      expect(loaded).toBeNull()
      expect(localStorage.getItem(`${STORAGE_KEY_GENERATION_TIMING_PREFIX}job-123`)).toBeNull()
    })

    it('should return null and clear data with wrong shape', () => {
      localStorage.setItem(
        `${STORAGE_KEY_GENERATION_TIMING_PREFIX}job-123`,
        JSON.stringify({ wrongField: 'value' })
      )

      const loaded = loadPhaseTiming('job-123')
      expect(loaded).toBeNull()
      expect(localStorage.getItem(`${STORAGE_KEY_GENERATION_TIMING_PREFIX}job-123`)).toBeNull()
    })
  })

  describe('clearPhaseTiming', () => {
    it('should remove timing data from localStorage', () => {
      localStorage.setItem(
        `${STORAGE_KEY_GENERATION_TIMING_PREFIX}job-123`,
        JSON.stringify({ jobId: 'job-123', jobStartedAt: 1000, phases: {} })
      )

      clearPhaseTiming('job-123')

      expect(localStorage.getItem(`${STORAGE_KEY_GENERATION_TIMING_PREFIX}job-123`)).toBeNull()
    })

    it('should not throw if key does not exist', () => {
      expect(() => clearPhaseTiming('nonexistent')).not.toThrow()
    })
  })

  describe('cleanupStaleTiming', () => {
    it('should remove entries older than maxAge', () => {
      const now = Date.now()
      vi.setSystemTime(now)

      // Old entry (25 hours ago)
      const oldTiming: GenerationTiming = {
        jobId: 'old-job',
        jobStartedAt: now - 25 * 60 * 60 * 1000,
        phases: {},
      }
      localStorage.setItem(
        `${STORAGE_KEY_GENERATION_TIMING_PREFIX}old-job`,
        JSON.stringify(oldTiming)
      )

      // Recent entry (1 hour ago)
      const recentTiming: GenerationTiming = {
        jobId: 'recent-job',
        jobStartedAt: now - 1 * 60 * 60 * 1000,
        phases: {},
      }
      localStorage.setItem(
        `${STORAGE_KEY_GENERATION_TIMING_PREFIX}recent-job`,
        JSON.stringify(recentTiming)
      )

      cleanupStaleTiming(24 * 60 * 60 * 1000) // 24 hours

      expect(localStorage.getItem(`${STORAGE_KEY_GENERATION_TIMING_PREFIX}old-job`)).toBeNull()
      expect(localStorage.getItem(`${STORAGE_KEY_GENERATION_TIMING_PREFIX}recent-job`)).not.toBeNull()
    })

    it('should handle corrupted entries during cleanup', () => {
      localStorage.setItem(`${STORAGE_KEY_GENERATION_TIMING_PREFIX}bad`, 'not json')
      localStorage.setItem('unrelated-key', 'value')

      // Should not throw
      expect(() => cleanupStaleTiming()).not.toThrow()

      // Bad entry should be removed
      expect(localStorage.getItem(`${STORAGE_KEY_GENERATION_TIMING_PREFIX}bad`)).toBeNull()
      // Unrelated key should be preserved
      expect(localStorage.getItem('unrelated-key')).toBe('value')
    })
  })
})
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/poecurt/projects/oya/.worktrees/persistent-timing/frontend && npm run test -- src/utils/generationTiming.test.ts`
Expected: FAIL with "Cannot find module './generationTiming'"

**Step 3: Write minimal implementation**

Create `frontend/src/utils/generationTiming.ts`:

```typescript
import { STORAGE_KEY_GENERATION_TIMING_PREFIX } from '../config/storage'

/**
 * Timing data for a wiki generation job.
 * Stored in localStorage to survive page refresh.
 */
export interface GenerationTiming {
  jobId: string
  jobStartedAt: number // Unix timestamp (ms)
  phases: {
    [phaseName: string]: {
      startedAt: number // Unix timestamp (ms)
      completedAt?: number // Set when phase finishes
      duration?: number // Calculated on completion (seconds)
    }
  }
}

/**
 * Validate that an object has the expected GenerationTiming shape.
 */
function isValidTiming(data: unknown): data is GenerationTiming {
  if (typeof data !== 'object' || data === null) return false
  const obj = data as Record<string, unknown>
  return (
    typeof obj.jobId === 'string' &&
    typeof obj.jobStartedAt === 'number' &&
    typeof obj.phases === 'object' &&
    obj.phases !== null
  )
}

/**
 * Save timing data for a generation job.
 * Fails silently if localStorage is unavailable or full.
 */
export function savePhaseTiming(jobId: string, timing: GenerationTiming): void {
  try {
    localStorage.setItem(
      `${STORAGE_KEY_GENERATION_TIMING_PREFIX}${jobId}`,
      JSON.stringify(timing)
    )
  } catch {
    // localStorage unavailable or quota exceeded - graceful degradation
    console.warn('Failed to save generation timing to localStorage')
  }
}

/**
 * Load timing data for a generation job.
 * Returns null if not found or corrupted (corrupted data is cleared).
 */
export function loadPhaseTiming(jobId: string): GenerationTiming | null {
  try {
    const key = `${STORAGE_KEY_GENERATION_TIMING_PREFIX}${jobId}`
    const stored = localStorage.getItem(key)
    if (!stored) return null

    const parsed = JSON.parse(stored)
    if (!isValidTiming(parsed)) {
      // Corrupted or wrong shape - clear it
      localStorage.removeItem(key)
      return null
    }
    return parsed
  } catch {
    // JSON parse failed - clear corrupted data
    clearPhaseTiming(jobId)
    return null
  }
}

/**
 * Clear timing data for a generation job.
 */
export function clearPhaseTiming(jobId: string): void {
  try {
    localStorage.removeItem(`${STORAGE_KEY_GENERATION_TIMING_PREFIX}${jobId}`)
  } catch {
    // localStorage unavailable - ignore
  }
}

/**
 * Remove stale timing entries older than maxAge.
 * Default maxAge is 24 hours.
 */
export function cleanupStaleTiming(maxAgeMs: number = 24 * 60 * 60 * 1000): void {
  try {
    const now = Date.now()
    const keysToRemove: string[] = []

    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i)
      if (!key || !key.startsWith(STORAGE_KEY_GENERATION_TIMING_PREFIX)) continue

      try {
        const stored = localStorage.getItem(key)
        if (!stored) continue

        const parsed = JSON.parse(stored)
        if (!isValidTiming(parsed) || now - parsed.jobStartedAt > maxAgeMs) {
          keysToRemove.push(key)
        }
      } catch {
        // Corrupted entry - mark for removal
        keysToRemove.push(key)
      }
    }

    for (const key of keysToRemove) {
      localStorage.removeItem(key)
    }
  } catch {
    // localStorage unavailable - ignore
  }
}
```

**Step 4: Run tests to verify they pass**

Run: `cd /Users/poecurt/projects/oya/.worktrees/persistent-timing/frontend && npm run test -- src/utils/generationTiming.test.ts`
Expected: PASS

**Step 5: Run lint**

Run: `cd /Users/poecurt/projects/oya/.worktrees/persistent-timing/frontend && npm run lint`
Expected: No errors

**Step 6: Commit**

```bash
git add frontend/src/utils/generationTiming.ts frontend/src/utils/generationTiming.test.ts
git commit -m "feat: add localStorage utilities for generation timing persistence"
```

---

## Task 3: Integrate Timing Persistence into GenerationProgress

**Files:**
- Modify: `frontend/src/components/GenerationProgress.tsx`
- Modify: `frontend/src/components/GenerationProgress.test.tsx`

**Step 1: Write failing tests for persistence behavior**

Add to `frontend/src/components/GenerationProgress.test.tsx`:

```typescript
import {
  loadPhaseTiming,
  savePhaseTiming,
  clearPhaseTiming,
} from '../utils/generationTiming'

// Add to existing vi.mock calls at top:
vi.mock('../utils/generationTiming', () => ({
  loadPhaseTiming: vi.fn(),
  savePhaseTiming: vi.fn(),
  clearPhaseTiming: vi.fn(),
  cleanupStaleTiming: vi.fn(),
}))

describe('GenerationProgress timing persistence', () => {
  let capturedOnProgress: ((event: ProgressEvent) => void) | null = null
  let capturedOnComplete: (() => void) | null = null

  beforeEach(() => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-01-29T12:00:00Z'))
    capturedOnProgress = null
    capturedOnComplete = null
    useUIStore.setState(initialState)

    vi.mocked(loadPhaseTiming).mockReturnValue(null)
    vi.mocked(savePhaseTiming).mockClear()
    vi.mocked(clearPhaseTiming).mockClear()

    vi.mocked(client.streamJobProgress).mockImplementation(
      (
        _jobId: string,
        onProgress: (event: ProgressEvent) => void,
        onComplete: () => void,
        _onError: (error: Error) => void
      ) => {
        capturedOnProgress = onProgress
        capturedOnComplete = onComplete
        return () => {}
      }
    )
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.clearAllMocks()
  })

  it('should load timing data on mount', () => {
    render(<GenerationProgress jobId="test-job" onComplete={vi.fn()} onError={vi.fn()} />)

    expect(loadPhaseTiming).toHaveBeenCalledWith('test-job')
  })

  it('should restore completed phase durations from localStorage', () => {
    vi.mocked(loadPhaseTiming).mockReturnValue({
      jobId: 'test-job',
      jobStartedAt: Date.now() - 120000, // 2 minutes ago
      phases: {
        syncing: { startedAt: Date.now() - 120000, completedAt: Date.now() - 110000, duration: 10 },
        files: { startedAt: Date.now() - 110000, completedAt: Date.now() - 60000, duration: 50 },
        directories: { startedAt: Date.now() - 60000 }, // in progress
      },
    })

    render(<GenerationProgress jobId="test-job" onComplete={vi.fn()} onError={vi.fn()} />)

    // Simulate SSE saying we're on directories phase
    act(() => {
      if (capturedOnProgress) {
        capturedOnProgress({ phase: '3:directories', total_phases: 8 })
      }
    })

    // Should show restored durations for completed phases
    expect(screen.getByText('10s')).toBeInTheDocument() // syncing
    expect(screen.getByText('50s')).toBeInTheDocument() // files
  })

  it('should save timing when phase changes', () => {
    render(<GenerationProgress jobId="test-job" onComplete={vi.fn()} onError={vi.fn()} />)

    // Start syncing phase
    act(() => {
      if (capturedOnProgress) {
        capturedOnProgress({ phase: '1:syncing', total_phases: 8 })
      }
    })

    // Advance time and change to files phase
    act(() => {
      vi.advanceTimersByTime(5000)
    })
    act(() => {
      if (capturedOnProgress) {
        capturedOnProgress({ phase: '2:files', total_phases: 8 })
      }
    })

    // Should have saved timing data
    expect(savePhaseTiming).toHaveBeenCalled()
  })

  it('should clear timing on job completion', () => {
    render(<GenerationProgress jobId="test-job" onComplete={vi.fn()} onError={vi.fn()} />)

    // Simulate completion
    act(() => {
      if (capturedOnComplete) {
        capturedOnComplete()
      }
    })

    expect(clearPhaseTiming).toHaveBeenCalledWith('test-job')
  })
})
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/poecurt/projects/oya/.worktrees/persistent-timing/frontend && npm run test -- src/components/GenerationProgress.test.tsx`
Expected: FAIL (new tests fail because persistence isn't integrated yet)

**Step 3: Integrate persistence into GenerationProgress**

Modify `frontend/src/components/GenerationProgress.tsx`:

Add imports at top:

```typescript
import {
  loadPhaseTiming,
  savePhaseTiming,
  clearPhaseTiming,
  cleanupStaleTiming,
  GenerationTiming,
} from '../utils/generationTiming'
```

Replace the `startTime` useState with a computed value from localStorage or current time.

Add a useEffect to load timing on mount and cleanup stale entries:

```typescript
// After existing state declarations, add:
const [restoredTiming, setRestoredTiming] = useState<GenerationTiming | null>(null)

// Replace: const [startTime] = useState<Date>(new Date())
// With computed startTime based on restored or current time:
const startTime = useMemo(() => {
  if (restoredTiming?.jobStartedAt) {
    return new Date(restoredTiming.jobStartedAt)
  }
  return new Date()
}, [restoredTiming])

// Add effect to load timing and cleanup stale entries on mount:
useEffect(() => {
  // Cleanup stale entries (runs once on app load)
  cleanupStaleTiming()

  // Load existing timing for this job
  if (jobId) {
    const timing = loadPhaseTiming(jobId)
    if (timing) {
      setRestoredTiming(timing)

      // Restore completed phase durations
      const restoredDurations: Record<string, number> = {}
      const restoredStartElapsed: Record<string, number> = {}

      for (const [phase, phaseData] of Object.entries(timing.phases)) {
        if (phaseData.duration !== undefined) {
          restoredDurations[phase] = phaseData.duration
        }
        if (phaseData.startedAt) {
          // Calculate what elapsed would have been at phase start
          const elapsedAtStart = Math.floor((phaseData.startedAt - timing.jobStartedAt) / 1000)
          restoredStartElapsed[phase] = elapsedAtStart
          phaseStartTimesRef.current[phase] = phaseData.startedAt
        }
      }

      setPhaseElapsedTimes(restoredDurations)
      setPhaseStartElapsedTimes(restoredStartElapsed)
    }
  }
}, [jobId])
```

In the SSE progress handler, after updating phase state, save to localStorage:

```typescript
// After line 108 (setCurrentPhaseNum(phaseNum)), add:
// Save timing to localStorage
if (jobId) {
  const now = Date.now()
  const currentTiming: GenerationTiming = {
    jobId,
    jobStartedAt: startTime.getTime(),
    phases: { ...phaseStartTimesRef.current },
  }

  // Convert to proper format with startedAt for each phase
  const phasesData: GenerationTiming['phases'] = {}
  for (const [p, startedAt] of Object.entries(phaseStartTimesRef.current)) {
    phasesData[p] = { startedAt }
  }

  // Add completion data for previous phase if it just changed
  if (prevPhase !== 'starting' && prevPhase !== phaseName && prevPhase in phaseStartTimesRef.current) {
    const duration = Math.floor((now - phaseStartTimesRef.current[prevPhase]) / 1000)
    phasesData[prevPhase] = {
      ...phasesData[prevPhase],
      completedAt: now,
      duration,
    }
  }

  currentTiming.phases = phasesData
  savePhaseTiming(jobId, currentTiming)
}
```

In the completion handler (around line 136), add timing clear:

```typescript
// After setIsComplete(true), add:
if (jobId) {
  clearPhaseTiming(jobId)
}
```

In the error handler (around line 141), add timing clear:

```typescript
// After setIsFailed(true), add:
if (jobId) {
  clearPhaseTiming(jobId)
}
```

In the cancellation handler (around line 146), add timing clear:

```typescript
// After setIsCancelled(true), add:
if (jobId) {
  clearPhaseTiming(jobId)
}
```

**Step 4: Run tests to verify they pass**

Run: `cd /Users/poecurt/projects/oya/.worktrees/persistent-timing/frontend && npm run test -- src/components/GenerationProgress.test.tsx`
Expected: PASS

**Step 5: Run all tests**

Run: `cd /Users/poecurt/projects/oya/.worktrees/persistent-timing/frontend && npm run test`
Expected: All tests pass

**Step 6: Run lint**

Run: `cd /Users/poecurt/projects/oya/.worktrees/persistent-timing/frontend && npm run lint`
Expected: No errors

**Step 7: Commit**

```bash
git add frontend/src/components/GenerationProgress.tsx frontend/src/components/GenerationProgress.test.tsx
git commit -m "feat: persist generation timing in localStorage

Durations now survive page refresh during wiki generation.
- Load timing on component mount
- Save on phase transitions
- Clear on job completion/failure/cancel
- Cleanup stale entries on app load"
```

---

## Task 4: Manual Testing

**Files:** None (manual verification)

**Step 1: Start the development servers**

Run backend:
```bash
cd /Users/poecurt/projects/oya/.worktrees/persistent-timing/backend && source .venv/bin/activate && uvicorn oya.main:app --reload
```

Run frontend:
```bash
cd /Users/poecurt/projects/oya/.worktrees/persistent-timing/frontend && npm run dev
```

**Step 2: Test the refresh behavior**

1. Start a wiki generation
2. Wait for at least 2 phases to complete (showing durations)
3. Refresh the page
4. Verify: Completed phase durations are restored, current phase shows live counter

**Step 3: Test cleanup on completion**

1. Let generation complete
2. Check localStorage (DevTools > Application > Local Storage)
3. Verify: No `oya-generation-timing-*` keys remain

**Step 4: Document any issues found**

If issues are found, create follow-up tasks.

---

## Summary

| Task | Description |
|------|-------------|
| 1 | Add storage key constant |
| 2 | Create timing utility module with tests |
| 3 | Integrate persistence into GenerationProgress |
| 4 | Manual testing and verification |
