import { useApp } from '../context/AppContext';

export function RightSidebar() {
  const { state, startGeneration, openNoteEditor } = useApp();
  const { currentPage, repoStatus } = state;

  // Determine scope and target based on current page
  const handleAddCorrection = () => {
    if (!currentPage) return;
    
    const pageType = currentPage.page_type;
    let scope: 'general' | 'file' | 'directory' | 'workflow' = 'general';
    let target = '';

    if (pageType === 'file') {
      scope = 'file';
      target = currentPage.source_path || '';
    } else if (pageType === 'directory') {
      scope = 'directory';
      target = currentPage.source_path || '';
    } else if (pageType === 'workflow') {
      scope = 'workflow';
      // For workflows, use source_path if available, otherwise extract from path
      target = currentPage.source_path || '';
    }

    openNoteEditor(scope, target);
  };

  // Extract headings from markdown for TOC
  const headings = currentPage?.content
    ? extractHeadings(currentPage.content)
    : [];

  return (
    <div className="p-4 space-y-6">
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
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
              </svg>
              Add correction
            </button>
          )}

          <button
            onClick={() => startGeneration()}
            className="w-full px-3 py-2 text-sm text-left text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-md flex items-center"
          >
            <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            Regenerate page
          </button>
        </div>
      </div>

      {/* Page info */}
      {currentPage && (
        <div>
          <h3 className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-2">
            Page info
          </h3>
          <dl className="text-xs text-gray-500 dark:text-gray-400 space-y-1">
            <div className="flex justify-between">
              <dt>Type:</dt>
              <dd className="font-medium">{currentPage.page_type}</dd>
            </div>
            <div className="flex justify-between">
              <dt>Words:</dt>
              <dd className="font-medium">{currentPage.word_count}</dd>
            </div>
          </dl>
        </div>
      )}

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
          </dl>
        </div>
      )}
    </div>
  );
}

interface Heading {
  text: string;
  level: number;
  id: string;
}

function extractHeadings(markdown: string): Heading[] {
  const lines = markdown.split('\n');
  const headings: Heading[] = [];

  for (const line of lines) {
    const match = line.match(/^(#{2,3})\s+(.+)$/);
    if (match) {
      const level = match[1].length;
      const text = match[2];
      const id = text.toLowerCase().replace(/[^\w]+/g, '-');
      headings.push({ text, level, id });
    }
  }

  return headings;
}
