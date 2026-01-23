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
  configurable: true,
})

// Mock matchMedia for dark mode detection
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  configurable: true,
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
  // Clear localStorage between tests to ensure isolation
  localStorageMock.clear()

  // Only reset if stores are loaded (they may not be in all tests)
  try {
    const { useWikiStore, initialState: wikiInitial } = await import('../stores/wikiStore')
    const { useGenerationStore, initialState: genInitial } =
      await import('../stores/generationStore')
    const { useUIStore, initialState: uiInitial } = await import('../stores/uiStore')
    const { useNoteEditorStore, initialState: noteInitial } =
      await import('../stores/noteEditorStore')

    useWikiStore.setState(wikiInitial)
    useGenerationStore.setState(genInitial)
    useUIStore.setState(uiInitial)
    useNoteEditorStore.setState(noteInitial)
  } catch {
    // Stores not yet created or not imported in this test
  }
})
