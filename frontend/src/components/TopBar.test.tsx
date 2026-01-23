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
  updateOyaignore: vi.fn(),
  ApiError: class ApiError extends Error {
    status: number
    constructor(status: number, message: string) {
      super(message)
      this.name = 'ApiError'
      this.status = status
    }
  },
}))

import { TopBar } from './TopBar'
import { useWikiStore, useGenerationStore, useUIStore, useNoteEditorStore } from '../stores'
import { initialState as wikiInitial } from '../stores/wikiStore'
import { initialState as genInitial } from '../stores/generationStore'
import { initialState as uiInitial } from '../stores/uiStore'
import { initialState as noteInitial } from '../stores/noteEditorStore'
import * as api from '../api/client'

beforeEach(() => {
  vi.clearAllMocks()

  // Reset stores to initial state
  useWikiStore.setState(wikiInitial)
  useGenerationStore.setState(genInitial)
  useUIStore.setState(uiInitial)
  useNoteEditorStore.setState(noteInitial)
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

  return render(<TopBar {...defaultProps} />)
}

describe('TopBar with DirectoryPicker', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(api.getRepoStatus).mockResolvedValue(mockRepoStatus)
    vi.mocked(api.getWikiTree).mockResolvedValue(mockWikiTree)
    vi.mocked(api.listDirectories).mockResolvedValue(mockDirectoryListing)

    // Set up store state directly
    useWikiStore.setState({
      repoStatus: mockRepoStatus,
      wikiTree: mockWikiTree,
      isLoading: false,
      error: null,
    })
  })

  describe('DirectoryPicker rendering', () => {
    it('renders DirectoryPicker component', async () => {
      renderTopBar()

      // DirectoryPicker should be rendered showing the current path
      expect(screen.getByLabelText(/Current workspace/i)).toBeInTheDocument()
    })

    it('displays current workspace path from repoStatus', async () => {
      renderTopBar()

      // The path should be visible in the DirectoryPicker
      expect(screen.getByText('/home/user/project')).toBeInTheDocument()
    })
  })

  describe('disabled during generation', () => {
    it('disables DirectoryPicker when generation job is running', async () => {
      // Set up store state with a running job
      useGenerationStore.setState({
        currentJob: {
          job_id: 'job-123',
          type: 'generation',
          status: 'running',
          started_at: null,
          completed_at: null,
          current_phase: null,
          total_phases: null,
          error_message: null,
        },
      })

      renderTopBar()

      // DirectoryPicker should be disabled
      const picker = screen.getByLabelText(/Current workspace/i)
      expect(picker).toBeDisabled()
    })

    it('shows disabled reason when generation is in progress', async () => {
      // Set up store state with a running job
      useGenerationStore.setState({
        currentJob: {
          job_id: 'job-123',
          type: 'generation',
          status: 'running',
          started_at: null,
          completed_at: null,
          current_phase: null,
          total_phases: null,
          error_message: null,
        },
      })

      renderTopBar()

      // Should show disabled reason
      expect(screen.getByTitle(/Cannot switch during generation/i)).toBeInTheDocument()
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

      // Set note editor as dirty directly in the store
      useNoteEditorStore.setState({ isDirty: true })

      renderTopBar()

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

      // Set note editor as dirty directly in the store
      useNoteEditorStore.setState({ isDirty: true })

      renderTopBar()

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

describe('Generate Wiki Button', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(api.getRepoStatus).mockResolvedValue(mockRepoStatus)
    vi.mocked(api.getWikiTree).mockResolvedValue(mockWikiTree)
    vi.mocked(api.listDirectories).mockResolvedValue(mockDirectoryListing)
    vi.mocked(api.getIndexableItems).mockResolvedValue({
      included: {
        directories: ['src', 'tests'],
        files: ['src/main.ts', 'tests/test.ts'],
      },
      excluded_by_oyaignore: {
        directories: [],
        files: [],
      },
      excluded_by_rule: {
        directories: [],
        files: [],
      },
    })

    // Set up store state directly
    useWikiStore.setState({
      repoStatus: mockRepoStatus,
      wikiTree: mockWikiTree,
      isLoading: false,
      error: null,
    })
  })

  it('renders Generate Wiki button when no generation is in progress', async () => {
    renderTopBar()

    // Generate Wiki button should be visible
    expect(screen.getByRole('button', { name: /generate wiki/i })).toBeInTheDocument()
  })

  it('does not render Preview button (consolidated into Generate Wiki)', async () => {
    renderTopBar()

    // Preview button should NOT exist
    expect(screen.queryByRole('button', { name: /^preview$/i })).not.toBeInTheDocument()
  })

  it('does not render Regenerate button (consolidated into Generate Wiki)', async () => {
    renderTopBar()

    // Regenerate button should NOT exist
    expect(screen.queryByRole('button', { name: /regenerate/i })).not.toBeInTheDocument()
  })

  it('opens IndexingPreviewModal when Generate Wiki button is clicked', async () => {
    renderTopBar()

    // Click Generate Wiki button
    const generateButton = screen.getByRole('button', { name: /generate wiki/i })
    await userEvent.click(generateButton)

    // Modal should be open
    await waitFor(() => {
      expect(screen.getByText('Indexing Preview')).toBeInTheDocument()
    })
  })

  it('hides Generate Wiki button when generation job is running', async () => {
    // Set up store state with a running job
    useGenerationStore.setState({
      currentJob: {
        job_id: 'job-123',
        type: 'generation',
        status: 'running',
        started_at: null,
        completed_at: null,
        current_phase: null,
        total_phases: null,
        error_message: null,
      },
    })

    renderTopBar()

    // The TopBar Generate Wiki button should be hidden because currentJob is set
    const generateButtons = screen.queryAllByRole('button', { name: /generate wiki/i })
    expect(generateButtons).toHaveLength(0)
  })
})

describe('Ask button during generation', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(api.getRepoStatus).mockResolvedValue(mockRepoStatus)
    vi.mocked(api.getWikiTree).mockResolvedValue(mockWikiTree)
    vi.mocked(api.listDirectories).mockResolvedValue(mockDirectoryListing)

    // Set up store state directly
    useWikiStore.setState({
      repoStatus: mockRepoStatus,
      wikiTree: mockWikiTree,
      isLoading: false,
      error: null,
    })
  })

  it('disables Ask button when generation is running', async () => {
    // Set up store state with a running job
    useGenerationStore.setState({
      currentJob: {
        job_id: 'job-123',
        type: 'generation',
        status: 'running',
        started_at: null,
        completed_at: null,
        current_phase: null,
        total_phases: null,
        error_message: null,
      },
    })

    renderTopBar()

    // Ask button should be disabled
    const askButton = screen.getByRole('button', { name: /ask/i })
    expect(askButton).toBeDisabled()
    expect(askButton).toHaveAttribute('title', 'Q&A unavailable during generation')
  })

  it('enables Ask button when no generation is running', async () => {
    renderTopBar()

    const askButton = screen.getByRole('button', { name: /ask/i })
    expect(askButton).not.toBeDisabled()
    expect(askButton).toHaveAttribute('title', 'Ask about the codebase')
  })
})
