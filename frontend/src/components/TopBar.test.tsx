import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { RepoStatus, WikiTree } from '../types'

// Mock the API module - must be before imports that use it
vi.mock('../api/client', () => ({
  getRepoStatus: vi.fn(),
  getWikiTree: vi.fn(),
  getIndexableItems: vi.fn(),
  updateOyaignore: vi.fn(),
  getLogs: vi.fn(),
  deleteLogs: vi.fn(),
}))

import { TopBar } from './TopBar'
import { useWikiStore, useGenerationStore, useUIStore, useReposStore } from '../stores'
import { initialState as wikiInitial } from '../stores/wikiStore'
import { initialState as genInitial } from '../stores/generationStore'
import { initialState as uiInitial } from '../stores/uiStore'
import { initialState as reposInitial } from '../stores/reposStore'
import * as api from '../api/client'

beforeEach(() => {
  vi.clearAllMocks()

  // Reset stores to initial state
  useWikiStore.setState(wikiInitial)
  useGenerationStore.setState(genInitial)
  useUIStore.setState(uiInitial)
  useReposStore.setState(reposInitial)
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

describe('Generate Wiki Button', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(api.getRepoStatus).mockResolvedValue(mockRepoStatus)
    vi.mocked(api.getWikiTree).mockResolvedValue(mockWikiTree)
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

describe('pending job status handling', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(api.getRepoStatus).mockResolvedValue(mockRepoStatus)
    vi.mocked(api.getWikiTree).mockResolvedValue(mockWikiTree)

    useWikiStore.setState({
      repoStatus: mockRepoStatus,
      wikiTree: mockWikiTree,
      isLoading: false,
      error: null,
    })
  })

  it('disables Ask button when job is pending', async () => {
    useGenerationStore.setState({
      currentJob: {
        job_id: 'job-123',
        type: 'generation',
        status: 'pending',
        started_at: null,
        completed_at: null,
        current_phase: null,
        total_phases: null,
        error_message: null,
      },
    })

    renderTopBar()

    const askButton = screen.getByRole('button', { name: /ask/i })
    expect(askButton).toBeDisabled()
  })

  it('hides Generate Wiki button when job is pending', async () => {
    useGenerationStore.setState({
      currentJob: {
        job_id: 'job-123',
        type: 'generation',
        status: 'pending',
        started_at: null,
        completed_at: null,
        current_phase: null,
        total_phases: null,
        error_message: null,
      },
    })

    renderTopBar()

    const generateButtons = screen.queryAllByRole('button', { name: /generate wiki/i })
    expect(generateButtons).toHaveLength(0)
  })
})

describe('Log Viewer Button', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(api.getRepoStatus).mockResolvedValue(mockRepoStatus)
    vi.mocked(api.getWikiTree).mockResolvedValue(mockWikiTree)

    useWikiStore.setState({
      repoStatus: mockRepoStatus,
      wikiTree: mockWikiTree,
      isLoading: false,
      error: null,
    })
  })

  it('shows log viewer button when a repo is active', async () => {
    useReposStore.setState({
      activeRepo: {
        id: 1,
        origin_url: 'https://github.com/test/repo',
        source_type: 'github',
        local_path: 'github.com/test/repo',
        display_name: 'Test Repo',
        head_commit: 'abc123',
        branch: 'main',
        created_at: null,
        last_pulled: null,
        last_generated: null,
        generation_duration_secs: null,
        files_processed: null,
        pages_generated: null,
        status: 'ready',
        error_message: null,
      },
    })

    renderTopBar()

    expect(screen.getByRole('button', { name: /view logs/i })).toBeInTheDocument()
  })

  it('hides log viewer button when no repo is active', async () => {
    useReposStore.setState({
      activeRepo: null,
    })

    renderTopBar()

    expect(screen.queryByRole('button', { name: /view logs/i })).not.toBeInTheDocument()
  })

  it('opens LogViewerModal when log button is clicked', async () => {
    vi.mocked(api.getLogs).mockResolvedValue({
      content: '{"test": true}\n',
      size_bytes: 15,
      entry_count: 1,
    })

    useReposStore.setState({
      activeRepo: {
        id: 1,
        origin_url: 'https://github.com/test/repo',
        source_type: 'github',
        local_path: 'github.com/test/repo',
        display_name: 'Test Repo',
        head_commit: 'abc123',
        branch: 'main',
        created_at: null,
        last_pulled: null,
        last_generated: null,
        generation_duration_secs: null,
        files_processed: null,
        pages_generated: null,
        status: 'ready',
        error_message: null,
      },
    })

    renderTopBar()

    await userEvent.click(screen.getByRole('button', { name: /view logs/i }))

    await waitFor(() => {
      expect(screen.getByText(/LLM Logs/)).toBeInTheDocument()
    })
  })
})
