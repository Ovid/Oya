import { create } from 'zustand'
import { subscribeWithSelector } from 'zustand/middleware'
import { getStorageValue, setStorageValue, hasStorageValue, loadStorage } from '../utils/storage'
import type { Toast, ToastType, ErrorModalState } from '../types'

function getInitialDarkMode(): boolean {
  if (typeof window === 'undefined') return false
  // Trigger migration from old keys before checking hasStorageValue.
  // Without this, users with old keys (e.g., oya-dark-mode) would lose
  // their preference on first load since hasStorageValue only checks
  // the consolidated storage key.
  loadStorage()
  // Check if user has explicitly set a preference (including false)
  if (hasStorageValue('darkMode')) {
    return getStorageValue('darkMode')
  }
  // No stored preference - use system preference
  return window.matchMedia('(prefers-color-scheme: dark)').matches
}

function getInitialAskPanelOpen(): boolean {
  if (typeof window === 'undefined') return false
  return getStorageValue('askPanelOpen')
}

let toastIdCounter = 0

interface UIState {
  darkMode: boolean
  askPanelOpen: boolean
  toasts: Toast[]
  errorModal: ErrorModalState | null
}

interface UIActions {
  toggleDarkMode: () => void
  setAskPanelOpen: (open: boolean) => void
  addToast: (message: string, type: ToastType) => string
  dismissToast: (id: string) => void
  showErrorModal: (title: string, message: string) => void
  dismissErrorModal: () => void
}

// For production: reads from localStorage/matchMedia
const runtimeInitialState: UIState = {
  darkMode: getInitialDarkMode(),
  askPanelOpen: getInitialAskPanelOpen(),
  toasts: [],
  errorModal: null,
}

// For testing: fixed default values
export const initialState: UIState = {
  darkMode: false,
  askPanelOpen: false,
  toasts: [],
  errorModal: null,
}

export const useUIStore = create<UIState & UIActions>()(
  subscribeWithSelector((set, get) => ({
    ...runtimeInitialState,

    toggleDarkMode: () => {
      const newValue = !get().darkMode
      setStorageValue('darkMode', newValue)
      set({ darkMode: newValue })
    },

    setAskPanelOpen: (open) => {
      setStorageValue('askPanelOpen', open)
      set({ askPanelOpen: open })
    },

    addToast: (message, type) => {
      const id = `toast-${++toastIdCounter}`
      const toast: Toast = {
        id,
        message,
        type,
        createdAt: Date.now(),
      }
      set((state) => ({ toasts: [...state.toasts, toast] }))
      return id
    },

    dismissToast: (id) => {
      set((state) => ({ toasts: state.toasts.filter((t) => t.id !== id) }))
    },

    showErrorModal: (title, message) => {
      set({ errorModal: { title, message } })
    },

    dismissErrorModal: () => {
      set({ errorModal: null })
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
