import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useUIStore, initialState } from './uiStore'

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

      expect(localStorage.setItem).toHaveBeenCalledWith('oya-dark-mode', 'true')
    })
  })

  describe('setAskPanelOpen', () => {
    it('sets ask panel open state', () => {
      useUIStore.getState().setAskPanelOpen(true)

      expect(useUIStore.getState().askPanelOpen).toBe(true)
    })

    it('persists to localStorage', () => {
      useUIStore.getState().setAskPanelOpen(true)

      expect(localStorage.setItem).toHaveBeenCalledWith('oya-ask-panel-open', 'true')
    })
  })
})
