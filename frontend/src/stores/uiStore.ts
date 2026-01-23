import { create } from 'zustand'
import { subscribeWithSelector } from 'zustand/middleware'
import { STORAGE_KEY_DARK_MODE, STORAGE_KEY_ASK_PANEL_OPEN } from '../config'

function getInitialDarkMode(): boolean {
  if (typeof window === 'undefined') return false
  const stored = localStorage.getItem(STORAGE_KEY_DARK_MODE)
  if (stored !== null) return stored === 'true'
  return window.matchMedia('(prefers-color-scheme: dark)').matches
}

function getInitialAskPanelOpen(): boolean {
  if (typeof window === 'undefined') return false
  const stored = localStorage.getItem(STORAGE_KEY_ASK_PANEL_OPEN)
  return stored === 'true'
}

interface UIState {
  darkMode: boolean
  askPanelOpen: boolean
}

interface UIActions {
  toggleDarkMode: () => void
  setAskPanelOpen: (open: boolean) => void
}

const initialState: UIState = {
  darkMode: getInitialDarkMode(),
  askPanelOpen: getInitialAskPanelOpen(),
}

export const useUIStore = create<UIState & UIActions>()(
  subscribeWithSelector((set, get) => ({
    ...initialState,

    toggleDarkMode: () => {
      const newValue = !get().darkMode
      localStorage.setItem(STORAGE_KEY_DARK_MODE, String(newValue))
      set({ darkMode: newValue })
    },

    setAskPanelOpen: (open) => {
      localStorage.setItem(STORAGE_KEY_ASK_PANEL_OPEN, String(open))
      set({ askPanelOpen: open })
    },
  }))
)

// Apply dark mode class to document
useUIStore.subscribe(
  (state) => state.darkMode,
  (darkMode) => {
    if (typeof document !== 'undefined') {
      if (darkMode) {
        document.documentElement.classList.add('dark')
      } else {
        document.documentElement.classList.remove('dark')
      }
    }
  },
  { fireImmediately: true }
)

// For testing - allows reset to initial state
// We only need to reset the state portion, not actions
;(useUIStore as unknown as { getInitialState: () => UIState }).getInitialState = () => ({
  darkMode: false,
  askPanelOpen: false,
})
