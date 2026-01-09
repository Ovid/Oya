import { useState, useRef, useEffect } from 'react';

interface DirectoryPickerProps {
  /** Current workspace path to display */
  currentPath: string;
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
 * - Click to enter edit mode with text input
 * - Submit on Enter or button click
 * - Cancel on Escape or cancel button
 * - Loading state during workspace switch
 * - Error display for failed switches
 * - Disabled state when generation is in progress
 */
export function DirectoryPicker({
  currentPath,
  onSwitch,
  disabled,
  disabledReason,
}: DirectoryPickerProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [inputValue, setInputValue] = useState(currentPath);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Sync input value when currentPath changes externally
  useEffect(() => {
    setInputValue(currentPath);
  }, [currentPath]);

  // Auto-focus and select input when entering edit mode
  useEffect(() => {
    if (isEditing && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [isEditing]);

  const handleClick = () => {
    if (disabled) return;
    setIsEditing(true);
    setError(null);
  };

  const handleCancel = () => {
    setIsEditing(false);
    setInputValue(currentPath);
    setError(null);
  };

  const handleSubmit = async () => {
    const trimmedPath = inputValue.trim();
    
    // Skip if path unchanged
    if (trimmedPath === currentPath) {
      setIsEditing(false);
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      await onSwitch(trimmedPath);
      setIsEditing(false);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to switch workspace';
      setError(message);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleSubmit();
    } else if (e.key === 'Escape') {
      e.preventDefault();
      handleCancel();
    }
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setInputValue(e.target.value);
    if (error) setError(null);
  };

  // Edit mode: show input field with submit/cancel buttons
  if (isEditing) {
    return (
      <div className="flex items-center space-x-2" role="group" aria-label="Workspace path editor">
        <div className="relative flex-1">
          <input
            ref={inputRef}
            type="text"
            value={inputValue}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            disabled={isLoading}
            aria-label="Workspace path"
            aria-invalid={!!error}
            aria-describedby={error ? 'path-error' : undefined}
            className="w-full px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-md 
                       bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100
                       focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent
                       disabled:opacity-50 disabled:cursor-not-allowed"
            placeholder="Enter workspace path"
          />
          {error && (
            <div 
              id="path-error"
              role="alert"
              className="absolute top-full left-0 mt-1 text-xs text-red-600 dark:text-red-400"
            >
              {error}
            </div>
          )}
        </div>
        
        {isLoading ? (
          <span className="text-sm text-gray-500 dark:text-gray-400" aria-live="polite">
            Switching...
          </span>
        ) : (
          <>
            <button
              onClick={handleSubmit}
              title="Switch workspace"
              aria-label="Confirm workspace switch"
              className="p-1.5 rounded-md hover:bg-gray-100 dark:hover:bg-gray-700 text-green-600 dark:text-green-400"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            </button>
            <button
              onClick={handleCancel}
              title="Cancel"
              aria-label="Cancel workspace change"
              className="p-1.5 rounded-md hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-500 dark:text-gray-400"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </>
        )}
      </div>
    );
  }

  // Display mode: show current path with folder icon
  return (
    <button
      onClick={handleClick}
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
  );
}
