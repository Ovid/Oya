# Generation Phases Upfront Display

## Problem

When clicking "Generate", users see a spinner but no roadmap of what's coming. Phases only appear in the progress log after they start or complete. The Analysis phase appears without an elapsed time initially.

## Solution

Show all phases immediately when generation starts, with visual distinction between completed, in-progress, and pending states.

## Behavior

**When generation starts:**
- All 8 phases appear immediately in the progress log
- Current phase shows a spinner icon and live counting timer (0s, 1s, 2s...)
- Pending phases show grayed out text with no icon
- Completed phases show green checkmark with final elapsed time

**Phase order:**
1. Analysis
2. Files
3. Directories
4. Synthesis
5. Architecture
6. Overview
7. Workflows
8. Indexing

## Implementation

**File:** `frontend/src/components/GenerationProgress.tsx`

**Changes to Progress Log section (~lines 321-397):**

1. Render full `PHASE_ORDER` array instead of filtering to started phases only

2. Determine phase state for each phase:
   - `completed`: phase exists in `phaseElapsedTimes`
   - `in_progress`: phase matches `currentPhase`
   - `pending`: neither completed nor in-progress

3. Calculate live elapsed time for in-progress phase using `phaseStartTimesRef`

4. Apply styling per state:
   - Completed: green checkmark, normal text, elapsed time
   - In-progress: spinner, normal text, live timer
   - Pending: no icon (spacer for alignment), muted gray text (`text-gray-500`), no time

**No backend changes required.**

## Notes

- Live timer piggybacks on existing 1-second re-render interval (from overall elapsed timer)
- Uses existing `phaseStartTimesRef` to track when each phase started
- Uses existing `formatElapsedTime()` helper for consistent time display
