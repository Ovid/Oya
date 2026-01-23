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
