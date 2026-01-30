import { useWikiStore } from './wikiStore'
import { useGenerationStore, loadStoredJob } from './generationStore'
import { useReposStore } from './reposStore'
import { useUIStore } from './uiStore'
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
          code_health: false,
          workflows: [],
          directories: [],
          files: [],
        },
      })
    }
  } catch {
    useUIStore.getState().addToast('Could not check generation status', 'warning')
  }

  // Only load wiki tree if build is complete
  if (!hasIncompleteBuild) {
    await wikiStore.refreshTree()
  }

  // Restore active job - first from localStorage, then verify with API
  // This ensures timing data is loaded with the correct job ID
  const storedJob = loadStoredJob()
  if (storedJob && (storedJob.status === 'running' || storedJob.status === 'pending')) {
    generationStore.setCurrentJob(storedJob)
  }

  // Verify/update job state from API
  try {
    const jobs = await api.listJobs(1)
    const activeJob = jobs.find((job) => job.status === 'running' || job.status === 'pending')
    if (activeJob) {
      // Update with fresh data from API (job may have progressed or completed)
      generationStore.setCurrentJob(activeJob)
    } else if (storedJob) {
      // API says no active job but localStorage had one - job must have completed/failed
      // Clear the stale job from store (setCurrentJob with null will also clear localStorage)
      generationStore.setCurrentJob(null)
    }
  } catch {
    // If API fails but we have a localStorage job, keep using it
    if (!storedJob) {
      useUIStore.getState().addToast('Could not check for running jobs', 'warning')
    }
  }

  wikiStore.setLoading(false)
}
