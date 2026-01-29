# Error Handling Improvements Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Prevent silent error discarding by adding a toast/modal notification system and fixing backend error handling.

**Architecture:** Extend `uiStore.ts` with toast queue and error modal state. Create reusable `ToastContainer` and `ErrorModal` components mounted globally in `App.tsx`. Convert existing silent error handling to use these components. Fix backend code to log or raise instead of silently passing.

**Tech Stack:** React, Zustand, TypeScript, Tailwind CSS (frontend); Python, FastAPI (backend)

---

## Task 1: Add Error Handling Policy to CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

**Step 1: Add the error handling section**

Add after the "Code Style" section at the end of CLAUDE.md:

```markdown
## Error Handling

### Never Silently Discard Errors
Errors that disappear make debugging impossible. Every error must either:
1. **Propagate** - Let it bubble up to a handler that can deal with it
2. **Log** - Record what went wrong with context (file, operation, relevant data)
3. **Transform** - Convert to a user-visible error state or message

### Catch Specific Exceptions
```python
# BAD - catches everything including bugs
except Exception:
    pass

# GOOD - catches what you expect
except (FileNotFoundError, PermissionError) as e:
    logger.warning(f"Could not read {path}: {e}")
```

### When Generic Except is Acceptable
Only in these cases, and MUST include a comment explaining why:
1. **Resource cleanup in finally/close()** - Best-effort cleanup where failure doesn't matter
2. **Graceful degradation** - Feature works without this, AND you log the fallback
3. **Top-level handlers** - API endpoints, CLI entry points that must not crash

### Required Documentation for `pass` in Except
If you must use `pass`, the comment must explain:
- What errors are expected
- Why ignoring them is safe
- What the fallback behavior is

```python
# ACCEPTABLE - documented, specific scenario
except sqlite3.OperationalError:
    # Column already exists from previous migration - safe to ignore
    pass

# UNACCEPTABLE - no explanation
except Exception:
    pass
```

### Distinguish "No Results" from "Query Failed"
Never return empty collections on error - this hides failures:
```python
# BAD - caller can't tell if search failed or found nothing
except Exception:
    return []

# GOOD - caller knows something went wrong
except ChromaDBError as e:
    logger.error(f"Vector search failed: {e}")
    raise SearchError(f"Search unavailable: {e}") from e
```
```

**Step 2: Verify the change**

Run: `head -100 CLAUDE.md && echo "..." && tail -80 CLAUDE.md`
Expected: New "Error Handling" section visible at end

**Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add error handling policy to CLAUDE.md"
```

---

## Task 2: Add Toast/Modal Types and Config

**Files:**
- Create: `frontend/src/types/notifications.ts`
- Modify: `frontend/src/types/index.ts`
- Modify: `frontend/src/config/timing.ts`

**Step 1: Create notification types**

Create `frontend/src/types/notifications.ts`:

```typescript
export type ToastType = 'error' | 'warning' | 'info'

export interface Toast {
  id: string
  message: string
  type: ToastType
  createdAt: number
}

export interface ErrorModalState {
  title: string
  message: string
}
```

**Step 2: Export from types/index.ts**

Add to `frontend/src/types/index.ts`:

```typescript
export * from './notifications'
```

**Step 3: Add toast timing config**

Add to `frontend/src/config/timing.ts` after existing exports:

```typescript
// =============================================================================
// Toast Notifications
// =============================================================================
// Configuration for toast notification display.

