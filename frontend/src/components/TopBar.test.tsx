import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { RepoStatus, WikiTree } from '../types'

// Mock the API module - must be before imports that use it
vi.mock('../api/client', () => ({
  getRepoStatus: vi.fn(),
  getWikiTree: vi.fn(),
  switchWorkspace: vi.fn(),
  listDirectories: vi.fn(),
  initRepo: vi.fn(),
  getJob: vi.fn(),
  getIndexableItems: vi.fn(),
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
let TopBar: typeof import('./TopBar').TopBar
let AppProvider: typeof import('../context/AppContext').AppProvider
let useApp: typeof import('../context/useApp').useApp
let api: typeof import('../api/client')

beforeEach(async () => {
  vi.resetModules()
  const topBarModule = await import('./TopBar')
  TopBar = topBarModule.TopBar
  const appContextModule = await import('../context/AppContext')
  AppProvider = appContextModule.AppProvider
  const useAppModule = await import('../context/useApp')
  useApp = useAppModule.useApp
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

const mockDirectoryListing = {
  path: '/home/user',
  parent: '/home',
  entries: [
    { name: 'project', path: '/home/user/project', is_dir: true },
    { name: 'other', path: '/home/user/other', is_dir: true },
  ],
}

function renderTopBar(props = {}) {
  const defaultProps = {
    onToggleSidebar: vi.fn(),
    onToggleRightSidebar: vi.fn(),
    onToggleAskPanel: vi.fn(),
    askPanelOpen: false,
    ...props,
  }

  return render(
    <AppProvider>
      <TopBar {...defaultProps} />
    </AppProvider>
  )
}

describe('TopBar with DirectoryPicker', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(api.getRepoStatus).mockResolvedValue(mockRepoStatus)
    vi.mocked(api.getWikiTree).mockResolvedValue(mockWikiTree)
    vi.mocked(api.listDirectories).mockResolvedValue(mockDirectoryListing)
  })

  describe('DirectoryPicker rendering', () => {
    it('renders DirectoryPicker component', async () => {
      renderTopBar()

      // Wait for initial load to complete
      await waitFor(() => {
        expect(screen.queryByText('Loading...')).not.toBeInTheDocument()
      })

      // DirectoryPicker should be rendered showing the current path
      expect(screen.getByLabelText(/Current workspace/i)).toBeInTheDocument()
    })

    it('displays current workspace path from repoStatus', async () => {
      renderTopBar()

      await waitFor(() => {
        expect(screen.queryByText('Loading...')).not.toBeInTheDocument()
      })

      // The path should be visible in the DirectoryPicker
      expect(screen.getByText('/home/user/project')).toBeInTheDocument()
    })
  })

  describe('disabled during generation', () => {
    it('disables DirectoryPicker when generation job is running', async () => {
      vi.mocked(api.getRepoStatus).mockResolvedValue({
        ...mockRepoStatus,
        initialized: false,
      })
      vi.mocked(api.initRepo).mockResolvedValue({
        job_id: 'job-123',
        status: 'pending',
        message: 'Job created',
      })
      vi.mocked(api.getJob).mockResolvedValue({
        job_id: 'job-123',
        type: 'generation',
        status: 'running',
        started_at: null,
        completed_at: null,
        current_phase: null,
        total_phases: null,
        error_message: null,
      })

      renderTopBar()

      await waitFor(() => {
        expect(screen.queryByText('Loading...')).not.toBeInTheDocument()
      })

      // Start generation
      const generateButton = screen.getByText('Generate Wiki')
      await userEvent.click(generateButton)

      // DirectoryPicker should be disabled
      await waitFor(() => {
        const picker = screen.getByLabelText(/Current workspace/i)
        expect(picker).toBeDisabled()
      })
    })

    it('shows disabled reason when generation is in progress', async () => {
      vi.mocked(api.getRepoStatus).mockResolvedValue({
        ...mockRepoStatus,
        initialized: false,
      })
      vi.mocked(api.initRepo).mockResolvedValue({
        job_id: 'job-123',
        status: 'pending',
        message: 'Job created',
      })
      vi.mocked(api.getJob).mockResolvedValue({
        job_id: 'job-123',
        type: 'generation',
        status: 'running',
        started_at: null,
        completed_at: null,
        current_phase: null,
        total_phases: null,
        error_message: null,
      })

      renderTopBar()

      await waitFor(() => {
        expect(screen.queryByText('Loading...')).not.toBeInTheDocument()
      })

      // Start generation
      const generateButton = screen.getByText('Generate Wiki')
      await userEvent.click(generateButton)

      // Should show disabled reason
      await waitFor(() => {
        expect(screen.getByTitle(/Cannot switch during generation/i)).toBeInTheDocument()
      })
    })
  })

  describe('unsaved changes confirmation', () => {
    it('prompts for confirmation when noteEditor.isDirty is true and switching workspace', async () => {
      // Mock window.confirm
      const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false)

      vi.mocked(api.switchWorkspace).mockResolvedValue({
        status: { ...mockRepoStatus, path: '/home/user/other' },
        message: 'Workspace switched',
      })

      // Create a test component that can set dirty state
      function TestWrapper() {
        const { setNoteEditorDirty } = useApp()
        return (
          <>
            <button onClick={() => setNoteEditorDirty(true)} data-testid="set-dirty">
              Set Dirty
            </button>
            <TopBar
              onToggleSidebar={vi.fn()}
              onToggleRightSidebar={vi.fn()}
              onToggleAskPanel={vi.fn()}
              askPanelOpen={false}
            />
          </>
        )
      }

      render(
        <AppProvider>
          <TestWrapper />
        </AppProvider>
      )

      await waitFor(() => {
        expect(screen.queryByText('Loading...')).not.toBeInTheDocument()
      })

      // Set the note editor as dirty
      const setDirtyButton = screen.getByTestId('set-dirty')
      await userEvent.click(setDirtyButton)

      // Click on the DirectoryPicker to open modal
      const picker = screen.getByLabelText(/Current workspace/i)
      await userEvent.click(picker)

      // Wait for modal to open and directories to load
      await waitFor(() => {
        expect(screen.getByText('Select Workspace')).toBeInTheDocument()
      })

      // Navigate to a different directory
      await userEvent.click(screen.getByText('other'))

      // Wait for navigation
      await waitFor(() => {
        expect(api.listDirectories).toHaveBeenCalledWith('/home/user/other')
      })

      // Click Select to switch
      await userEvent.click(screen.getByText('Select'))

      // Confirmation dialog should have been shown
      expect(confirmSpy).toHaveBeenCalledWith(
        'You have unsaved changes. Are you sure you want to switch workspaces?'
      )

      // Since we returned false, the switch should not have happened
      expect(api.switchWorkspace).not.toHaveBeenCalled()

      confirmSpy.mockRestore()
    })

    it('proceeds with switch when user confirms', async () => {
      // Mock window.confirm to return true
      const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true)

      vi.mocked(api.switchWorkspace).mockResolvedValue({
        status: { ...mockRepoStatus, path: '/home/user/other' },
        message: 'Workspace switched',
      })

      // Create a test component that can set dirty state
      function TestWrapper() {
        const { setNoteEditorDirty } = useApp()
        return (
          <>
            <button onClick={() => setNoteEditorDirty(true)} data-testid="set-dirty">
              Set Dirty
            </button>
            <TopBar
              onToggleSidebar={vi.fn()}
              onToggleRightSidebar={vi.fn()}
              onToggleAskPanel={vi.fn()}
              askPanelOpen={false}
            />
          </>
        )
      }

      render(
        <AppProvider>
          <TestWrapper />
        </AppProvider>
      )

      await waitFor(() => {
        expect(screen.queryByText('Loading...')).not.toBeInTheDocument()
      })

      // Set the note editor as dirty
      const setDirtyButton = screen.getByTestId('set-dirty')
      await userEvent.click(setDirtyButton)

      // Click on the DirectoryPicker to open modal
      const picker = screen.getByLabelText(/Current workspace/i)
      await userEvent.click(picker)

      // Wait for modal to open
      await waitFor(() => {
        expect(screen.getByText('Select Workspace')).toBeInTheDocument()
      })

      // Click Select to switch (using current browsed path)
      await userEvent.click(screen.getByText('Select'))

      // Confirmation dialog should have been shown
      expect(confirmSpy).toHaveBeenCalled()

      // Since we returned true, the switch should have happened
      await waitFor(() => {
        expect(api.switchWorkspace).toHaveBeenCalled()
      })

      confirmSpy.mockRestore()
    })
  })
})

