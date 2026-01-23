# AppContext Zustand Migration Implementation Plan

**Goal:** Replace the monolithic AppContext with four focused Zustand stores to improve testability, reduce coupling, and enable fine-grained subscriptions.

**Architecture:** Four domain-specific stores (wiki, generation, ui, noteEditor) replace one context. Each store is self-contained with its own state and actions. An initialize.ts module handles app startup. Components subscribe only to the state slices they need.

**Tech Stack:** Zustand (state management), React, TypeScript, Vitest

---

## Task 1: Add Zustand Dependency

**Files:**
- Modify: `frontend/package.json`

**Step 1: Install zustand**

Run:
```bash
cd frontend && npm install zustand
```

**Step 2: Verify installation**

Run:
```bash
grep zustand frontend/package.json
```

Expected: `"zustand": "^5.x.x"` in dependencies

**Step 3: Commit**

```bash
git add frontend/package.json frontend/package-lock.json
git commit -m "chore: add zustand dependency for state management"
```

---

## Task 2: Create wikiStore

**Files:**
- Create: `frontend/src/stores/wikiStore.ts`
- Create: `frontend/src/stores/wikiStore.test.ts`

**Step 1: Write the store tests**

Create `frontend/src/stores/wikiStore.test.ts`:

```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useWikiStore } from './wikiStore'

// Mock the API module
vi.mock('../api/client', () => ({
  getRepoStatus: vi.fn(),
  getWikiTree: vi.fn(),
  switchWorkspace: vi.fn(),
  ApiError: class ApiError extends Error {
    status: number
    constructor(status: number, message: string) {
      super(message)
      this.name = 'ApiError'
      this.status = status
    }
  },
}))

let api: typeof import('../api/client')

beforeEach(async () => {
  vi.resetModules()
  api = await import('../api/client')
  vi.clearAllMocks()
  // Reset store to initial state
  useWikiStore.setState(useWikiStore.getInitialState())
})

const mockRepoStatus = {
  path: '/home/user/project',
  head_commit: 'abc123',
  head_message: 'Initial commit',
  branch: 'main',
  initialized: true,
  is_docker: false,
  last_generation: null,
  generation_status: null,
  embedding_metadata: null,
  current_provider: null,
  current_model: null,
  embedding_mismatch: false,
}

const mockWikiTree = {
  overview: true,
  architecture: true,
  workflows: [],
  directories: [],
  files: [],
}

describe('wikiStore', () => {
  describe('initial state', () => {
    it('has correct initial values', () => {
      const state = useWikiStore.getState()
      expect(state.repoStatus).toBeNull()
      expect(state.wikiTree).toBeNull()
      expect(state.currentPage).toBeNull()
      expect(state.isLoading).toBe(true)
      expect(state.error).toBeNull()
    })
  })

  describe('refreshStatus', () => {
    it('fetches and updates repo status', async () => {
      vi.mocked(api.getRepoStatus).mockResolvedValue(mockRepoStatus)

      await useWikiStore.getState().refreshStatus()

      expect(api.getRepoStatus).toHaveBeenCalled()
      expect(useWikiStore.getState().repoStatus).toEqual(mockRepoStatus)
    })

    it('sets error on failure', async () => {
      vi.mocked(api.getRepoStatus).mockRejectedValue(new Error('Network error'))

      await useWikiStore.getState().refreshStatus()

      expect(useWikiStore.getState().error).toBe('Failed to fetch repo status')
    })
  })

  describe('refreshTree', () => {
    it('fetches and updates wiki tree', async () => {
      vi.mocked(api.getWikiTree).mockResolvedValue(mockWikiTree)

      await useWikiStore.getState().refreshTree()

      expect(api.getWikiTree).toHaveBeenCalled()
      expect(useWikiStore.getState().wikiTree).toEqual(mockWikiTree)
    })

    it('silently ignores errors', async () => {
      vi.mocked(api.getWikiTree).mockRejectedValue(new Error('Network error'))

      await useWikiStore.getState().refreshTree()

      expect(useWikiStore.getState().error).toBeNull()
    })
  })

  describe('switchWorkspace', () => {
    it('updates repo status and clears current page', async () => {
      const newStatus = { ...mockRepoStatus, path: '/new/path' }
      vi.mocked(api.switchWorkspace).mockResolvedValue({
        status: newStatus,
        message: 'Switched',
      })
      vi.mocked(api.getWikiTree).mockResolvedValue(mockWikiTree)

      // Set a current page first
      useWikiStore.setState({ currentPage: { title: 'Test', content: '', page_type: 'overview', source_path: null } })

      await useWikiStore.getState().switchWorkspace('/new/path')

      expect(useWikiStore.getState().repoStatus).toEqual(newStatus)
      expect(useWikiStore.getState().currentPage).toBeNull()
      expect(api.getWikiTree).toHaveBeenCalled()
    })

    it('sets error and throws on failure', async () => {
      vi.mocked(api.switchWorkspace).mockRejectedValue(new Error('Failed'))

      await expect(useWikiStore.getState().switchWorkspace('/bad/path')).rejects.toThrow()
      expect(useWikiStore.getState().error).toBe('Failed to switch workspace')
      expect(useWikiStore.getState().isLoading).toBe(false)
    })
  })

  describe('setCurrentPage', () => {
    it('updates current page', () => {
      const page = { title: 'Test', content: 'Content', page_type: 'overview' as const, source_path: null }

      useWikiStore.getState().setCurrentPage(page)

      expect(useWikiStore.getState().currentPage).toEqual(page)
    })
  })
})
```

