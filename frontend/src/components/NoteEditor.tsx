import { useState, useEffect } from 'react'
import { saveNote } from '../api/client'
import { useNoteEditorStore } from '../stores'
import type { NoteScope, Note } from '../types'

interface NoteEditorProps {
  isOpen: boolean
  onClose: () => void
  onSaved: (note: Note) => void
  scope: NoteScope
  target: string
  existingContent?: string
}

export function NoteEditor({
  isOpen,
  onClose,
  onSaved,
  scope,
  target,
  existingContent = '',
}: NoteEditorProps) {
  const isDirty = useNoteEditorStore((s) => s.isDirty)
  const setDirty = useNoteEditorStore((s) => s.setDirty)
  const [content, setContent] = useState(existingContent)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const isEditing = !!existingContent

  // Reset state when editor opens
  useEffect(() => {
    if (isOpen) {
      setContent(existingContent)
      setError(null)
    }
  }, [isOpen, existingContent])

  // Confirm before closing with unsaved changes
  const handleClose = () => {
    if (isDirty) {
      if (window.confirm('You have unsaved changes. Are you sure you want to close?')) {
        setDirty(false)
        onClose()
      }
    } else {
      onClose()
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!content.trim()) return

    setIsSubmitting(true)
    setError(null)

    try {
      const note = await saveNote(scope, target, content.trim())
      setDirty(false)
      onSaved(note)
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save correction')
    } finally {
      setIsSubmitting(false)
    }
  }

  if (!isOpen) return null

  const scopeLabel =
    scope === 'file'
      ? 'File'
      : scope === 'directory'
        ? 'Directory'
        : scope === 'workflow'
          ? 'Workflow'
          : 'General'

  return (
    <div className="fixed inset-0 z-50 overflow-hidden">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black bg-opacity-50" onClick={handleClose} />

      {/* Slide-over panel */}
      <div className="absolute inset-y-0 right-0 max-w-lg w-full bg-white dark:bg-gray-800 shadow-xl">
        <form onSubmit={handleSubmit} className="h-full flex flex-col">
          {/* Header */}
          <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
              {isEditing ? 'Edit Correction' : 'Add Correction'}
            </h2>
            <button
              type="button"
              onClick={handleClose}
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
            {/* Target info */}
            <div className="p-3 bg-gray-100 dark:bg-gray-700 rounded-lg">
              <div className="text-sm text-gray-500 dark:text-gray-400">{scopeLabel}</div>
              <div className="font-mono text-sm text-gray-900 dark:text-white">
                {target || '(general)'}
              </div>
            </div>

            {/* Content editor */}
            <div className="flex-1">
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Correction (Markdown supported)
              </label>
              <textarea
                value={content}
                onChange={(e) => {
                  setContent(e.target.value)
                  setDirty(!!e.target.value.trim() && e.target.value !== existingContent)
                }}
                placeholder="Describe the correction. This will be shown to the LLM during wiki generation..."
                rows={12}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono text-sm"
                autoFocus
              />
              <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                This correction will be included in the LLM prompt when regenerating documentation
                for this {scope}.
              </p>
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
              onClick={handleClose}
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
