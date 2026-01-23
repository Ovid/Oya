import '@testing-library/jest-dom'
import { vi, beforeEach } from 'vitest'

// jsdom's localStorage can be incomplete in some configurations.
// Provide a complete mock to ensure consistent behavior.
const localStorageMock = (() => {
  let store: Record<string, string> = {}
  return {
    getItem: vi.fn((key: string) => store[key] ?? null),
    setItem: vi.fn((key: string, value: string) => {
      store[key] = value
    }),
    removeItem: vi.fn((key: string) => {
      delete store[key]
    }),
    clear: vi.fn(() => {
      store = {}
    }),
    get length() {
      return Object.keys(store).length
    },
    key: vi.fn((index: number) => Object.keys(store)[index] ?? null),
  }
})()

Object.defineProperty(window, 'localStorage', {
  value: localStorageMock,
  writable: true,
})

// Mock matchMedia for dark mode detection
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
})

// Reset stores between tests when they're imported
beforeEach(async () => {
  // Only reset if stores are loaded (they may not be in all tests)
  try {
    const { useWikiStore } = await import('../stores/wikiStore')
    const { useGenerationStore } = await import('../stores/generationStore')
    const { useUIStore } = await import('../stores/uiStore')
    const { useNoteEditorStore } = await import('../stores/noteEditorStore')

    useWikiStore.setState(useWikiStore.getInitialState())
    useGenerationStore.setState(useGenerationStore.getInitialState())
    useUIStore.setState(useUIStore.getInitialState())
    useNoteEditorStore.setState(useNoteEditorStore.getInitialState())
  } catch {
    // Stores not yet created or not imported in this test
  }
})