**Step 2: Run test to verify it fails**

Run:
```bash
cd frontend && npm test -- --run src/stores/wikiStore.test.ts
```

Expected: FAIL (module not found)

**Step 3: Create the store**

Create `frontend/src/stores/wikiStore.ts`:

```typescript
import { create } from 'zustand'
import type { RepoStatus, WikiTree, WikiPage } from '../types'
import * as api from '../api/client'

interface WikiState {
  repoStatus: RepoStatus | null
  wikiTree: WikiTree | null
  currentPage: WikiPage | null
  isLoading: boolean
  error: string | null
}

interface WikiActions {
  refreshStatus: () => Promise<void>
  refreshTree: () => Promise<void>
  switchWorkspace: (path: string) => Promise<void>
  setCurrentPage: (page: WikiPage | null) => void
  setLoading: (loading: boolean) => void
  setError: (error: string | null) => void
}

const initialState: WikiState = {
  repoStatus: null,
  wikiTree: null,
  currentPage: null,
  isLoading: true,
  error: null,
}

export const useWikiStore = create<WikiState & WikiActions>()((set, get) => ({
  ...initialState,

  refreshStatus: async () => {
    try {
      const status = await api.getRepoStatus()
      set({ repoStatus: status })
    } catch {
      set({ error: 'Failed to fetch repo status' })
    }
  },

  refreshTree: async () => {
    try {
      const tree = await api.getWikiTree()
      set({ wikiTree: tree })
    } catch {
      // Wiki may not exist yet - silently ignore
    }
  },

  switchWorkspace: async (path: string) => {
    set({ isLoading: true, error: null })
    try {
      const result = await api.switchWorkspace(path)
      set({ repoStatus: result.status, currentPage: null })
      await get().refreshTree()
    } catch (err) {
      const message = err instanceof api.ApiError ? err.message : 'Failed to switch workspace'
      set({ error: message })
      throw err
    } finally {
      set({ isLoading: false })
    }
  },

  setCurrentPage: (page) => set({ currentPage: page }),
  setLoading: (loading) => set({ isLoading: loading }),
  setError: (error) => set({ error, isLoading: false }),
}))

// For testing - allows reset to initial state
useWikiStore.getInitialState = () => initialState
```

**Step 4: Run test to verify it passes**

Run:
```bash
cd frontend && npm test -- --run src/stores/wikiStore.test.ts
```

Expected: PASS

**Step 5: Commit**

```bash
git add frontend/src/stores/wikiStore.ts frontend/src/stores/wikiStore.test.ts
git commit -m "feat: add wikiStore for repository and wiki tree state"
```

---

## Task 3: Create generationStore

**Files:**
- Create: `frontend/src/stores/generationStore.ts`
- Create: `frontend/src/stores/generationStore.test.ts`

**Step 1: Write the store tests**

Create `frontend/src/stores/generationStore.test.ts`:

```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useGenerationStore } from './generationStore'

vi.mock('../api/client', () => ({
  initRepo: vi.fn(),
  getJob: vi.fn(),
}))

let api: typeof import('../api/client')

beforeEach(async () => {
  vi.resetModules()
  api = await import('../api/client')
  vi.clearAllMocks()
  useGenerationStore.setState(useGenerationStore.getInitialState())
})

describe('generationStore', () => {
  describe('initial state', () => {
    it('has correct initial values', () => {
      const state = useGenerationStore.getState()
      expect(state.currentJob).toBeNull()
      expect(state.generationStatus).toBeNull()
    })
  })

  describe('startGeneration', () => {
    it('returns job_id on success', async () => {
      vi.mocked(api.initRepo).mockResolvedValue({
        job_id: 'test-job-123',
        status: 'pending',
        message: 'Created',
      })
      vi.mocked(api.getJob).mockResolvedValue({
        job_id: 'test-job-123',
        type: 'generation',
        status: 'running',
        started_at: null,
        completed_at: null,
        current_phase: null,
        total_phases: null,
        error_message: null,
      })

      const jobId = await useGenerationStore.getState().startGeneration()

      expect(jobId).toBe('test-job-123')
      expect(useGenerationStore.getState().currentJob?.job_id).toBe('test-job-123')
    })

    it('clears generationStatus when starting', async () => {
      useGenerationStore.setState({ generationStatus: { status: 'incomplete', message: 'test' } })
      vi.mocked(api.initRepo).mockResolvedValue({
        job_id: 'job',
        status: 'pending',
        message: 'Created',
      })
      vi.mocked(api.getJob).mockResolvedValue({
        job_id: 'job',
        type: 'generation',
        status: 'running',
        started_at: null,
        completed_at: null,
        current_phase: null,
        total_phases: null,
        error_message: null,
      })

      await useGenerationStore.getState().startGeneration()

      expect(useGenerationStore.getState().generationStatus).toBeNull()
    })

    it('returns null and sets error on failure', async () => {
      vi.mocked(api.initRepo).mockRejectedValue(new Error('Server error'))

      const jobId = await useGenerationStore.getState().startGeneration()

      expect(jobId).toBeNull()
      expect(useGenerationStore.getState().error).toBe('Failed to start generation')
    })
  })

  describe('setCurrentJob', () => {
    it('updates current job', () => {
      const job = {
        job_id: 'test',
        type: 'generation' as const,
        status: 'running' as const,
        started_at: null,
        completed_at: null,
        current_phase: null,
        total_phases: null,
        error_message: null,
      }

      useGenerationStore.getState().setCurrentJob(job)

      expect(useGenerationStore.getState().currentJob).toEqual(job)
    })
  })

  describe('dismissGenerationStatus', () => {
    it('clears generation status', () => {
      useGenerationStore.setState({ generationStatus: { status: 'incomplete', message: 'test' } })

      useGenerationStore.getState().dismissGenerationStatus()

      expect(useGenerationStore.getState().generationStatus).toBeNull()
    })
  })
})
```

