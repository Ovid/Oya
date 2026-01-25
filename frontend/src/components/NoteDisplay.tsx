import { useState } from 'react'
import { deleteNote } from '../api/client'
import type { Note, NoteScope } from '../types'

interface NoteDisplayProps {
  note: Note
  scope: NoteScope
  target: string
  onEdit: () => void
  onDeleted: () => void
}

export function NoteDisplay({ note, scope, target, onEdit, onDeleted }: NoteDisplayProps) {
  const [isDeleting, setIsDeleting] = useState(false)
  const [isExpanded, setIsExpanded] = useState(true)

  const handleDelete = async () => {
    if (!confirm('Delete this correction? This cannot be undone.')) return

    setIsDeleting(true)
    try {
      await deleteNote(scope, target)
      onDeleted()
    } catch (err) {
      console.error('Failed to delete note:', err)
    } finally {
      setIsDeleting(false)
    }
  }

  const formatDate = (isoString: string) => {
    const date = new Date(isoString)
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    })
  }

  return (
    <div className="mb-6 border border-amber-200 dark:border-amber-800 rounded-lg bg-amber-50 dark:bg-amber-900/20">
      {/* Header */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full px-4 py-3 flex items-center justify-between text-left hover:bg-amber-100 dark:hover:bg-amber-900/30 rounded-t-lg"
      >
        <div className="flex items-center gap-2">
          <svg
            className="w-5 h-5 text-amber-600 dark:text-amber-400"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"
            />
          </svg>
          <span className="font-medium text-amber-800 dark:text-amber-200">
            Developer Correction
          </span>
        </div>
        <svg
          className={`w-5 h-5 text-amber-600 dark:text-amber-400 transition-transform ${
            isExpanded ? 'rotate-180' : ''
          }`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {/* Content */}
      {isExpanded && (
        <div className="px-4 pb-4">
          <div className="prose prose-sm dark:prose-invert max-w-none text-gray-800 dark:text-gray-200">
            {note.content.split('\n').map((line, i) => (
              <p key={i} className="my-2">
                {line || '\u00A0'}
              </p>
            ))}
          </div>

          {/* Footer */}
          <div className="mt-4 pt-3 border-t border-amber-200 dark:border-amber-800 flex items-center justify-between text-sm">
            <div className="text-amber-700 dark:text-amber-300">
              {note.author && <span>Updated by {note.author} &middot; </span>}
              <span>{formatDate(note.updated_at)}</span>
            </div>
            <div className="flex gap-2">
              <button
                onClick={onEdit}
                className="px-3 py-1 text-amber-700 dark:text-amber-300 hover:bg-amber-200 dark:hover:bg-amber-800 rounded"
              >
                Edit
              </button>
              <button
                onClick={handleDelete}
                disabled={isDeleting}
                className="px-3 py-1 text-red-600 dark:text-red-400 hover:bg-red-100 dark:hover:bg-red-900/30 rounded disabled:opacity-50"
              >
                {isDeleting ? 'Deleting...' : 'Delete'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
