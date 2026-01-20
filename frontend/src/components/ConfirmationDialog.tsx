interface ConfirmationDialogProps {
  isOpen: boolean
  title: string
  onConfirm: () => void
  onCancel: () => void
  confirmLabel?: string
  cancelLabel?: string
  children: React.ReactNode
}

export function ConfirmationDialog({
  isOpen,
  title,
  onConfirm,
  onCancel,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  children,
}: ConfirmationDialogProps) {
  if (!isOpen) return null

  const handleBackdropClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (e.target === e.currentTarget) {
      onCancel()
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      onClick={handleBackdropClick}
      data-testid="confirmation-backdrop"
    >
      <div
        className="bg-white dark:bg-gray-800 rounded-lg shadow-xl p-6 mx-4 max-w-md w-full"
        onClick={(e) => e.stopPropagation()}
      >
        <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">
          {title}
        </h3>
        <div className="text-sm text-gray-600 dark:text-gray-400 mb-6">
          {children}
        </div>
        <div className="flex justify-end space-x-2">
          <button
            onClick={onCancel}
            className="px-3 py-1.5 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-md"
          >
            {cancelLabel}
          </button>
          <button
            onClick={onConfirm}
            className="px-3 py-1.5 text-sm text-white bg-indigo-600 hover:bg-indigo-700 rounded-md"
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  )
}