**Step 2: Run test to verify it fails**

Run:
```bash
cd frontend && npm test -- --run src/stores/generationStore.test.ts
```

Expected: FAIL

**Step 3: Create the store**

Create `frontend/src/stores/generationStore.ts`:

```typescript
import { create } from 'zustand'
import type { JobStatus, GenerationStatus } from '../types'
import * as api from '../api/client'

interface GenerationState {
  currentJob: JobStatus | null
  generationStatus: GenerationStatus | null
  isLoading: boolean
  error: string | null
}

interface GenerationActions {
  startGeneration: () => Promise<string | null>
  setCurrentJob: (job: JobStatus | null) => void
  setGenerationStatus: (status: GenerationStatus | null) => void
  dismissGenerationStatus: () => void
  setLoading: (loading: boolean) => void
  setError: (error: string | null) => void
}

const initialState: GenerationState = {
  currentJob: null,
  generationStatus: null,
  isLoading: false,
  error: null,
}

export const useGenerationStore = create<GenerationState & GenerationActions>()((set) => ({
  ...initialState,

  startGeneration: async () => {
    set({ isLoading: true, generationStatus: null, error: null })
    try {
      const result = await api.initRepo()
      const job = await api.getJob(result.job_id)
      set({ currentJob: job })
      return result.job_id
    } catch {
      set({ error: 'Failed to start generation' })
      return null
    } finally {
      set({ isLoading: false })
    }
  },

  setCurrentJob: (job) => set({ currentJob: job }),
  setGenerationStatus: (status) => set({ generationStatus: status }),
  dismissGenerationStatus: () => set({ generationStatus: null }),
  setLoading: (loading) => set({ isLoading: loading }),
  setError: (error) => set({ error }),
}))

useGenerationStore.getInitialState = () => initialState
```

**Step 4: Run test to verify it passes**

Run:
```bash
cd frontend && npm test -- --run src/stores/generationStore.test.ts
```

Expected: PASS

**Step 5: Commit**

```bash
git add frontend/src/stores/generationStore.ts frontend/src/stores/generationStore.test.ts
git commit -m "feat: add generationStore for job tracking state"
```

---

## Task 4: Create uiStore

**Files:**
- Create: `frontend/src/stores/uiStore.ts`
- Create: `frontend/src/stores/uiStore.test.ts`

**Step 1: Write the store tests**

Create `frontend/src/stores/uiStore.test.ts`:

```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useUIStore } from './uiStore'

beforeEach(() => {
  vi.resetModules()
  // Mock localStorage
  const localStorageMock = {
    getItem: vi.fn(() => null),
    setItem: vi.fn(),
    removeItem: vi.fn(),
    clear: vi.fn(),
    length: 0,
    key: vi.fn(),
  }
  vi.stubGlobal('localStorage', localStorageMock)

  // Mock matchMedia
  vi.stubGlobal(
    'matchMedia',
    vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }))
  )

  // Reset store
  useUIStore.setState(useUIStore.getInitialState())
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
```

**Step 2: Run test to verify it fails**

Run:
```bash
cd frontend && npm test -- --run src/stores/uiStore.test.ts
```

Expected: FAIL

**Step 3: Create the store**

Create `frontend/src/stores/uiStore.ts`:

```typescript
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

useUIStore.getInitialState = () => ({
  darkMode: false,
  askPanelOpen: false,
})
```

**Step 4: Run test to verify it passes**

Run:
```bash
cd frontend && npm test -- --run src/stores/uiStore.test.ts
```

Expected: PASS

**Step 5: Commit**

```bash
git add frontend/src/stores/uiStore.ts frontend/src/stores/uiStore.test.ts
git commit -m "feat: add uiStore for dark mode and panel preferences"
```

---

