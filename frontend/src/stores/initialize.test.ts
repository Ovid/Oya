import { describe, it, expect, vi, beforeEach } from 'vitest'
import { initializeApp } from './initialize'
import { useWikiStore, initialState as wikiInitial } from './wikiStore'
import { useGenerationStore, initialState as genInitial } from './generationStore'
import * as api from '../api/client'

vi.mock('../api/client', () => ({
  getRepoStatus: vi.fn(),
  getWikiTree: vi.fn(),
  getGenerationStatus: vi.fn(),
  listJobs: vi.fn(),
}))

const mockRepoStatus = {
  path: '/test',
  head_commit: 'abc',
  head_message: 'Test',
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
  architecture: false,
  workflows: [],
  directories: [],
  files: [],
}

beforeEach(() => {
  vi.clearAllMocks()
  useWikiStore.setState(wikiInitial)
  useGenerationStore.setState(genInitial)
})

describe('initializeApp', () => {
  it('loads repo status and wiki tree', async () => {
    vi.mocked(api.getRepoStatus).mockResolvedValue(mockRepoStatus)
    vi.mocked(api.getWikiTree).mockResolvedValue(mockWikiTree)
    vi.mocked(api.getGenerationStatus).mockResolvedValue(null)
    vi.mocked(api.listJobs).mockResolvedValue([])

    await initializeApp()

    expect(useWikiStore.getState().repoStatus).toEqual(mockRepoStatus)
    expect(useWikiStore.getState().wikiTree).toEqual(mockWikiTree)
    expect(useWikiStore.getState().isLoading).toBe(false)
  })

  it('detects incomplete build and clears wiki tree', async () => {
    vi.mocked(api.getRepoStatus).mockResolvedValue(mockRepoStatus)
    vi.mocked(api.getWikiTree).mockResolvedValue(mockWikiTree)
    vi.mocked(api.getGenerationStatus).mockResolvedValue({
      status: 'incomplete',
      message: 'Build interrupted',
    })
    vi.mocked(api.listJobs).mockResolvedValue([])

    await initializeApp()

    expect(useGenerationStore.getState().generationStatus?.status).toBe('incomplete')
    expect(useWikiStore.getState().wikiTree?.overview).toBe(false)
  })

  it('restores running job', async () => {
    vi.mocked(api.getRepoStatus).mockResolvedValue(mockRepoStatus)
    vi.mocked(api.getWikiTree).mockResolvedValue(mockWikiTree)
    vi.mocked(api.getGenerationStatus).mockResolvedValue(null)
    vi.mocked(api.listJobs).mockResolvedValue([
      {
        job_id: 'running-123',
        type: 'generation',
        status: 'running',
        started_at: null,
        completed_at: null,
        current_phase: null,
        total_phases: null,
        error_message: null,
      },
    ])

    await initializeApp()

    expect(useGenerationStore.getState().currentJob?.job_id).toBe('running-123')
  })
})
