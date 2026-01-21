import { useEffect, useState, useCallback } from 'react'
import type { WikiPage } from '../types'
import { WikiContent } from './WikiContent'
import { NotFound } from './NotFound'
import { useApp } from '../context/useApp'
import { ApiError } from '../api/client'
import { GenerationProgress } from './GenerationProgress'

interface PageLoaderProps {
  loadPage: () => Promise<WikiPage>
}

export function PageLoader({ loadPage }: PageLoaderProps) {
  const { dispatch, refreshTree, refreshStatus, state } = useApp()
  const [page, setPage] = useState<WikiPage | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [notFound, setNotFound] = useState(false)

  useEffect(() => {
    let cancelled = false

    const load = async () => {
      setLoading(true)
      setError(null)
      setNotFound(false)

      try {
        const data = await loadPage()
        if (!cancelled) {
          setPage(data)
          dispatch({ type: 'SET_CURRENT_PAGE', payload: data })
        }
      } catch (err) {
        if (!cancelled) {
          if (err instanceof ApiError && err.status === 404) {
            setNotFound(true)
          } else {
            setError(err instanceof Error ? err.message : 'Failed to load page')
          }
          dispatch({ type: 'SET_CURRENT_PAGE', payload: null })
        }
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    }

    load()

    return () => {
      cancelled = true
    }
  }, [loadPage, dispatch])

  const handleGenerationComplete = useCallback(async () => {
    // Clear the current job from global state
    dispatch({ type: 'SET_CURRENT_JOB', payload: null })
    // Refresh the wiki tree, repo status, and reload the page
    await refreshTree()
    await refreshStatus()
    // Re-trigger page load
    setLoading(true)
    setNotFound(false)
    try {
      const data = await loadPage()
      setPage(data)
      dispatch({ type: 'SET_CURRENT_PAGE', payload: data })
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        setNotFound(true)
      } else {
        setError(err instanceof Error ? err.message : 'Failed to load page')
      }
    } finally {
      setLoading(false)
    }
  }, [loadPage, dispatch, refreshTree, refreshStatus])

  const handleGenerationError = useCallback(
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    (_errorMessage: string) => {
      // Clear the current job from global state
      dispatch({ type: 'SET_CURRENT_JOB', payload: null })
    },
    [dispatch]
  )

  // Show generation progress if a global job is running
  const activeJobId = state.currentJob?.status === 'running' ? state.currentJob.job_id : null
  if (activeJobId) {
    return (
      <GenerationProgress
        jobId={activeJobId}
        onComplete={handleGenerationComplete}
        onError={handleGenerationError}
      />
    )
  }

  // Show loading spinner while page is loading OR while AppContext is still initializing
  // This prevents showing "not found" before we've checked for running jobs
  if (loading || state.isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600"></div>
      </div>
    )
  }

  if (notFound) {
    // If wiki hasn't been generated yet, show welcome message
    // last_generation is null when no wiki exists
    if (!state.repoStatus?.last_generation) {
      return (
        <div className="text-center py-12">
          <svg
            className="mx-auto h-12 w-12 text-gray-400"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={1.5}
              d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"
            />
          </svg>
          <h2 className="mt-4 text-xl font-semibold text-gray-900 dark:text-white">
            Welcome to Ọya!
          </h2>
          <p className="mt-2 text-gray-600 dark:text-gray-400 max-w-md mx-auto">
            To get started, click <strong>Generate Wiki</strong> in the top bar.
          </p>
        </div>
      )
    }

    // Wiki exists but this specific page doesn't - show 404
    return <NotFound />
  }

  if (error) {
    return (
      <div className="rounded-md bg-red-50 dark:bg-red-900/20 p-4">
        <div className="flex">
          <div className="flex-shrink-0">
            <svg className="h-5 w-5 text-red-400" viewBox="0 0 20 20" fill="currentColor">
              <path
                fillRule="evenodd"
                d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
                clipRule="evenodd"
              />
            </svg>
          </div>
          <div className="ml-3">
            <h3 className="text-sm font-medium text-red-800 dark:text-red-200">
              Error loading page
            </h3>
            <div className="mt-2 text-sm text-red-700 dark:text-red-300">{error}</div>
          </div>
        </div>
      </div>
    )
  }

  if (!page) {
    return (
      <div className="text-center py-12 text-gray-500 dark:text-gray-400">
        <p>Page not found.</p>
      </div>
    )
  }

  return <WikiContent page={page} />
}
