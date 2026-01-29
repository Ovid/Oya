// frontend/src/utils/storage.test.ts
import { describe, it, expect, beforeEach } from 'vitest'
import { loadStorage, saveStorage, getStorageValue, setStorageValue, DEFAULT_STORAGE } from './storage'

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
      localStorage.setItem('oya', JSON.stringify({
        dark_mode: true,
        ask_panel_open: true,
        sidebar_left_width: 300,
        sidebar_right_width: 250,
        current_job: null,
        qa_settings: { quick_mode: false, temperature: 0.7, timeout_minutes: 5 },
        generation_timing: {}
      }))

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
      localStorage.setItem('oya', JSON.stringify({
        dark_mode: true
      }))
      const storage = loadStorage()
      expect(storage.darkMode).toBe(true)
      expect(storage.askPanelOpen).toBe(false) // default
      expect(storage.sidebarLeftWidth).toBe(256) // default
    })
  })

  describe('saveStorage', () => {
    it('saves storage with snake_case keys', () => {
      saveStorage({
        darkMode: true,
        askPanelOpen: false,
        sidebarLeftWidth: 300,
        sidebarRightWidth: 200,
        currentJob: null,
        qaSettings: { quickMode: true, temperature: 0.5, timeoutMinutes: 3 },
        generationTiming: {}
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
      localStorage.setItem('oya', JSON.stringify({
        dark_mode: false,
        sidebar_left_width: 300
      }))
      setStorageValue('darkMode', true)
      const stored = JSON.parse(localStorage.getItem('oya')!)
      expect(stored.dark_mode).toBe(true)
      expect(stored.sidebar_left_width).toBe(300)
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
        error_message: null
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
        phases: { files: { startedAt: 1700000001000 } }
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
      localStorage.setItem('oya-qa-settings', JSON.stringify({ quickMode: false, temperature: 0.6, timeoutMinutes: 4 }))

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
})
