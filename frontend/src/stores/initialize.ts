import { useWikiStore } from './wikiStore'
import { useGenerationStore } from './generationStore'
import * as api from '../api/client'

export async function initializeApp(): Promise<void> {
  const wikiStore = useWikiStore.getState()
  const generationStore = useGenerationStore.getState()

  wikiStore.setLoading(true)
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

  // Check for any running jobs to restore generation progress after refresh
  try {
    const jobs = await api.listJobs(1)
    const runningJob = jobs.find((job) => job.status === 'running')
    if (runningJob) {
      generationStore.setCurrentJob(runningJob)
    }
  } catch {
    // Ignore errors when checking for running jobs
  }

  wikiStore.setLoading(false)
}
