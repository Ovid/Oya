import { useState } from 'react'
import { useWikiStore, useGenerationStore, useUIStore } from '../stores'
import { IndexingPreviewModal } from './IndexingPreviewModal'
import { RepoDropdown } from './RepoDropdown'
import { AddRepoModal } from './AddRepoModal'

interface TopBarProps {
  onToggleSidebar: () => void
  onToggleRightSidebar: () => void
  onToggleAskPanel: () => void
  askPanelOpen: boolean
}

export function TopBar({
  onToggleSidebar,
  onToggleRightSidebar,
  onToggleAskPanel,
  askPanelOpen,
}: TopBarProps) {
  const repoStatus = useWikiStore((s) => s.repoStatus)
  const wikiIsLoading = useWikiStore((s) => s.isLoading)
  const currentJob = useGenerationStore((s) => s.currentJob)
  const generationIsLoading = useGenerationStore((s) => s.isLoading)
  const startGeneration = useGenerationStore((s) => s.startGeneration)
  const darkMode = useUIStore((s) => s.darkMode)
  const toggleDarkMode = useUIStore((s) => s.toggleDarkMode)
  const [isPreviewModalOpen, setIsPreviewModalOpen] = useState(false)
  const [isAddRepoModalOpen, setIsAddRepoModalOpen] = useState(false)
  const [showGeneratePrompt, setShowGeneratePrompt] = useState(false)

  const isLoading = wikiIsLoading || generationIsLoading
  const isGenerating = currentJob?.status === 'running' || currentJob?.status === 'pending'

  const handleRepoAdded = () => {
    setShowGeneratePrompt(true)
  }

  const getStatusBadge = () => {
    if (isLoading) {
      return (
        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200">
          <span className="animate-pulse mr-1">●</span>
          Loading...
        </span>
      )
    }

    if (isGenerating) {
      return (
        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200">
          <span className="animate-pulse mr-1">●</span>
          Generating...
        </span>
      )
    }

    if (repoStatus?.initialized) {
      return (
        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200">
          Ready
        </span>
      )
    }

    return (
      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200">
        Not initialized
      </span>
    )
  }

  return (
    <header className="fixed top-0 left-0 right-0 h-14 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 z-50">
      <div className="h-full px-4 flex items-center justify-between">
        {/* Left section */}
        <div className="flex items-center space-x-4">
          <button
            onClick={onToggleSidebar}
            className="p-2 rounded-md hover:bg-gray-100 dark:hover:bg-gray-700"
            title="Toggle sidebar"
          >
            <svg
              className="w-5 h-5 text-gray-600 dark:text-gray-300"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M4 6h16M4 12h16M4 18h16"
              />
            </svg>
          </button>

          <div className="flex items-center space-x-2">
            <span className="text-xl font-bold text-indigo-600 dark:text-indigo-400">Ọya</span>
            <RepoDropdown onAddRepo={() => setIsAddRepoModalOpen(true)} disabled={isGenerating} />
          </div>
        </div>

        {/* Center section */}
        <div className="flex items-center space-x-3">
          {getStatusBadge()}
          {repoStatus?.head_commit && (
            <span className="text-xs text-gray-400 dark:text-gray-500 font-mono">
              {repoStatus.head_commit.slice(0, 7)}
            </span>
          )}
        </div>

        {/* Right section */}
        <div className="flex items-center space-x-2">
          {!currentJob && (
            <button
              onClick={() => setIsPreviewModalOpen(true)}
              disabled={isLoading || isGenerating}
              className="px-3 py-1.5 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 rounded-md disabled:opacity-50"
            >
              Generate Wiki
            </button>
          )}

          <button
            onClick={onToggleAskPanel}
            disabled={isGenerating}
            className={`px-3 py-1.5 text-sm font-medium rounded-md ${
              isGenerating
                ? 'opacity-50 cursor-not-allowed'
                : askPanelOpen
                  ? 'text-white bg-indigo-600 hover:bg-indigo-700'
                  : 'text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600'
            }`}
            title={isGenerating ? 'Q&A unavailable during generation' : 'Ask about the codebase'}
          >
            Ask
          </button>

          <button
            onClick={toggleDarkMode}
            className="p-2 rounded-md hover:bg-gray-100 dark:hover:bg-gray-700"
            title={darkMode ? 'Switch to light mode' : 'Switch to dark mode'}
          >
            {darkMode ? (
              <svg
                className="w-5 h-5 text-gray-600 dark:text-gray-300"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"
                />
              </svg>
            ) : (
              <svg
                className="w-5 h-5 text-gray-600 dark:text-gray-300"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z"
                />
              </svg>
            )}
          </button>

          <button
            onClick={onToggleRightSidebar}
            className="p-2 rounded-md hover:bg-gray-100 dark:hover:bg-gray-700"
            title="Toggle right sidebar"
          >
            <svg
              className="w-5 h-5 text-gray-600 dark:text-gray-300"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M4 6h16M4 12h8m-8 6h16"
              />
            </svg>
          </button>
        </div>
      </div>

      {/* Indexing Preview Modal */}
      <IndexingPreviewModal
        isOpen={isPreviewModalOpen}
        onClose={() => setIsPreviewModalOpen(false)}
        onGenerate={() => startGeneration()}
      />

      {/* Add Repo Modal */}
      <AddRepoModal
        isOpen={isAddRepoModalOpen}
        onClose={() => setIsAddRepoModalOpen(false)}
        onRepoAdded={handleRepoAdded}
      />

      {/* Generate Wiki Prompt */}
      {showGeneratePrompt && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/50" onClick={() => setShowGeneratePrompt(false)} />
          <div className="relative bg-white dark:bg-gray-800 rounded-lg shadow-xl w-full max-w-sm mx-4 p-6">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-2">
              Repository Added
            </h3>
            <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
              Would you like to generate documentation for this repository now?
            </p>
            <div className="flex justify-end space-x-3">
              <button
                onClick={() => setShowGeneratePrompt(false)}
                className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 rounded-md"
              >
                Later
              </button>
              <button
                onClick={() => {
                  setShowGeneratePrompt(false)
                  setIsPreviewModalOpen(true)
                }}
                className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 rounded-md"
              >
                Generate Now
              </button>
            </div>
          </div>
        </div>
      )}
    </header>
  )
}
