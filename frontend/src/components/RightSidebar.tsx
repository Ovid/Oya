import { useWikiStore, useNoteEditorStore } from '../stores'
import { MS_PER_DAY, MS_PER_HOUR, MS_PER_MINUTE } from '../config'

function formatLastBuilt(isoString: string): string {
  // Backend stores UTC timestamps without 'Z' suffix, so append it
  const utcString = isoString.endsWith('Z') ? isoString : isoString + 'Z'
  const date = new Date(utcString)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / MS_PER_MINUTE)
  const diffHours = Math.floor(diffMs / MS_PER_HOUR)
  const diffDays = Math.floor(diffMs / MS_PER_DAY)

  if (diffMins < 1) return 'Just now'
  if (diffMins < 60) return `${diffMins}m ago`
  if (diffHours < 24) return `${diffHours}h ago`
  if (diffDays < 7) return `${diffDays}d ago`

  return date.toLocaleDateString()
}

export function RightSidebar() {
  const currentPage = useWikiStore((s) => s.currentPage)
  const repoStatus = useWikiStore((s) => s.repoStatus)
  const openNoteEditor = useNoteEditorStore((s) => s.open)

  // Determine scope and target based on current page
  const handleAddCorrection = () => {
    if (!currentPage) return

    const pageType = currentPage.page_type
    let scope: 'general' | 'file' | 'directory' | 'workflow' = 'general'
    let target = ''

    if (pageType === 'file') {
      scope = 'file'
      target = currentPage.source_path || ''
    } else if (pageType === 'directory') {
      scope = 'directory'
      target = currentPage.source_path || ''
    } else if (pageType === 'workflow') {
      scope = 'workflow'
      // For workflows, use source_path if available, otherwise extract from path
      target = currentPage.source_path || ''
    }

    openNoteEditor(scope, target)
  }

  // Extract headings from markdown for TOC
  const headings = currentPage?.content ? extractHeadings(currentPage.content) : []

  return (
    <div className="p-4 space-y-6">
      {/* Repo status */}
      {repoStatus && (
        <div>
          <h3 className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-2">
            Repository
          </h3>
          <dl className="text-xs text-gray-500 dark:text-gray-400 space-y-1">
            {repoStatus.branch && (
              <div className="flex justify-between">
                <dt>Branch:</dt>
                <dd className="font-mono font-medium">{repoStatus.branch}</dd>
              </div>
            )}
            {repoStatus.head_commit && (
              <div className="flex justify-between">
                <dt>Commit:</dt>
                <dd className="font-mono font-medium">{repoStatus.head_commit.slice(0, 7)}</dd>
              </div>
            )}
            {repoStatus.current_provider && (
              <div className="flex justify-between">
                <dt>Provider:</dt>
                <dd className="font-medium">{repoStatus.current_provider}</dd>
              </div>
            )}
            {repoStatus.current_model && (
              <div className="flex justify-between">
                <dt>Model:</dt>
                <dd className="font-medium truncate max-w-[100px]" title={repoStatus.current_model}>
                  {repoStatus.current_model}
                </dd>
              </div>
            )}
            {repoStatus.last_generation && (
              <div className="flex justify-between">
                <dt>Last Built:</dt>
                <dd className="font-medium" title={repoStatus.last_generation}>
                  {formatLastBuilt(repoStatus.last_generation)}
                </dd>
              </div>
            )}
          </dl>
        </div>
      )}

      {/* On this page (TOC) */}
      {headings.length > 0 && (
        <div>
          <h3 className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-2">
            On this page
          </h3>
          <nav className="space-y-1">
            {headings.map((heading, index) => (
              <a
                key={index}
                href={`#${heading.id}`}
                className={`block text-sm text-gray-600 dark:text-gray-300 hover:text-indigo-600 dark:hover:text-indigo-400 ${
                  heading.level === 2 ? '' : 'pl-3'
                }`}
              >
                {heading.text}
              </a>
            ))}
          </nav>
        </div>
      )}

      {/* Quick actions */}
      <div>
        <h3 className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-2">
          Actions
        </h3>
        <div className="space-y-2">
          {currentPage && (
            <button
              onClick={handleAddCorrection}
              className="w-full px-3 py-2 text-sm text-left text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-md flex items-center"
            >
              <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"
                />
              </svg>
              Add correction
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

interface Heading {
  text: string
  level: number
  id: string
}

function extractHeadings(markdown: string): Heading[] {
  const lines = markdown.split('\n')
  const headings: Heading[] = []

  for (const line of lines) {
    const match = line.match(/^(#{2,3})\s+(.+)$/)
    if (match) {
      const level = match[1].length
      const text = match[2]
      const id = text.toLowerCase().replace(/[^\w]+/g, '-')
      headings.push({ text, level, id })
    }
  }

  return headings
}
