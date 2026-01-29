/**
 * Timing configuration.
 *
 * Intervals and thresholds for time-based operations like polling,
 * animations, and relative time formatting ("5 minutes ago").
 */

// =============================================================================
// Polling Intervals
// =============================================================================
// How frequently to check for updates during long-running operations.
// Values in milliseconds.

export const ELAPSED_TIME_UPDATE_MS = 1000 // Update elapsed time display

// =============================================================================
// Relative Time Thresholds
// =============================================================================
// Thresholds for formatting timestamps as relative time ("just now", "5 min ago").
// When the time difference exceeds a threshold, we use the next larger unit.
// Values in milliseconds.

export const MS_PER_MINUTE = 60_000
export const MS_PER_HOUR = 3_600_000
export const MS_PER_DAY = 86_400_000

export const RELATIVE_TIME_MINUTES_THRESHOLD = 60 // Show minutes until 60 min
export const RELATIVE_TIME_HOURS_THRESHOLD = 24 // Show hours until 24 hours
export const RELATIVE_TIME_DAYS_THRESHOLD = 7 // Show days until 7 days

// =============================================================================
// API Defaults
// =============================================================================
// Default parameters for API calls.

export const DEFAULT_JOBS_LIST_LIMIT = 20

// =============================================================================
// Toast Notifications
// =============================================================================
// Configuration for toast notification display.

export const TOAST_AUTO_DISMISS_MS = 5000 // Auto-dismiss toasts after 5 seconds
export const TOAST_MAX_VISIBLE = 3 // Maximum number of toasts shown at once
