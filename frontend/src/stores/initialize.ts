import { useWikiStore } from './wikiStore'
import { useGenerationStore } from './generationStore'
import { useReposStore } from './reposStore'
import * as api from '../api/client'

export async function initializeApp(): Promise<void> {
  const wikiStore = useWikiStore.getState()
  const generationStore = useGenerationStore.getState()
  const reposStore = useReposStore.getState()

  wikiStore.setLoading(true)

  // Fetch repos and active repo for multi-repo mode
  try {
    await reposStore.fetchRepos()
    await reposStore.fetchActiveRepo()
  } catch {
    // Ignore errors - may not be in multi-repo mode
  }

  // Refresh repo status (works in both legacy and multi-repo mode)
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
