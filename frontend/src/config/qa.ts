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
// Tailwind classes for styling the confidence banner on each answer.
// Green = high confidence, yellow = medium, red = low. Includes dark mode variants.

export const CONFIDENCE_COLORS = {
  high: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200',
  medium: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200',
  low: 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200',
} as const;
