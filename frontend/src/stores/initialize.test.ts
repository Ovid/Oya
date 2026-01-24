import { describe, it, expect, vi, beforeEach } from 'vitest'
import { initializeApp } from './initialize'
import { useWikiStore, initialState as wikiInitial } from './wikiStore'
import { useGenerationStore, initialState as genInitial } from './generationStore'
import { useReposStore, initialState as reposInitial } from './reposStore'
import * as api from '../api/client'
import type { Repo } from '../types'

vi.mock('../api/client', () => ({
  getRepoStatus: vi.fn(),
  getWikiTree: vi.fn(),
  getGenerationStatus: vi.fn(),
  listJobs: vi.fn(),
  listRepos: vi.fn(),
  getActiveRepo: vi.fn(),
  activateRepo: vi.fn(),
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

const mockRepo: Repo = {
  id: 1,
  origin_url: 'https://github.com/test/repo',
  source_type: 'github',
  local_path: '/test/repo',
  display_name: 'Test Repo',
  head_commit: null,
  branch: null,
  created_at: '2024-01-01T00:00:00Z',
  last_pulled: null,
  last_generated: null,
  generation_duration_secs: null,
  files_processed: null,
  pages_generated: null,
  status: 'ready',
  error_message: null,
}

beforeEach(() => {
  vi.clearAllMocks()
  useWikiStore.setState(wikiInitial)
  useGenerationStore.setState(genInitial)
  useReposStore.setState(reposInitial)
})

describe('initializeApp', () => {
  it('loads repo status and wiki tree', async () => {
    vi.mocked(api.listRepos).mockResolvedValue({ repos: [], total: 0 })
    vi.mocked(api.getActiveRepo).mockResolvedValue({ active_repo: null })
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
    vi.mocked(api.listRepos).mockResolvedValue({ repos: [], total: 0 })
    vi.mocked(api.getActiveRepo).mockResolvedValue({ active_repo: null })
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
    vi.mocked(api.listRepos).mockResolvedValue({ repos: [], total: 0 })
    vi.mocked(api.getActiveRepo).mockResolvedValue({ active_repo: null })
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

  it('auto-selects first repo when repos exist but none is active', async () => {
    vi.mocked(api.listRepos).mockResolvedValue({ repos: [mockRepo], total: 1 })
    vi.mocked(api.getActiveRepo).mockResolvedValue({ active_repo: null })
    vi.mocked(api.activateRepo).mockResolvedValue({ active_repo_id: mockRepo.id })
    vi.mocked(api.getRepoStatus).mockResolvedValue(mockRepoStatus)
    vi.mocked(api.getWikiTree).mockResolvedValue(mockWikiTree)
    vi.mocked(api.getGenerationStatus).mockResolvedValue(null)
    vi.mocked(api.listJobs).mockResolvedValue([])

    await initializeApp()

    expect(api.activateRepo).toHaveBeenCalledWith(mockRepo.id)
  })

  it('does not auto-select when an active repo already exists', async () => {
    vi.mocked(api.listRepos).mockResolvedValue({ repos: [mockRepo], total: 1 })
    vi.mocked(api.getActiveRepo).mockResolvedValue({ active_repo: mockRepo })
    vi.mocked(api.getRepoStatus).mockResolvedValue(mockRepoStatus)
    vi.mocked(api.getWikiTree).mockResolvedValue(mockWikiTree)
    vi.mocked(api.getGenerationStatus).mockResolvedValue(null)
    vi.mocked(api.listJobs).mockResolvedValue([])

    await initializeApp()

    expect(api.activateRepo).not.toHaveBeenCalled()
  })

  it('does not auto-select when no repos exist', async () => {
    vi.mocked(api.listRepos).mockResolvedValue({ repos: [], total: 0 })
    vi.mocked(api.getActiveRepo).mockResolvedValue({ active_repo: null })
    vi.mocked(api.getRepoStatus).mockResolvedValue(mockRepoStatus)
    vi.mocked(api.getWikiTree).mockResolvedValue(mockWikiTree)
    vi.mocked(api.getGenerationStatus).mockResolvedValue(null)
    vi.mocked(api.listJobs).mockResolvedValue([])

    await initializeApp()

    expect(api.activateRepo).not.toHaveBeenCalled()
  })
})
