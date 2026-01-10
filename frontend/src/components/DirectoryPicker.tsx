import { useState, useEffect } from 'react';
import * as api from '../api/client';
import type { DirectoryEntry } from '../types';

interface DirectoryPickerProps {
  /** Current workspace path to display */
  currentPath: string;
  /** Whether running in Docker mode */
  isDocker: boolean;
  /** Callback when user submits a new path */
  onSwitch: (path: string) => Promise<void>;
  /** Whether the picker is disabled */
  disabled: boolean;
  /** Reason for being disabled (shown as tooltip) */
  disabledReason?: string;
}

/**
 * DirectoryPicker allows users to view and change the current workspace path.
 * 
 * Features:
 * - Displays current path with folder icon
 * - Click to open directory browser modal
 * - Browse directories with navigation
 * - Loading state during workspace switch
 * - Error display for failed switches (with Docker-specific messages)
 * - Disabled state when generation is in progress
 */
export function DirectoryPicker({
  currentPath,
  isDocker,
  onSwitch,
  disabled,
  disabledReason,
}: DirectoryPickerProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [browsePath, setBrowsePath] = useState<string | null>(null);
  const [entries, setEntries] = useState<DirectoryEntry[]>([]);
  const [parentPath, setParentPath] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isSwitching, setIsSwitching] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load directory listing when browser opens or path changes
  useEffect(() => {
    if (!isOpen) return;
    
    const loadDirectory = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const listing = await api.listDirectories(browsePath || undefined);
        setBrowsePath(listing.path);
        setParentPath(listing.parent);
        setEntries(listing.entries);
      } catch (err) {
        let message = err instanceof api.ApiError ? err.message : 'Failed to load directories';
        // Try to parse JSON error detail
        try {
          const parsed = JSON.parse(message);
          message = parsed.detail || message;
        } catch {
          // Not JSON, use as-is
        }
        if (isDocker) {
          message += ' (Note: Directory browsing is limited in Docker mode)';
        }
        setError(message);
      } finally {
        setIsLoading(false);
      }
    };
    
    loadDirectory();
  }, [isOpen, browsePath, isDocker]);

  const handleOpen = () => {
    if (disabled) return;
    setBrowsePath(null); // Start from base path
    setIsOpen(true);
    setError(null);
  };

  const handleClose = () => {
    setIsOpen(false);
    setError(null);
  };

  const handleNavigate = (path: string) => {
    setBrowsePath(path);
  };

  const handleSelect = async () => {
    if (!browsePath) return;
    
    setIsSwitching(true);
    setError(null);
    
    try {
      await onSwitch(browsePath);
      setIsOpen(false);
    } catch (err) {
      let message = err instanceof Error ? err.message : 'Failed to switch workspace';
      // Try to parse JSON error detail
      try {
        const parsed = JSON.parse(message);
        message = parsed.detail || message;
      } catch {
        // Not JSON, use as-is
      }
      if (isDocker) {
        message += ' (Note: In Docker mode, you may need to update REPO_PATH in .env and restart)';
      }
      setError(message);
    } finally {
      setIsSwitching(false);
    }
  };

  // Display mode: show current path with folder icon
  return (
    <>
      <button
        onClick={handleOpen}
        disabled={disabled}
        title={disabledReason || 'Click to change workspace'}
        aria-label={`Current workspace: ${currentPath}. ${disabled ? disabledReason : 'Click to change'}`}
        className={`flex items-center space-x-2 px-3 py-1.5 rounded-md text-sm
                    ${disabled 
                      ? 'cursor-not-allowed opacity-50' 
                      : 'hover:bg-gray-100 dark:hover:bg-gray-700 cursor-pointer'
                    }
                    text-gray-700 dark:text-gray-300`}
      >
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} 
                d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
        </svg>
        <span className="truncate max-w-xs">{currentPath}</span>
      </button>

      {/* Directory Browser Modal */}
      {isOpen && (
        <div 
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
          onClick={handleClose}
        >
          <div 
            className="bg-white dark:bg-gray-800 rounded-lg shadow-xl w-full max-w-lg mx-4 max-h-[80vh] flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Header */}
            <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
                Select Workspace
              </h2>
              <button
                onClick={handleClose}
                className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700"
                aria-label="Close"
              >
                <svg className="w-5 h-5 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            {/* Current path */}
            <div className="px-4 py-2 bg-gray-50 dark:bg-gray-900 border-b border-gray-200 dark:border-gray-700">
              <div className="flex items-center space-x-2 text-sm">
                <span className="text-gray-500 dark:text-gray-400">Path:</span>
                <span className="font-mono text-gray-900 dark:text-gray-100 truncate">
                  {browsePath || 'Loading...'}
                </span>
              </div>
            </div>

            {/* Directory listing */}
            <div className="flex-1 overflow-y-auto min-h-[200px]">
              {isLoading ? (
                <div className="flex items-center justify-center h-32">
                  <span className="text-gray-500 dark:text-gray-400">Loading...</span>
                </div>
              ) : error ? (
                <div className="p-4 text-red-600 dark:text-red-400 text-sm">
                  {error}
                </div>
              ) : (
                <div className="divide-y divide-gray-100 dark:divide-gray-700">
                  {/* Parent directory */}
                  {parentPath && (
                    <button
                      onClick={() => handleNavigate(parentPath)}
                      className="w-full px-4 py-2 flex items-center space-x-3 hover:bg-gray-50 dark:hover:bg-gray-700 text-left"
                    >
                      <svg className="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 17l-5-5m0 0l5-5m-5 5h12" />
                      </svg>
                      <span className="text-gray-600 dark:text-gray-300">..</span>
                    </button>
                  )}
                  
                  {/* Directory entries */}
                  {entries.filter(e => e.is_dir).map((entry) => (
                    <button
                      key={entry.path}
                      onClick={() => handleNavigate(entry.path)}
                      className="w-full px-4 py-2 flex items-center space-x-3 hover:bg-gray-50 dark:hover:bg-gray-700 text-left"
                    >
                      <svg className="w-5 h-5 text-yellow-500" fill="currentColor" viewBox="0 0 24 24">
                        <path d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
                      </svg>
                      <span className="text-gray-900 dark:text-gray-100">{entry.name}</span>
                    </button>
                  ))}
                  
                  {entries.filter(e => e.is_dir).length === 0 && !parentPath && (
                    <div className="px-4 py-8 text-center text-gray-500 dark:text-gray-400">
                      No subdirectories found
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Footer */}
            <div className="px-4 py-3 border-t border-gray-200 dark:border-gray-700 flex items-center justify-between">
              <div className="text-xs text-gray-500 dark:text-gray-400">
                {isDocker && (
                  <span className="flex items-center space-x-1">
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    <span>Running in Docker</span>
                  </span>
                )}
              </div>
              <div className="flex items-center space-x-2">
                <button
                  onClick={handleClose}
                  className="px-3 py-1.5 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-md"
                >
                  Cancel
                </button>
                <button
                  onClick={handleSelect}
                  disabled={isSwitching || !browsePath}
                  className="px-3 py-1.5 text-sm text-white bg-indigo-600 hover:bg-indigo-700 rounded-md disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {isSwitching ? 'Switching...' : 'Select'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
