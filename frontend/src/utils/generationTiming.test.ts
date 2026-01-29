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
      localStorage.setItem(`${STORAGE_KEY_GENERATION_TIMING_PREFIX}job-123`, JSON.stringify(timing))

      const loaded = loadPhaseTiming('job-123')
      expect(loaded).toEqual(timing)
    })

    it('should return null if no data exists', () => {
      const loaded = loadPhaseTiming('nonexistent-job')
      expect(loaded).toBeNull()
    })

    it('should return null and clear corrupted data', () => {
      localStorage.setItem(`${STORAGE_KEY_GENERATION_TIMING_PREFIX}job-123`, 'not valid json {')

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
      expect(
        localStorage.getItem(`${STORAGE_KEY_GENERATION_TIMING_PREFIX}recent-job`)
      ).not.toBeNull()
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
