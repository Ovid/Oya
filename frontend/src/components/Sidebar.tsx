import { NavLink } from 'react-router-dom';
import { useApp } from '../context/AppContext';
import { Disclosure } from '@headlessui/react';

// Known file extensions to help reconstruct filenames from slugs
const FILE_EXTENSIONS = ['py', 'js', 'ts', 'tsx', 'jsx', 'java', 'go', 'rs', 'rb', 'php', 'c', 'cpp', 'h', 'hpp', 'cs', 'swift', 'kt', 'scala', 'md', 'json', 'yaml', 'yml', 'toml', 'xml', 'html', 'css', 'scss', 'less'];

/**
 * Convert a file slug back to a display name.
 * Slugs are created by replacing / and . with -, so we need to reconstruct.
 * e.g., "backend-src-oya-main-py" -> "main.py"
 */
function slugToFilename(slug: string): string {
  const parts = slug.split('-');

  // Check if last part is a known extension
  const lastPart = parts[parts.length - 1];
  if (FILE_EXTENSIONS.includes(lastPart) && parts.length >= 2) {
    // Reconstruct filename: second-to-last part + . + extension
    const namePart = parts[parts.length - 2];
    return `${namePart}.${lastPart}`;
  }

  // Fallback: just return the last part
  return lastPart || slug;
}

/**
 * Convert a file slug back to a full path for the title tooltip.
 * e.g., "backend-src-oya-main-py" -> "backend/src/oya/main.py"
 */
function slugToPath(slug: string): string {
  const parts = slug.split('-');

  // Check if last part is a known extension
  const lastPart = parts[parts.length - 1];
  if (FILE_EXTENSIONS.includes(lastPart) && parts.length >= 2) {
    // Join all but last with /, then add .extension
    const pathParts = parts.slice(0, -1);
    return pathParts.join('/') + '.' + lastPart;
  }

  // Fallback: just replace dashes with slashes
  return slug.replace(/-/g, '/');
}

export function Sidebar() {
  const { state } = useApp();
  const { wikiTree } = state;

  const linkClass = ({ isActive }: { isActive: boolean }) =>
    `block px-3 py-2 rounded-md text-sm ${
      isActive
        ? 'bg-indigo-100 text-indigo-700 dark:bg-indigo-900 dark:text-indigo-200'
        : 'text-gray-700 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-700'
    }`;

  return (
    <nav className="p-4 space-y-1">
      {/* Overview */}
      {wikiTree?.overview && (
        <NavLink to="/" className={linkClass}>
          <div className="flex items-center">
            <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
            </svg>
            Overview
          </div>
        </NavLink>
      )}

      {/* Architecture */}
      {wikiTree?.architecture && (
        <NavLink to="/architecture" className={linkClass}>
          <div className="flex items-center">
            <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
            </svg>
            Architecture
          </div>
        </NavLink>
      )}

      {/* Workflows */}
      {wikiTree && wikiTree.workflows.length > 0 && (
        <Disclosure defaultOpen>
          {({ open }) => (
            <>
              <Disclosure.Button className="flex items-center w-full px-3 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-md">
                <svg className={`w-4 h-4 mr-2 transition-transform ${open ? 'rotate-90' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                </svg>
                Workflows ({wikiTree.workflows.length})
              </Disclosure.Button>
              <Disclosure.Panel className="pl-6">
                {wikiTree.workflows.map((slug) => (
                  <NavLink
                    key={slug}
                    to={`/workflows/${slug}`}
                    className={linkClass}
                  >
                    {slug.replace(/-/g, ' ')}
                  </NavLink>
                ))}
              </Disclosure.Panel>
            </>
          )}
        </Disclosure>
      )}

      {/* Directories */}
      {wikiTree && wikiTree.directories.length > 0 && (
        <Disclosure>
          {({ open }) => (
            <>
              <Disclosure.Button className="flex items-center w-full px-3 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-md">
                <svg className={`w-4 h-4 mr-2 transition-transform ${open ? 'rotate-90' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                </svg>
                Directories ({wikiTree.directories.length})
              </Disclosure.Button>
              <Disclosure.Panel className="pl-6">
                {wikiTree.directories.map((slug) => (
                  <NavLink
                    key={slug}
                    to={`/directories/${slug}`}
                    className={linkClass}
                  >
                    {slug.replace(/-/g, '/')}
                  </NavLink>
                ))}
              </Disclosure.Panel>
            </>
          )}
        </Disclosure>
      )}

      {/* Files */}
      {wikiTree && wikiTree.files.length > 0 && (
        <Disclosure>
          {({ open }) => (
            <>
              <Disclosure.Button className="flex items-center w-full px-3 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-md">
                <svg className={`w-4 h-4 mr-2 transition-transform ${open ? 'rotate-90' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                </svg>
                Files ({wikiTree.files.length})
              </Disclosure.Button>
              <Disclosure.Panel className="pl-6 max-h-64 overflow-y-auto">
                {wikiTree.files.map((slug) => (
                  <NavLink
                    key={slug}
                    to={`/files/${slug}`}
                    className={linkClass}
                  >
                    <span className="truncate block" title={slugToPath(slug)}>
                      {slugToFilename(slug)}
                    </span>
                  </NavLink>
                ))}
              </Disclosure.Panel>
            </>
          )}
        </Disclosure>
      )}

      {/* Empty state */}
      {!wikiTree?.overview && !wikiTree?.architecture && (
        <div className="px-3 py-8 text-center text-gray-500 dark:text-gray-400">
          <p className="text-sm">No wiki pages yet.</p>
          <p className="text-xs mt-1">Click "Generate Wiki" to get started.</p>
        </div>
      )}
    </nav>
  );
}
