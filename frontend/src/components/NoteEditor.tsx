import { useState, useEffect } from 'react'
import { saveNote } from '../api/client'
import { useNoteEditorStore } from '../stores'
import type { NoteScope, Note } from '../types'

interface NoteEditorProps {
  isOpen: boolean
  onClose: () => void
  onNoteCreated?: (note: Note) => void
  defaultScope?: NoteScope
  defaultTarget?: string
}

export function NoteEditor({
  isOpen,
  onClose,
  onNoteCreated,
  defaultScope = 'general',
  defaultTarget = '',
}: NoteEditorProps) {
  const setDirty = useNoteEditorStore((s) => s.setDirty)
  const [scope, setScope] = useState<NoteScope>(defaultScope)
  const [target, setTarget] = useState(defaultTarget)
  const [content, setContent] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Reset state when editor opens
  useEffect(() => {
    if (isOpen) {
      setScope(defaultScope)
      setTarget(defaultTarget)
      setContent('')
      setError(null)
    }
  }, [isOpen, defaultScope, defaultTarget])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!content.trim()) return

    setIsSubmitting(true)
    setError(null)

    try {
      const actualTarget = scope === 'general' ? '_general' : target
      const note = await saveNote(scope, actualTarget, content.trim())
      onNoteCreated?.(note)
      onClose()
      setContent('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save note')
    } finally {
      setIsSubmitting(false)
    }
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 overflow-hidden">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black bg-opacity-50" onClick={onClose} />

      {/* Slide-over panel */}
      <div className="absolute inset-y-0 right-0 max-w-lg w-full bg-white dark:bg-gray-800 shadow-xl">
        <form onSubmit={handleSubmit} className="h-full flex flex-col">
          {/* Header */}
          <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Add Correction</h2>
            <button
              type="button"
              onClick={onClose}
              className="text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M6 18L18 6M6 6l12 12"
                />
              </svg>
            </button>
          </div>

          {/* Body */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {/* Scope selector */}
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Scope
              </label>
              <div className="flex gap-2 flex-wrap">
                {(['general', 'file', 'directory', 'workflow'] as NoteScope[]).map((s) => (
                  <button
                    key={s}
                    type="button"
                    onClick={() => setScope(s)}
                    className={`px-3 py-1 text-sm rounded capitalize ${
                      scope === s
                        ? 'bg-blue-600 text-white'
                        : 'bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300'
                    }`}
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>

            {/* Target input */}
            {scope !== 'general' && (
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Target{' '}
                  {scope === 'file' ? 'File' : scope === 'directory' ? 'Directory' : 'Workflow'}
                </label>
                <input
                  type="text"
                  value={target}
                  onChange={(e) => setTarget(e.target.value)}
                  placeholder={
                    scope === 'file'
                      ? 'e.g., src/main.py'
                      : scope === 'directory'
                        ? 'e.g., src/utils'
                        : 'e.g., authentication'
                  }
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            )}

            {/* Content editor */}
            <div className="flex-1">
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Correction (Markdown supported)
              </label>
              <textarea
                value={content}
                onChange={(e) => {
                  setContent(e.target.value)
                  setDirty(!!e.target.value.trim())
                }}
                placeholder="Describe the correction or additional information..."
                rows={10}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono text-sm"
              />
            </div>

            {/* Error message */}
            {error && (
              <div className="p-3 bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 rounded-lg text-sm">
                {error}
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="px-4 py-3 border-t border-gray-200 dark:border-gray-700 flex justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting || !content.trim()}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isSubmitting ? 'Saving...' : 'Save Correction'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