export const TOAST_AUTO_DISMISS_MS = 5000 // Auto-dismiss toasts after 5 seconds
export const TOAST_MAX_VISIBLE = 3 // Maximum number of toasts shown at once
```

**Step 4: Run TypeScript check**

Run: `cd frontend && npm run build 2>&1 | head -20`
Expected: No TypeScript errors

**Step 5: Commit**

```bash
git add frontend/src/types/notifications.ts frontend/src/types/index.ts frontend/src/config/timing.ts
git commit -m "feat: add toast and error modal types"
```

---

## Task 3: Extend uiStore with Toast/Modal State

**Files:**
- Modify: `frontend/src/stores/uiStore.ts`
- Modify: `frontend/src/stores/uiStore.test.ts`

**Step 1: Write tests for toast functionality**

Add to `frontend/src/stores/uiStore.test.ts`:

```typescript
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
```

**Step 2: Run tests to verify they fail**

Run: `cd frontend && npm run test -- --run src/stores/uiStore.test.ts 2>&1 | tail -20`
Expected: FAIL - addToast, dismissToast, showErrorModal, dismissErrorModal not defined

**Step 3: Update uiStore with toast/modal state**

Replace `frontend/src/stores/uiStore.ts`:

```typescript
import { create } from 'zustand'
import { subscribeWithSelector } from 'zustand/middleware'
import { STORAGE_KEY_DARK_MODE, STORAGE_KEY_ASK_PANEL_OPEN } from '../config'
import type { Toast, ToastType, ErrorModalState } from '../types'

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
      localStorage.setItem(STORAGE_KEY_DARK_MODE, String(newValue))
      set({ darkMode: newValue })
    },

    setAskPanelOpen: (open) => {
      localStorage.setItem(STORAGE_KEY_ASK_PANEL_OPEN, String(open))
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
```

**Step 4: Run tests to verify they pass**

Run: `cd frontend && npm run test -- --run src/stores/uiStore.test.ts 2>&1 | tail -10`
Expected: All tests pass

**Step 5: Commit**

```bash
git add frontend/src/stores/uiStore.ts frontend/src/stores/uiStore.test.ts
git commit -m "feat: add toast and error modal state to uiStore"
```

---

## Task 4: Create ToastContainer Component

**Files:**
- Create: `frontend/src/components/ToastContainer.tsx`
- Create: `frontend/src/components/ToastContainer.test.tsx`

**Step 1: Write tests for ToastContainer**

Create `frontend/src/components/ToastContainer.test.tsx`:

```typescript
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { ToastContainer } from './ToastContainer'
import { useUIStore, initialState } from '../stores/uiStore'

beforeEach(() => {
  vi.clearAllMocks()
  useUIStore.setState(initialState)
})

describe('ToastContainer', () => {
  it('renders nothing when no toasts', () => {
    const { container } = render(<ToastContainer />)
    expect(container.firstChild).toBeNull()
  })

  it('renders a toast message', () => {
    useUIStore.getState().addToast('Test error message', 'error')

    render(<ToastContainer />)

    expect(screen.getByText('Test error message')).toBeInTheDocument()
  })

  it('renders multiple toasts', () => {
    useUIStore.getState().addToast('First message', 'error')
    useUIStore.getState().addToast('Second message', 'warning')

    render(<ToastContainer />)

    expect(screen.getByText('First message')).toBeInTheDocument()
    expect(screen.getByText('Second message')).toBeInTheDocument()
  })

  it('dismisses toast when X button clicked', () => {
    useUIStore.getState().addToast('Dismissable', 'info')

    render(<ToastContainer />)
    const dismissButton = screen.getByRole('button', { name: /dismiss/i })
    fireEvent.click(dismissButton)

    expect(screen.queryByText('Dismissable')).not.toBeInTheDocument()
  })

  it('limits visible toasts to max', () => {
    // Add more than TOAST_MAX_VISIBLE toasts
    useUIStore.getState().addToast('First', 'error')
    useUIStore.getState().addToast('Second', 'error')
    useUIStore.getState().addToast('Third', 'error')
    useUIStore.getState().addToast('Fourth', 'error')

    render(<ToastContainer />)

    // Should only show 3 (TOAST_MAX_VISIBLE)
    const toasts = screen.getAllByRole('alert')
    expect(toasts.length).toBeLessThanOrEqual(3)
  })

  it('applies correct styling for error type', () => {
    useUIStore.getState().addToast('Error toast', 'error')

    render(<ToastContainer />)

    const toast = screen.getByRole('alert')
    expect(toast.className).toContain('bg-red')
  })

  it('applies correct styling for warning type', () => {
    useUIStore.getState().addToast('Warning toast', 'warning')

    render(<ToastContainer />)

    const toast = screen.getByRole('alert')
    expect(toast.className).toContain('bg-amber')
  })

  it('applies correct styling for info type', () => {
    useUIStore.getState().addToast('Info toast', 'info')

    render(<ToastContainer />)

    const toast = screen.getByRole('alert')
    expect(toast.className).toContain('bg-blue')
  })
})
```

**Step 2: Run tests to verify they fail**

Run: `cd frontend && npm run test -- --run src/components/ToastContainer.test.tsx 2>&1 | tail -15`
Expected: FAIL - ToastContainer module not found

**Step 3: Create ToastContainer component**

Create `frontend/src/components/ToastContainer.tsx`:

```tsx
import { useEffect } from 'react'
import { useUIStore } from '../stores/uiStore'
import { TOAST_AUTO_DISMISS_MS, TOAST_MAX_VISIBLE } from '../config'
import type { Toast, ToastType } from '../types'

const typeStyles: Record<ToastType, string> = {
  error: 'bg-red-600 text-white',
  warning: 'bg-amber-500 text-white',
  info: 'bg-blue-600 text-white',
}

const typeIcons: Record<ToastType, JSX.Element> = {
  error: (
    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
    </svg>
  ),
  warning: (
    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
      />
    </svg>
  ),
  info: (
    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
      />
    </svg>
  ),
}

function ToastItem({ toast, onDismiss }: { toast: Toast; onDismiss: () => void }) {
  useEffect(() => {
    const timer = setTimeout(onDismiss, TOAST_AUTO_DISMISS_MS)
    return () => clearTimeout(timer)
  }, [onDismiss])

  return (
    <div
      role="alert"
      className={`flex items-center gap-3 px-4 py-3 rounded-lg shadow-lg ${typeStyles[toast.type]}`}
    >
      {typeIcons[toast.type]}
      <span className="flex-1 text-sm font-medium">{toast.message}</span>
      <button
        onClick={onDismiss}
        className="p-1 rounded hover:bg-white/20 transition-colors"
        aria-label="Dismiss"
      >
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>
  )
}

export function ToastContainer() {
  const toasts = useUIStore((s) => s.toasts)
  const dismissToast = useUIStore((s) => s.dismissToast)

  // Show only the most recent toasts up to max
  const visibleToasts = toasts.slice(-TOAST_MAX_VISIBLE)

  if (visibleToasts.length === 0) {
    return null
  }

  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 max-w-sm">
      {visibleToasts.map((toast) => (
        <ToastItem key={toast.id} toast={toast} onDismiss={() => dismissToast(toast.id)} />
      ))}
    </div>
  )
}
```

**Step 4: Run tests to verify they pass**

Run: `cd frontend && npm run test -- --run src/components/ToastContainer.test.tsx 2>&1 | tail -10`
Expected: All tests pass

**Step 5: Commit**

```bash
git add frontend/src/components/ToastContainer.tsx frontend/src/components/ToastContainer.test.tsx
git commit -m "feat: create ToastContainer component"
```

---

## Task 5: Create ErrorModal Component

**Files:**
- Create: `frontend/src/components/ErrorModal.tsx`
- Create: `frontend/src/components/ErrorModal.test.tsx`

**Step 1: Write tests for ErrorModal**

Create `frontend/src/components/ErrorModal.test.tsx`:

```typescript
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { ErrorModal } from './ErrorModal'
import { useUIStore, initialState } from '../stores/uiStore'