## Task 5: Create noteEditorStore

**Files:**
- Create: `frontend/src/stores/noteEditorStore.ts`
- Create: `frontend/src/stores/noteEditorStore.test.ts`

**Step 1: Write the store tests**

Create `frontend/src/stores/noteEditorStore.test.ts`:

```typescript
import { describe, it, expect, beforeEach } from 'vitest'
import { useNoteEditorStore } from './noteEditorStore'

beforeEach(() => {
  useNoteEditorStore.setState(useNoteEditorStore.getInitialState())
})

describe('noteEditorStore', () => {
  describe('initial state', () => {
    it('has correct initial values', () => {
      const state = useNoteEditorStore.getState()
      expect(state.isOpen).toBe(false)
      expect(state.isDirty).toBe(false)
      expect(state.defaultScope).toBe('general')
      expect(state.defaultTarget).toBe('')
    })
  })

  describe('open', () => {
    it('opens editor with default values', () => {
      useNoteEditorStore.getState().open()

      const state = useNoteEditorStore.getState()
      expect(state.isOpen).toBe(true)
      expect(state.defaultScope).toBe('general')
      expect(state.defaultTarget).toBe('')
    })

    it('opens editor with specified scope and target', () => {
      useNoteEditorStore.getState().open('file', '/src/main.ts')

      const state = useNoteEditorStore.getState()
      expect(state.isOpen).toBe(true)
      expect(state.defaultScope).toBe('file')
      expect(state.defaultTarget).toBe('/src/main.ts')
    })
  })

  describe('close', () => {
    it('closes editor and resets isDirty', () => {
      useNoteEditorStore.setState({ isOpen: true, isDirty: true })

      useNoteEditorStore.getState().close()

      const state = useNoteEditorStore.getState()
      expect(state.isOpen).toBe(false)
      expect(state.isDirty).toBe(false)
    })
  })

  describe('setDirty', () => {
    it('sets dirty state', () => {
      useNoteEditorStore.getState().setDirty(true)

      expect(useNoteEditorStore.getState().isDirty).toBe(true)
    })
  })
})
```

**Step 2: Run test to verify it fails**

Run:
```bash
cd frontend && npm test -- --run src/stores/noteEditorStore.test.ts
```

Expected: FAIL

**Step 3: Create the store**

Create `frontend/src/stores/noteEditorStore.ts`:

```typescript
import { create } from 'zustand'
import type { NoteScope } from '../types'

interface NoteEditorState {
  isOpen: boolean
  isDirty: boolean
  defaultScope: NoteScope
  defaultTarget: string
}

interface NoteEditorActions {
  open: (scope?: NoteScope, target?: string) => void
  close: () => void
  setDirty: (isDirty: boolean) => void
}

const initialState: NoteEditorState = {
  isOpen: false,
  isDirty: false,
  defaultScope: 'general',
  defaultTarget: '',
}

export const useNoteEditorStore = create<NoteEditorState & NoteEditorActions>()((set) => ({
  ...initialState,

  open: (scope = 'general', target = '') => {
    set({ isOpen: true, defaultScope: scope, defaultTarget: target })
  },

  close: () => {
    set({ isOpen: false, isDirty: false })
  },

  setDirty: (isDirty) => set({ isDirty }),
}))

useNoteEditorStore.getInitialState = () => initialState
```

**Step 4: Run test to verify it passes**

Run:
```bash
cd frontend && npm test -- --run src/stores/noteEditorStore.test.ts
```

Expected: PASS

**Step 5: Commit**

```bash
git add frontend/src/stores/noteEditorStore.ts frontend/src/stores/noteEditorStore.test.ts
git commit -m "feat: add noteEditorStore for note editor modal state"
```

---

## Task 6: Create initialize.ts

**Files:**
- Create: `frontend/src/stores/initialize.ts`
- Create: `frontend/src/stores/initialize.test.ts`

**Step 1: Write the tests**

Create `frontend/src/stores/initialize.test.ts`:

