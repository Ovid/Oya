import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useGenerationStore, initialState } from './generationStore'
import { useUIStore, initialState as uiInitialState } from './uiStore'
import * as api from '../api/client'
import * as storage from '../utils/storage'

vi.mock('../api/client', () => ({
  initRepo: vi.fn(),
  getJob: vi.fn(),
}))

vi.mock('../utils/storage', () => ({
  getStorageValue: vi.fn(() => null),
  setStorageValue: vi.fn(),
  hasStorageValue: vi.fn(() => false),
  DEFAULT_STORAGE: {
    darkMode: false,
    askPanelOpen: false,
    sidebarLeftWidth: 256,
    sidebarRightWidth: 200,
    currentJob: null,
    qaSettings: { quickMode: true, temperature: 0.5, timeoutMinutes: 3 },
    generationTiming: {},
  },
}))

beforeEach(() => {
  vi.clearAllMocks()
  useGenerationStore.setState(initialState)
  useUIStore.setState(uiInitialState)
})

describe('generationStore', () => {
  describe('initial state', () => {
    it('has correct initial values', () => {
      const state = useGenerationStore.getState()
      expect(state.currentJob).toBeNull()
      expect(state.generationStatus).toBeNull()
    })
  })

  describe('startGeneration', () => {
    it('returns job_id on success', async () => {
      vi.mocked(api.initRepo).mockResolvedValue({
        job_id: 'test-job-123',
        status: 'pending',
        message: 'Created',
      })
      vi.mocked(api.getJob).mockResolvedValue({
        job_id: 'test-job-123',
        type: 'generation',
        status: 'running',
        started_at: null,
        completed_at: null,
        current_phase: null,
        total_phases: null,
        error_message: null,
      })

      const jobId = await useGenerationStore.getState().startGeneration()

      expect(jobId).toBe('test-job-123')
      expect(useGenerationStore.getState().currentJob?.job_id).toBe('test-job-123')
    })

    it('clears generationStatus when starting', async () => {
      useGenerationStore.setState({ generationStatus: { status: 'incomplete', message: 'test' } })
      vi.mocked(api.initRepo).mockResolvedValue({
        job_id: 'job',
        status: 'pending',
        message: 'Created',
      })
      vi.mocked(api.getJob).mockResolvedValue({
        job_id: 'job',
        type: 'generation',
        status: 'running',
        started_at: null,
        completed_at: null,
        current_phase: null,
        total_phases: null,
        error_message: null,
      })

      await useGenerationStore.getState().startGeneration()

      expect(useGenerationStore.getState().generationStatus).toBeNull()
    })

    it('returns null and sets error on failure', async () => {
      vi.mocked(api.initRepo).mockRejectedValue(new Error('Server error'))

      const jobId = await useGenerationStore.getState().startGeneration()

      expect(jobId).toBeNull()
      expect(useGenerationStore.getState().error).toBe('Server error')
    })

    it('shows error modal on failure', async () => {
      vi.mocked(api.initRepo).mockRejectedValue(new Error('Server error'))

      await useGenerationStore.getState().startGeneration()

      const errorModal = useUIStore.getState().errorModal
      expect(errorModal).not.toBeNull()
      expect(errorModal?.title).toBe('Generation Failed')
      expect(errorModal?.message).toBe('Server error')
    })

    it('returns null without calling API if already loading', async () => {
      useGenerationStore.setState({ isLoading: true })

      const jobId = await useGenerationStore.getState().startGeneration()

      expect(jobId).toBeNull()
      expect(api.initRepo).not.toHaveBeenCalled()
    })

    it('returns null without calling API if job is already running', async () => {
      useGenerationStore.setState({
        currentJob: {
          job_id: 'existing',
          type: 'generation',
          status: 'running',
          started_at: null,
          completed_at: null,
          current_phase: null,
          total_phases: null,
          error_message: null,
        },
      })

      const jobId = await useGenerationStore.getState().startGeneration()

      expect(jobId).toBeNull()
      expect(api.initRepo).not.toHaveBeenCalled()
    })

    it('returns null without calling API if job is pending', async () => {
      useGenerationStore.setState({
        currentJob: {
          job_id: 'existing',
          type: 'generation',
          status: 'pending',
          started_at: null,
          completed_at: null,
          current_phase: null,
          total_phases: null,
          error_message: null,
        },
      })

      const jobId = await useGenerationStore.getState().startGeneration()

      expect(jobId).toBeNull()
      expect(api.initRepo).not.toHaveBeenCalled()
    })

    it('persists job to storage on success', async () => {
      vi.mocked(api.initRepo).mockResolvedValue({
        job_id: 'test-job-123',
        status: 'pending',
        message: 'Created',
      })
      vi.mocked(api.getJob).mockResolvedValue({
        job_id: 'test-job-123',
        type: 'generation',
        status: 'running',
        started_at: '2024-01-01T00:00:00Z',
        completed_at: null,
        current_phase: 'parsing',
        total_phases: 5,
        error_message: null,
      })

      await useGenerationStore.getState().startGeneration()

      expect(storage.setStorageValue).toHaveBeenCalledWith(
        'currentJob',
        expect.objectContaining({ jobId: 'test-job-123' })
      )
    })
  })

  describe('setCurrentJob', () => {
    it('updates current job', () => {
      const job = {
        job_id: 'test',
        type: 'generation' as const,
        status: 'running' as const,
        started_at: null,
        completed_at: null,
        current_phase: null,
        total_phases: null,
        error_message: null,
      }

      useGenerationStore.getState().setCurrentJob(job)

      expect(useGenerationStore.getState().currentJob).toEqual(job)
    })

    it('persists running job to storage', () => {
      const job = {
        job_id: 'test',
        type: 'generation' as const,
        status: 'running' as const,
        started_at: '2024-01-01T00:00:00Z',
        completed_at: null,
        current_phase: 'parsing',
        total_phases: 5,
        error_message: null,
      }

      useGenerationStore.getState().setCurrentJob(job)

      expect(storage.setStorageValue).toHaveBeenCalledWith('currentJob', {
        jobId: 'test',
        type: 'generation',
        status: 'running',
        startedAt: '2024-01-01T00:00:00Z',
        completedAt: null,
        currentPhase: 'parsing',
        totalPhases: 5,
        errorMessage: null,
      })
    })

    it('clears job from storage when set to null', () => {
      useGenerationStore.getState().setCurrentJob(null)

      expect(storage.setStorageValue).toHaveBeenCalledWith('currentJob', null)
    })

    it('clears job from storage when job status is completed', () => {
      const job = {
        job_id: 'test',
        type: 'generation' as const,
        status: 'completed' as const,
        started_at: '2024-01-01T00:00:00Z',
        completed_at: '2024-01-01T00:01:00Z',
        current_phase: null,
        total_phases: 5,
        error_message: null,
      }

      useGenerationStore.getState().setCurrentJob(job)

      expect(storage.setStorageValue).toHaveBeenCalledWith('currentJob', null)
    })

    it('clears job from storage when job status is failed', () => {
      const job = {
        job_id: 'test',
        type: 'generation' as const,
        status: 'failed' as const,
        started_at: '2024-01-01T00:00:00Z',
        completed_at: null,
        current_phase: null,
        total_phases: 5,
        error_message: 'Something went wrong',
      }

      useGenerationStore.getState().setCurrentJob(job)

      expect(storage.setStorageValue).toHaveBeenCalledWith('currentJob', null)
    })
  })

  describe('loadStoredJob', () => {
    it('returns null when no job is stored', async () => {
      vi.mocked(storage.getStorageValue).mockReturnValue(null)

      const { loadStoredJob } = await import('./generationStore')
      const job = loadStoredJob()

      expect(job).toBeNull()
    })

    it('converts stored job from camelCase to snake_case', async () => {
      vi.mocked(storage.getStorageValue).mockReturnValue({
        jobId: 'stored-job',
        type: 'generation',
        status: 'running',
        startedAt: '2024-01-01T00:00:00Z',
        completedAt: null,
        currentPhase: 'parsing',
        totalPhases: 5,
        errorMessage: null,
      })

      const { loadStoredJob } = await import('./generationStore')
      const job = loadStoredJob()

      expect(job).toEqual({
        job_id: 'stored-job',
        type: 'generation',
        status: 'running',
        started_at: '2024-01-01T00:00:00Z',
        completed_at: null,
        current_phase: 'parsing',
        total_phases: 5,
        error_message: null,
      })
    })

    it('clears storage and returns null for invalid shape (missing jobId)', async () => {
      vi.mocked(storage.getStorageValue).mockReturnValue({
        status: 'running',
      })

      const { loadStoredJob } = await import('./generationStore')
      const job = loadStoredJob()

      expect(job).toBeNull()
      expect(storage.setStorageValue).toHaveBeenCalledWith('currentJob', null)
    })

    it('clears storage and returns null for invalid shape (missing status)', async () => {
      vi.mocked(storage.getStorageValue).mockReturnValue({
        jobId: 'job-123',
      })

      const { loadStoredJob } = await import('./generationStore')
      const job = loadStoredJob()

      expect(job).toBeNull()
      expect(storage.setStorageValue).toHaveBeenCalledWith('currentJob', null)
    })

    it('clears storage and returns null for wrong types', async () => {
      vi.mocked(storage.getStorageValue).mockReturnValue({
        jobId: 123, // should be string
        status: 'running',
      })

      const { loadStoredJob } = await import('./generationStore')
      const job = loadStoredJob()

      expect(job).toBeNull()
      expect(storage.setStorageValue).toHaveBeenCalledWith('currentJob', null)
    })
  })

  describe('dismissGenerationStatus', () => {
    it('clears generation status', () => {
      useGenerationStore.setState({ generationStatus: { status: 'incomplete', message: 'test' } })

      useGenerationStore.getState().dismissGenerationStatus()

      expect(useGenerationStore.getState().generationStatus).toBeNull()
    })
  })
})
