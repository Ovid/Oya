import { create } from 'zustand'
import type { JobStatus, GenerationStatus } from '../types'
import * as api from '../api/client'

interface GenerationState {
  currentJob: JobStatus | null
  generationStatus: GenerationStatus | null
  isLoading: boolean
  error: string | null
}

interface GenerationActions {
  startGeneration: () => Promise<string | null>
  setCurrentJob: (job: JobStatus | null) => void
  setGenerationStatus: (status: GenerationStatus | null) => void
  dismissGenerationStatus: () => void
  setLoading: (loading: boolean) => void
  setError: (error: string | null) => void
}

export const initialState: GenerationState = {
  currentJob: null,
  generationStatus: null,
  isLoading: false,
  error: null,
}

export const useGenerationStore = create<GenerationState & GenerationActions>()((set, get) => ({
  ...initialState,

  startGeneration: async () => {
    // Guard against concurrent calls
    const state = get()
    const jobIsActive =
      state.currentJob?.status === 'running' || state.currentJob?.status === 'pending'
    if (state.isLoading || jobIsActive) {
      return null
    }

    set({ isLoading: true, generationStatus: null, error: null })
    try {
      const result = await api.initRepo()
      const job = await api.getJob(result.job_id)
      set({ currentJob: job })
      return result.job_id
    } catch {
      set({ error: 'Failed to start generation' })
      return null
    } finally {
      set({ isLoading: false })
    }
  },

  setCurrentJob: (job) => set({ currentJob: job }),
  setGenerationStatus: (status) => set({ generationStatus: status }),
  dismissGenerationStatus: () => set({ generationStatus: null }),
  setLoading: (loading) => set({ isLoading: loading }),
  setError: (error) => set({ error }),
}))