```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('../api/client', () => ({
  getRepoStatus: vi.fn(),
  getWikiTree: vi.fn(),
  getGenerationStatus: vi.fn(),
  listJobs: vi.fn(),
}))

let api: typeof import('../api/client')
let initializeApp: typeof import('./initialize').initializeApp
let useWikiStore: typeof import('./wikiStore').useWikiStore
let useGenerationStore: typeof import('./generationStore').useGenerationStore

const mockRepoStatus = {
  path: '/test',
  head_commit: 'abc',
  head_message: 'Test',
  branch: 'main',
  initialized: true,
  is_docker: false,
  last_generation: null,
  generation_status: null,
  embedding_metadata: null,
  current_provider: null,
  current_model: null,
  embedding_mismatch: false,
}

const mockWikiTree = {
  overview: true,
  architecture: false,
  workflows: [],
  directories: [],
  files: [],
}

beforeEach(async () => {
  vi.resetModules()
  api = await import('../api/client')
  const initModule = await import('./initialize')
  initializeApp = initModule.initializeApp
  const wikiModule = await import('./wikiStore')
  useWikiStore = wikiModule.useWikiStore
  const genModule = await import('./generationStore')
  useGenerationStore = genModule.useGenerationStore

  vi.clearAllMocks()
  useWikiStore.setState(useWikiStore.getInitialState())
  useGenerationStore.setState(useGenerationStore.getInitialState())
})

describe('initializeApp', () => {
  it('loads repo status and wiki tree', async () => {
    vi.mocked(api.getRepoStatus).mockResolvedValue(mockRepoStatus)
    vi.mocked(api.getWikiTree).mockResolvedValue(mockWikiTree)
    vi.mocked(api.getGenerationStatus).mockResolvedValue(null)
    vi.mocked(api.listJobs).mockResolvedValue([])

    await initializeApp()

    expect(useWikiStore.getState().repoStatus).toEqual(mockRepoStatus)
    expect(useWikiStore.getState().wikiTree).toEqual(mockWikiTree)
    expect(useWikiStore.getState().isLoading).toBe(false)
  })

  it('detects incomplete build and clears wiki tree', async () => {
    vi.mocked(api.getRepoStatus).mockResolvedValue(mockRepoStatus)
    vi.mocked(api.getWikiTree).mockResolvedValue(mockWikiTree)
    vi.mocked(api.getGenerationStatus).mockResolvedValue({
      status: 'incomplete',
      message: 'Build interrupted',
    })
    vi.mocked(api.listJobs).mockResolvedValue([])

    await initializeApp()

    expect(useGenerationStore.getState().generationStatus?.status).toBe('incomplete')
    expect(useWikiStore.getState().wikiTree?.overview).toBe(false)
  })

  it('restores running job', async () => {
    vi.mocked(api.getRepoStatus).mockResolvedValue(mockRepoStatus)
    vi.mocked(api.getWikiTree).mockResolvedValue(mockWikiTree)
    vi.mocked(api.getGenerationStatus).mockResolvedValue(null)
    vi.mocked(api.listJobs).mockResolvedValue([
      {
        job_id: 'running-123',
        type: 'generation',
        status: 'running',
        started_at: null,
        completed_at: null,
        current_phase: null,
        total_phases: null,
        error_message: null,
      },
    ])

    await initializeApp()

    expect(useGenerationStore.getState().currentJob?.job_id).toBe('running-123')
  })
})
```

**Step 2: Run test to verify it fails**

Run:
```bash
cd frontend && npm test -- --run src/stores/initialize.test.ts
```

Expected: FAIL

**Step 3: Create the initialization module**

Create `frontend/src/stores/initialize.ts`:

```typescript
import { useWikiStore } from './wikiStore'
import { useGenerationStore } from './generationStore'
import * as api from '../api/client'

export async function initializeApp(): Promise<void> {
  const wikiStore = useWikiStore.getState()
  const generationStore = useGenerationStore.getState()

  wikiStore.setLoading(true)
  await wikiStore.refreshStatus()

  // Check for incomplete build FIRST
  let hasIncompleteBuild = false
  try {
    const genStatus = await api.getGenerationStatus()
    if (genStatus && genStatus.status === 'incomplete') {
      generationStore.setGenerationStatus(genStatus)
      hasIncompleteBuild = true
      // Clear wiki tree when build is incomplete
      useWikiStore.setState({
        wikiTree: {
          overview: false,
          architecture: false,
          workflows: [],
          directories: [],
          files: [],
        },
      })
    }
  } catch {
    // Ignore errors when checking generation status
  }

  // Only load wiki tree if build is complete
  if (!hasIncompleteBuild) {
    await wikiStore.refreshTree()
  }

  // Check for any running jobs to restore generation progress after refresh
  try {
    const jobs = await api.listJobs(1)
    const runningJob = jobs.find((job) => job.status === 'running')
    if (runningJob) {
      generationStore.setCurrentJob(runningJob)
    }
  } catch {
    // Ignore errors when checking for running jobs
  }

  wikiStore.setLoading(false)
}
```

**Step 4: Run test to verify it passes**

Run:
```bash
cd frontend && npm test -- --run src/stores/initialize.test.ts
```

Expected: PASS

**Step 5: Commit**

```bash
git add frontend/src/stores/initialize.ts frontend/src/stores/initialize.test.ts
git commit -m "feat: add initializeApp for app startup sequence"
```

---

## Task 7: Add store reset to test setup

**Files:**
- Modify: `frontend/src/test/setup.ts`

**Step 1: Update test setup**

Edit `frontend/src/test/setup.ts`:

```typescript
import '@testing-library/jest-dom'
import { beforeEach, vi } from 'vitest'

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
```

**Step 2: Run all tests to verify setup works**

Run:
```bash
cd frontend && npm test -- --run
```

Expected: All tests pass

**Step 3: Commit**

```bash
git add frontend/src/test/setup.ts
git commit -m "chore: add store reset to test setup"
```

---

## Task 8: Create stores index file

**Files:**
- Create: `frontend/src/stores/index.ts`

**Step 1: Create index file**

Create `frontend/src/stores/index.ts`:

```typescript
export { useWikiStore } from './wikiStore'
export { useGenerationStore } from './generationStore'
export { useUIStore } from './uiStore'
export { useNoteEditorStore } from './noteEditorStore'
export { initializeApp } from './initialize'
```

**Step 2: Commit**

```bash
git add frontend/src/stores/index.ts
git commit -m "chore: add stores index for cleaner imports"
```

---

## Task 9: Migrate Sidebar component

**Files:**
- Modify: `frontend/src/components/Sidebar.tsx`

**Step 1: Update imports and hook usage**

Replace the useApp import and usage in `frontend/src/components/Sidebar.tsx`:

Change line 2:
```typescript
// FROM:
import { useApp } from '../context/useApp'

// TO:
import { useWikiStore } from '../stores'
```

Change lines 99-101:
```typescript
// FROM:
export function Sidebar() {
  const { state } = useApp()
  const { wikiTree } = state

// TO:
export function Sidebar() {
  const wikiTree = useWikiStore((s) => s.wikiTree)
```

**Step 2: Run tests**

Run:
```bash
cd frontend && npm test -- --run
```

Expected: All tests pass

**Step 3: Commit**

```bash
git add frontend/src/components/Sidebar.tsx
git commit -m "refactor: migrate Sidebar to useWikiStore"
```

---

## Task 10: Migrate InterruptedGenerationBanner component

**Files:**
- Modify: `frontend/src/components/InterruptedGenerationBanner.tsx`

**Step 1: Update imports and hook usage**

Replace in `frontend/src/components/InterruptedGenerationBanner.tsx`:

Change line 1:
```typescript
// FROM:
import { useApp } from '../context/useApp'

// TO:
import { useGenerationStore } from '../stores'
```

Change lines 3-5:
```typescript
// FROM:
export function InterruptedGenerationBanner() {
  const { state, dismissGenerationStatus, startGeneration } = useApp()
  const { generationStatus } = state

// TO:
export function InterruptedGenerationBanner() {
  const generationStatus = useGenerationStore((s) => s.generationStatus)
  const dismissGenerationStatus = useGenerationStore((s) => s.dismissGenerationStatus)
  const startGeneration = useGenerationStore((s) => s.startGeneration)
```

**Step 2: Run tests**

Run:
```bash
cd frontend && npm test -- --run
```

Expected: All tests pass

**Step 3: Commit**

```bash
git add frontend/src/components/InterruptedGenerationBanner.tsx
git commit -m "refactor: migrate InterruptedGenerationBanner to useGenerationStore"
```

---

## Task 11: Migrate RightSidebar component

**Files:**
- Modify: `frontend/src/components/RightSidebar.tsx`

**Step 1: Update imports and hook usage**

Replace in `frontend/src/components/RightSidebar.tsx`:

Change line 1:
```typescript
// FROM:
import { useApp } from '../context/useApp'

// TO:
import { useWikiStore, useNoteEditorStore } from '../stores'
```

Change lines 22-24:
```typescript
// FROM:
export function RightSidebar() {
  const { state, openNoteEditor } = useApp()
  const { currentPage, repoStatus } = state

// TO:
export function RightSidebar() {
  const currentPage = useWikiStore((s) => s.currentPage)
  const repoStatus = useWikiStore((s) => s.repoStatus)
  const openNoteEditor = useNoteEditorStore((s) => s.open)
```

**Step 2: Run tests**

Run:
```bash
cd frontend && npm test -- --run
```

Expected: All tests pass

**Step 3: Commit**

```bash
git add frontend/src/components/RightSidebar.tsx
git commit -m "refactor: migrate RightSidebar to Zustand stores"
```

---

## Task 12: Migrate AskPanel component

**Files:**
- Modify: `frontend/src/components/AskPanel.tsx`

**Step 1: Update imports and hook usage**

Replace in `frontend/src/components/AskPanel.tsx`:

Change line 9:
```typescript
// FROM:
import { useApp } from '../context/useApp'

// TO:
import { useWikiStore, useGenerationStore } from '../stores'
```

Change lines 49-58:
```typescript
// FROM:
export function AskPanel({ isOpen, onClose }: AskPanelProps) {
  const { state } = useApp()
  const isGenerating = state.currentJob?.status === 'running'
  const hasWiki =
    state.wikiTree &&
    (state.wikiTree.overview ||
      state.wikiTree.architecture ||
      state.wikiTree.workflows.length > 0 ||
      state.wikiTree.directories.length > 0 ||
      state.wikiTree.files.length > 0)

// TO:
export function AskPanel({ isOpen, onClose }: AskPanelProps) {
  const currentJob = useGenerationStore((s) => s.currentJob)
  const wikiTree = useWikiStore((s) => s.wikiTree)
  const isGenerating = currentJob?.status === 'running'
  const hasWiki =
    wikiTree &&
    (wikiTree.overview ||
      wikiTree.architecture ||
      wikiTree.workflows.length > 0 ||
      wikiTree.directories.length > 0 ||
      wikiTree.files.length > 0)
```

**Step 2: Run tests**

Run:
```bash
cd frontend && npm test -- --run
```

