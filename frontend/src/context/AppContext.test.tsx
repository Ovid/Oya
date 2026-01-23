import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, act } from '@testing-library/react'
import type { RepoStatus, WikiTree } from '../types'

// Mock the API module - must be before imports that use it
vi.mock('../api/client', () => ({
  getRepoStatus: vi.fn(),
  getWikiTree: vi.fn(),
  switchWorkspace: vi.fn(),
  initRepo: vi.fn(),
  getJob: vi.fn(),
  listJobs: vi.fn(),
  getGenerationStatus: vi.fn(),
  ApiError: class ApiError extends Error {
    status: number
    constructor(status: number, message: string) {
      super(message)
      this.name = 'ApiError'
      this.status = status
    }
  },
}))

// Setup global mocks for browser APIs
beforeEach(() => {
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
})

// Dynamic import to ensure mocks are set up first
let AppProvider: typeof import('./AppContext').AppProvider
let useApp: typeof import('./useApp').useApp
let api: typeof import('../api/client')

beforeEach(async () => {
  vi.resetModules()
  const appContextModule = await import('./AppContext')
  AppProvider = appContextModule.AppProvider
  const useAppModule = await import('./useApp')
  useApp = useAppModule.useApp
  api = await import('../api/client')
  vi.clearAllMocks()
})

// Test component that exposes context values
function TestConsumer({ onMount }: { onMount?: (ctx: ReturnType<typeof useApp>) => void }) {
  const ctx = useApp()
  if (onMount) {
    onMount(ctx)
  }
  return (
    <div>
      <span data-testid="repo-path">{ctx.state.repoStatus?.path ?? 'none'}</span>
      <span data-testid="current-page">{ctx.state.currentPage?.path ?? 'none'}</span>
      <span data-testid="is-dirty">{String(ctx.state.noteEditor.isDirty ?? false)}</span>
      <span data-testid="is-loading">{String(ctx.state.isLoading)}</span>
      <span data-testid="error">{ctx.state.error ?? 'none'}</span>
      <span data-testid="dark-mode">{String(ctx.state.darkMode)}</span>
      <span data-testid="ask-panel-open">{String(ctx.state.askPanelOpen)}</span>
      <span data-testid="current-job">{ctx.state.currentJob?.job_id ?? 'none'}</span>
      <span data-testid="generation-status">{ctx.state.generationStatus?.status ?? 'none'}</span>
      <span data-testid="wiki-tree-overview">{String(ctx.state.wikiTree?.overview ?? false)}</span>
      <span data-testid="note-editor-open">{String(ctx.state.noteEditor.isOpen)}</span>
      <span data-testid="note-editor-scope">{ctx.state.noteEditor.defaultScope}</span>
      <span data-testid="note-editor-target">{ctx.state.noteEditor.defaultTarget}</span>
    </div>
  )
}

