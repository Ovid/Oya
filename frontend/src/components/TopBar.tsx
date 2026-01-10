import { useApp } from '../context/AppContext';
import { DirectoryPicker } from './DirectoryPicker';

interface TopBarProps {
  onToggleSidebar: () => void;
  onToggleRightSidebar: () => void;
}

export function TopBar({ onToggleSidebar, onToggleRightSidebar }: TopBarProps) {
  const { state, startGeneration, toggleDarkMode, switchWorkspace } = useApp();
  const { repoStatus, currentJob, isLoading, darkMode, noteEditor } = state;

  const isGenerating = currentJob?.status === 'running';
  const hasUnsavedChanges = noteEditor.isDirty;

  const handleWorkspaceSwitch = async (path: string) => {
    if (hasUnsavedChanges) {
      const confirmed = window.confirm(
        'You have unsaved changes. Are you sure you want to switch workspaces?'
      );
      if (!confirmed) return;
    }
    await switchWorkspace(path);
  };

  const getStatusBadge = () => {
    if (isLoading) {
      return (
        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200">
          <span className="animate-pulse mr-1">●</span>
          Loading...
        </span>
      );
    }

    if (isGenerating) {
      return (
        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200">
          <span className="animate-pulse mr-1">●</span>
          Generating...
        </span>
      );
    }

    if (repoStatus?.initialized) {
      return (
        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200">
          Ready
        </span>
      );
    }

    return (
      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200">
        Not initialized
      </span>
    );
  };

  return (
    <header className="fixed top-0 left-0 right-0 h-14 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 z-50">
      <div className="h-full px-4 flex items-center justify-between">
        {/* Left section */}
        <div className="flex items-center space-x-4">
          <button
            onClick={onToggleSidebar}
            className="p-2 rounded-md hover:bg-gray-100 dark:hover:bg-gray-700"
            title="Toggle sidebar"
          >
            <svg className="w-5 h-5 text-gray-600 dark:text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>

          <div className="flex items-center space-x-2">
            <span className="text-xl font-bold text-indigo-600 dark:text-indigo-400">Oya</span>
            {repoStatus && (
              <DirectoryPicker
                currentPath={repoStatus.path}
                isDocker={repoStatus.is_docker}
                onSwitch={handleWorkspaceSwitch}
                disabled={isGenerating}
                disabledReason={isGenerating ? 'Cannot switch during generation' : undefined}
              />
            )}
          </div>
        </div>

        {/* Center section */}
        <div className="flex items-center space-x-3">
          {getStatusBadge()}
          {repoStatus?.head_commit && (
            <span className="text-xs text-gray-400 dark:text-gray-500 font-mono">
              {repoStatus.head_commit.slice(0, 7)}
            </span>
          )}
        </div>

        {/* Right section */}
        <div className="flex items-center space-x-2">
          {repoStatus?.initialized && !currentJob && (
            <button
              onClick={() => startGeneration()}
              className="px-3 py-1.5 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 rounded-md"
            >
              Regenerate
            </button>
          )}

          {!repoStatus?.initialized && (
            <button
              onClick={() => startGeneration()}
              disabled={isLoading}
              className="px-3 py-1.5 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 rounded-md disabled:opacity-50"
            >
              Generate Wiki
            </button>
          )}

          <button
            onClick={toggleDarkMode}
            className="p-2 rounded-md hover:bg-gray-100 dark:hover:bg-gray-700"
            title={darkMode ? 'Switch to light mode' : 'Switch to dark mode'}
          >
            {darkMode ? (
              <svg className="w-5 h-5 text-gray-600 dark:text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
              </svg>
            ) : (
              <svg className="w-5 h-5 text-gray-600 dark:text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
              </svg>
            )}
          </button>

          <button
            onClick={onToggleRightSidebar}
            className="p-2 rounded-md hover:bg-gray-100 dark:hover:bg-gray-700"
            title="Toggle right sidebar"
          >
            <svg className="w-5 h-5 text-gray-600 dark:text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h8m-8 6h16" />
            </svg>
          </button>
        </div>
      </div>
    </header>
  );
}
