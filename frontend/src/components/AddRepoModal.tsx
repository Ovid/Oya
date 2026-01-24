import { useState } from 'react'
import { useReposStore } from '../stores'
import type { Repo } from '../types'

interface AddRepoModalProps {
  isOpen: boolean
  onClose: () => void
  onSuccess?: () => void
  onRepoAdded?: (repo: Repo) => void
}

export function AddRepoModal({ isOpen, onClose, onSuccess, onRepoAdded }: AddRepoModalProps) {
  const [url, setUrl] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [localError, setLocalError] = useState<string | null>(null)

  const addRepo = useReposStore((s) => s.addRepo)
  const setActiveRepo = useReposStore((s) => s.setActiveRepo)
  const isLoading = useReposStore((s) => s.isLoading)
  const storeError = useReposStore((s) => s.error)
  const clearError = useReposStore((s) => s.clearError)

  const error = localError || storeError

  if (!isOpen) return null

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLocalError(null)
    clearError()

    if (!url.trim()) {
      setLocalError('URL or path is required')
      return
    }

    try {
      const repo = await addRepo(url.trim(), displayName.trim() || undefined)
      // Activate the newly created repo
      await setActiveRepo(repo.id)
      // Reset form
      setUrl('')
      setDisplayName('')
      onClose()
      onSuccess?.()
      onRepoAdded?.(repo)
    } catch {
      // Error is handled by store or localError
    }
  }

  const handleClose = () => {
    setUrl('')
    setDisplayName('')
    setLocalError(null)
    clearError()
    onClose()
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/50" onClick={handleClose} />

      {/* Modal */}
      <div className="relative bg-white dark:bg-gray-800 rounded-lg shadow-xl w-full max-w-md mx-4">
        {/* Header */}
        <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Add Repository</h2>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit}>
          <div className="px-6 py-4 space-y-4">
            <div>
              <label
                htmlFor="repo-url"
                className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1"
              >
                Repository URL or Path
              </label>
              <input
                type="text"
                id="repo-url"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://github.com/owner/repo or /path/to/local/repo"
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-indigo-500 focus:border-indigo-500 dark:bg-gray-700 dark:text-gray-100"
                disabled={isLoading}
                autoFocus
              />
              <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                Supports GitHub, GitLab, Bitbucket URLs, or local paths
              </p>
            </div>

            <div>
              <label
                htmlFor="display-name"
                className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1"
              >
                Display Name (optional)
              </label>
              <input
                type="text"
                id="display-name"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                placeholder="My Project"
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-indigo-500 focus:border-indigo-500 dark:bg-gray-700 dark:text-gray-100"
                disabled={isLoading}
              />
              <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                If not provided, will use the repository name
              </p>
            </div>

            {error && (
              <div className="p-3 bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-800 rounded-md">
                <p className="text-sm text-red-700 dark:text-red-300">{error}</p>
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="px-6 py-4 border-t border-gray-200 dark:border-gray-700 flex justify-end space-x-3">
            <button
              type="button"
              onClick={handleClose}
              disabled={isLoading}
              className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 rounded-md disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isLoading}
              className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 rounded-md disabled:opacity-50 flex items-center"
            >
              {isLoading && (
                <svg
                  className="animate-spin -ml-1 mr-2 h-4 w-4 text-white"
                  fill="none"
                  viewBox="0 0 24 24"
                >
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                  />
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                  />
                </svg>
              )}
              {isLoading ? 'Adding...' : 'Add Repository'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