beforeEach(() => {
  vi.clearAllMocks()
  useUIStore.setState(initialState)
})

describe('ErrorModal', () => {
  it('renders nothing when no error modal state', () => {
    const { container } = render(<ErrorModal />)
    expect(container.firstChild).toBeNull()
  })

  it('renders modal with title and message', () => {
    useUIStore.getState().showErrorModal('Error Title', 'Error details here')

    render(<ErrorModal />)

    expect(screen.getByText('Error Title')).toBeInTheDocument()
    expect(screen.getByText('Error details here')).toBeInTheDocument()
  })

  it('dismisses modal when Dismiss button clicked', () => {
    useUIStore.getState().showErrorModal('Title', 'Message')

    render(<ErrorModal />)
    fireEvent.click(screen.getByRole('button', { name: /dismiss/i }))

    expect(useUIStore.getState().errorModal).toBeNull()
  })

  it('dismisses modal when backdrop clicked', () => {
    useUIStore.getState().showErrorModal('Title', 'Message')

    render(<ErrorModal />)
    // Click the backdrop (the outer fixed div)
    const backdrop = screen.getByTestId('error-modal-backdrop')
    fireEvent.click(backdrop)

    expect(useUIStore.getState().errorModal).toBeNull()
  })

  it('shows error icon', () => {
    useUIStore.getState().showErrorModal('Title', 'Message')

    render(<ErrorModal />)

    // Icon container should have red styling
    const iconContainer = screen.getByTestId('error-modal-icon')
    expect(iconContainer.className).toContain('bg-red')
  })
})
```

**Step 2: Run tests to verify they fail**

Run: `cd frontend && npm run test -- --run src/components/ErrorModal.test.tsx 2>&1 | tail -15`
Expected: FAIL - ErrorModal module not found

**Step 3: Create ErrorModal component**

Create `frontend/src/components/ErrorModal.tsx`:

```tsx
import { useUIStore } from '../stores/uiStore'

