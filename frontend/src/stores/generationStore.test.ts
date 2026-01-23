import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useGenerationStore } from './generationStore'
import * as api from '../api/client'

vi.mock('../api/client', () => ({
  initRepo: vi.fn(),
  getJob: vi.fn(),
}))

beforeEach(() => {
  vi.clearAllMocks()
  useGenerationStore.setState(useGenerationStore.getInitialState())
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
      expect(useGenerationStore.getState().error).toBe('Failed to start generation')
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
  })

  describe('dismissGenerationStatus', () => {
    it('clears generation status', () => {
      useGenerationStore.setState({ generationStatus: { status: 'incomplete', message: 'test' } })

      useGenerationStore.getState().dismissGenerationStatus()

      expect(useGenerationStore.getState().generationStatus).toBeNull()
    })
  })
})
