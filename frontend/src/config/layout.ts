/**
 * Layout configuration.
 *
 * Dimensions and spacing for the main application shell. The layout consists
 * of a fixed top bar, collapsible left sidebar (navigation), collapsible right
 * sidebar (table of contents), and an optional ask panel that replaces the
 * right sidebar when open.
 */

// =============================================================================
// Panel Dimensions
// =============================================================================
// Width values for the main layout panels. These are used for both the panel
// itself and the margin applied to the main content area when panels are open.
// Values are in pixels and correspond to Tailwind classes (w-64 = 256px, etc.)

export const SIDEBAR_WIDTH = 256;        // w-64 - Left navigation sidebar
export const RIGHT_SIDEBAR_WIDTH = 224;  // w-56 - Table of contents
export const ASK_PANEL_WIDTH = 350;      // w-[350px] - Q&A panel
export const TOP_BAR_HEIGHT = 56;        // h-14 - Fixed header height

// =============================================================================
// Z-Index Layers
// =============================================================================
// Stacking order for overlapping elements. Higher values appear on top.
// Modals and their backdrops should be above all other content.

export const Z_INDEX_TOP_BAR = 50;
export const Z_INDEX_MODAL_BACKDROP = 50;
export const Z_INDEX_MODAL = 50;