describe('Preview Button', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(api.getRepoStatus).mockResolvedValue(mockRepoStatus)
    vi.mocked(api.getWikiTree).mockResolvedValue(mockWikiTree)
    vi.mocked(api.listDirectories).mockResolvedValue(mockDirectoryListing)
    vi.mocked(api.getIndexableItems).mockResolvedValue({
      directories: ['src', 'tests'],
      files: ['src/main.ts', 'tests/test.ts'],
      total_directories: 2,
      total_files: 2,
    })
  })

  it('renders Preview button when no generation is in progress', async () => {
    renderTopBar()

    await waitFor(() => {
      expect(screen.queryByText('Loading...')).not.toBeInTheDocument()
    })

    // Preview button should be visible
    expect(screen.getByRole('button', { name: /preview/i })).toBeInTheDocument()
  })

  it('disables Preview button during generation', async () => {
    vi.mocked(api.getRepoStatus).mockResolvedValue({
      ...mockRepoStatus,
      initialized: false,
    })
    vi.mocked(api.initRepo).mockResolvedValue({
      job_id: 'job-123',
      status: 'pending',
      message: 'Job created',
    })
    vi.mocked(api.getJob).mockResolvedValue({
      job_id: 'job-123',
      type: 'generation',
      status: 'running',
      started_at: null,
      completed_at: null,
      current_phase: null,
      total_phases: null,
      error_message: null,
    })

    renderTopBar()

    await waitFor(() => {
      expect(screen.queryByText('Loading...')).not.toBeInTheDocument()
    })

    // Start generation
    const generateButton = screen.getByText('Generate Wiki')
    await userEvent.click(generateButton)

    // Preview button should be disabled
    await waitFor(() => {
      const previewButton = screen.getByRole('button', { name: /preview/i })
      expect(previewButton).toBeDisabled()
    })
  })

  it('opens IndexingPreviewModal when Preview button is clicked', async () => {
    renderTopBar()

    await waitFor(() => {
      expect(screen.queryByText('Loading...')).not.toBeInTheDocument()
    })

    // Click Preview button
    const previewButton = screen.getByRole('button', { name: /preview/i })
    await userEvent.click(previewButton)

    // Modal should be open
    await waitFor(() => {
      expect(screen.getByText('Indexing Preview')).toBeInTheDocument()
    })
  })
})
