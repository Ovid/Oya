import { create } from 'zustand'
import type { JobStatus, GenerationStatus } from '../types'
import * as api from '../api/client'
import { useUIStore } from './uiStore'
import { STORAGE_KEY_CURRENT_JOB } from '../config/storage'

/**
 * Load current job from localStorage.
 * Returns null if not found or invalid.
 */
function loadStoredJob(): JobStatus | null {
  try {
    const stored = localStorage.getItem(STORAGE_KEY_CURRENT_JOB)
    if (!stored) return null
    const parsed = JSON.parse(stored)
    // Validate basic shape
    if (parsed && typeof parsed.job_id === 'string' && typeof parsed.status === 'string') {
      return parsed as JobStatus
    }
    localStorage.removeItem(STORAGE_KEY_CURRENT_JOB)
    return null
  } catch {
    localStorage.removeItem(STORAGE_KEY_CURRENT_JOB)
    return null
  }
}

/**
 * Save current job to localStorage.
 */
function saveStoredJob(job: JobStatus | null): void {
  try {
    if (job && (job.status === 'running' || job.status === 'pending')) {
      localStorage.setItem(STORAGE_KEY_CURRENT_JOB, JSON.stringify(job))
    } else {
      localStorage.removeItem(STORAGE_KEY_CURRENT_JOB)
    }
  } catch {
    // localStorage unavailable - graceful degradation
  }
}

interface GenerationState {
  currentJob: JobStatus | null
  generationStatus: GenerationStatus | null
  isLoading: boolean
  error: string | null
}

interface GenerationActions {
  startGeneration: (mode?: 'incremental' | 'full') => Promise<string | null>
  setCurrentJob: (job: JobStatus | null) => void
  setGenerationStatus: (status: GenerationStatus | null) => void
  dismissGenerationStatus: () => void
  setLoading: (loading: boolean) => void
  setError: (error: string | null) => void
}

// Load persisted job on module init (before store creation)
const persistedJob = loadStoredJob()

export const initialState: GenerationState = {
  currentJob: persistedJob,
  generationStatus: null,
  isLoading: false,
  error: null,
}

export const useGenerationStore = create<GenerationState & GenerationActions>()((set, get) => ({
  ...initialState,

  startGeneration: async (mode: 'incremental' | 'full' = 'incremental') => {
    // Guard against concurrent calls
    const state = get()
    const jobIsActive =
      state.currentJob?.status === 'running' || state.currentJob?.status === 'pending'
    if (state.isLoading || jobIsActive) {
      return null
    }

    set({ isLoading: true, generationStatus: null, error: null })
    try {
      const result = await api.initRepo(mode)
      const job = await api.getJob(result.job_id)
      saveStoredJob(job)
      set({ currentJob: job })
      return result.job_id
    } catch (e) {
      const message = e instanceof Error ? e.message : 'Failed to start generation'
      set({ error: message })
      useUIStore.getState().showErrorModal('Generation Failed', message)
      return null
    } finally {
      set({ isLoading: false })
    }
  },

  setCurrentJob: (job) => {
    saveStoredJob(job)
    set({ currentJob: job })
  },
  setGenerationStatus: (status) => set({ generationStatus: status }),
  dismissGenerationStatus: () => set({ generationStatus: null }),
  setLoading: (loading) => set({ isLoading: loading }),
  setError: (error) => set({ error }),
}))
