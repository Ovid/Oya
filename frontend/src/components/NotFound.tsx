export function NotFound() {
  return (
    <div className="text-center py-12">
      <svg
        className="mx-auto h-12 w-12 text-gray-400"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={1.5}
          d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M12 2a10 10 0 100 20 10 10 0 000-20z"
        />
      </svg>
      <h2 className="mt-4 text-xl font-semibold text-gray-900 dark:text-white">Page not found</h2>
      <p className="mt-2 text-gray-600 dark:text-gray-400 max-w-md mx-auto">
        The page you're looking for doesn't exist. It may have been moved or deleted.
      </p>
    </div>
  )
}
