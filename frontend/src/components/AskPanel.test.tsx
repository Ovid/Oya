import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import type { RepoStatus, WikiTree, JobStatus } from '../types'

// Mock the API module - must be before imports that use it
vi.mock('../api/client', () => ({
  getRepoStatus: vi.fn(),
  getWikiTree: vi.fn(),
  switchWorkspace: vi.fn(),
  listDirectories: vi.fn(),
  initRepo: vi.fn(),
  getJob: vi.fn(),
  listJobs: vi.fn(),
  getGenerationStatus: vi.fn(),
  askQuestionStream: vi.fn(),
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

  // Mock scrollIntoView
  Element.prototype.scrollIntoView = vi.fn()
})

// Dynamic import to ensure mocks are set up first
let AskPanel: typeof import('./AskPanel').AskPanel
let AppContext: typeof import('../context/AppContext').AppContext
let api: typeof import('../api/client')

beforeEach(async () => {
  vi.resetModules()
  const askPanelModule = await import('./AskPanel')
  AskPanel = askPanelModule.AskPanel
  const appContextModule = await import('../context/AppContext')
  AppContext = appContextModule.AppContext
  api = await import('../api/client')
  vi.clearAllMocks()
})

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

const mockRunningJob: JobStatus = {
  job_id: 'job-123',
  type: 'generation',
  status: 'running',
  started_at: null,
  completed_at: null,
  current_phase: null,
  total_phases: null,
  error_message: null,
}

const mockCompletedJob: JobStatus = {
  job_id: 'job-123',
  type: 'generation',
  status: 'completed',
  started_at: '2024-01-01T00:00:00Z',
  completed_at: '2024-01-01T00:05:00Z',
  current_phase: null,
  total_phases: null,
  error_message: null,
}

function renderAskPanel(props = {}, contextOverrides: { currentJob?: JobStatus | null } = {}) {
  const defaultProps = {
    isOpen: true,
    onClose: vi.fn(),
    ...props,
  }

  // Create a wrapper that provides context with optional overrides
  const mockContextValue = {
    state: {
      repoStatus: mockRepoStatus,
      wikiTree: mockWikiTree,
      currentPage: null,
      currentJob: contextOverrides.currentJob !== undefined ? contextOverrides.currentJob : null,
      isLoading: false,
      error: null,
      noteEditor: {
        isOpen: false,
        isDirty: false,
        defaultScope: 'general' as const,
        defaultTarget: '',
      },
      darkMode: false,
      generationStatus: null,
      askPanelOpen: true,
    },
    dispatch: vi.fn(),
    refreshStatus: vi.fn(),
    refreshTree: vi.fn(),
    startGeneration: vi.fn(),
    openNoteEditor: vi.fn(),
    closeNoteEditor: vi.fn(),
    toggleDarkMode: vi.fn(),
    switchWorkspace: vi.fn(),
    setNoteEditorDirty: vi.fn(),
    dismissGenerationStatus: vi.fn(),
    setAskPanelOpen: vi.fn(),
  }

  return render(
    <MemoryRouter>
      <AppContext.Provider value={mockContextValue}>
        <AskPanel {...defaultProps} />
      </AppContext.Provider>
    </MemoryRouter>
  )
}

describe('AskPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(api.getRepoStatus).mockResolvedValue(mockRepoStatus)
    vi.mocked(api.getWikiTree).mockResolvedValue(mockWikiTree)
    vi.mocked(api.listJobs).mockResolvedValue([])
    vi.mocked(api.getGenerationStatus).mockResolvedValue(null)
  })

  describe('basic rendering', () => {
    it('renders when isOpen is true', async () => {
      renderAskPanel({ isOpen: true })

      await waitFor(() => {
        expect(screen.getByText('Ask about this codebase')).toBeInTheDocument()
      })
    })

    it('does not render when isOpen is false', async () => {
      renderAskPanel({ isOpen: false })

      expect(screen.queryByText('Ask about this codebase')).not.toBeInTheDocument()
    })

    it('renders input field', async () => {
      renderAskPanel({ isOpen: true })

      await waitFor(() => {
        expect(screen.getByPlaceholderText('Ask a question...')).toBeInTheDocument()
      })
    })

    it('renders Ask button', async () => {
      renderAskPanel({ isOpen: true })

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /ask/i })).toBeInTheDocument()
      })
    })
  })

  describe('during generation', () => {
    it('shows disabled banner when generation is running', async () => {
      renderAskPanel({ isOpen: true }, { currentJob: mockRunningJob })

      await waitFor(() => {
        expect(
          screen.getByText('Q&A is unavailable while the wiki is being generated.')
        ).toBeInTheDocument()
      })
    })

    it('disables input field during generation', async () => {
      renderAskPanel({ isOpen: true }, { currentJob: mockRunningJob })

      await waitFor(() => {
        const input = screen.getByPlaceholderText('Ask a question...')
        expect(input).toBeDisabled()
      })
    })

    it('disables submit button during generation', async () => {
      renderAskPanel({ isOpen: true }, { currentJob: mockRunningJob })

      await waitFor(() => {
        const submitButton = screen.getByRole('button', { name: /ask/i })
        expect(submitButton).toBeDisabled()
      })
    })

    it('does not show disabled banner when generation is not running', async () => {
      renderAskPanel({ isOpen: true }, { currentJob: null })

      await waitFor(() => {
        expect(
          screen.queryByText('Q&A is unavailable while the wiki is being generated.')
        ).not.toBeInTheDocument()
      })
    })

    it('does not show disabled banner when job is completed', async () => {
      renderAskPanel({ isOpen: true }, { currentJob: mockCompletedJob })

      await waitFor(() => {
        expect(
          screen.queryByText('Q&A is unavailable while the wiki is being generated.')
        ).not.toBeInTheDocument()
      })
    })

    it('enables input field when generation is not running', async () => {
      renderAskPanel({ isOpen: true }, { currentJob: null })

      await waitFor(() => {
        const input = screen.getByPlaceholderText('Ask a question...')
        expect(input).not.toBeDisabled()
      })
    })
  })
})