export function ErrorModal() {
  const errorModal = useUIStore((s) => s.errorModal)
  const dismissErrorModal = useUIStore((s) => s.dismissErrorModal)

  if (!errorModal) {
    return null
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div
        data-testid="error-modal-backdrop"
        className="fixed inset-0 bg-black/50"
        onClick={dismissErrorModal}
      />
      <div className="relative bg-white dark:bg-gray-800 rounded-lg shadow-xl p-6 max-w-lg mx-4">
        <div className="flex items-start mb-4">
          <div className="flex-shrink-0">
            <div
              data-testid="error-modal-icon"
              className="inline-flex items-center justify-center w-12 h-12 bg-red-100 dark:bg-red-900 rounded-full"
            >
              <svg
                className="w-6 h-6 text-red-600 dark:text-red-400"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M6 18L18 6M6 6l12 12"
                />
              </svg>
            </div>
          </div>
          <div className="ml-4">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
              {errorModal.title}
            </h3>
            <p className="mt-2 text-sm text-gray-600 dark:text-gray-400 max-h-48 overflow-y-auto whitespace-pre-wrap">
              {errorModal.message}
            </p>
          </div>
        </div>
        <div className="flex justify-end">
          <button
            onClick={dismissErrorModal}
            className="px-4 py-2 text-sm font-medium text-white bg-red-600 hover:bg-red-700 rounded-md"
          >
            Dismiss
          </button>
        </div>
      </div>
    </div>
  )
}
```

**Step 4: Run tests to verify they pass**

Run: `cd frontend && npm run test -- --run src/components/ErrorModal.test.tsx 2>&1 | tail -10`
Expected: All tests pass

**Step 5: Commit**

```bash
git add frontend/src/components/ErrorModal.tsx frontend/src/components/ErrorModal.test.tsx
git commit -m "feat: create ErrorModal component"
```

---

## Task 6: Mount Global Components in App

**Files:**
- Modify: `frontend/src/App.tsx`

**Step 1: Add ToastContainer and ErrorModal to App**

Update `frontend/src/App.tsx`:

```tsx
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { Layout } from './components/Layout'
import { NotFound } from './components/NotFound'
import { FirstRunWizard } from './components/FirstRunWizard'
import { ToastContainer } from './components/ToastContainer'
import { ErrorModal } from './components/ErrorModal'
import { useReposStore } from './stores'
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
  const repos = useReposStore((s) => s.repos)
  const activeRepo = useReposStore((s) => s.activeRepo)
  const isInitialized = useReposStore((s) => s.isInitialized)
  const fetchRepos = useReposStore((s) => s.fetchRepos)
  const fetchActiveRepo = useReposStore((s) => s.fetchActiveRepo)

  // Show first-run wizard if no repos in the registry (only after initialization completes)
  const showFirstRunWizard = isInitialized && repos.length === 0 && activeRepo === null

  const handleFirstRunComplete = async () => {
    // Refresh repos after adding first one
    await fetchRepos()
    await fetchActiveRepo()
  }

  if (showFirstRunWizard) {
    return (
      <>
        <FirstRunWizard onComplete={handleFirstRunComplete} />
        <ToastContainer />
        <ErrorModal />
      </>
    )
  }

  return (
    <>
      <BrowserRouter>
        <Layout key={activeRepo?.id ?? 'no-repo'}>
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
      <ToastContainer />
      <ErrorModal />
    </>
  )
}

