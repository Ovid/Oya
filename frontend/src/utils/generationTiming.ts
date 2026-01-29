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
    localStorage.setItem(`${STORAGE_KEY_GENERATION_TIMING_PREFIX}${jobId}`, JSON.stringify(timing))
  } catch {
    // localStorage unavailable or quota exceeded - graceful degradation
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
    // localStorage unavailable - timing cleanup will happen naturally on next successful access
    console.warn('Failed to clear generation timing from localStorage')
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
    // localStorage unavailable - stale entries will be cleaned up on next successful access
    console.warn('Failed to cleanup stale generation timing entries')
  }
}
