/**
 * Local storage configuration.
 *
 * Keys for browser localStorage used to persist user preferences across
 * sessions. All keys are prefixed with 'oya-' to avoid collisions with
 * other applications on the same domain.
 */

// =============================================================================
// Preference Keys
// =============================================================================
// These preferences are restored when the app loads and persisted when changed.

export const STORAGE_KEY_DARK_MODE = 'oya-dark-mode';
export const STORAGE_KEY_ASK_PANEL_OPEN = 'oya-ask-panel-open';
