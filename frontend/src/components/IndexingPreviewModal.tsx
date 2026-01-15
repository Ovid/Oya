import { useState, useEffect, useMemo } from 'react'
import * as api from '../api/client'
import type { IndexableItems } from '../types'

interface IndexingPreviewModalProps {
  isOpen: boolean
  onClose: () => void
  onSave: () => void
}

interface PendingExclusions {
  directories: Set<string>
  files: Set<string>
}

/**
 * IndexingPreviewModal displays a preview of directories and files that will be indexed.
 * Users can selectively exclude items before generation.
 */
export function IndexingPreviewModal({ isOpen, onClose }: IndexingPreviewModalProps) {
  const [indexableItems, setIndexableItems] = useState<IndexableItems | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [pendingExclusions, setPendingExclusions] = useState<PendingExclusions>({
    directories: new Set(),
    files: new Set(),
  })
  const [showConfirmation, setShowConfirmation] = useState(false)
  const [isSaving, setIsSaving] = useState(false)

  // Fetch indexable items when modal opens
  useEffect(() => {
    if (!isOpen) {
      // Reset state when modal closes
      setIndexableItems(null)
      setError(null)
      setSearchQuery('')
      setPendingExclusions({ directories: new Set(), files: new Set() })
      setShowConfirmation(false)
      setIsSaving(false)
      return
    }

    const fetchItems = async () => {
      setIsLoading(true)
      setError(null)
      try {
        const items = await api.getIndexableItems()
        setIndexableItems(items)
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to load indexable items'
        setError(message)
      } finally {
        setIsLoading(false)
      }
    }

    fetchItems()
  }, [isOpen])

  // Filter directories based on search query and excluded parent directories (case-insensitive)
  const filteredDirectories = useMemo(() => {
    if (!indexableItems) return []

    let dirs = indexableItems.directories

    // Filter out directories that are children of excluded directories
    dirs = dirs.filter((dir) => {
      for (const excludedDir of pendingExclusions.directories) {
        if (dir.startsWith(excludedDir + '/')) {
          return false
        }
      }
      return true
    })

    // Apply search filter
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase()
      dirs = dirs.filter((dir) => dir.toLowerCase().includes(query))
    }

    return dirs
  }, [indexableItems, searchQuery, pendingExclusions.directories])

  // Filter files based on search query and excluded directories
  const filteredFiles = useMemo(() => {
    if (!indexableItems) return []

    let files = indexableItems.files

    // Filter out files within excluded directories
    files = files.filter((file) => {
      for (const excludedDir of pendingExclusions.directories) {
        if (file.startsWith(excludedDir + '/')) {
          return false
        }
      }
      return true
    })

    // Apply search filter
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase()
      files = files.filter((file) => file.toLowerCase().includes(query))
    }

    return files
  }, [indexableItems, searchQuery, pendingExclusions.directories])

  // Toggle directory exclusion
  const toggleDirectoryExclusion = (dir: string) => {
    setPendingExclusions((prev) => {
      const newDirs = new Set(prev.directories)
      let newFiles = prev.files

      if (newDirs.has(dir)) {
        newDirs.delete(dir)
      } else {
        newDirs.add(dir)
        // Clear any pending file exclusions within this directory
        newFiles = new Set(Array.from(prev.files).filter((file) => !file.startsWith(dir + '/')))
      }
      return { directories: newDirs, files: newFiles }
    })
  }

  // Toggle file exclusion
  const toggleFileExclusion = (file: string) => {
    setPendingExclusions((prev) => {
      const newFiles = new Set(prev.files)
      if (newFiles.has(file)) {
        newFiles.delete(file)
      } else {
        newFiles.add(file)
      }
      return { ...prev, files: newFiles }
    })
  }

  // Compute effective counts after exclusions
  const effectiveCounts = useMemo(() => {
    if (!indexableItems) return { directories: 0, files: 0 }

    // Count directories not excluded (including child directories of excluded parents)
    const includedDirs = indexableItems.directories.filter((dir) => {
      // Check if this directory is excluded
      if (pendingExclusions.directories.has(dir)) return false
      // Check if any parent directory is excluded
      for (const excludedDir of pendingExclusions.directories) {
        if (dir.startsWith(excludedDir + '/')) return false
      }
      return true
    })

    // Count files not excluded (including files in excluded directories)
    const includedFiles = indexableItems.files.filter((file) => {
      // Check if this file is excluded
      if (pendingExclusions.files.has(file)) return false
      // Check if any parent directory is excluded
      for (const excludedDir of pendingExclusions.directories) {
        if (file.startsWith(excludedDir + '/')) return false
      }
      return true
    })

    return {
      directories: includedDirs.length,
      files: includedFiles.length,
    }
  }, [indexableItems, pendingExclusions])

  // Check if there are any pending exclusions
  const hasExclusions = pendingExclusions.directories.size > 0 || pendingExclusions.files.size > 0

  // Handle save button click
  const handleSaveClick = () => {
    if (hasExclusions) {
      setShowConfirmation(true)
    }
  }

  // Handle confirmation
  const handleConfirm = async () => {
    setIsSaving(true)
    try {
      await api.updateOyaignore({
        directories: Array.from(pendingExclusions.directories),
        files: Array.from(pendingExclusions.files),
      })
      setShowConfirmation(false)
      onClose()
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to save exclusions'
      setError(message)
    } finally {
      setIsSaving(false)
    }
  }

  // Handle cancel confirmation
  const handleCancelConfirmation = () => {
    setShowConfirmation(false)
  }

  if (!isOpen) {
    return null
  }

  const handleBackdropClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (e.target === e.currentTarget) {
      onClose()
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      onClick={handleBackdropClick}
      data-testid="modal-backdrop"
    >
      <div
        className="bg-white dark:bg-gray-800 rounded-lg shadow-xl w-full max-w-4xl mx-4 max-h-[80vh] flex flex-col relative"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
            Indexing Preview
          </h2>
          <button
            onClick={onClose}
            className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700"
            aria-label="Close"
          >
            <svg
              className="w-5 h-5 text-gray-500"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-4">
          {isLoading ? (
            <p className="text-gray-500 dark:text-gray-400">Loading...</p>
          ) : error ? (
            <p className="text-red-600 dark:text-red-400">{error}</p>
          ) : indexableItems ? (
            <div className="space-y-6">
              {/* Search input */}
              <div>
                <input
                  type="text"
                  placeholder="Search directories and files..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 placeholder-gray-500 dark:placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>

              {/* Counts summary */}
              <div className="flex space-x-4 text-sm text-gray-600 dark:text-gray-400">
                <span>
                  {effectiveCounts.directories}{' '}
                  {effectiveCounts.directories === 1 ? 'directory' : 'directories'}
                </span>
                <span>
                  {effectiveCounts.files} {effectiveCounts.files === 1 ? 'file' : 'files'}
                </span>
              </div>

              {/* Directories section */}
              <div>
                <h3 className="text-md font-medium text-gray-900 dark:text-gray-100 mb-2">
                  Directories
                </h3>
                <div className="space-y-1">
                  {filteredDirectories.map((dir) => (
                    <div
                      key={dir}
                      className="flex items-center space-x-2 py-1 px-2 rounded hover:bg-gray-50 dark:hover:bg-gray-700"
                    >
                      <input
                        type="checkbox"
                        checked={pendingExclusions.directories.has(dir)}
                        onChange={() => toggleDirectoryExclusion(dir)}
                        className="h-4 w-4 text-indigo-600 border-gray-300 rounded focus:ring-indigo-500"
                      />
                      <svg
                        className="w-4 h-4 text-yellow-500"
                        fill="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
                      </svg>
                      <span
                        className={`text-sm ${
                          pendingExclusions.directories.has(dir)
                            ? 'text-gray-400 line-through'
                            : 'text-gray-700 dark:text-gray-300'
                        }`}
                      >
                        {dir}
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Files section */}
              <div>
                <h3 className="text-md font-medium text-gray-900 dark:text-gray-100 mb-2">Files</h3>
                <div className="space-y-1">
                  {filteredFiles.map((file) => (
                    <div
                      key={file}
                      className="flex items-center space-x-2 py-1 px-2 rounded hover:bg-gray-50 dark:hover:bg-gray-700"
                    >
                      <input
                        type="checkbox"
                        checked={pendingExclusions.files.has(file)}
                        onChange={() => toggleFileExclusion(file)}
                        className="h-4 w-4 text-indigo-600 border-gray-300 rounded focus:ring-indigo-500"
                      />
                      <svg
                        className="w-4 h-4 text-gray-400"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                        />
                      </svg>
                      <span
                        className={`text-sm ${
                          pendingExclusions.files.has(file)
                            ? 'text-gray-400 line-through'
                            : 'text-gray-700 dark:text-gray-300'
                        }`}
                      >
                        {file}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ) : null}
        </div>

        {/* Footer */}
        <div className="px-4 py-3 border-t border-gray-200 dark:border-gray-700 flex items-center justify-end space-x-2">
          <button
            onClick={onClose}
            className="px-3 py-1.5 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-md"
          >
            Cancel
          </button>
          <button
            onClick={handleSaveClick}
            disabled={!hasExclusions || isSaving}
            className="px-3 py-1.5 text-sm text-white bg-indigo-600 hover:bg-indigo-700 rounded-md disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Save
          </button>
        </div>

        {/* Confirmation Dialog */}
        {showConfirmation && (
          <div className="absolute inset-0 flex items-center justify-center bg-black/50 rounded-lg">
            <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl p-6 mx-4 max-w-md">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">
                Confirm Exclusions
              </h3>
              <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
                You are about to exclude:
              </p>
              <ul className="text-sm text-gray-700 dark:text-gray-300 mb-6 space-y-1">
                {pendingExclusions.directories.size > 0 && (
                  <li>
                    {pendingExclusions.directories.size}{' '}
                    {pendingExclusions.directories.size === 1 ? 'directory' : 'directories'}
                  </li>
                )}
                {pendingExclusions.files.size > 0 && (
                  <li>
                    {pendingExclusions.files.size}{' '}
                    {pendingExclusions.files.size === 1 ? 'file' : 'files'}
                  </li>
                )}
              </ul>
              <div className="flex justify-end space-x-2">
                <button
                  onClick={handleCancelConfirmation}
                  className="px-3 py-1.5 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-md"
                >
                  Cancel
                </button>
                <button
                  onClick={handleConfirm}
                  disabled={isSaving}
                  className="px-3 py-1.5 text-sm text-white bg-indigo-600 hover:bg-indigo-700 rounded-md disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {isSaving ? 'Saving...' : 'Confirm'}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
