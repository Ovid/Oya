import { useUIStore } from '../stores/uiStore'

export function ErrorModal() {
  const errorModal = useUIStore((s) => s.errorModal)
  const dismissErrorModal = useUIStore((s) => s.dismissErrorModal)

  if (!errorModal) {
    return null
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="error-modal-title"
      aria-describedby="error-modal-description"
      className="fixed inset-0 z-50 flex items-center justify-center"
    >
      <div
        data-testid="error-modal-backdrop"
        className="fixed inset-0 bg-black/50"
        onClick={dismissErrorModal}
      />
      <div className="relative bg-white dark:bg-gray-800 rounded-lg shadow-xl p-6 max-w-lg mx-4">
        <div className="flex items-start mb-4">
          <div className="flex-shrink-0">
            <div
              data-testid="error-modal-icon"
              className="inline-flex items-center justify-center w-12 h-12 bg-red-100 dark:bg-red-900 rounded-full"
            >
              <svg
                className="w-6 h-6 text-red-600 dark:text-red-400"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M6 18L18 6M6 6l12 12"
                />
              </svg>
            </div>
          </div>
          <div className="ml-4">
            <h3
              id="error-modal-title"
              className="text-lg font-semibold text-gray-900 dark:text-white"
            >
              {errorModal.title}
            </h3>
            <p
              id="error-modal-description"
              className="mt-2 text-sm text-gray-600 dark:text-gray-400 max-h-48 overflow-y-auto whitespace-pre-wrap"
            >
              {errorModal.message}
            </p>
          </div>
        </div>
        <div className="flex justify-end">
          <button
            onClick={dismissErrorModal}
            className="px-4 py-2 text-sm font-medium text-white bg-red-600 hover:bg-red-700 rounded-md"
          >
            Dismiss
          </button>
        </div>
      </div>
    </div>
  )
}
