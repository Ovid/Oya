# AppContext Refactoring: Zustand Store Migration

## Problem

The frontend's `AppContext` is a monolithic global store combining:
- Wiki domain state (repoStatus, wikiTree, currentPage)
- Job/generation state (currentJob, generationStatus)
- UI preferences (darkMode, askPanelOpen)
- Feature state (noteEditor)
- API operations (refreshStatus, refreshTree, startGeneration, switchWorkspace)

This causes:
1. **Tight coupling** - Unrelated features share one provider lifecycle
2. **Risky changes** - Touching context affects all 10+ consumers
3. **Test friction** - Components need full context mocks even for isolated behavior
4. **Implicit dependencies** - Any component can reach into any state

## Solution

Replace the single AppContext with four Zustand stores split by concern.

## Store Structure

```
frontend/src/stores/
├── wikiStore.ts        # Repository and wiki tree state
├── generationStore.ts  # Job tracking and generation status
├── uiStore.ts          # Dark mode, ask panel preferences
├── noteEditorStore.ts  # Note editor modal state
└── initialize.ts       # App startup logic
```

### Store Responsibilities

| Store | State | Actions |
|-------|-------|---------|
| `wikiStore` | repoStatus, wikiTree, currentPage, isLoading, error | refreshStatus, refreshTree, switchWorkspace, setCurrentPage |
| `generationStore` | currentJob, generationStatus | startGeneration, setCurrentJob, setGenerationStatus, dismissStatus |
| `uiStore` | darkMode, askPanelOpen | toggleDarkMode, setAskPanelOpen |
| `noteEditorStore` | isOpen, isDirty, defaultScope, defaultTarget | open, close, setDirty |

## Implementation Pattern

Each store follows this pattern:

```typescript
// frontend/src/stores/wikiStore.ts
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

export const useWikiStore = create<WikiState & WikiActions>((set, get) => ({
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

// Export for testing
useWikiStore.getInitialState = () => initialState
```

## Component Usage

Components subscribe only to what they need:

```typescript
// Sidebar - only needs wikiTree
const wikiTree = useWikiStore((s) => s.wikiTree)

// TopBar - needs multiple stores
const { repoStatus, isLoading } = useWikiStore(
  (s) => ({ repoStatus: s.repoStatus, isLoading: s.isLoading }),
  shallow
)
const currentJob = useGenerationStore((s) => s.currentJob)
const { darkMode, toggleDarkMode } = useUIStore(
  (s) => ({ darkMode: s.darkMode, toggleDarkMode: s.toggleDarkMode }),
  shallow
)
```

## Testing Pattern

Tests become simple - no Provider wrapper needed:

```typescript
// Before (current)
function createMockContextValue(overrides = {}) {
  return {
    state: { /* 12 fields */ },
    dispatch: vi.fn(),
    refreshStatus: vi.fn(),
    // ... 10 more functions
  }
}
render(
  <AppContext.Provider value={createMockContextValue()}>
    <PageLoader loadPage={loadPage} />
  </AppContext.Provider>
)

// After (with Zustand)
beforeEach(() => {
  useWikiStore.setState({ repoStatus: mockRepoStatus })
})
render(<PageLoader loadPage={loadPage} />)  // No wrapper needed
```

Store reset between tests:

```typescript
// frontend/src/test/setup.ts
beforeEach(() => {
  useWikiStore.setState(useWikiStore.getInitialState())
  useGenerationStore.setState(useGenerationStore.getInitialState())
  useUIStore.setState(useUIStore.getInitialState())
  useNoteEditorStore.setState(useNoteEditorStore.getInitialState())
})
```

## Initialization

App startup moves from `AppProvider` useEffect to a standalone function:

```typescript
// frontend/src/stores/initialize.ts
export async function initializeApp(): Promise<void> {
  const wikiStore = useWikiStore.getState()
  const generationStore = useGenerationStore.getState()

  wikiStore.setLoading(true)
  await wikiStore.refreshStatus()

  // Check for incomplete build
  let hasIncompleteBuild = false
  try {
    const genStatus = await api.getGenerationStatus()
    if (genStatus?.status === 'incomplete') {
      generationStore.setGenerationStatus(genStatus)
      hasIncompleteBuild = true
      useWikiStore.setState({
        wikiTree: { overview: false, architecture: false, workflows: [], directories: [], files: [] }
      })
    }
  } catch { /* ignore */ }

  if (!hasIncompleteBuild) {
    await wikiStore.refreshTree()
  }

  // Restore running job
  try {
    const jobs = await api.listJobs(1)
    const runningJob = jobs.find((job) => job.status === 'running')
    if (runningJob) {
      generationStore.setCurrentJob(runningJob)
    }
  } catch { /* ignore */ }

  wikiStore.setLoading(false)
}
```

Called once in main.tsx:

```typescript
// frontend/src/main.tsx
import { initializeApp } from './stores/initialize'

initializeApp()  // Fire and forget

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </StrictMode>
)
```

## Side Effects

Dark mode CSS class is handled via Zustand's subscribe API:

```typescript
// In uiStore.ts, after store creation
useUIStore.subscribe(
  (state) => state.darkMode,
  (darkMode) => {
    if (darkMode) {
      document.documentElement.classList.add('dark')
    } else {
      document.documentElement.classList.remove('dark')
    }
  },
  { fireImmediately: true }
)
```

## Migration Plan

### Phase 1: Create stores (non-breaking)
1. Add zustand dependency
2. Create all four stores with full functionality
3. Create initialize.ts
4. Add store reset to test setup

### Phase 2: Migrate components (incremental)
Migrate one component at a time, keeping AppContext as fallback:
1. Sidebar (simplest - only uses wikiTree)
2. PageLoader
3. AskPanel
4. Layout
5. RightSidebar
6. InterruptedGenerationBanner
7. TopBar (most complex - uses all stores)

### Phase 3: Cleanup
1. Remove AppContext.tsx
2. Remove useApp.ts
3. Remove AppProvider from App.tsx
4. Simplify test mocks

## File Changes

### New files
- `frontend/src/stores/wikiStore.ts`
- `frontend/src/stores/generationStore.ts`
- `frontend/src/stores/uiStore.ts`
- `frontend/src/stores/noteEditorStore.ts`
- `frontend/src/stores/initialize.ts`

### Modified files
- `frontend/src/main.tsx` - add initializeApp() call
- `frontend/src/App.tsx` - remove AppProvider wrapper
- `frontend/src/test/setup.ts` - add store reset
- `frontend/src/components/Sidebar.tsx`
- `frontend/src/components/PageLoader.tsx`
- `frontend/src/components/AskPanel.tsx`
- `frontend/src/components/Layout.tsx`
- `frontend/src/components/RightSidebar.tsx`
- `frontend/src/components/InterruptedGenerationBanner.tsx`
- `frontend/src/components/TopBar.tsx`

### Deleted files (after migration)
- `frontend/src/context/AppContext.tsx`
- `frontend/src/context/useApp.ts`

### Test files to update
- `frontend/src/components/PageLoader.test.tsx` - simplify mocking
- `frontend/src/components/TopBar.test.tsx` - simplify mocking
- `frontend/src/components/AskPanel.test.tsx` - simplify mocking
- `frontend/src/context/AppContext.test.tsx` - convert to store tests

## Dependencies

```bash
cd frontend && npm install zustand
```

Zustand is ~1KB gzipped with no additional dependencies.

## Test Coverage

All AppContext behaviors have been tested before this refactoring (38 tests in AppContext.test.tsx). These tests serve as the safety net - they must continue passing after migration to Zustand stores.
