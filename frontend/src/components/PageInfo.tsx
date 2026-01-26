import { useState } from 'react'
import type { WikiPageMeta } from '../utils/frontmatter'

interface PageInfoProps {
  meta: WikiPageMeta | null
}

export function PageInfo({ meta }: PageInfoProps) {
  const [isExpanded, setIsExpanded] = useState(false)

  // Return nothing if meta is null or has no defined fields
  if (!meta) return null

  const hasContent = Object.values(meta).some((v) => v !== undefined)
  if (!hasContent) return null

  const formatDate = (isoString: string) => {
    const date = new Date(isoString)
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    })
  }

  const fields: { key: keyof WikiPageMeta; label: string }[] = [
    { key: 'source', label: 'Source' },
    { key: 'type', label: 'Type' },
    { key: 'layer', label: 'Layer' },
    { key: 'generated', label: 'Generated' },
    { key: 'commit', label: 'Commit' },
  ]

  return (
    <div className="mb-6 border border-gray-200 dark:border-gray-700 rounded-lg bg-gray-50 dark:bg-gray-800/50">
      {/* Header */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        aria-label={isExpanded ? 'Collapse page info' : 'Expand page info'}
        className="w-full px-4 py-3 flex items-center justify-between text-left hover:bg-gray-100 dark:hover:bg-gray-700/50 rounded-lg"
      >
        <div className="flex items-center gap-2">
          <svg
            className="w-5 h-5 text-gray-500 dark:text-gray-400"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
          <span className="font-medium text-gray-700 dark:text-gray-200">Page Info</span>
        </div>
        <svg
          className={`w-5 h-5 text-gray-500 dark:text-gray-400 transition-transform ${
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
          <dl className="space-y-2 text-sm">
            {fields.map(({ key, label }) => {
              const value = meta[key]
              if (value === undefined) return null

              const displayValue = key === 'generated' ? formatDate(value) : value

              return (
                <div key={key} className="flex gap-2">
                  <dt className="font-medium text-gray-600 dark:text-gray-400 min-w-20">
                    {label}
                  </dt>
                  <dd className="text-gray-800 dark:text-gray-200 break-all">{displayValue}</dd>
                </div>
              )
            })}
          </dl>
        </div>
      )}
    </div>
  )
}
