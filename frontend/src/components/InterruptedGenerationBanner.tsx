import { useApp } from '../context/AppContext';

export function InterruptedGenerationBanner() {
  const { state, dismissGenerationStatus, startGeneration } = useApp();
  const { generationStatus } = state;

  if (!generationStatus || generationStatus.status !== 'incomplete') {
    return null;
  }

  const handleRegenerate = async () => {
    dismissGenerationStatus();
    await startGeneration();
  };

  return (
    <div className="bg-amber-50 dark:bg-amber-900/30 border-b border-amber-200 dark:border-amber-800 px-4 py-3">
      <div className="flex items-start gap-3 max-w-4xl mx-auto">
        <div className="flex-shrink-0">
          <svg className="w-5 h-5 text-amber-600 dark:text-amber-400 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
        </div>
        <div className="flex-1 min-w-0">
          <h3 className="text-sm font-medium text-amber-800 dark:text-amber-200">
            Wiki Generation Incomplete
          </h3>
          <p className="mt-1 text-sm text-amber-700 dark:text-amber-300">
            {generationStatus.message}
          </p>
        </div>
        <div className="flex-shrink-0">
          <button
            onClick={handleRegenerate}
            className="px-3 py-1.5 text-sm font-medium text-white bg-amber-600 hover:bg-amber-700 dark:bg-amber-700 dark:hover:bg-amber-600 rounded-md transition-colors"
          >
            Generate Wiki
          </button>
        </div>
      </div>
    </div>
  );
}
