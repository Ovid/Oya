/**
 * Q&A panel configuration.
 *
 * Styling for the Ask panel, which displays answers with confidence levels.
 * Confidence indicates how well the search results matched the question:
 * high = strong matches found, medium = partial matches, low = weak/no matches.
 */

// =============================================================================
// Confidence Level Colors
// =============================================================================

export const CONFIDENCE_COLORS = {
  high: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200',
  medium: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200',
  low: 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200',
} as const

// =============================================================================
// Q&A Settings Constraints
// =============================================================================

export const QA_CONSTRAINTS = {
  temperature: { min: 0, max: 1, step: 0.1 },
  timeout: { min: 1, max: 10, step: 1 },
} as const

// Note: QA_DEFAULTS and QA_STORAGE_KEY moved to utils/storage.ts
