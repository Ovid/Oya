import { useState, useEffect, useCallback } from 'react'
import { getLogs, deleteLogs } from '../api/client'

interface LogEntry {
  [key: string]: unknown
}

interface LogViewerModalProps {
  isOpen: boolean
  onClose: () => void
  repoId: number
  repoName: string
}

export function LogViewerModal({ isOpen, onClose, repoId, repoName }: LogViewerModalProps) {
  const [entries, setEntries] = useState<LogEntry[]>([])
  const [currentIndex, setCurrentIndex] = useState(0)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [isEmpty, setIsEmpty] = useState(false)
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const [searchTerm, setSearchTerm] = useState('')

  const loadLogs = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    setIsEmpty(false)

    try {
      const response = await getLogs(repoId)
      const parsed = response.content
        .split('\n')
        .filter((line) => line.trim())
        .map((line) => {
          try {
            return JSON.parse(line)
          } catch {
            return { error: 'Failed to parse entry' }
          }
        })

      if (parsed.length === 0) {
        setIsEmpty(true)
      } else {
        setEntries(parsed)
        setCurrentIndex(0)
      }
    } catch (e) {
      if ((e as { status?: number }).status === 404) {
        setIsEmpty(true)
      } else {
        setError(e instanceof Error ? e.message : 'Failed to load logs')
      }
    } finally {
      setIsLoading(false)
    }
  }, [repoId])

  useEffect(() => {
    if (isOpen) {
      loadLogs()
    } else {
      // Reset state when modal closes
      setEntries([])
      setCurrentIndex(0)
      setError(null)
      setIsEmpty(false)
      setShowDeleteConfirm(false)
      setSearchTerm('')
    }
  }, [isOpen, loadLogs])

  useEffect(() => {
    if (!isOpen) return

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement) return

      switch (e.key) {
        case 'ArrowRight':
        case 'j':
          if (currentIndex < entries.length - 1) {
            setCurrentIndex((i) => i + 1)
          }
          break
        case 'ArrowLeft':
        case 'k':
          if (currentIndex > 0) {
            setCurrentIndex((i) => i - 1)
          }
          break
        case 'Home':
          setCurrentIndex(0)
          e.preventDefault()
          break
        case 'End':
          setCurrentIndex(entries.length - 1)
          e.preventDefault()
          break
        case 'Escape':
          onClose()
          break
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, currentIndex, entries.length, onClose])

  const handleDelete = async () => {
    try {
      await deleteLogs(repoId)
      setEntries([])
      setIsEmpty(true)
      setShowDeleteConfirm(false)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to delete logs')
    }
  }

  const handleSearch = () => {
    if (!searchTerm) return

    const searchLower = searchTerm.toLowerCase()
    // Search from current index + 1 to end
    for (let i = currentIndex + 1; i < entries.length; i++) {
      if (JSON.stringify(entries[i]).toLowerCase().includes(searchLower)) {
        setCurrentIndex(i)
        return
      }
    }
    // Wrap around: search from beginning to current index
    for (let i = 0; i <= currentIndex; i++) {
      if (JSON.stringify(entries[i]).toLowerCase().includes(searchLower)) {
        setCurrentIndex(i)
        return
      }
    }
  }

  const handleBackdropClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (e.target === e.currentTarget) {
      onClose()
    }
  }

  if (!isOpen) return null

  const currentEntry = entries[currentIndex]

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      data-testid="modal-backdrop"
      onClick={handleBackdropClick}
    >
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/50" />

      {/* Modal */}
      <div
        className="relative bg-white dark:bg-gray-800 rounded-lg shadow-xl w-full max-w-4xl mx-4 max-h-[80vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">LLM Logs</h2>
            <p className="text-sm text-gray-500 dark:text-gray-400">{repoName}</p>
          </div>
          <div className="flex items-center space-x-2">
            {!isEmpty && entries.length > 0 && (
              <>
                <button
                  onClick={loadLogs}
                  className="p-2 rounded-md hover:bg-gray-100 dark:hover:bg-gray-700"
                  title="Refresh"
                  aria-label="refresh"
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
                      d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
                    />
                  </svg>
                </button>
                {!showDeleteConfirm ? (
                  <button
                    onClick={() => setShowDeleteConfirm(true)}
                    className="p-2 rounded-md hover:bg-red-100 dark:hover:bg-red-900/30"
                    title="Delete logs"
                    aria-label="delete"
                  >
                    <svg
                      className="w-5 h-5 text-red-600 dark:text-red-400"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                      />
                    </svg>
                  </button>
                ) : (
                  <div className="flex items-center space-x-2 bg-red-50 dark:bg-red-900/30 px-3 py-1 rounded-md">
                    <span className="text-sm text-red-700 dark:text-red-300">
                      Delete all LLM logs?
                    </span>
                    <button
                      onClick={() => setShowDeleteConfirm(false)}
                      className="px-2 py-1 text-xs font-medium text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 rounded"
                      aria-label="cancel"
                    >
                      Cancel
                    </button>
                    <button
                      onClick={handleDelete}
                      className="px-2 py-1 text-xs font-medium text-white bg-red-600 hover:bg-red-700 rounded"
                      aria-label="confirm"
                    >
                      Delete
                    </button>
                  </div>
                )}
              </>
            )}
            <button
              onClick={onClose}
              className="p-2 rounded-md hover:bg-gray-100 dark:hover:bg-gray-700"
              aria-label="close"
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
                  d="M6 18L18 6M6 6l12 12"
                />
              </svg>
            </button>
          </div>
        </div>

        {/* Loading state */}
        {isLoading && (
          <div className="flex-1 flex items-center justify-center p-8">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600"></div>
          </div>
        )}

        {/* Error state */}
        {error && !isLoading && (
          <div className="flex-1 flex flex-col items-center justify-center p-8">
            <p className="text-red-600 dark:text-red-400 mb-4">{error}</p>
            <button
              onClick={loadLogs}
              className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 rounded-md"
              aria-label="retry"
            >
              Retry
            </button>
          </div>
        )}

        {/* Empty state */}
        {isEmpty && !isLoading && !error && (
          <div className="flex-1 flex flex-col items-center justify-center p-8 text-center">
            <svg
              className="w-16 h-16 text-gray-300 dark:text-gray-600 mb-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.5}
                d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
              />
            </svg>
            <p className="text-lg font-medium text-gray-900 dark:text-gray-100 mb-2">
              No LLM logs yet for this repository
            </p>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              Logs are created when you generate documentation or use Q&A
            </p>
          </div>
        )}

        {/* Content */}
        {!isLoading && !error && !isEmpty && entries.length > 0 && (
          <>
            {/* Controls */}
            <div className="px-6 py-3 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between flex-wrap gap-3">
              <div className="flex items-center space-x-2">
                <button
                  onClick={() => setCurrentIndex(0)}
                  disabled={currentIndex === 0}
                  className="px-3 py-1.5 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 rounded-md disabled:opacity-50 disabled:cursor-not-allowed"
                  aria-label="first"
                >
                  First
                </button>
                <button
                  onClick={() => setCurrentIndex((i) => i - 1)}
                  disabled={currentIndex === 0}
                  className="px-3 py-1.5 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 rounded-md disabled:opacity-50 disabled:cursor-not-allowed"
                  aria-label="previous"
                >
                  Prev
                </button>
                <button
                  onClick={() => setCurrentIndex((i) => i + 1)}
                  disabled={currentIndex === entries.length - 1}
                  className="px-3 py-1.5 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 rounded-md disabled:opacity-50 disabled:cursor-not-allowed"
                  aria-label="next"
                >
                  Next
                </button>
                <button
                  onClick={() => setCurrentIndex(entries.length - 1)}
                  disabled={currentIndex === entries.length - 1}
                  className="px-3 py-1.5 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 rounded-md disabled:opacity-50 disabled:cursor-not-allowed"
                  aria-label="last"
                >
                  Last
                </button>
              </div>

              <span className="text-sm font-medium text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-700 px-3 py-1.5 rounded-md">
                Entry {currentIndex + 1} of {entries.length}
              </span>

              <div className="flex items-center space-x-2">
                <input
                  type="text"
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                  placeholder="Search..."
                  className="px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-md dark:bg-gray-700 dark:text-gray-100"
                />
                <button
                  onClick={handleSearch}
                  className="px-3 py-1.5 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 rounded-md"
                  aria-label="find"
                >
                  Find
                </button>
              </div>
            </div>

            {/* Entry metadata */}
            {currentEntry && (
              <div className="px-6 py-2 border-b border-gray-200 dark:border-gray-700 flex flex-wrap gap-4 text-sm">
                {'timestamp' in currentEntry && currentEntry.timestamp != null && (
                  <div>
                    <span className="font-medium text-gray-700 dark:text-gray-300">
                      Timestamp:{' '}
                    </span>
                    <span className="text-gray-600 dark:text-gray-400">
                      {String(currentEntry.timestamp)}
                    </span>
                  </div>
                )}
                {'provider' in currentEntry && currentEntry.provider != null && (
                  <div>
                    <span className="font-medium text-gray-700 dark:text-gray-300">
                      Provider:{' '}
                    </span>
                    <span className="text-gray-600 dark:text-gray-400">
                      {String(currentEntry.provider)}
                    </span>
                  </div>
                )}
                {'model' in currentEntry && currentEntry.model != null && (
                  <div>
                    <span className="font-medium text-gray-700 dark:text-gray-300">Model: </span>
                    <span className="text-gray-600 dark:text-gray-400">
                      {String(currentEntry.model)}
                    </span>
                  </div>
                )}
              </div>
            )}

            {/* JSON display */}
            <div className="flex-1 overflow-auto p-6">
              <pre className="bg-gray-900 dark:bg-gray-950 text-gray-100 p-4 rounded-lg text-sm font-mono overflow-x-auto whitespace-pre-wrap">
                <JsonDisplay data={currentEntry} />
              </pre>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

function JsonDisplay({ data, indent = 0 }: { data: unknown; indent?: number }) {
  const spaces = '  '.repeat(indent)

  if (data === null) return <span className="text-purple-400">null</span>
  if (typeof data === 'boolean') return <span className="text-purple-400">{String(data)}</span>
  if (typeof data === 'number') return <span className="text-green-400">{data}</span>
  if (typeof data === 'string') return <span className="text-amber-400">"{data}"</span>

  if (Array.isArray(data)) {
    if (data.length === 0) return <span>[]</span>
    return (
      <>
        {'[\n'}
        {data.map((item, i) => (
          <span key={i}>
            {spaces} <JsonDisplay data={item} indent={indent + 1} />
            {i < data.length - 1 ? ',' : ''}
            {'\n'}
          </span>
        ))}
        {spaces}]
      </>
    )
  }

  if (typeof data === 'object') {
    const entries = Object.entries(data as Record<string, unknown>)
    if (entries.length === 0) return <span>{'{}'}</span>
    return (
      <>
        {'{\n'}
        {entries.map(([key, value], i) => (
          <span key={key}>
            {spaces} <span className="text-blue-400">"{key}"</span>:{' '}
            <JsonDisplay data={value} indent={indent + 1} />
            {i < entries.length - 1 ? ',' : ''}
            {'\n'}
          </span>
        ))}
        {spaces}
        {'}'}
      </>
    )
  }

  return <span>{String(data)}</span>
}