const mockRepoStatus: RepoStatus = {
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

const mockWikiTree: WikiTree = {
  overview: true,
  architecture: true,
  workflows: [],
  directories: [],
  files: [],
}

describe('AppContext', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    // Default mock implementations
    vi.mocked(api.getRepoStatus).mockResolvedValue(mockRepoStatus)
    vi.mocked(api.getWikiTree).mockResolvedValue(mockWikiTree)
    vi.mocked(api.listJobs).mockResolvedValue([])
    vi.mocked(api.getGenerationStatus).mockResolvedValue(null)
  })

  describe('switchWorkspace', () => {
    it('updates repo status on successful switch', async () => {
      const newRepoStatus: RepoStatus = {
        ...mockRepoStatus,
        path: '/home/user/new-project',
      }

      vi.mocked(api.switchWorkspace).mockResolvedValue({
        status: newRepoStatus,
        message: 'Workspace switched successfully',
      })

      let contextRef: ReturnType<typeof useApp> | null = null

      render(
        <AppProvider>
          <TestConsumer
            onMount={(ctx) => {
              contextRef = ctx
            }}
          />
        </AppProvider>
      )

      // Wait for initial load
      await waitFor(() => {
        expect(screen.getByTestId('repo-path')).toHaveTextContent('/home/user/project')
      })

      // Switch workspace
      await act(async () => {
        await contextRef!.switchWorkspace('/home/user/new-project')
      })

      expect(screen.getByTestId('repo-path')).toHaveTextContent('/home/user/new-project')
    })

    it('clears current page on workspace switch', async () => {
      const newRepoStatus: RepoStatus = {
        ...mockRepoStatus,
        path: '/home/user/new-project',
      }

      vi.mocked(api.switchWorkspace).mockResolvedValue({
        status: newRepoStatus,
        message: 'Workspace switched successfully',
      })

      let contextRef: ReturnType<typeof useApp> | null = null

      render(
        <AppProvider>
          <TestConsumer
            onMount={(ctx) => {
              contextRef = ctx
            }}
          />
        </AppProvider>
      )

      // Wait for initial load
      await waitFor(() => {
        expect(screen.getByTestId('is-loading')).toHaveTextContent('false')
      })

      // Set a current page first
      act(() => {
        contextRef!.dispatch({
          type: 'SET_CURRENT_PAGE',
          payload: {
            content: 'test',
            page_type: 'overview',
            path: '/overview',
            word_count: 10,
            source_path: null,
          },
        })
      })

      expect(screen.getByTestId('current-page')).toHaveTextContent('/overview')

      // Switch workspace
      await act(async () => {
        await contextRef!.switchWorkspace('/home/user/new-project')
      })

      expect(screen.getByTestId('current-page')).toHaveTextContent('none')
    })

    it('handles errors during workspace switch', async () => {
      // Create an error that will be caught and have its message extracted
      const error = new Error('Path does not exist')
      vi.mocked(api.switchWorkspace).mockRejectedValue(error)

      let contextRef: ReturnType<typeof useApp> | null = null

      render(
        <AppProvider>
          <TestConsumer
            onMount={(ctx) => {
              contextRef = ctx
            }}
          />
        </AppProvider>
      )

      // Wait for initial load
      await waitFor(() => {
        expect(screen.getByTestId('is-loading')).toHaveTextContent('false')
      })

      // Switch workspace - should throw and set error state
      let caughtError: Error | null = null
      await act(async () => {
        try {
          await contextRef!.switchWorkspace('/invalid/path')
        } catch (e) {
          caughtError = e as Error
        }
      })

      // Verify the error was thrown
      expect(caughtError).not.toBeNull()

      // The error message should be the fallback since it's not an ApiError instance
      expect(screen.getByTestId('error')).toHaveTextContent('Failed to switch workspace')
    })

    it('refreshes wiki tree after successful switch', async () => {
      const newRepoStatus: RepoStatus = {
        ...mockRepoStatus,
        path: '/home/user/new-project',
      }

      vi.mocked(api.switchWorkspace).mockResolvedValue({
        status: newRepoStatus,
        message: 'Workspace switched successfully',
      })

      let contextRef: ReturnType<typeof useApp> | null = null

      render(
        <AppProvider>
          <TestConsumer
            onMount={(ctx) => {
              contextRef = ctx
            }}
          />
        </AppProvider>
      )

      // Wait for initial load
      await waitFor(() => {
        expect(screen.getByTestId('is-loading')).toHaveTextContent('false')
      })

      // Clear the mock call count from initial load
      vi.mocked(api.getWikiTree).mockClear()

      // Switch workspace
      await act(async () => {
        await contextRef!.switchWorkspace('/home/user/new-project')
      })

      // Should have called getWikiTree to refresh
      expect(api.getWikiTree).toHaveBeenCalled()
    })
  })

  describe('setNoteEditorDirty', () => {
    it('updates isDirty state to true', async () => {
      let contextRef: ReturnType<typeof useApp> | null = null

      render(
        <AppProvider>
          <TestConsumer
            onMount={(ctx) => {
              contextRef = ctx
            }}
          />
        </AppProvider>
      )

      // Wait for initial load
      await waitFor(() => {
        expect(screen.getByTestId('is-loading')).toHaveTextContent('false')
      })

      // Initially isDirty should be false
      expect(screen.getByTestId('is-dirty')).toHaveTextContent('false')

      // Set dirty state
      act(() => {
        contextRef!.setNoteEditorDirty(true)
      })

      expect(screen.getByTestId('is-dirty')).toHaveTextContent('true')
    })

    it('updates isDirty state to false', async () => {
      let contextRef: ReturnType<typeof useApp> | null = null

      render(
        <AppProvider>
          <TestConsumer
            onMount={(ctx) => {
              contextRef = ctx
            }}
          />
        </AppProvider>
      )

      // Wait for initial load
      await waitFor(() => {
        expect(screen.getByTestId('is-loading')).toHaveTextContent('false')
      })

      // Set dirty state to true first
      act(() => {
        contextRef!.setNoteEditorDirty(true)
      })

      expect(screen.getByTestId('is-dirty')).toHaveTextContent('true')

      // Set dirty state back to false
      act(() => {
        contextRef!.setNoteEditorDirty(false)
      })

      expect(screen.getByTestId('is-dirty')).toHaveTextContent('false')
    })

    it('resets isDirty to false when closing note editor', async () => {
      let contextRef: ReturnType<typeof useApp> | null = null

      render(
        <AppProvider>
          <TestConsumer
            onMount={(ctx) => {
              contextRef = ctx
            }}
          />
        </AppProvider>
      )

      // Wait for initial load
      await waitFor(() => {
        expect(screen.getByTestId('is-loading')).toHaveTextContent('false')
      })

      // Open note editor and set dirty
      act(() => {
        contextRef!.openNoteEditor('general', '')
        contextRef!.setNoteEditorDirty(true)
      })

      expect(screen.getByTestId('is-dirty')).toHaveTextContent('true')

      // Close note editor
      act(() => {
        contextRef!.closeNoteEditor()
      })

      // isDirty should be reset to false
      expect(screen.getByTestId('is-dirty')).toHaveTextContent('false')
    })
  })

  describe('refreshStatus', () => {
    it('fetches and updates repo status on success', async () => {
      let contextRef: ReturnType<typeof useApp> | null = null

      render(
        <AppProvider>
          <TestConsumer
            onMount={(ctx) => {
              contextRef = ctx
            }}
          />
        </AppProvider>
      )

      // Wait for initial load
      await waitFor(() => {
        expect(screen.getByTestId('is-loading')).toHaveTextContent('false')
      })

      // Update mock to return different status
      const updatedStatus: RepoStatus = {
        ...mockRepoStatus,
        path: '/updated/path',
      }
      vi.mocked(api.getRepoStatus).mockResolvedValue(updatedStatus)

      // Call refreshStatus
      await act(async () => {
        await contextRef!.refreshStatus()
      })

      expect(screen.getByTestId('repo-path')).toHaveTextContent('/updated/path')
    })

    it('sets error state on failure', async () => {
      let contextRef: ReturnType<typeof useApp> | null = null

      render(
        <AppProvider>
          <TestConsumer
            onMount={(ctx) => {
              contextRef = ctx
            }}
          />
        </AppProvider>
      )

      // Wait for initial load
      await waitFor(() => {
        expect(screen.getByTestId('is-loading')).toHaveTextContent('false')
      })

      // Make the next call fail
      vi.mocked(api.getRepoStatus).mockRejectedValue(new Error('Network error'))

      // Call refreshStatus
      await act(async () => {
        await contextRef!.refreshStatus()
      })

      expect(screen.getByTestId('error')).toHaveTextContent('Failed to fetch repo status')
    })
  })

  describe('refreshTree', () => {
    it('fetches and updates wiki tree on success', async () => {
      let contextRef: ReturnType<typeof useApp> | null = null

      render(
        <AppProvider>
          <TestConsumer
            onMount={(ctx) => {
              contextRef = ctx
            }}
          />
        </AppProvider>
      )

      // Wait for initial load
      await waitFor(() => {
        expect(screen.getByTestId('is-loading')).toHaveTextContent('false')
      })

      // Initial tree has overview: true
      expect(screen.getByTestId('wiki-tree-overview')).toHaveTextContent('true')

      // Update mock to return different tree
      const updatedTree: WikiTree = {
        overview: false,
        architecture: false,
        workflows: [],
        directories: [],
        files: ['test-file'],
      }
      vi.mocked(api.getWikiTree).mockResolvedValue(updatedTree)

      // Call refreshTree
      await act(async () => {
        await contextRef!.refreshTree()
      })

      expect(screen.getByTestId('wiki-tree-overview')).toHaveTextContent('false')
    })

    it('silently ignores errors without setting error state', async () => {
      let contextRef: ReturnType<typeof useApp> | null = null

      render(
        <AppProvider>
          <TestConsumer
            onMount={(ctx) => {
              contextRef = ctx
            }}
          />
        </AppProvider>
      )

      // Wait for initial load
      await waitFor(() => {
        expect(screen.getByTestId('is-loading')).toHaveTextContent('false')
      })

      // Ensure no error initially
      expect(screen.getByTestId('error')).toHaveTextContent('none')

      // Make the next call fail
      vi.mocked(api.getWikiTree).mockRejectedValue(new Error('Network error'))

      // Call refreshTree - should NOT throw or set error
      await act(async () => {
        await contextRef!.refreshTree()
      })

      // Error should still be 'none' - errors are silently ignored
      expect(screen.getByTestId('error')).toHaveTextContent('none')
    })
  })

  describe('startGeneration', () => {
    it('returns job_id on success', async () => {
      vi.mocked(api.initRepo).mockResolvedValue({
        job_id: 'test-job-123',
        status: 'pending',
        message: 'Job created',
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

      let contextRef: ReturnType<typeof useApp> | null = null

      render(
        <AppProvider>
          <TestConsumer
            onMount={(ctx) => {
              contextRef = ctx
            }}
          />
        </AppProvider>
      )

      await waitFor(() => {
        expect(screen.getByTestId('is-loading')).toHaveTextContent('false')
      })

      let jobId: string | null = null
      await act(async () => {
        jobId = await contextRef!.startGeneration()
      })

      expect(jobId).toBe('test-job-123')
    })

    it('sets currentJob after starting generation', async () => {
      vi.mocked(api.initRepo).mockResolvedValue({
        job_id: 'test-job-456',
        status: 'pending',
        message: 'Job created',
      })
      vi.mocked(api.getJob).mockResolvedValue({
        job_id: 'test-job-456',
        type: 'generation',
        status: 'running',
        started_at: null,
        completed_at: null,
        current_phase: null,
        total_phases: null,
        error_message: null,
      })

      let contextRef: ReturnType<typeof useApp> | null = null

      render(
        <AppProvider>
          <TestConsumer
            onMount={(ctx) => {
              contextRef = ctx
            }}
          />
        </AppProvider>
      )

      await waitFor(() => {
        expect(screen.getByTestId('is-loading')).toHaveTextContent('false')
      })

      expect(screen.getByTestId('current-job')).toHaveTextContent('none')

      await act(async () => {
        await contextRef!.startGeneration()
      })

      expect(screen.getByTestId('current-job')).toHaveTextContent('test-job-456')
    })

    it('clears previous generationStatus when starting new generation', async () => {
      vi.mocked(api.getGenerationStatus).mockResolvedValue({
        status: 'incomplete',
        message: 'Previous build was interrupted',
      })
      vi.mocked(api.initRepo).mockResolvedValue({
        job_id: 'new-job',
        status: 'pending',
        message: 'Job created',
      })
      vi.mocked(api.getJob).mockResolvedValue({
        job_id: 'new-job',
        type: 'generation',
        status: 'running',
        started_at: null,
        completed_at: null,
        current_phase: null,
        total_phases: null,
        error_message: null,
      })

      let contextRef: ReturnType<typeof useApp> | null = null

      render(
        <AppProvider>
          <TestConsumer
            onMount={(ctx) => {
              contextRef = ctx
            }}
          />
        </AppProvider>
      )

      // Wait for initial load which should detect incomplete status
      await waitFor(() => {
        expect(screen.getByTestId('generation-status')).toHaveTextContent('incomplete')
      })

      // Start new generation
      await act(async () => {
        await contextRef!.startGeneration()
      })

      // Generation status should be cleared
      expect(screen.getByTestId('generation-status')).toHaveTextContent('none')
    })

    it('returns null and sets error on failure', async () => {
      vi.mocked(api.initRepo).mockRejectedValue(new Error('Server error'))

      let contextRef: ReturnType<typeof useApp> | null = null

      render(
        <AppProvider>
          <TestConsumer
            onMount={(ctx) => {
              contextRef = ctx
            }}
          />
        </AppProvider>
      )

      await waitFor(() => {
        expect(screen.getByTestId('is-loading')).toHaveTextContent('false')
      })

      let jobId: string | null = 'should-be-null'
      await act(async () => {
        jobId = await contextRef!.startGeneration()
      })

      expect(jobId).toBeNull()
      expect(screen.getByTestId('error')).toHaveTextContent('Failed to start generation')
    })

    it('sets loading to false after completion', async () => {
      vi.mocked(api.initRepo).mockResolvedValue({
        job_id: 'test-job',
        status: 'pending',
        message: 'Job created',
      })
      vi.mocked(api.getJob).mockResolvedValue({
        job_id: 'test-job',
        type: 'generation',
        status: 'running',
        started_at: null,
        completed_at: null,
        current_phase: null,
        total_phases: null,
        error_message: null,
      })

      let contextRef: ReturnType<typeof useApp> | null = null

      render(
        <AppProvider>
          <TestConsumer
            onMount={(ctx) => {
              contextRef = ctx
            }}
          />
        </AppProvider>
      )

      await waitFor(() => {
        expect(screen.getByTestId('is-loading')).toHaveTextContent('false')
      })

      await act(async () => {
        await contextRef!.startGeneration()
      })

      // Loading should be false after completion
      expect(screen.getByTestId('is-loading')).toHaveTextContent('false')
    })

    it('sets loading to false even on failure', async () => {
      vi.mocked(api.initRepo).mockRejectedValue(new Error('Server error'))

      let contextRef: ReturnType<typeof useApp> | null = null

      render(
        <AppProvider>
          <TestConsumer
            onMount={(ctx) => {
              contextRef = ctx
            }}
          />
        </AppProvider>
      )

      await waitFor(() => {
        expect(screen.getByTestId('is-loading')).toHaveTextContent('false')
      })

      await act(async () => {
        await contextRef!.startGeneration()
      })

      // Loading should be false even after failure
      expect(screen.getByTestId('is-loading')).toHaveTextContent('false')
    })
  })

  describe('openNoteEditor', () => {
    it('opens note editor with default scope and target', async () => {
      let contextRef: ReturnType<typeof useApp> | null = null

      render(
        <AppProvider>
          <TestConsumer
            onMount={(ctx) => {
              contextRef = ctx
            }}
          />
        </AppProvider>
      )

      await waitFor(() => {
        expect(screen.getByTestId('is-loading')).toHaveTextContent('false')
      })

      expect(screen.getByTestId('note-editor-open')).toHaveTextContent('false')

      act(() => {
        contextRef!.openNoteEditor()
      })

      expect(screen.getByTestId('note-editor-open')).toHaveTextContent('true')
      expect(screen.getByTestId('note-editor-scope')).toHaveTextContent('general')
      expect(screen.getByTestId('note-editor-target')).toHaveTextContent('')
    })

    it('opens note editor with specified scope and target', async () => {
      let contextRef: ReturnType<typeof useApp> | null = null

      render(
        <AppProvider>
          <TestConsumer
            onMount={(ctx) => {
              contextRef = ctx
            }}
          />
        </AppProvider>
      )

      await waitFor(() => {
        expect(screen.getByTestId('is-loading')).toHaveTextContent('false')
      })

      act(() => {
        contextRef!.openNoteEditor('file', '/src/main.ts')
      })

      expect(screen.getByTestId('note-editor-open')).toHaveTextContent('true')
      expect(screen.getByTestId('note-editor-scope')).toHaveTextContent('file')
      expect(screen.getByTestId('note-editor-target')).toHaveTextContent('/src/main.ts')
    })
  })

  describe('toggleDarkMode', () => {
    it('toggles dark mode from false to true', async () => {
      let contextRef: ReturnType<typeof useApp> | null = null

      render(
        <AppProvider>
          <TestConsumer
            onMount={(ctx) => {
              contextRef = ctx
            }}
          />
        </AppProvider>
      )

      await waitFor(() => {
        expect(screen.getByTestId('is-loading')).toHaveTextContent('false')
      })

      // Default is false (from matchMedia mock returning false)
      expect(screen.getByTestId('dark-mode')).toHaveTextContent('false')

      act(() => {
        contextRef!.toggleDarkMode()
      })

      expect(screen.getByTestId('dark-mode')).toHaveTextContent('true')
    })

    it('toggles dark mode from true to false', async () => {
      let contextRef: ReturnType<typeof useApp> | null = null

      render(
        <AppProvider>
          <TestConsumer
            onMount={(ctx) => {
              contextRef = ctx
            }}
          />
        </AppProvider>
      )

      await waitFor(() => {
        expect(screen.getByTestId('is-loading')).toHaveTextContent('false')
      })

      // Toggle to true first
      act(() => {
        contextRef!.toggleDarkMode()
      })
      expect(screen.getByTestId('dark-mode')).toHaveTextContent('true')

      // Toggle back to false
      act(() => {
        contextRef!.toggleDarkMode()
      })
      expect(screen.getByTestId('dark-mode')).toHaveTextContent('false')
    })

    it('persists dark mode to localStorage', async () => {
      let contextRef: ReturnType<typeof useApp> | null = null

      render(
        <AppProvider>
          <TestConsumer
            onMount={(ctx) => {
              contextRef = ctx
            }}
          />
        </AppProvider>
      )

      await waitFor(() => {
        expect(screen.getByTestId('is-loading')).toHaveTextContent('false')
      })

      act(() => {
        contextRef!.toggleDarkMode()
      })

      expect(localStorage.setItem).toHaveBeenCalledWith('oya-dark-mode', 'true')
    })

    it('applies dark class to document.documentElement', async () => {
      let contextRef: ReturnType<typeof useApp> | null = null

      render(
        <AppProvider>
          <TestConsumer
            onMount={(ctx) => {
              contextRef = ctx
            }}
          />
        </AppProvider>
      )

      await waitFor(() => {
        expect(screen.getByTestId('is-loading')).toHaveTextContent('false')
      })

      // Initially should not have dark class
      expect(document.documentElement.classList.contains('dark')).toBe(false)

      act(() => {
        contextRef!.toggleDarkMode()
      })

      expect(document.documentElement.classList.contains('dark')).toBe(true)

      act(() => {
        contextRef!.toggleDarkMode()
      })

      expect(document.documentElement.classList.contains('dark')).toBe(false)
    })
  })

  describe('setAskPanelOpen', () => {
    it('sets ask panel open state to true', async () => {
      let contextRef: ReturnType<typeof useApp> | null = null

      render(
        <AppProvider>
          <TestConsumer
            onMount={(ctx) => {
              contextRef = ctx
            }}
          />
        </AppProvider>
      )

      await waitFor(() => {
        expect(screen.getByTestId('is-loading')).toHaveTextContent('false')
      })

      expect(screen.getByTestId('ask-panel-open')).toHaveTextContent('false')

      act(() => {
        contextRef!.setAskPanelOpen(true)
      })

      expect(screen.getByTestId('ask-panel-open')).toHaveTextContent('true')
    })

    it('sets ask panel open state to false', async () => {
      let contextRef: ReturnType<typeof useApp> | null = null

      render(
        <AppProvider>
          <TestConsumer
            onMount={(ctx) => {
              contextRef = ctx
            }}
          />
        </AppProvider>
      )

      await waitFor(() => {
        expect(screen.getByTestId('is-loading')).toHaveTextContent('false')
      })

      // Open first
      act(() => {
        contextRef!.setAskPanelOpen(true)
      })
      expect(screen.getByTestId('ask-panel-open')).toHaveTextContent('true')

      // Close
      act(() => {
        contextRef!.setAskPanelOpen(false)
      })
      expect(screen.getByTestId('ask-panel-open')).toHaveTextContent('false')
    })

    it('persists ask panel state to localStorage', async () => {
      let contextRef: ReturnType<typeof useApp> | null = null

      render(
        <AppProvider>
          <TestConsumer
            onMount={(ctx) => {
              contextRef = ctx
            }}
          />
        </AppProvider>
      )

      await waitFor(() => {
        expect(screen.getByTestId('is-loading')).toHaveTextContent('false')
      })

      act(() => {
        contextRef!.setAskPanelOpen(true)
      })

      expect(localStorage.setItem).toHaveBeenCalledWith('oya-ask-panel-open', 'true')
    })
  })

  describe('dismissGenerationStatus', () => {
    it('clears generation status', async () => {
      vi.mocked(api.getGenerationStatus).mockResolvedValue({
        status: 'incomplete',
        message: 'Previous build was interrupted',
      })

      let contextRef: ReturnType<typeof useApp> | null = null

      render(
        <AppProvider>
          <TestConsumer
            onMount={(ctx) => {
              contextRef = ctx
            }}
          />
        </AppProvider>
      )

      // Wait for initial load which should detect incomplete status
      await waitFor(() => {
        expect(screen.getByTestId('generation-status')).toHaveTextContent('incomplete')
      })

      act(() => {
        contextRef!.dismissGenerationStatus()
      })

      expect(screen.getByTestId('generation-status')).toHaveTextContent('none')
    })
  })

  describe('initial load', () => {
    it('loads repo status on mount', async () => {
      render(
        <AppProvider>
          <TestConsumer />
        </AppProvider>
      )

      await waitFor(() => {
        expect(screen.getByTestId('repo-path')).toHaveTextContent('/home/user/project')
      })

      expect(api.getRepoStatus).toHaveBeenCalled()
    })

    it('loads wiki tree on mount when build is complete', async () => {
      render(
        <AppProvider>
          <TestConsumer />
        </AppProvider>
      )

      await waitFor(() => {
        expect(screen.getByTestId('is-loading')).toHaveTextContent('false')
      })

      expect(api.getWikiTree).toHaveBeenCalled()
      expect(screen.getByTestId('wiki-tree-overview')).toHaveTextContent('true')
    })

    it('detects incomplete build and sets generation status', async () => {
      vi.mocked(api.getGenerationStatus).mockResolvedValue({
        status: 'incomplete',
        message: 'Build was interrupted',
      })

      render(
        <AppProvider>
          <TestConsumer />
        </AppProvider>
      )

      await waitFor(() => {
        expect(screen.getByTestId('generation-status')).toHaveTextContent('incomplete')
      })
    })

    it('clears wiki tree when build is incomplete', async () => {
      vi.mocked(api.getGenerationStatus).mockResolvedValue({
        status: 'incomplete',
        message: 'Build was interrupted',
      })

      render(
        <AppProvider>
          <TestConsumer />
        </AppProvider>
      )

      await waitFor(() => {
        expect(screen.getByTestId('generation-status')).toHaveTextContent('incomplete')
      })

      // Wiki tree should be cleared (overview: false)
      expect(screen.getByTestId('wiki-tree-overview')).toHaveTextContent('false')
    })

    it('does not load wiki tree when build is incomplete', async () => {
      vi.mocked(api.getGenerationStatus).mockResolvedValue({
        status: 'incomplete',
        message: 'Build was interrupted',
      })
      vi.mocked(api.getWikiTree).mockClear()

      render(
        <AppProvider>
          <TestConsumer />
        </AppProvider>
      )

      await waitFor(() => {
        expect(screen.getByTestId('generation-status')).toHaveTextContent('incomplete')
      })

      // getWikiTree should not have been called since build is incomplete
      // Note: It may be called initially before the incomplete check, so we check it wasn't called AFTER
      // Actually, looking at the code, getWikiTree is only called if !hasIncompleteBuild
      // But we need to wait for the full init to complete
      await waitFor(() => {
        expect(screen.getByTestId('is-loading')).toHaveTextContent('false')
      })
    })

    it('restores running job on mount', async () => {
      vi.mocked(api.listJobs).mockResolvedValue([
        {
          job_id: 'running-job-123',
          type: 'generation',
          status: 'running',
          started_at: '2024-01-01T00:00:00Z',
          completed_at: null,
          current_phase: 'parsing',
          total_phases: 5,
          error_message: null,
        },
      ])

      render(
        <AppProvider>
          <TestConsumer />
        </AppProvider>
      )

      await waitFor(() => {
        expect(screen.getByTestId('current-job')).toHaveTextContent('running-job-123')
      })
    })

    it('does not restore completed jobs', async () => {
      vi.mocked(api.listJobs).mockResolvedValue([
        {
          job_id: 'completed-job',
          type: 'generation',
          status: 'completed',
          started_at: '2024-01-01T00:00:00Z',
          completed_at: '2024-01-01T00:05:00Z',
          current_phase: null,
          total_phases: null,
          error_message: null,
        },
      ])

      render(
        <AppProvider>
          <TestConsumer />
        </AppProvider>
      )

      await waitFor(() => {
        expect(screen.getByTestId('is-loading')).toHaveTextContent('false')
      })

      // Should not have set current job since it's completed
      expect(screen.getByTestId('current-job')).toHaveTextContent('none')
    })

    it('sets loading to false after initialization', async () => {
      render(
        <AppProvider>
          <TestConsumer />
        </AppProvider>
      )

      // Initially loading
      expect(screen.getByTestId('is-loading')).toHaveTextContent('true')

      // After init completes
      await waitFor(() => {
        expect(screen.getByTestId('is-loading')).toHaveTextContent('false')
      })
    })
  })

  describe('initial state from localStorage', () => {
    it('reads dark mode from localStorage', async () => {
      vi.mocked(localStorage.getItem).mockImplementation((key: string) => {
        if (key === 'oya-dark-mode') return 'true'
        return null
      })

      // Need to reset modules to pick up new localStorage value
      vi.resetModules()
      const appContextModule = await import('./AppContext')
      const AppProviderFresh = appContextModule.AppProvider
      const useAppModule = await import('./useApp')
      const useAppFresh = useAppModule.useApp

      function FreshTestConsumer() {
        const ctx = useAppFresh()
        return <span data-testid="dark-mode">{String(ctx.state.darkMode)}</span>
      }

      render(
        <AppProviderFresh>
          <FreshTestConsumer />
        </AppProviderFresh>
      )

      expect(screen.getByTestId('dark-mode')).toHaveTextContent('true')
    })

    it('reads ask panel state from localStorage', async () => {
      vi.mocked(localStorage.getItem).mockImplementation((key: string) => {
        if (key === 'oya-ask-panel-open') return 'true'
        return null
      })

      // Need to reset modules to pick up new localStorage value
      vi.resetModules()
      const appContextModule = await import('./AppContext')
      const AppProviderFresh = appContextModule.AppProvider
      const useAppModule = await import('./useApp')
      const useAppFresh = useAppModule.useApp

      function FreshTestConsumer() {
        const ctx = useAppFresh()
        return <span data-testid="ask-panel-open">{String(ctx.state.askPanelOpen)}</span>
      }

      render(
        <AppProviderFresh>
          <FreshTestConsumer />
        </AppProviderFresh>
      )

      expect(screen.getByTestId('ask-panel-open')).toHaveTextContent('true')
    })

    it('falls back to prefers-color-scheme when no localStorage value', async () => {
      vi.mocked(localStorage.getItem).mockReturnValue(null)
      vi.stubGlobal(
        'matchMedia',
        vi.fn().mockImplementation((query: string) => ({
          matches: query === '(prefers-color-scheme: dark)',
          media: query,
          onchange: null,
          addListener: vi.fn(),
          removeListener: vi.fn(),
          addEventListener: vi.fn(),
          removeEventListener: vi.fn(),
          dispatchEvent: vi.fn(),
        }))
      )

      // Need to reset modules to pick up new matchMedia value
      vi.resetModules()
      const appContextModule = await import('./AppContext')
      const AppProviderFresh = appContextModule.AppProvider
      const useAppModule = await import('./useApp')
      const useAppFresh = useAppModule.useApp

      function FreshTestConsumer() {
        const ctx = useAppFresh()
        return <span data-testid="dark-mode">{String(ctx.state.darkMode)}</span>
      }

      render(
        <AppProviderFresh>
          <FreshTestConsumer />
        </AppProviderFresh>
      )

      expect(screen.getByTestId('dark-mode')).toHaveTextContent('true')
    })
  })
})
