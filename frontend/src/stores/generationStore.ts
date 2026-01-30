import { create } from 'zustand'
import type { JobStatus, GenerationStatus } from '../types'
import * as api from '../api/client'
import { useUIStore } from './uiStore'
import {
  getStorageValue,
  setStorageValue,
  clearStorageValue,
  type StoredJobStatus,
} from '../utils/storage'

// =============================================================================
// Storage Conversion Functions
// =============================================================================

/**
 * Convert API JobStatus (snake_case) to storage format (camelCase).
 */
function toStoredJob(job: JobStatus): StoredJobStatus {
  return {
    jobId: job.job_id,
    type: job.type,
    status: job.status,
    startedAt: job.started_at,
    completedAt: job.completed_at,
    currentPhase: job.current_phase,
    totalPhases: job.total_phases,
    errorMessage: job.error_message,
  }
}

/**
 * Convert storage format (camelCase) to API JobStatus (snake_case).
 */
function fromStoredJob(stored: StoredJobStatus): JobStatus {
  return {
    job_id: stored.jobId,
    type: stored.type,
    status: stored.status as JobStatus['status'],
    started_at: stored.startedAt,
    completed_at: stored.completedAt,
    current_phase: stored.currentPhase,
    total_phases: stored.totalPhases,
    error_message: stored.errorMessage,
  }
}

// =============================================================================
// Storage Functions
// =============================================================================

// Valid job status values
const VALID_JOB_STATUSES = ['pending', 'running', 'completed', 'failed', 'cancelled'] as const

/**
 * Load current job from consolidated storage.
 * Returns null if not found or invalid.
 * Exported so initializeApp can call this after React is ready.
 */
export function loadStoredJob(): JobStatus | null {
  const stored = getStorageValue('currentJob')
  if (!stored) return null

  // Validate minimal shape before converting to JobStatus.
  // Handles corrupted/partial writes, older app versions, or manual edits.
  if (
    typeof stored !== 'object' ||
    typeof stored.jobId !== 'string' ||
    typeof stored.status !== 'string'
  ) {
    clearStorageValue('currentJob')
    return null
  }

  // Validate status is one of the allowed values
  if (!VALID_JOB_STATUSES.includes(stored.status as (typeof VALID_JOB_STATUSES)[number])) {
    clearStorageValue('currentJob')
    return null
  }

  return fromStoredJob(stored)
}

/**
 * Save current job to consolidated storage.
 * Only persists running/pending jobs; clears for other statuses.
 */
export function saveStoredJob(job: JobStatus | null): void {
  if (job && (job.status === 'running' || job.status === 'pending')) {
    setStorageValue('currentJob', toStoredJob(job))
  } else {
    clearStorageValue('currentJob')
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

// Note: Job restoration moved to initializeApp() to ensure localStorage is ready.
// Module-level localStorage access can be unreliable in Vite dev mode.

export const initialState: GenerationState = {
  currentJob: null,
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
