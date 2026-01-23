import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useWikiStore } from './wikiStore'
import * as api from '../api/client'

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

beforeEach(() => {
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
      useWikiStore.setState({
        currentPage: {
          content: '',
          page_type: 'overview',
          path: '/overview',
          word_count: 0,
          source_path: null,
        },
      })

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
      const page = {
        content: 'Content',
        page_type: 'overview' as const,
        path: '/overview',
        word_count: 10,
        source_path: null,
      }

      useWikiStore.getState().setCurrentPage(page)

      expect(useWikiStore.getState().currentPage).toEqual(page)
    })
  })
})
