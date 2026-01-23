import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import type { RepoStatus, WikiTree, WikiPage } from '../types'

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
  ApiError: class ApiError extends Error {
    status: number
    constructor(status: number, message: string) {
      super(message)
      this.name = 'ApiError'
      this.status = status
    }
  },
}))

// Note: localStorage/matchMedia mocks handled by test/setup.ts

import { PageLoader } from './PageLoader'
import { useWikiStore, useGenerationStore } from '../stores'
import { initialState as wikiInitial } from '../stores/wikiStore'
import { initialState as genInitial } from '../stores/generationStore'
import * as api from '../api/client'

beforeEach(() => {
  vi.clearAllMocks()
  // Reset stores to initial state
  useWikiStore.setState(wikiInitial)
  useGenerationStore.setState(genInitial)
})

const mockRepoStatusWithWiki: RepoStatus = {
  path: '/home/user/project',
  head_commit: 'abc123',
  head_message: 'Initial commit',
  branch: 'main',
  initialized: true,
  is_docker: false,
  last_generation: '2024-01-01T00:00:00Z', // Wiki exists
  generation_status: null,
  embedding_metadata: null,
  current_provider: null,
  current_model: null,
  embedding_mismatch: false,
}

const mockRepoStatusWithoutWiki: RepoStatus = {
  path: '/home/user/project',
  head_commit: 'abc123',
  head_message: 'Initial commit',
  branch: 'main',
  initialized: true,
  is_docker: false,
  last_generation: null, // No wiki generated
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

const mockWikiPage: WikiPage = {
  content: '# Test Content',
  page_type: 'overview',
  path: '/overview',
  word_count: 2,
  source_path: null,
}

function renderPageLoader(
  loadPage: () => Promise<WikiPage>,
  storeOverrides: { repoStatus?: RepoStatus | null } = {}
) {
  // Set store state for overrides - ensure isLoading is false so component doesn't just show spinner
  useWikiStore.setState({
    repoStatus:
      storeOverrides.repoStatus !== undefined ? storeOverrides.repoStatus : mockRepoStatusWithWiki,
    wikiTree: mockWikiTree,
    isLoading: false,
  })

  return render(
    <MemoryRouter>
      <PageLoader loadPage={loadPage} />
    </MemoryRouter>
  )
}

describe('PageLoader', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(api.getRepoStatus).mockResolvedValue(mockRepoStatusWithWiki)
    vi.mocked(api.getWikiTree).mockResolvedValue(mockWikiTree)
    vi.mocked(api.listJobs).mockResolvedValue([])
    vi.mocked(api.getGenerationStatus).mockResolvedValue(null)
  })

  describe('successful page load', () => {
    it('renders page content when load succeeds', async () => {
      const loadPage = vi.fn().mockResolvedValue(mockWikiPage)

      renderPageLoader(loadPage)

      await waitFor(() => {
        expect(screen.getByText('Test Content')).toBeInTheDocument()
      })
    })
  })

  describe('404 handling', () => {
    it('shows welcome message when page not found and no wiki exists', async () => {
      const { ApiError } = await import('../api/client')
      const loadPage = vi.fn().mockRejectedValue(new ApiError(404, 'Not found'))

      renderPageLoader(loadPage, { repoStatus: mockRepoStatusWithoutWiki })

      await waitFor(() => {
        expect(screen.getByText('Welcome to Ọya!')).toBeInTheDocument()
        expect(screen.getByText(/click/i)).toBeInTheDocument()
        expect(screen.getByText(/Generate Wiki/i)).toBeInTheDocument()
      })
    })

    it('shows 404 error when page not found but wiki exists', async () => {
      const { ApiError } = await import('../api/client')
      const loadPage = vi.fn().mockRejectedValue(new ApiError(404, 'Not found'))

      renderPageLoader(loadPage, { repoStatus: mockRepoStatusWithWiki })

      await waitFor(() => {
        expect(screen.getByText('Page not found')).toBeInTheDocument()
        expect(screen.getByText(/doesn't exist/)).toBeInTheDocument()
      })
    })

    it('shows 404 error when wiki exists with recent generation', async () => {
      const { ApiError } = await import('../api/client')
      const loadPage = vi.fn().mockRejectedValue(new ApiError(404, 'Not found'))
      const repoWithRecentGen = {
        ...mockRepoStatusWithWiki,
        last_generation: new Date().toISOString(),
      }

      renderPageLoader(loadPage, { repoStatus: repoWithRecentGen })

      await waitFor(() => {
        expect(screen.getByText('Page not found')).toBeInTheDocument()
      })
    })
  })

  describe('error handling', () => {
    it('shows error message for non-404 errors', async () => {
      const loadPage = vi.fn().mockRejectedValue(new Error('Network error'))

      renderPageLoader(loadPage)

      await waitFor(() => {
        expect(screen.getByText('Error loading page')).toBeInTheDocument()
        expect(screen.getByText('Network error')).toBeInTheDocument()
      })
    })
  })

  describe('loading state', () => {
    it('shows loading spinner while page is loading', async () => {
      // Create a promise that never resolves to keep loading state
      const loadPage = vi.fn().mockReturnValue(new Promise(() => {}))

      renderPageLoader(loadPage)

      // The spinner should be visible (it's a div with animate-spin class)
      const spinner = document.querySelector('.animate-spin')
      expect(spinner).toBeInTheDocument()
    })
  })
})
