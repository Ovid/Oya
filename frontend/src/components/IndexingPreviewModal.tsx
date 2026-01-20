import { useState, useEffect, useMemo } from 'react'
import * as api from '../api/client'
import type { IndexableItems } from '../types'
import { ConfirmationDialog } from './ConfirmationDialog'

interface IndexingPreviewModalProps {
  isOpen: boolean
  onClose: () => void
  onGenerate: () => void
}

interface PendingExclusions {
  directories: Set<string>
  files: Set<string>
}

/**
 * IndexingPreviewModal displays a preview of directories and files that will be indexed.
 * Users can selectively exclude items before generation.
 *
 * Files are displayed in three visual states:
 * 1. Included (default) - Checkbox checked, normal text
 * 2. Excluded via .oyaignore - Checkbox unchecked, "(from .oyaignore)" badge, can be re-included
 * 3. Excluded via rules - Checkbox disabled/grayed, "(excluded by rule)" badge, cannot change
 */
export function IndexingPreviewModal({ isOpen, onClose, onGenerate }: IndexingPreviewModalProps) {
  const [indexableItems, setIndexableItems] = useState<IndexableItems | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  // Track items to exclude (unchecked from included list)
  const [pendingExclusions, setPendingExclusions] = useState<PendingExclusions>({
    directories: new Set(),
    files: new Set(),
  })
  // Track patterns to re-include (checked from oyaignore list)
  const [pendingInclusions, setPendingInclusions] = useState<Set<string>>(new Set())
  const [showGenerateConfirm, setShowGenerateConfirm] = useState(false)
  const [showUnsavedWarning, setShowUnsavedWarning] = useState(false)
  const [isSaving, setIsSaving] = useState(false)

  // Fetch indexable items when modal opens
  useEffect(() => {
    if (!isOpen) {
      // Reset state when modal closes
      setIndexableItems(null)
      setError(null)
      setSearchQuery('')
      setPendingExclusions({ directories: new Set(), files: new Set() })
      setPendingInclusions(new Set())
      setShowGenerateConfirm(false)
      setShowUnsavedWarning(false)
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

  // Filter included directories based on search query and excluded parent directories
  const filteredIncludedDirectories = useMemo(() => {
    if (!indexableItems) return []

    let dirs = indexableItems.included.directories

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

  // Filter included files based on search query and excluded directories
  const filteredIncludedFiles = useMemo(() => {
    if (!indexableItems) return []

    let files = indexableItems.included.files

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

  // Filter oyaignore directories
  const filteredOyaignoreDirectories = useMemo(() => {
    if (!indexableItems) return []

    let dirs = indexableItems.excluded_by_oyaignore.directories

    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase()
      dirs = dirs.filter((dir) => dir.toLowerCase().includes(query))
    }

    return dirs
  }, [indexableItems, searchQuery])

  // Filter oyaignore files
  const filteredOyaignoreFiles = useMemo(() => {
    if (!indexableItems) return []

    let files = indexableItems.excluded_by_oyaignore.files

    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase()
      files = files.filter((file) => file.toLowerCase().includes(query))
    }

    return files
  }, [indexableItems, searchQuery])

  // Filter rule-excluded directories
  const filteredRuleDirectories = useMemo(() => {
    if (!indexableItems) return []

    let dirs = indexableItems.excluded_by_rule.directories

    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase()
      dirs = dirs.filter((dir) => dir.toLowerCase().includes(query))
    }

    return dirs
  }, [indexableItems, searchQuery])

  // Filter rule-excluded files
  const filteredRuleFiles = useMemo(() => {
    if (!indexableItems) return []

    let files = indexableItems.excluded_by_rule.files

    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase()
      files = files.filter((file) => file.toLowerCase().includes(query))
    }

    return files
  }, [indexableItems, searchQuery])

  // Toggle directory exclusion (for included directories)
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

  // Toggle file exclusion (for included files)
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

  // Toggle inclusion for oyaignore items (re-include by removing from .oyaignore)
  const toggleInclusion = (pattern: string) => {
    setPendingInclusions((prev) => {
      const newSet = new Set(prev)
      if (newSet.has(pattern)) {
        newSet.delete(pattern)
      } else {
        newSet.add(pattern)
      }
      return newSet
    })
  }

  // Compute effective counts after exclusions
  const effectiveCounts = useMemo(() => {
    if (!indexableItems) return { directories: 0, files: 0 }

    // Count included directories not excluded (including child directories of excluded parents)
    const includedDirs = indexableItems.included.directories.filter((dir) => {
      // Check if this directory is excluded
      if (pendingExclusions.directories.has(dir)) return false
      // Check if any parent directory is excluded
      for (const excludedDir of pendingExclusions.directories) {
        if (dir.startsWith(excludedDir + '/')) return false
      }
      return true
    })

    // Count included files not excluded (including files in excluded directories)
    const includedFiles = indexableItems.included.files.filter((file) => {
      // Check if this file is excluded
      if (pendingExclusions.files.has(file)) return false
      // Check if any parent directory is excluded
      for (const excludedDir of pendingExclusions.directories) {
        if (file.startsWith(excludedDir + '/')) return false
      }
      return true
    })

    // Count oyaignore items that will be re-included
    const reincludedDirs = indexableItems.excluded_by_oyaignore.directories.filter((dir) =>
      pendingInclusions.has(dir)
    )
    const reincludedFiles = indexableItems.excluded_by_oyaignore.files.filter((file) =>
      pendingInclusions.has(file)
    )

    return {
      directories: includedDirs.length + reincludedDirs.length,
      files: includedFiles.length + reincludedFiles.length,
    }
  }, [indexableItems, pendingExclusions, pendingInclusions])

  // Check if there are any pending changes
  const hasChanges =
    pendingExclusions.directories.size > 0 ||
    pendingExclusions.files.size > 0 ||
    pendingInclusions.size > 0

  // Handle close with unsaved check
  const handleClose = () => {
    if (hasChanges) {
      setShowUnsavedWarning(true)
    } else {
      onClose()
    }
  }

  // Handle generate button click
  const handleGenerateClick = () => {
    setShowGenerateConfirm(true)
  }

  // Handle generation confirm
  const handleConfirmGenerate = async () => {
    setIsSaving(true)
    try {
      if (hasChanges) {
        await api.updateOyaignore({
          directories: Array.from(pendingExclusions.directories),
          files: Array.from(pendingExclusions.files),
          removals: Array.from(pendingInclusions),
        })
      }
      onGenerate()
      onClose()
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to save changes'
      setError(message)
    } finally {
      setShowGenerateConfirm(false)
      setIsSaving(false)
    }
  }

  // Handle cancel generate confirmation
  const handleCancelGenerateConfirm = () => {
    setShowGenerateConfirm(false)
  }

  // Handle discard changes
  const handleDiscardChanges = () => {
    setShowUnsavedWarning(false)
    onClose()
  }

  // Handle keep editing
  const handleKeepEditing = () => {
    setShowUnsavedWarning(false)
  }

  if (!isOpen) {
    return null
  }

  const handleBackdropClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (e.target === e.currentTarget) {
      handleClose()
    }
  }

  // Check if we have any items in each category
  const hasIncludedItems =
    indexableItems &&
    (indexableItems.included.directories.length > 0 || indexableItems.included.files.length > 0)
  const hasOyaignoreItems =
    indexableItems &&
    (indexableItems.excluded_by_oyaignore.directories.length > 0 ||
      indexableItems.excluded_by_oyaignore.files.length > 0)
  const hasRuleItems =
    indexableItems &&
    (indexableItems.excluded_by_rule.directories.length > 0 ||
      indexableItems.excluded_by_rule.files.length > 0)

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
            onClick={handleClose}
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

              {/* Included items section */}
              {hasIncludedItems && (
                <>
                  {/* Included Directories */}
                  {filteredIncludedDirectories.length > 0 && (
                    <div>
                      <h3 className="text-md font-medium text-gray-900 dark:text-gray-100 mb-2">
                        Directories
                      </h3>
                      <div className="space-y-1">
                        {filteredIncludedDirectories.map((dir) => {
                          const isExcluded = pendingExclusions.directories.has(dir)
                          return (
                            <div
                              key={dir}
                              className="flex items-center space-x-2 py-1 px-2 rounded hover:bg-gray-50 dark:hover:bg-gray-700"
                            >
                              <input
                                type="checkbox"
                                checked={!isExcluded}
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
                                  isExcluded
                                    ? 'text-gray-400 line-through'
                                    : 'text-gray-700 dark:text-gray-300'
                                }`}
                              >
                                {dir}
                              </span>
                            </div>
                          )
                        })}
                      </div>
                    </div>
                  )}

                  {/* Included Files */}
                  {filteredIncludedFiles.length > 0 && (
                    <div>
                      <h3 className="text-md font-medium text-gray-900 dark:text-gray-100 mb-2">
                        Files
                      </h3>
                      <div className="space-y-1">
                        {filteredIncludedFiles.map((file) => {
                          const isExcluded = pendingExclusions.files.has(file)
                          return (
                            <div
                              key={file}
                              className="flex items-center space-x-2 py-1 px-2 rounded hover:bg-gray-50 dark:hover:bg-gray-700"
                            >
                              <input
                                type="checkbox"
                                checked={!isExcluded}
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
                                  isExcluded
                                    ? 'text-gray-400 line-through'
                                    : 'text-gray-700 dark:text-gray-300'
                                }`}
                              >
                                {file}
                              </span>
                            </div>
                          )
                        })}
                      </div>
                    </div>
                  )}
                </>
              )}

              {/* Excluded by .oyaignore section */}
              {hasOyaignoreItems && (
                <div className="border-t border-gray-200 dark:border-gray-700 pt-4">
                  <h3 className="text-md font-medium text-gray-900 dark:text-gray-100 mb-2">
                    Excluded by .oyaignore
                  </h3>
                  <p className="text-xs text-gray-500 dark:text-gray-400 mb-2">
                    Check to remove from .oyaignore and include in indexing
                  </p>
                  <div className="space-y-1">
                    {/* Oyaignore directories */}
                    {filteredOyaignoreDirectories.map((dir) => {
                      const willInclude = pendingInclusions.has(dir)
                      return (
                        <div
                          key={`oyaignore-dir-${dir}`}
                          className="flex items-center space-x-2 py-1 px-2 rounded hover:bg-gray-50 dark:hover:bg-gray-700"
                        >
                          <input
                            type="checkbox"
                            checked={willInclude}
                            onChange={() => toggleInclusion(dir)}
                            className="h-4 w-4 text-indigo-600 border-gray-300 rounded focus:ring-indigo-500"
                          />
                          <svg
                            className="w-4 h-4 text-yellow-500 opacity-50"
                            fill="currentColor"
                            viewBox="0 0 24 24"
                          >
                            <path d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
                          </svg>
                          <span
                            className={`text-sm ${
                              willInclude
                                ? 'text-gray-700 dark:text-gray-300'
                                : 'text-gray-400 dark:text-gray-500'
                            }`}
                          >
                            {dir}
                          </span>
                          <span className="text-xs text-gray-400 dark:text-gray-500 ml-2">
                            (from .oyaignore)
                          </span>
                        </div>
                      )
                    })}
                    {/* Oyaignore files */}
                    {filteredOyaignoreFiles.map((file) => {
                      const willInclude = pendingInclusions.has(file)
                      return (
                        <div
                          key={`oyaignore-file-${file}`}
                          className="flex items-center space-x-2 py-1 px-2 rounded hover:bg-gray-50 dark:hover:bg-gray-700"
                        >
                          <input
                            type="checkbox"
                            checked={willInclude}
                            onChange={() => toggleInclusion(file)}
                            className="h-4 w-4 text-indigo-600 border-gray-300 rounded focus:ring-indigo-500"
                          />
                          <svg
                            className="w-4 h-4 text-gray-400 opacity-50"
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
                              willInclude
                                ? 'text-gray-700 dark:text-gray-300'
                                : 'text-gray-400 dark:text-gray-500'
                            }`}
                          >
                            {file}
                          </span>
                          <span className="text-xs text-gray-400 dark:text-gray-500 ml-2">
                            (from .oyaignore)
                          </span>
                        </div>
                      )
                    })}
                  </div>
                </div>
              )}

              {/* Excluded by rule section */}
              {hasRuleItems && (
                <div className="border-t border-gray-200 dark:border-gray-700 pt-4">
                  <h3 className="text-md font-medium text-gray-900 dark:text-gray-100 mb-2">
                    Excluded by Rules
                  </h3>
                  <p className="text-xs text-gray-500 dark:text-gray-400 mb-2">
                    These items are excluded by system rules and cannot be changed
                  </p>
                  <div className="space-y-1">
                    {/* Rule-excluded directories */}
                    {filteredRuleDirectories.map((dir) => (
                      <div
                        key={`rule-dir-${dir}`}
                        className="flex items-center space-x-2 py-1 px-2 rounded opacity-50"
                      >
                        <input
                          type="checkbox"
                          checked={false}
                          disabled
                          className="h-4 w-4 text-gray-400 border-gray-300 rounded cursor-not-allowed"
                        />
                        <svg
                          className="w-4 h-4 text-yellow-500 opacity-50"
                          fill="currentColor"
                          viewBox="0 0 24 24"
                        >
                          <path d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
                        </svg>
                        <span className="text-sm text-gray-400 dark:text-gray-500">{dir}</span>
                        <span className="text-xs text-gray-400 dark:text-gray-500 ml-2">
                          (excluded by rule)
                        </span>
                      </div>
                    ))}
                    {/* Rule-excluded files */}
                    {filteredRuleFiles.map((file) => (
                      <div
                        key={`rule-file-${file}`}
                        className="flex items-center space-x-2 py-1 px-2 rounded opacity-50"
                      >
                        <input
                          type="checkbox"
                          checked={false}
                          disabled
                          className="h-4 w-4 text-gray-400 border-gray-300 rounded cursor-not-allowed"
                        />
                        <svg
                          className="w-4 h-4 text-gray-400 opacity-50"
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
                        <span className="text-sm text-gray-400 dark:text-gray-500">{file}</span>
                        <span className="text-xs text-gray-400 dark:text-gray-500 ml-2">
                          (excluded by rule)
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : null}
        </div>

        {/* Footer */}
        <div className="px-4 py-3 border-t border-gray-200 dark:border-gray-700 flex items-center justify-end space-x-2">
          <button
            onClick={handleClose}
            className="px-3 py-1.5 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-md"
          >
            Cancel
          </button>
          <button
            onClick={handleGenerateClick}
            className="px-3 py-1.5 text-sm text-white bg-indigo-600 hover:bg-indigo-700 rounded-md"
          >
            Generate Wiki
          </button>
        </div>

        {/* Generate Wiki Confirmation Dialog */}
        <ConfirmationDialog
          isOpen={showGenerateConfirm}
          title="Generate Wiki"
          confirmLabel={isSaving ? 'Generating...' : 'Generate'}
          onConfirm={handleConfirmGenerate}
          onCancel={handleCancelGenerateConfirm}
        >
          <p className="mb-2">{effectiveCounts.files} files will be indexed</p>
          {hasChanges && (
            <p className="text-gray-500 dark:text-gray-400">.oyaignore will be updated</p>
          )}
        </ConfirmationDialog>

        {/* Unsaved Changes Warning Dialog */}
        <ConfirmationDialog
          isOpen={showUnsavedWarning}
          title="Unsaved Changes"
          confirmLabel="Discard Changes"
          cancelLabel="Keep Editing"
          onConfirm={handleDiscardChanges}
          onCancel={handleKeepEditing}
        >
          <p>You have exclusion changes that haven't been saved. Close anyway?</p>
        </ConfirmationDialog>
      </div>
    </div>
  )
}