export default App
```

**Step 2: Verify TypeScript compiles**

Run: `cd frontend && npm run build 2>&1 | head -10`
Expected: No errors

**Step 3: Run all frontend tests**

Run: `cd frontend && npm run test -- --run 2>&1 | tail -10`
Expected: All tests pass

**Step 4: Commit**

```bash
git add frontend/src/App.tsx
git commit -m "feat: mount ToastContainer and ErrorModal globally in App"
```

---

## Task 7: Convert GenerationProgress to Use ErrorModal

**Files:**
- Modify: `frontend/src/components/GenerationProgress.tsx`

**Step 1: Remove inline error modal, use global ErrorModal**

The GenerationProgress component currently has its own inline error modal (lines 229-276). We need to:
1. Remove the inline modal rendering
2. Call `useUIStore.getState().showErrorModal()` when an error occurs
3. The `onError` callback still gets called for any additional handling

Update `frontend/src/components/GenerationProgress.tsx`:

In the imports section, add:
```tsx
import { useUIStore } from '../stores/uiStore'
```

Replace the `handleErrorDismiss` function (around line 178):
```tsx
const handleErrorDismiss = () => {
  useUIStore.getState().dismissErrorModal()
  onError(errorMessage)
}
```

In the `useEffect` that sets up the SSE stream, update the error callback (around line 139-142):
```tsx
(error: Error) => {
  setIsFailed(true)
  setErrorMessage(error.message)
  useUIStore.getState().showErrorModal('Generation Failed', error.message)
},
```

Replace the entire error modal rendering block (lines 229-276) with:
```tsx
// Show error state (modal is handled by global ErrorModal component)
if (isFailed) {
  return (
    <div className="max-w-xl mx-auto py-8">
      <div className="text-center">
        <div className="inline-flex items-center justify-center w-16 h-16 bg-red-100 dark:bg-red-900 rounded-full mb-4">
          <svg
            className="w-8 h-8 text-red-600 dark:text-red-400"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M6 18L18 6M6 6l12 12"
            />
          </svg>
        </div>
        <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
          Generation Failed
        </h2>
        <p className="mt-2 text-sm text-gray-600 dark:text-gray-400">
          An error occurred during wiki generation.
        </p>
      </div>
    </div>
  )
}
```

**Step 2: Run existing tests**

Run: `cd frontend && npm run test -- --run src/components/GenerationProgress.test.tsx 2>&1 | tail -15`
Expected: Tests pass (may need minor updates if tests check for inline modal)

**Step 3: Run TypeScript check**

Run: `cd frontend && npm run build 2>&1 | head -10`
Expected: No errors

**Step 4: Commit**

```bash
git add frontend/src/components/GenerationProgress.tsx
git commit -m "refactor: use global ErrorModal in GenerationProgress"
```

---

## Task 8: Convert initialize.ts to Use Toasts

**Files:**
- Modify: `frontend/src/stores/initialize.ts`

**Step 1: Add toast notifications for silent errors**

Update `frontend/src/stores/initialize.ts`:

Add import at top:
```typescript
import { useUIStore } from './uiStore'
```

Replace the first silent catch (lines 58-60):
```typescript
} catch (e) {
  useUIStore.getState().addToast('Could not check generation status', 'warning')
}
```

Replace the second silent catch (lines 74-76):
```typescript
} catch (e) {
  useUIStore.getState().addToast('Could not check for running jobs', 'warning')
}
```

**Step 2: Run tests**

Run: `cd frontend && npm run test -- --run src/stores/initialize.test.ts 2>&1 | tail -10`
Expected: Tests pass

**Step 3: Commit**

```bash
git add frontend/src/stores/initialize.ts
git commit -m "fix: show toast instead of silently ignoring init errors"
```

---

## Task 9: Convert generationStore to Use Error Modal

**Files:**
- Modify: `frontend/src/stores/generationStore.ts`

**Step 1: Show error modal on generation start failure**

Update `frontend/src/stores/generationStore.ts`:

Add import:
```typescript
import { useUIStore } from './uiStore'
```

Replace the catch block in `startGeneration` (lines 46-48):
```typescript
} catch (e) {
  const message = e instanceof Error ? e.message : 'Failed to start generation'
  set({ error: message })
  useUIStore.getState().showErrorModal('Generation Failed', message)
  return null
}
```

**Step 2: Run tests**

Run: `cd frontend && npm run test -- --run src/stores/generationStore.test.ts 2>&1 | tail -10`
Expected: Tests pass

**Step 3: Commit**

```bash
git add frontend/src/stores/generationStore.ts
git commit -m "fix: show error modal when generation fails to start"
```

---

## Task 10: Convert wikiStore to Use Toasts

**Files:**
- Modify: `frontend/src/stores/wikiStore.ts`

**Step 1: Add toast for repo status error**

Update `frontend/src/stores/wikiStore.ts`:

Add import:
```typescript
import { useUIStore } from './uiStore'
```

Update the `refreshStatus` catch block (lines 37-39):
```typescript
} catch (e) {
  set({ error: 'Failed to fetch repo status' })
  useUIStore.getState().addToast('Failed to fetch repo status', 'error')
}
```

The `refreshTree` catch block (lines 46-48) can stay silent since "wiki may not exist yet" is an expected state, not an error.

**Step 2: Run tests**

Run: `cd frontend && npm run test -- --run src/stores/wikiStore.test.ts 2>&1 | tail -10`
Expected: Tests pass

**Step 3: Commit**

```bash
git add frontend/src/stores/wikiStore.ts
git commit -m "fix: show toast when repo status fetch fails"
```

---

## Task 11: Convert main.tsx to Use Error Modal

**Files:**
- Modify: `frontend/src/main.tsx`

**Step 1: Show error modal on init failure**

Update `frontend/src/main.tsx`:

```tsx
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { initializeApp } from './stores/initialize'
import { useUIStore } from './stores/uiStore'

