// frontend/src/utils/storage.test.ts
import { describe, it, expect, beforeEach } from 'vitest'
import {
  loadStorage,
  saveStorage,
  getStorageValue,
  setStorageValue,
  hasStorageValue,
  DEFAULT_STORAGE,
  getTimingForJob,
  setTimingForJob,
  clearTimingForJob,
  cleanupStaleTiming,
} from './storage'

describe('storage module', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  describe('loadStorage', () => {
    it('returns default values when no storage exists', () => {
      const storage = loadStorage()
      expect(storage).toEqual(DEFAULT_STORAGE)
    })

    it('loads existing storage with snake_case keys', () => {
      localStorage.setItem(
        'oya',
        JSON.stringify({
          dark_mode: true,
          ask_panel_open: true,
          sidebar_left_width: 300,
          sidebar_right_width: 250,
          current_job: null,
          qa_settings: { quick_mode: false, temperature: 0.7, timeout_minutes: 5 },
          generation_timing: {},
        })
      )

      const storage = loadStorage()
      expect(storage.darkMode).toBe(true)
      expect(storage.askPanelOpen).toBe(true)
      expect(storage.sidebarLeftWidth).toBe(300)
      expect(storage.qaSettings.quickMode).toBe(false)
    })

    it('handles corrupted JSON gracefully', () => {
      localStorage.setItem('oya', 'not valid json {')
      const storage = loadStorage()
      expect(storage).toEqual(DEFAULT_STORAGE)
      expect(localStorage.getItem('oya')).toBeNull()
    })

    it('merges partial storage with defaults', () => {
      localStorage.setItem(
        'oya',
        JSON.stringify({
          dark_mode: true,
        })
      )
      const storage = loadStorage()
      expect(storage.darkMode).toBe(true)
      expect(storage.askPanelOpen).toBe(false) // default
      expect(storage.sidebarLeftWidth).toBe(256) // default
    })

    it('falls back to defaults for invalid number types', () => {
      localStorage.setItem(
        'oya',
        JSON.stringify({
          sidebar_left_width: 'not-a-number',
          sidebar_right_width: null,
          qa_settings: { temperature: 'high', timeout_minutes: {} },
        })
      )
      const storage = loadStorage()
      expect(storage.sidebarLeftWidth).toBe(256) // default
      expect(storage.sidebarRightWidth).toBe(320) // default
      expect(storage.qaSettings.temperature).toBe(0.5) // default
      expect(storage.qaSettings.timeoutMinutes).toBe(3) // default
    })

    it('falls back to defaults for invalid boolean types', () => {
      localStorage.setItem(
        'oya',
        JSON.stringify({
          dark_mode: 'true', // string, not boolean
          ask_panel_open: 1, // number, not boolean
          qa_settings: { quick_mode: 'yes' },
        })
      )
      const storage = loadStorage()
      expect(storage.darkMode).toBe(false) // default
      expect(storage.askPanelOpen).toBe(false) // default
      expect(storage.qaSettings.quickMode).toBe(true) // default
    })

    it('falls back to defaults for NaN number values', () => {
      localStorage.setItem(
        'oya',
        JSON.stringify({
          sidebar_left_width: NaN,
        })
      )
      const storage = loadStorage()
      // NaN is serialized as null in JSON, so it becomes default
      expect(storage.sidebarLeftWidth).toBe(256)
    })

    it('returns null for invalid current_job (missing job_id)', () => {
      localStorage.setItem(
        'oya',
        JSON.stringify({
          current_job: { status: 'running' },
        })
      )
      const storage = loadStorage()
      expect(storage.currentJob).toBeNull()
    })

    it('returns null for invalid current_job (missing status)', () => {
      localStorage.setItem(
        'oya',
        JSON.stringify({
          current_job: { job_id: 'test-123' },
        })
      )
      const storage = loadStorage()
      expect(storage.currentJob).toBeNull()
    })

    it('returns null for invalid current_job (wrong types)', () => {
      localStorage.setItem(
        'oya',
        JSON.stringify({
          current_job: { job_id: 123, status: 'running' },
        })
      )
      const storage = loadStorage()
      expect(storage.currentJob).toBeNull()
    })

    it('returns valid current_job when shape is correct', () => {
      localStorage.setItem(
        'oya',
        JSON.stringify({
          current_job: {
            job_id: 'test-123',
            type: 'generation',
            status: 'running',
            started_at: '2024-01-01T00:00:00Z',
            completed_at: null,
            current_phase: 'parsing',
            total_phases: 5,
            error_message: null,
          },
        })
      )
      const storage = loadStorage()
      expect(storage.currentJob).not.toBeNull()
      expect(storage.currentJob?.jobId).toBe('test-123')
      expect(storage.currentJob?.status).toBe('running')
    })

    it('normalizes partial current_job with missing fields', () => {
      localStorage.setItem(
        'oya',
        JSON.stringify({
          current_job: {
            job_id: 'test-456',
            status: 'pending',
            // missing: type, started_at, completed_at, current_phase, total_phases, error_message
          },
        })
      )
      const storage = loadStorage()
      expect(storage.currentJob).not.toBeNull()
      expect(storage.currentJob?.jobId).toBe('test-456')
      expect(storage.currentJob?.status).toBe('pending')
      expect(storage.currentJob?.type).toBe('') // normalized to empty string
      expect(storage.currentJob?.startedAt).toBeNull()
      expect(storage.currentJob?.completedAt).toBeNull()
      expect(storage.currentJob?.currentPhase).toBeNull()
      expect(storage.currentJob?.totalPhases).toBeNull()
      expect(storage.currentJob?.errorMessage).toBeNull()
    })

    it('normalizes current_job with wrong field types', () => {
      localStorage.setItem(
        'oya',
        JSON.stringify({
          current_job: {
            job_id: 'test-789',
            status: 'running',
            type: 123, // should be string
            started_at: true, // should be string
            total_phases: 'five', // should be number
          },
        })
      )
      const storage = loadStorage()
      expect(storage.currentJob).not.toBeNull()
      expect(storage.currentJob?.type).toBe('') // normalized to empty string
      expect(storage.currentJob?.startedAt).toBeNull() // normalized to null
      expect(storage.currentJob?.totalPhases).toBeNull() // normalized to null
    })
  })

  describe('saveStorage', () => {
    it('saves storage with snake_case keys', () => {
      saveStorage({
        darkMode: true,
        askPanelOpen: false,
        sidebarLeftWidth: 300,
        sidebarRightWidth: 320,
        currentJob: null,
        qaSettings: { quickMode: true, temperature: 0.5, timeoutMinutes: 3 },
        generationTiming: {},
      })

      const stored = JSON.parse(localStorage.getItem('oya')!)
      expect(stored.dark_mode).toBe(true)
      expect(stored.sidebar_left_width).toBe(300)
      expect(stored.qa_settings.quick_mode).toBe(true)
    })
  })

  describe('getStorageValue', () => {
    it('returns specific value from storage', () => {
      localStorage.setItem('oya', JSON.stringify({ dark_mode: true }))
      expect(getStorageValue('darkMode')).toBe(true)
    })

    it('returns default when key missing', () => {
      expect(getStorageValue('darkMode')).toBe(false)
    })
  })

  describe('setStorageValue', () => {
    it('updates specific value in storage', () => {
      setStorageValue('darkMode', true)
      const stored = JSON.parse(localStorage.getItem('oya')!)
      expect(stored.dark_mode).toBe(true)
    })

    it('preserves other values', () => {
      localStorage.setItem(
        'oya',
        JSON.stringify({
          dark_mode: false,
          sidebar_left_width: 300,
        })
      )
      setStorageValue('darkMode', true)
      const stored = JSON.parse(localStorage.getItem('oya')!)
      expect(stored.dark_mode).toBe(true)
      expect(stored.sidebar_left_width).toBe(300)
    })
  })

  describe('hasStorageValue', () => {
    it('returns false when no storage exists', () => {
      expect(hasStorageValue('darkMode')).toBe(false)
    })

    it('returns true when key is explicitly stored', () => {
      localStorage.setItem('oya', JSON.stringify({ dark_mode: true }))
      expect(hasStorageValue('darkMode')).toBe(true)
    })

    it('returns true when key is explicitly stored as false', () => {
      localStorage.setItem('oya', JSON.stringify({ dark_mode: false }))
      expect(hasStorageValue('darkMode')).toBe(true)
    })

    it('returns false when key is not in storage', () => {
      localStorage.setItem('oya', JSON.stringify({ sidebar_left_width: 300 }))
      expect(hasStorageValue('darkMode')).toBe(false)
    })

    it('returns false for corrupted storage', () => {
      localStorage.setItem('oya', 'not valid json')
      expect(hasStorageValue('darkMode')).toBe(false)
    })
  })

  describe('migration from old keys', () => {
    it('migrates oya-dark-mode', () => {
      localStorage.setItem('oya-dark-mode', 'true')
      const storage = loadStorage()
      expect(storage.darkMode).toBe(true)
      expect(localStorage.getItem('oya-dark-mode')).toBeNull()
    })

    it('migrates oya-ask-panel-open', () => {
      localStorage.setItem('oya-ask-panel-open', 'true')
      const storage = loadStorage()
      expect(storage.askPanelOpen).toBe(true)
      expect(localStorage.getItem('oya-ask-panel-open')).toBeNull()
    })

    it('migrates oya-sidebar-left-width', () => {
      localStorage.setItem('oya-sidebar-left-width', '350')
      const storage = loadStorage()
      expect(storage.sidebarLeftWidth).toBe(350)
      expect(localStorage.getItem('oya-sidebar-left-width')).toBeNull()
    })

    it('migrates oya-sidebar-right-width', () => {
      localStorage.setItem('oya-sidebar-right-width', '280')
      const storage = loadStorage()
      expect(storage.sidebarRightWidth).toBe(280)
      expect(localStorage.getItem('oya-sidebar-right-width')).toBeNull()
    })

    it('migrates oya-current-job', () => {
      const job = {
        job_id: 'test-123',
        type: 'full',
        status: 'running',
        started_at: '2026-01-30T10:00:00',
        completed_at: null,
        current_phase: 'files',
        total_phases: 8,
        error_message: null,
      }
      localStorage.setItem('oya-current-job', JSON.stringify(job))
      const storage = loadStorage()
      expect(storage.currentJob?.jobId).toBe('test-123')
      expect(storage.currentJob?.status).toBe('running')
      expect(localStorage.getItem('oya-current-job')).toBeNull()
    })

    it('migrates oya-qa-settings', () => {
      const settings = { quickMode: false, temperature: 0.8, timeoutMinutes: 7 }
      localStorage.setItem('oya-qa-settings', JSON.stringify(settings))
      const storage = loadStorage()
      expect(storage.qaSettings.quickMode).toBe(false)
      expect(storage.qaSettings.temperature).toBe(0.8)
      expect(localStorage.getItem('oya-qa-settings')).toBeNull()
    })

    it('migrates oya-generation-timing-* keys', () => {
      const timing = {
        jobId: 'job-abc',
        jobStartedAt: 1700000000000,
        phases: { files: { startedAt: 1700000001000 } },
      }
      localStorage.setItem('oya-generation-timing-job-abc', JSON.stringify(timing))
      const storage = loadStorage()
      expect(storage.generationTiming['job-abc']).toBeDefined()
      expect(storage.generationTiming['job-abc'].jobId).toBe('job-abc')
      expect(localStorage.getItem('oya-generation-timing-job-abc')).toBeNull()
    })

    it('migrates all old keys together', () => {
      localStorage.setItem('oya-dark-mode', 'true')
      localStorage.setItem('oya-sidebar-left-width', '300')
      localStorage.setItem(
        'oya-qa-settings',
        JSON.stringify({ quickMode: false, temperature: 0.6, timeoutMinutes: 4 })
      )

      const storage = loadStorage()

      expect(storage.darkMode).toBe(true)
      expect(storage.sidebarLeftWidth).toBe(300)
      expect(storage.qaSettings.quickMode).toBe(false)
      expect(localStorage.getItem('oya-dark-mode')).toBeNull()
      expect(localStorage.getItem('oya-sidebar-left-width')).toBeNull()
      expect(localStorage.getItem('oya-qa-settings')).toBeNull()
    })

    it('new storage takes precedence over old keys', () => {
      localStorage.setItem('oya', JSON.stringify({ dark_mode: false }))
      localStorage.setItem('oya-dark-mode', 'true')
      const storage = loadStorage()
      expect(storage.darkMode).toBe(false) // new key wins
    })
  })

  describe('generation timing helpers', () => {
    describe('getTimingForJob', () => {
      it('returns timing for existing job', () => {
        const timing = { jobId: 'job-1', jobStartedAt: 1000, phases: {} }
        localStorage.setItem(
          'oya',
          JSON.stringify({
            generation_timing: { 'job-1': { job_id: 'job-1', job_started_at: 1000, phases: {} } },
          })
        )
        expect(getTimingForJob('job-1')).toEqual(timing)
      })

      it('returns null for non-existent job', () => {
        expect(getTimingForJob('no-such-job')).toBeNull()
      })
    })

    describe('setTimingForJob', () => {
      it('adds timing for new job', () => {
        const timing = {
          jobId: 'job-2',
          jobStartedAt: 2000,
          phases: { files: { startedAt: 2001 } },
        }
        setTimingForJob('job-2', timing)
        expect(getTimingForJob('job-2')).toEqual(timing)
      })

      it('updates timing for existing job', () => {
        setTimingForJob('job-3', { jobId: 'job-3', jobStartedAt: 3000, phases: {} })
        setTimingForJob('job-3', {
          jobId: 'job-3',
          jobStartedAt: 3000,
          phases: { files: { startedAt: 3001, completedAt: 3005, duration: 4 } },
        })
        expect(getTimingForJob('job-3')?.phases.files?.completedAt).toBe(3005)
      })
    })

    describe('clearTimingForJob', () => {
      it('removes timing for job', () => {
        setTimingForJob('job-4', { jobId: 'job-4', jobStartedAt: 4000, phases: {} })
        clearTimingForJob('job-4')
        expect(getTimingForJob('job-4')).toBeNull()
      })

      it('does not throw for non-existent job', () => {
        expect(() => clearTimingForJob('no-job')).not.toThrow()
      })
    })

    describe('cleanupStaleTiming', () => {
      it('removes entries older than maxAge', () => {
        const now = Date.now()
        // Old entry (25 hours ago)
        setTimingForJob('old-job', {
          jobId: 'old-job',
          jobStartedAt: now - 25 * 60 * 60 * 1000,
          phases: {},
        })
        // Recent entry (1 hour ago)
        setTimingForJob('new-job', {
          jobId: 'new-job',
          jobStartedAt: now - 1 * 60 * 60 * 1000,
          phases: {},
        })

        cleanupStaleTiming(24 * 60 * 60 * 1000)

        expect(getTimingForJob('old-job')).toBeNull()
        expect(getTimingForJob('new-job')).not.toBeNull()
      })

      it('removes corrupted entries with missing jobStartedAt', () => {
        const now = Date.now()
        localStorage.setItem(
          'oya',
          JSON.stringify({
            generation_timing: {
              'valid-job': { job_id: 'valid-job', job_started_at: now, phases: {} },
              'bad-job': { job_id: 'bad-job', phases: {} }, // missing job_started_at
            },
          })
        )

        cleanupStaleTiming()

        expect(getTimingForJob('valid-job')).not.toBeNull()
        expect(getTimingForJob('bad-job')).toBeNull()
      })

      it('removes corrupted entries with non-numeric jobStartedAt', () => {
        const now = Date.now()
        localStorage.setItem(
          'oya',
          JSON.stringify({
            generation_timing: {
              'valid-job': { job_id: 'valid-job', job_started_at: now, phases: {} },
              'bad-job': { job_id: 'bad-job', job_started_at: 'not-a-number', phases: {} },
            },
          })
        )

        cleanupStaleTiming()

        expect(getTimingForJob('valid-job')).not.toBeNull()
        expect(getTimingForJob('bad-job')).toBeNull()
      })

      it('handles null timing entries gracefully', () => {
        localStorage.setItem(
          'oya',
          JSON.stringify({
            generation_timing: {
              'null-job': null,
            },
          })
        )

        // Should not throw
        expect(() => cleanupStaleTiming()).not.toThrow()
        expect(getTimingForJob('null-job')).toBeNull()
      })

      it('resets generationTiming if it is not an object', () => {
        localStorage.setItem(
          'oya',
          JSON.stringify({
            generation_timing: 'not-an-object',
          })
        )

        // Should not throw
        expect(() => cleanupStaleTiming()).not.toThrow()
        const stored = JSON.parse(localStorage.getItem('oya')!)
        expect(stored.generation_timing).toEqual({})
      })
    })
  })
})
