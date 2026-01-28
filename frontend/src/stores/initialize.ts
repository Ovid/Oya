import { useWikiStore } from './wikiStore'
import { useGenerationStore } from './generationStore'
import { useReposStore } from './reposStore'
import * as api from '../api/client'

export async function initializeApp(): Promise<void> {
  const wikiStore = useWikiStore.getState()
  const generationStore = useGenerationStore.getState()
  const reposStore = useReposStore.getState()

  wikiStore.setLoading(true)

  // Fetch repos and active repo
  await reposStore.fetchRepos()

  // Check if fetch succeeded - fetchRepos catches errors internally
  // and sets error state rather than throwing
  const { error: fetchError } = useReposStore.getState()
  if (fetchError) {
    // Don't mark as initialized when fetch fails - we don't know repo state
    // This prevents showing FirstRunWizard when backend isn't ready
    wikiStore.setLoading(false)
    return
  }

  await reposStore.fetchActiveRepo()

  // Auto-select first repo if repos exist but none is active
  const { repos, activeRepo } = useReposStore.getState()
  if (repos.length > 0 && !activeRepo) {
    await reposStore.setActiveRepo(repos[0].id)
  }

  // Only mark as initialized after successful fetch
  reposStore.setInitialized(true)

  // Refresh repo status for the active repo
  await wikiStore.refreshStatus()

  // Check for incomplete build FIRST
  let hasIncompleteBuild = false
  try {
    const genStatus = await api.getGenerationStatus()
    if (genStatus && genStatus.status === 'incomplete') {
      generationStore.setGenerationStatus(genStatus)
      hasIncompleteBuild = true
      // Clear wiki tree when build is incomplete
      useWikiStore.setState({
        wikiTree: {
          overview: false,
          architecture: false,
          workflows: [],
          directories: [],
          files: [],
        },
      })
    }
  } catch {
    // Ignore errors when checking generation status
  }

  // Only load wiki tree if build is complete
  if (!hasIncompleteBuild) {
    await wikiStore.refreshTree()
  }

  // Check for any active jobs (pending or running) to restore generation progress after refresh
  try {
    const jobs = await api.listJobs(1)
    const activeJob = jobs.find((job) => job.status === 'running' || job.status === 'pending')
    if (activeJob) {
      generationStore.setCurrentJob(activeJob)
    }
  } catch {
    // Ignore errors when checking for running jobs
  }

  wikiStore.setLoading(false)
}