Expected: All tests pass

**Step 3: Commit**

```bash
git add frontend/src/components/AskPanel.tsx
git commit -m "refactor: migrate AskPanel to Zustand stores"
```

---

## Task 13: Migrate PageLoader component

**Files:**
- Modify: `frontend/src/components/PageLoader.tsx`

**Step 1: Update imports and hook usage**

Replace in `frontend/src/components/PageLoader.tsx`:

Change line 5:
```typescript
// FROM:
import { useApp } from '../context/useApp'

// TO:
import { useWikiStore, useGenerationStore } from '../stores'
```

Change lines 13-14:
```typescript
// FROM:
export function PageLoader({ loadPage }: PageLoaderProps) {
  const { dispatch, refreshTree, refreshStatus, state } = useApp()

// TO:
export function PageLoader({ loadPage }: PageLoaderProps) {
  const repoStatus = useWikiStore((s) => s.repoStatus)
  const isLoading = useWikiStore((s) => s.isLoading)
  const setCurrentPage = useWikiStore((s) => s.setCurrentPage)
  const refreshTree = useWikiStore((s) => s.refreshTree)
  const refreshStatus = useWikiStore((s) => s.refreshStatus)
  const currentJob = useGenerationStore((s) => s.currentJob)
  const setCurrentJob = useGenerationStore((s) => s.setCurrentJob)
```

Update all `dispatch({ type: 'SET_CURRENT_PAGE', payload: ... })` calls to `setCurrentPage(...)`:
- Line 32: `setCurrentPage(data)`
- Line 41: `setCurrentPage(null)`
- Line 69: `setCurrentPage(data)`

Update all `dispatch({ type: 'SET_CURRENT_JOB', payload: null })` calls to `setCurrentJob(null)`:
- Line 59: `setCurrentJob(null)`
- Line 85: `setCurrentJob(null)`

Update state references:
- Line 91: Change `state.currentJob?.status` to `currentJob?.status`
- Line 91: Change `state.currentJob.job_id` to `currentJob.job_id`
- Line 104: Change `state.isLoading` to `isLoading`
- Line 115: Change `state.repoStatus?.last_generation` to `repoStatus?.last_generation`

**Step 2: Run tests**

Run:
```bash
cd frontend && npm test -- --run
```

Expected: All tests pass

**Step 3: Commit**

```bash
git add frontend/src/components/PageLoader.tsx
git commit -m "refactor: migrate PageLoader to Zustand stores"
```

---

## Task 14: Migrate Layout component

**Files:**
- Modify: `frontend/src/components/Layout.tsx`

**Step 1: Update imports and hook usage**

Replace in `frontend/src/components/Layout.tsx`:

Change line 9:
```typescript
// FROM:
import { useApp } from '../context/useApp'

// TO:
import { useWikiStore, useUIStore, useNoteEditorStore } from '../stores'
```

Change lines 25-29:
```typescript
// FROM:
export function Layout({ children }: LayoutProps) {
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [rightSidebarOpen, setRightSidebarOpen] = useState(true)
  const { state, closeNoteEditor, refreshTree, setAskPanelOpen } = useApp()
  const { noteEditor, askPanelOpen } = state

// TO:
export function Layout({ children }: LayoutProps) {
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [rightSidebarOpen, setRightSidebarOpen] = useState(true)

  const noteEditor = useNoteEditorStore((s) => ({ isOpen: s.isOpen, defaultScope: s.defaultScope, defaultTarget: s.defaultTarget }))
  const closeNoteEditor = useNoteEditorStore((s) => s.close)
  const refreshTree = useWikiStore((s) => s.refreshTree)
  const askPanelOpen = useUIStore((s) => s.askPanelOpen)
  const setAskPanelOpen = useUIStore((s) => s.setAskPanelOpen)
```

**Step 2: Run tests**

Run:
```bash
cd frontend && npm test -- --run
```

Expected: All tests pass

**Step 3: Commit**

```bash
git add frontend/src/components/Layout.tsx
git commit -m "refactor: migrate Layout to Zustand stores"
```

---

## Task 15: Migrate TopBar component

**Files:**
- Modify: `frontend/src/components/TopBar.tsx`

**Step 1: Update imports and hook usage**

Replace in `frontend/src/components/TopBar.tsx`:

Change line 2:
```typescript
// FROM:
import { useApp } from '../context/useApp'

// TO:
import { useWikiStore, useGenerationStore, useUIStore, useNoteEditorStore } from '../stores'
```

Change lines 18-21:
```typescript
// FROM:
export function TopBar({
  onToggleSidebar,
  onToggleRightSidebar,
  onToggleAskPanel,
  askPanelOpen,
}: TopBarProps) {
  const { state, startGeneration, toggleDarkMode, switchWorkspace } = useApp()
  const { repoStatus, currentJob, isLoading, darkMode, noteEditor } = state

// TO:
export function TopBar({
  onToggleSidebar,
  onToggleRightSidebar,
  onToggleAskPanel,
  askPanelOpen,
}: TopBarProps) {
  const repoStatus = useWikiStore((s) => s.repoStatus)
  const isLoading = useWikiStore((s) => s.isLoading)
  const switchWorkspace = useWikiStore((s) => s.switchWorkspace)
  const currentJob = useGenerationStore((s) => s.currentJob)
  const startGeneration = useGenerationStore((s) => s.startGeneration)
  const darkMode = useUIStore((s) => s.darkMode)
  const toggleDarkMode = useUIStore((s) => s.toggleDarkMode)
  const noteEditorIsDirty = useNoteEditorStore((s) => s.isDirty)
```

