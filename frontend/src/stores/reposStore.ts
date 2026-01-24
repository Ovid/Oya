import { create } from 'zustand'
import { subscribeWithSelector } from 'zustand/middleware'
import type { Repo } from '../types'
import { listRepos, createRepo, deleteRepo, activateRepo, getActiveRepo } from '../api/client'

interface ReposState {
  repos: Repo[]
  activeRepo: Repo | null
  isLoading: boolean
  error: string | null
}

interface ReposActions {
  fetchRepos: () => Promise<void>
  fetchActiveRepo: () => Promise<void>
  addRepo: (url: string, displayName?: string) => Promise<Repo>
  removeRepo: (repoId: number) => Promise<void>
  setActiveRepo: (repoId: number) => Promise<void>
  clearError: () => void
}

export const initialState: ReposState = {
  repos: [],
  activeRepo: null,
  isLoading: false,
  error: null,
}

export const useReposStore = create<ReposState & ReposActions>()(
  subscribeWithSelector((set, get) => ({
    ...initialState,

    fetchRepos: async () => {
      set({ isLoading: true, error: null })
      try {
        const response = await listRepos()
        set({ repos: response.repos, isLoading: false })
      } catch (e) {
        set({
          error: e instanceof Error ? e.message : 'Failed to fetch repos',
          isLoading: false,
        })
      }
    },

    fetchActiveRepo: async () => {
      try {
        const response = await getActiveRepo()
        set({ activeRepo: response.active_repo })
      } catch (e) {
        set({
          error: e instanceof Error ? e.message : 'Failed to fetch active repo',
        })
      }
    },

    addRepo: async (url: string, displayName?: string) => {
      set({ isLoading: true, error: null })
      try {
        const response = await createRepo({ url, display_name: displayName })
        // Refresh the repos list to get the full repo object
        await get().fetchRepos()
        set({ isLoading: false })
        // Find and return the newly created repo
        const newRepo = get().repos.find((r) => r.id === response.id)
        if (!newRepo) {
          throw new Error('Failed to find newly created repo')
        }
        return newRepo
      } catch (e) {
        const message = e instanceof Error ? e.message : 'Failed to add repo'
        set({ error: message, isLoading: false })
        throw e
      }
    },

    removeRepo: async (repoId: number) => {
      set({ isLoading: true, error: null })
      try {
        await deleteRepo(repoId)
        // If we deleted the active repo, clear it
        const { activeRepo } = get()
        if (activeRepo && activeRepo.id === repoId) {
          set({ activeRepo: null })
        }
        // Refresh repos list
        await get().fetchRepos()
        set({ isLoading: false })
      } catch (e) {
        set({
          error: e instanceof Error ? e.message : 'Failed to delete repo',
          isLoading: false,
        })
        throw e
      }
    },

    setActiveRepo: async (repoId: number) => {
      set({ isLoading: true, error: null })
      try {
        await activateRepo(repoId)
        // Fetch the active repo details
        await get().fetchActiveRepo()
        set({ isLoading: false })
      } catch (e) {
        set({
          error: e instanceof Error ? e.message : 'Failed to activate repo',
          isLoading: false,
        })
        throw e
      }
    },

    clearError: () => {
      set({ error: null })
    },
  }))
)
