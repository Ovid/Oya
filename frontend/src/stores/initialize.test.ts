import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('../api/client', () => ({
  getRepoStatus: vi.fn(),
  getWikiTree: vi.fn(),
  getGenerationStatus: vi.fn(),
  listJobs: vi.fn(),
}))

let api: typeof import('../api/client')
let initializeApp: typeof import('./initialize').initializeApp
let useWikiStore: typeof import('./wikiStore').useWikiStore
let useGenerationStore: typeof import('./generationStore').useGenerationStore

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

beforeEach(async () => {
  vi.resetModules()
  api = await import('../api/client')
  const initModule = await import('./initialize')
  initializeApp = initModule.initializeApp
  const wikiModule = await import('./wikiStore')
  useWikiStore = wikiModule.useWikiStore
  const genModule = await import('./generationStore')
  useGenerationStore = genModule.useGenerationStore

  vi.clearAllMocks()
  useWikiStore.setState(useWikiStore.getInitialState())
  useGenerationStore.setState(useGenerationStore.getInitialState())
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