Change line 24 to use `noteEditorIsDirty` instead of `noteEditor.isDirty`:
```typescript
// FROM:
  const hasUnsavedChanges = noteEditor.isDirty

// TO:
  const hasUnsavedChanges = noteEditorIsDirty
```

**Step 2: Run tests**

Run:
```bash
cd frontend && npm test -- --run
```

Expected: All tests pass

**Step 3: Commit**

```bash
git add frontend/src/components/TopBar.tsx
git commit -m "refactor: migrate TopBar to Zustand stores"
```

---

## Task 16: Update main.tsx to call initializeApp

**Files:**
- Modify: `frontend/src/main.tsx`

**Step 1: Update main.tsx**

Replace `frontend/src/main.tsx`:

```typescript
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { initializeApp } from './stores'

// Initialize app state (fire and forget)
initializeApp()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>
)
```

**Step 2: Run the app to verify it works**

Run:
```bash
cd frontend && npm run dev
```

Verify the app loads correctly in the browser.

**Step 3: Commit**

```bash
git add frontend/src/main.tsx
git commit -m "feat: call initializeApp on startup"
```

---

## Task 17: Remove AppProvider from App.tsx

**Files:**
- Modify: `frontend/src/App.tsx`

**Step 1: Remove AppProvider wrapper**

Replace `frontend/src/App.tsx`:

```typescript
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { Layout } from './components/Layout'
import { NotFound } from './components/NotFound'
import {
  OverviewPage,
  ArchitecturePage,
  WorkflowPage,
  DirectoryPage,
  FilePage,
} from './components/pages'

function WelcomePage() {
  return (
    <div className="text-center py-12">
      <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">Welcome to Ọya</h1>
      <p className="text-gray-600 dark:text-gray-400 max-w-md mx-auto">
        Generate comprehensive documentation for your codebase. Click "Generate Wiki" to get
        started.
      </p>
    </div>
  )
}

function App() {
  return (
    <BrowserRouter>
      <Layout>
        <Routes>
          <Route path="/" element={<OverviewPage />} />
          <Route path="/architecture" element={<ArchitecturePage />} />
          <Route path="/workflows/:slug" element={<WorkflowPage />} />
          <Route path="/directories/:slug" element={<DirectoryPage />} />
          <Route path="/files/:slug" element={<FilePage />} />
          <Route path="/welcome" element={<WelcomePage />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  )
}

export default App
```

**Step 2: Run all tests**

Run:
```bash
cd frontend && npm test -- --run
```

Expected: All tests pass

**Step 3: Commit**

```bash
git add frontend/src/App.tsx
git commit -m "refactor: remove AppProvider wrapper from App"
```

---

## Task 18: Delete AppContext files

**Files:**
- Delete: `frontend/src/context/AppContext.tsx`
- Delete: `frontend/src/context/useApp.ts`
- Delete: `frontend/src/context/AppContext.test.tsx`

**Step 1: Delete the files**

```bash
rm frontend/src/context/AppContext.tsx
rm frontend/src/context/useApp.ts
rm frontend/src/context/AppContext.test.tsx
rmdir frontend/src/context
```

**Step 2: Run all tests**

Run:
```bash
cd frontend && npm test -- --run
```

Expected: All tests pass

**Step 3: Commit**

```bash
git add -A
git commit -m "chore: remove legacy AppContext files"
```

---

## Task 19: Final verification

**Step 1: Run all tests**

Run:
```bash
cd frontend && npm test -- --run
```

Expected: All tests pass

**Step 2: Run the dev server and manually verify**

Run:
```bash
cd frontend && npm run dev
```

Verify:
- App loads without errors
- Dark mode toggle works
- Sidebar shows wiki tree
- Generation works
- Ask panel opens/closes
- Note editor opens/closes

**Step 3: Build for production**

Run:
```bash
cd frontend && npm run build
```

Expected: Build succeeds with no TypeScript errors

**Step 4: Final commit**

```bash
git add -A
git commit -m "feat: complete Zustand migration - all AppContext behaviors migrated"
```

---

## Summary

This plan migrates the monolithic AppContext to four focused Zustand stores:
- **wikiStore**: Repository and wiki tree state
- **generationStore**: Job tracking and generation status
- **uiStore**: Dark mode and panel preferences
- **noteEditorStore**: Note editor modal state

Key benefits achieved:
1. Components subscribe only to state they need (fine-grained updates)
2. Tests no longer need Provider wrappers or full context mocks
3. Clear separation of concerns
4. Easier to reason about state changes
