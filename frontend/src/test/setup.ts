import '@testing-library/jest-dom'
import { vi, beforeEach } from 'vitest'

// Factory to create fresh localStorage mock
function createLocalStorageMock() {
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
}

// Factory to create fresh matchMedia mock
function createMatchMediaMock() {
  return vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }))
}

// Install initial mocks at module load time (needed for store initialization)
Object.defineProperty(window, 'localStorage', {
  value: createLocalStorageMock(),
  writable: true,
  configurable: true,
})

Object.defineProperty(window, 'matchMedia', {
  value: createMatchMediaMock(),
  writable: true,
  configurable: true,
})

// Reset browser API mocks and stores between tests
beforeEach(async () => {
  // Unstub any globals that tests may have stubbed
  vi.unstubAllGlobals()

  // Re-install fresh localStorage mock
  Object.defineProperty(window, 'localStorage', {
    value: createLocalStorageMock(),
    writable: true,
    configurable: true,
  })

  // Re-install fresh matchMedia mock
  Object.defineProperty(window, 'matchMedia', {
    value: createMatchMediaMock(),
    writable: true,
    configurable: true,
  })

  // Reset all stores to initial state
  const { useWikiStore, initialState: wikiInitial } = await import('../stores/wikiStore')
  const { useGenerationStore, initialState: genInitial } = await import('../stores/generationStore')
  const { useUIStore, initialState: uiInitial } = await import('../stores/uiStore')
  const { useNoteEditorStore, initialState: noteInitial } =
    await import('../stores/noteEditorStore')

  useWikiStore.setState(wikiInitial)
  useGenerationStore.setState(genInitial)
  useUIStore.setState(uiInitial)
  useNoteEditorStore.setState(noteInitial)
})
