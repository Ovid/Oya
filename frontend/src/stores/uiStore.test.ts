import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useUIStore, initialState } from './uiStore'
import { STORAGE_KEY_DARK_MODE, STORAGE_KEY_ASK_PANEL_OPEN } from '../config'

beforeEach(() => {
  vi.clearAllMocks()
  // Reset store to initial state
  useUIStore.setState(initialState)
})

describe('uiStore', () => {
  describe('toggleDarkMode', () => {
    it('toggles dark mode from false to true', () => {
      useUIStore.setState({ darkMode: false })

      useUIStore.getState().toggleDarkMode()

      expect(useUIStore.getState().darkMode).toBe(true)
    })

    it('toggles dark mode from true to false', () => {
      useUIStore.setState({ darkMode: true })

      useUIStore.getState().toggleDarkMode()

      expect(useUIStore.getState().darkMode).toBe(false)
    })

    it('persists to localStorage', () => {
      useUIStore.setState({ darkMode: false })

      useUIStore.getState().toggleDarkMode()

      expect(localStorage.setItem).toHaveBeenCalledWith(STORAGE_KEY_DARK_MODE, 'true')
    })
  })

  describe('setAskPanelOpen', () => {
    it('sets ask panel open state', () => {
      useUIStore.getState().setAskPanelOpen(true)

      expect(useUIStore.getState().askPanelOpen).toBe(true)
    })

    it('persists to localStorage', () => {
      useUIStore.getState().setAskPanelOpen(true)

      expect(localStorage.setItem).toHaveBeenCalledWith(STORAGE_KEY_ASK_PANEL_OPEN, 'true')
    })
  })
})
