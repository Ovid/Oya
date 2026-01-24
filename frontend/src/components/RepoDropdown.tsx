import { useState, useRef, useEffect } from 'react'
import { useReposStore, useWikiStore, useGenerationStore } from '../stores'
import type { Repo } from '../types'

interface RepoDropdownProps {
  onAddRepo: () => void
  disabled?: boolean
}

export function RepoDropdown({ onAddRepo, disabled }: RepoDropdownProps) {
  const [isOpen, setIsOpen] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)

  const repos = useReposStore((s) => s.repos)
  const activeRepo = useReposStore((s) => s.activeRepo)
  const setActiveRepo = useReposStore((s) => s.setActiveRepo)
  const isLoading = useReposStore((s) => s.isLoading)
  const refreshStatus = useWikiStore((s) => s.refreshStatus)
  const refreshTree = useWikiStore((s) => s.refreshTree)
  const setCurrentJob = useGenerationStore((s) => s.setCurrentJob)

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside)
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [isOpen])

  const handleSelectRepo = async (repo: Repo) => {
    if (repo.id === activeRepo?.id) {
      setIsOpen(false)
      return
    }

    try {
      await setActiveRepo(repo.id)
      setIsOpen(false)

      // Refresh wiki data for the new repo
      setCurrentJob(null)
      await refreshStatus()
      await refreshTree()
    } catch {
      // Error is handled in store
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'ready':
        return 'bg-green-500'
      case 'generating':
        return 'bg-yellow-500 animate-pulse'
      case 'cloning':
        return 'bg-blue-500 animate-pulse'
      case 'failed':
        return 'bg-red-500'
      default:
        return 'bg-gray-400'
    }
  }

  return (
    <div ref={dropdownRef} className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        disabled={disabled || isLoading}
        className="flex items-center space-x-2 px-3 py-1.5 text-sm font-medium text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 rounded-md disabled:opacity-50"
      >
        {activeRepo ? (
          <>
            <span className={`w-2 h-2 rounded-full ${getStatusColor(activeRepo.status)}`} />
            <span className="max-w-[200px] truncate">{activeRepo.display_name}</span>
          </>
        ) : (
          <span className="text-gray-500 dark:text-gray-400">Select a repository</span>
        )}
        <svg
          className={`w-4 h-4 transition-transform ${isOpen ? 'rotate-180' : ''}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {isOpen && (
        <div className="absolute top-full left-0 mt-1 w-64 bg-white dark:bg-gray-800 rounded-md shadow-lg border border-gray-200 dark:border-gray-700 z-50">
          <div className="py-1 max-h-64 overflow-y-auto">
            {repos.length === 0 ? (
              <div className="px-4 py-3 text-sm text-gray-500 dark:text-gray-400">
                No repositories yet
              </div>
            ) : (
              repos.map((repo) => (
                <button
                  key={repo.id}
                  onClick={() => handleSelectRepo(repo)}
                  className={`w-full px-4 py-2 text-left flex items-center space-x-3 hover:bg-gray-100 dark:hover:bg-gray-700 ${
                    repo.id === activeRepo?.id ? 'bg-indigo-50 dark:bg-indigo-900/30' : ''
                  }`}
                >
                  <span
                    className={`w-2 h-2 rounded-full flex-shrink-0 ${getStatusColor(repo.status)}`}
                  />
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium text-gray-900 dark:text-gray-100 truncate">
                      {repo.display_name}
                    </div>
                    <div className="text-xs text-gray-500 dark:text-gray-400 truncate">
                      {repo.source_type === 'local' ? repo.origin_url : repo.local_path}
                    </div>
                  </div>
                  {repo.id === activeRepo?.id && (
                    <svg
                      className="w-4 h-4 text-indigo-600 dark:text-indigo-400 flex-shrink-0"
                      fill="currentColor"
                      viewBox="0 0 20 20"
                    >
                      <path
                        fillRule="evenodd"
                        d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                        clipRule="evenodd"
                      />
                    </svg>
                  )}
                </button>
              ))
            )}
          </div>

          <div className="border-t border-gray-200 dark:border-gray-700">
            <button
              onClick={() => {
                setIsOpen(false)
                onAddRepo()
              }}
              className="w-full px-4 py-2 text-left text-sm font-medium text-indigo-600 dark:text-indigo-400 hover:bg-gray-100 dark:hover:bg-gray-700 flex items-center space-x-2"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 4v16m8-8H4"
                />
              </svg>
              <span>Add Repository</span>
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
