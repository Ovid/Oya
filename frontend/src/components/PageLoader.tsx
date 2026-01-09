import { useEffect, useState, useCallback } from 'react';
import type { WikiPage } from '../types';
import { WikiContent } from './WikiContent';
import { useApp } from '../context/AppContext';
import { ApiError } from '../api/client';
import { GenerationProgress } from './GenerationProgress';

interface PageLoaderProps {
  loadPage: () => Promise<WikiPage>;
}

export function PageLoader({ loadPage }: PageLoaderProps) {
  const { dispatch, startGeneration, refreshTree, state } = useApp();
  const [page, setPage] = useState<WikiPage | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [generatingJobId, setGeneratingJobId] = useState<string | null>(null);
  const [generationError, setGenerationError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      setLoading(true);
      setError(null);
      setNotFound(false);

      try {
        const data = await loadPage();
        if (!cancelled) {
          setPage(data);
          dispatch({ type: 'SET_CURRENT_PAGE', payload: data });
        }
      } catch (err) {
        if (!cancelled) {
          if (err instanceof ApiError && err.status === 404) {
            setNotFound(true);
          } else {
            setError(err instanceof Error ? err.message : 'Failed to load page');
          }
          dispatch({ type: 'SET_CURRENT_PAGE', payload: null });
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    load();

    return () => {
      cancelled = true;
    };
  }, [loadPage, dispatch]);

  const handleGenerate = async () => {
    setGenerationError(null);
    const jobId = await startGeneration();
    if (jobId) {
      setGeneratingJobId(jobId);
    }
  };

  const handleGenerationComplete = useCallback(async () => {
    setGeneratingJobId(null);
    // Clear the current job from global state
    dispatch({ type: 'SET_CURRENT_JOB', payload: null });
    // Refresh the wiki tree and reload the page
    await refreshTree();
    // Re-trigger page load
    setLoading(true);
    setNotFound(false);
    try {
      const data = await loadPage();
      setPage(data);
      dispatch({ type: 'SET_CURRENT_PAGE', payload: data });
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        setNotFound(true);
      } else {
        setError(err instanceof Error ? err.message : 'Failed to load page');
      }
    } finally {
      setLoading(false);
    }
  }, [loadPage, dispatch, refreshTree]);

  const handleGenerationError = useCallback((errorMessage: string) => {
    setGeneratingJobId(null);
    setGenerationError(errorMessage);
    // Clear the current job from global state
    dispatch({ type: 'SET_CURRENT_JOB', payload: null });
  }, [dispatch]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600"></div>
      </div>
    );
  }

  // Show generation progress if a job is running (either local or global)
  const activeJobId = generatingJobId || (state.currentJob?.status === 'running' ? state.currentJob.job_id : null);
  if (activeJobId) {
    return (
      <GenerationProgress
        jobId={activeJobId}
        onComplete={handleGenerationComplete}
        onError={handleGenerationError}
      />
    );
  }

  if (notFound) {
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
          Welcome to Oya
        </h2>
        <p className="mt-2 text-gray-600 dark:text-gray-400 max-w-md mx-auto">
          No documentation has been generated yet. Click the button below to analyze your codebase and generate comprehensive documentation.
        </p>

        {generationError && (
          <div className="mt-4 rounded-md bg-red-50 dark:bg-red-900/20 p-4 max-w-md mx-auto">
            <div className="flex">
              <div className="flex-shrink-0">
                <svg className="h-5 w-5 text-red-400" viewBox="0 0 20 20" fill="currentColor">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                </svg>
              </div>
              <div className="ml-3 text-left">
                <h3 className="text-sm font-medium text-red-800 dark:text-red-200">
                  Generation failed
                </h3>
                <div className="mt-1 text-sm text-red-700 dark:text-red-300">
                  {generationError}
                </div>
              </div>
            </div>
          </div>
        )}

        <button
          onClick={handleGenerate}
          disabled={state.currentJob?.status === 'running'}
          className="mt-6 inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {generationError ? 'Try Again' : 'Generate Documentation'}
        </button>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-md bg-red-50 dark:bg-red-900/20 p-4">
        <div className="flex">
          <div className="flex-shrink-0">
            <svg className="h-5 w-5 text-red-400" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
            </svg>
          </div>
          <div className="ml-3">
            <h3 className="text-sm font-medium text-red-800 dark:text-red-200">
              Error loading page
            </h3>
            <div className="mt-2 text-sm text-red-700 dark:text-red-300">
              {error}
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (!page) {
    return (
      <div className="text-center py-12 text-gray-500 dark:text-gray-400">
        <p>Page not found.</p>
      </div>
    );
  }

  return <WikiContent page={page} />;
}
