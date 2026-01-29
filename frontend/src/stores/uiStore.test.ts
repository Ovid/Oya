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

  describe('toast notifications', () => {
    it('adds a toast with unique id', () => {
      useUIStore.getState().addToast('Test message', 'error')

      const toasts = useUIStore.getState().toasts
      expect(toasts).toHaveLength(1)
      expect(toasts[0].message).toBe('Test message')
      expect(toasts[0].type).toBe('error')
      expect(toasts[0].id).toBeDefined()
    })

    it('adds multiple toasts', () => {
      useUIStore.getState().addToast('First', 'error')
      useUIStore.getState().addToast('Second', 'warning')

      expect(useUIStore.getState().toasts).toHaveLength(2)
    })

    it('dismisses a toast by id', () => {
      useUIStore.getState().addToast('Test', 'info')
      const toastId = useUIStore.getState().toasts[0].id

      useUIStore.getState().dismissToast(toastId)

      expect(useUIStore.getState().toasts).toHaveLength(0)
    })

    it('only dismisses the specified toast', () => {
      useUIStore.getState().addToast('First', 'error')
      useUIStore.getState().addToast('Second', 'warning')
      const firstId = useUIStore.getState().toasts[0].id

      useUIStore.getState().dismissToast(firstId)

      const remaining = useUIStore.getState().toasts
      expect(remaining).toHaveLength(1)
      expect(remaining[0].message).toBe('Second')
    })
  })

  describe('error modal', () => {
    it('shows error modal', () => {
      useUIStore.getState().showErrorModal('Error Title', 'Error details')

      const modal = useUIStore.getState().errorModal
      expect(modal).not.toBeNull()
      expect(modal?.title).toBe('Error Title')
      expect(modal?.message).toBe('Error details')
    })

    it('dismisses error modal', () => {
      useUIStore.getState().showErrorModal('Title', 'Message')
      useUIStore.getState().dismissErrorModal()

      expect(useUIStore.getState().errorModal).toBeNull()
    })
  })
})