// Initialize app state
void initializeApp().catch((e) => {
  const message = e instanceof Error ? e.message : 'Unknown error'
  useUIStore.getState().showErrorModal('Initialization Failed', message)
  console.error('App initialization failed:', e)
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>
)
```

**Step 2: Verify TypeScript compiles**

Run: `cd frontend && npm run build 2>&1 | head -10`
Expected: No errors

**Step 3: Run all frontend tests**

Run: `cd frontend && npm run test -- --run 2>&1 | tail -5`
Expected: All tests pass

**Step 4: Commit**

```bash
git add frontend/src/main.tsx
git commit -m "fix: show error modal when app initialization fails"
```

---

## Task 12: Fix Backend vectorstore/issues.py

**Files:**
- Modify: `backend/src/oya/vectorstore/issues.py`

**Step 1: Add logging import**

Add at top of file after existing imports:
```python
import logging

logger = logging.getLogger(__name__)
```

**Step 2: Fix delete_issues_for_file (lines 73-74)**

Replace:
```python
except Exception:
    pass
```

With:
```python
except Exception as e:
    logger.warning(f"Failed to delete issues for {file_path}: {e}")
```

**Step 3: Fix query_issues (lines 119-120)**

Replace:
```python
except Exception:
    return []
```

With:
```python
except Exception as e:
    logger.error(f"Issue query failed: {e}")
    raise
```

**Step 4: Fix close method (lines 135-136)**

Replace:
```python
except Exception:
    pass
```

With:
```python
except Exception as e:
    # Best-effort cleanup - log but don't fail
    logger.debug(f"Cleanup error (non-critical): {e}")
```

**Step 5: Run backend tests**

Run: `cd backend && source .venv/bin/activate && pytest tests/ -k "issue" -v 2>&1 | tail -20`
Expected: Tests pass (or identify tests that need updating due to raised exceptions)

**Step 6: Commit**

```bash
git add backend/src/oya/vectorstore/issues.py
git commit -m "fix: log errors instead of silently ignoring in issues store"
```

---

## Task 13: Fix Backend vectorstore/store.py

**Files:**
- Modify: `backend/src/oya/vectorstore/store.py`

**Step 1: Add logging import if not present**

Add near top of file:
```python
import logging

logger = logging.getLogger(__name__)
```

**Step 2: Fix close method (lines 115-116)**

Replace:
```python
except Exception:
    pass  # Best effort cleanup
```

With:
```python
except Exception as e:
    # Best-effort cleanup - log but don't fail
    logger.debug(f"Cleanup error (non-critical): {e}")
```

**Step 3: Run backend tests**

Run: `cd backend && source .venv/bin/activate && pytest tests/ -k "store" -v 2>&1 | tail -15`
Expected: Tests pass

**Step 4: Commit**

```bash
git add backend/src/oya/vectorstore/store.py
git commit -m "fix: log cleanup errors in vector store"
```

---

## Task 14: Fix Backend generation/orchestrator.py

**Files:**
- Modify: `backend/src/oya/generation/orchestrator.py`

**Step 1: Fix _get_cache_info (lines 330-331)**

Replace:
```python
except Exception:
    pass
```

With:
```python
except Exception as e:
    logger.warning(f"Failed to parse cache metadata: {e}")
```

**Step 2: Fix _has_new_notes (lines 357-358)**

Replace:
```python
except Exception:
    return False
```

With:
```python
except Exception as e:
    logger.error(f"Database error checking notes: {e}")
    raise
```

**Step 3: Fix package.json parsing (lines 886-887)**

Replace:
```python
except Exception:
    pass
```

With:
```python
except (json.JSONDecodeError, KeyError, TypeError) as e:
    logger.debug(f"Could not parse package.json: {e}")
```

**Step 4: Fix pyproject.toml parsing (lines 899-900)**

Replace:
```python
except Exception:
    pass
```

With:
```python
except (tomllib.TOMLDecodeError, KeyError, TypeError) as e:
    logger.debug(f"Could not parse pyproject.toml: {e}")
```

**Step 5: Fix database recording (lines 1651-1653 and 1714-1716)**

Replace both occurrences of:
```python
except Exception:
    # Table might not exist yet, skip recording
    pass
```

With:
```python
except sqlite3.OperationalError as e:
    if "no such table" in str(e):
        logger.debug("Page tracking table not yet created, skipping record")
    else:
        logger.error(f"Failed to record generated page: {e}")
        raise
```

Add import at top if not present:
```python
import sqlite3
```

**Step 6: Run backend tests**

Run: `cd backend && source .venv/bin/activate && pytest tests/ -k "orchestrator" -v 2>&1 | tail -20`
Expected: Tests pass

**Step 7: Commit**

```bash
git add backend/src/oya/generation/orchestrator.py
git commit -m "fix: improve error handling in orchestrator"
```

---

## Task 15: Fix Backend generation/prompts.py

**Files:**
- Modify: `backend/src/oya/generation/prompts.py`

**Step 1: Add logging import if not present**

Check if `logger` is already defined. If not, add:
```python
import logging

logger = logging.getLogger(__name__)
```

**Step 2: Fix note fetching (lines 1407-1408)**

Replace:
```python
except Exception:
    return []
```

With:
```python
except Exception as e:
    logger.error(f"Failed to fetch notes from database: {e}")
    return []  # Graceful degradation - generation can continue without notes
```

**Step 3: Run backend tests**

Run: `cd backend && source .venv/bin/activate && pytest tests/ -k "prompt" -v 2>&1 | tail -15`
Expected: Tests pass

**Step 4: Commit**

```bash
git add backend/src/oya/generation/prompts.py
git commit -m "fix: log errors when fetching notes fails"
```

---

## Task 16: Run Full Test Suite and Final Verification

**Files:**
- None (verification only)

**Step 1: Run all frontend tests**

Run: `cd frontend && npm run test -- --run 2>&1 | tail -10`
Expected: All 268+ tests pass

**Step 2: Run frontend lint**

Run: `cd frontend && npm run lint 2>&1 | tail -10`
Expected: No errors

**Step 3: Run frontend build**

Run: `cd frontend && npm run build 2>&1 | tail -5`
Expected: Build succeeds

**Step 4: Run all backend tests**

Run: `cd backend && source .venv/bin/activate && pytest 2>&1 | tail -10`
Expected: All 1063+ tests pass

**Step 5: Commit any remaining changes**

If there are any uncommitted changes:
```bash
git status
git add -A
git commit -m "chore: cleanup from error handling improvements"
```

---

## Task 17: Export Components and Create Summary

**Files:**
- Modify: `frontend/src/components/index.ts` (if exists)

**Step 1: Export new components**

If `frontend/src/components/index.ts` exists, add:
```typescript
export { ToastContainer } from './ToastContainer'
export { ErrorModal } from './ErrorModal'
```

If it doesn't exist, skip this step (components are imported directly).

**Step 2: Verify exports work**

Run: `cd frontend && npm run build 2>&1 | tail -5`
Expected: Build succeeds

**Step 3: Final commit**

```bash
git add .
git commit -m "chore: export new notification components" --allow-empty
```

**Step 4: Create summary of changes**

Run: `git log --oneline HEAD~17..HEAD`
Expected: See all commits from this implementation

---

## Summary

After completing all tasks, the following changes will be in place:

**Policy (CLAUDE.md):**
- New "Error Handling" section with clear guidelines

**Frontend:**
- `uiStore.ts` - Extended with toast queue and error modal state
- `ToastContainer.tsx` - New component for toast notifications
- `ErrorModal.tsx` - New reusable error modal component
- `App.tsx` - Mounts ToastContainer and ErrorModal globally
- `GenerationProgress.tsx` - Uses global ErrorModal instead of inline
- `initialize.ts` - Shows toasts instead of silently ignoring errors
- `generationStore.ts` - Shows error modal on generation failure
- `wikiStore.ts` - Shows toast on repo status fetch failure
- `main.tsx` - Shows error modal on init failure

**Backend:**
- `vectorstore/issues.py` - Logs errors, raises on query failure
- `vectorstore/store.py` - Logs cleanup errors
- `generation/orchestrator.py` - Logs errors, catches specific exceptions
- `generation/prompts.py` - Logs errors when fetching notes fails
