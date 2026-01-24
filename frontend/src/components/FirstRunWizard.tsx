import { useState } from 'react'
import { useReposStore } from '../stores'

interface FirstRunWizardProps {
  onComplete?: () => void
}

export function FirstRunWizard({ onComplete }: FirstRunWizardProps) {
  const [url, setUrl] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [localError, setLocalError] = useState<string | null>(null)

  const addRepo = useReposStore((s) => s.addRepo)
  const setActiveRepo = useReposStore((s) => s.setActiveRepo)
  const isLoading = useReposStore((s) => s.isLoading)
  const storeError = useReposStore((s) => s.error)
  const clearError = useReposStore((s) => s.clearError)

  const error = localError || storeError

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLocalError(null)
    clearError()

    if (!url.trim()) {
      setLocalError('Please enter a repository URL or local path')
      return
    }

    try {
      const repo = await addRepo(url.trim(), displayName.trim() || undefined)
      await setActiveRepo(repo.id)
      onComplete?.()
    } catch {
      // Error is handled by store
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-900 p-4">
      <div className="max-w-md w-full">
        {/* Logo and welcome */}
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold text-indigo-600 dark:text-indigo-400 mb-2">Ọya</h1>
          <p className="text-xl text-gray-600 dark:text-gray-400">
            Welcome to your codebase wiki
          </p>
        </div>

        {/* Card */}
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl p-6">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">
            Add your first repository
          </h2>

          <p className="text-sm text-gray-600 dark:text-gray-400 mb-6">
            Enter a Git URL or local path to get started. Oya will clone the repository and
            generate documentation for it.
          </p>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label
                htmlFor="wizard-url"
                className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1"
              >
                Repository URL or Path
              </label>
              <input
                type="text"
                id="wizard-url"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://github.com/owner/repo"
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-indigo-500 focus:border-indigo-500 dark:bg-gray-700 dark:text-gray-100"
                disabled={isLoading}
                autoFocus
              />
            </div>

            <div>
              <label
                htmlFor="wizard-name"
                className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1"
              >
                Display Name (optional)
              </label>
              <input
                type="text"
                id="wizard-name"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                placeholder="My Project"
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-indigo-500 focus:border-indigo-500 dark:bg-gray-700 dark:text-gray-100"
                disabled={isLoading}
              />
            </div>

            {error && (
              <div className="p-3 bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-800 rounded-md">
                <p className="text-sm text-red-700 dark:text-red-300">{error}</p>
              </div>
            )}

            <button
              type="submit"
              disabled={isLoading}
              className="w-full px-4 py-2 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 rounded-md disabled:opacity-50 flex items-center justify-center"
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
              {isLoading ? 'Adding repository...' : 'Get Started'}
            </button>
          </form>

          {/* Examples */}
          <div className="mt-6 pt-6 border-t border-gray-200 dark:border-gray-700">
            <p className="text-xs text-gray-500 dark:text-gray-400 mb-2">Examples:</p>
            <ul className="text-xs text-gray-500 dark:text-gray-400 space-y-1">
              <li>
                <code className="bg-gray-100 dark:bg-gray-700 px-1 rounded">
                  https://github.com/owner/repo
                </code>
              </li>
              <li>
                <code className="bg-gray-100 dark:bg-gray-700 px-1 rounded">
                  git@github.com:owner/repo.git
                </code>
              </li>
              <li>
                <code className="bg-gray-100 dark:bg-gray-700 px-1 rounded">
                  /path/to/local/repo
                </code>
              </li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  )
}
