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
})
