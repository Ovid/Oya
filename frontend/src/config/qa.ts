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
} as const

// =============================================================================
// Q&A Settings Defaults
// =============================================================================
// Default values for the Q&A settings panel. Quick mode skips follow-up
// iterations for faster responses. Temperature controls LLM creativity.
// Timeout limits how long a query can run.

export const QA_DEFAULTS = {
  quickMode: true,
  temperature: 0.5,
  timeoutMinutes: 3,
} as const

// =============================================================================
// Q&A Settings Constraints
// =============================================================================
// Min/max/step values for settings sliders. Temperature ranges 0-1 (deterministic
// to creative). Timeout ranges 1-5 minutes.

export const QA_CONSTRAINTS = {
  temperature: { min: 0, max: 1, step: 0.1 },
  timeout: { min: 1, max: 5, step: 1 },
} as const

// =============================================================================
// Q&A Storage
// =============================================================================
// localStorage key for persisting user's Q&A settings across sessions.

export const QA_STORAGE_KEY = 'oya-qa-settings'
