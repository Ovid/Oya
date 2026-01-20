# Wiki Generation Flow Redesign

## Overview

Redesign the wiki generation flow to simplify the user experience by consolidating the "Preview" and "Generate" actions into a single flow, with clearer file inclusion/exclusion management.

## Changes Summary

1. Remove separate "Preview" button - single "Generate Wiki" entry point
2. Modal always opens on Generate, showing all files with inclusion checkboxes
3. Clear visual distinction between included files, .oyaignore exclusions, and rule-based exclusions
4. New shared confirmation dialog component
5. Q&A disabled during generation
6. Remove "up to date" check - always allow regeneration

## Design

### 1. TopBar Changes

**Current state:**
- "Preview" button opens `IndexingPreviewModal`
- "Generate Wiki" / "Regenerate" button starts generation directly

**New state:**
- Remove "Preview" button entirely
- Single "Generate Wiki" button that always opens the modal
- Button text is always "Generate Wiki" (not context-dependent)
- Button remains disabled during active generation (existing behavior)

**Ask button changes:**
- During generation: button is grayed out (not hidden)
- Tooltip on hover: "Q&A unavailable during generation"
- Uses the existing `disabled` prop pattern with a conditional tooltip

**Files affected:**
- `frontend/src/components/TopBar.tsx`

### 2. File Display States in Modal

**Three visual states for files/directories:**

1. **Included (default)**
   - Checkbox: checked, enabled
   - Appearance: normal text, no special styling
   - Behavior: unchecking adds to pending exclusions

2. **Excluded via .oyaignore**
   - Checkbox: unchecked, enabled
   - Appearance: normal text + badge "(from .oyaignore)"
   - Inline hint: "Check to remove from .oyaignore"
   - Behavior: checking removes from pending exclusions (will delete from .oyaignore on generate)

3. **Excluded via rules**
   - Checkbox: unchecked, disabled (grayed out)
   - Appearance: muted/grayed text + badge "(excluded by rule)"
   - Behavior: cannot be changed

**Data flow:**
- Backend returns three lists: `included`, `excludedByOyaignore`, `excludedByRule`
- Frontend merges into unified display with visual differentiation
- Pending changes tracked locally until generation

**Files affected:**
- `frontend/src/components/IndexingPreviewModal.tsx`
- `backend/src/oya/api/routers/repos.py`

### 3. Modal Flow and Generation Trigger

**Modal open behavior:**
- Triggered by clicking "Generate Wiki" in TopBar
- Fetches file lists on open (existing pattern)
- All includable files shown checked by default
- .oyaignore files shown unchecked with badge
- Rule-excluded files shown disabled with badge

**User interactions:**
- Check/uncheck files and directories to adjust inclusions
- Search/filter to find specific items (existing functionality)
- Directory exclusion cascades to child files (existing behavior)

**Generate Wiki button (in modal):**
- Always labeled "Generate Wiki"
- Clicking opens the confirmation dialog
- No disabled state needed - user can always generate

**Close/cancel behavior:**
- X button or clicking outside closes modal
- If pending exclusion changes exist: show warning "You have unsaved changes. Close anyway?"
- Uses the new shared confirmation component for this warning

**On generation confirm:**
1. Save exclusion changes to `.oyaignore` (add new exclusions, remove re-included items)
2. Start generation via existing `api.initRepo()`
3. Close modal immediately
4. Progress shown via existing `GenerationProgress` component

**Files affected:**
- `frontend/src/components/IndexingPreviewModal.tsx`

### 4. Shared Confirmation Component

**New component:** `ConfirmationDialog.tsx`

```typescript
interface ConfirmationDialogProps {
  isOpen: boolean
  title: string
  onConfirm: () => void
  onCancel: () => void
  confirmLabel?: string  // default: "Confirm"
  cancelLabel?: string   // default: "Cancel"
  children: React.ReactNode  // flexible content area
}
```

**Visual design:**
- Modal overlay with centered dialog
- Title at top
- Content area (children) for flexible messaging
- Cancel and Confirm buttons at bottom right

**Usage 1 - Generation confirmation:**
- Title: "Generate Wiki"
- Content: Summary showing "X files will be indexed, Y files excluded"
- Expandable details section listing excluded files/directories
- Note about .oyaignore changes if any items being added/removed
- Buttons: "Cancel" / "Generate"

**Usage 2 - Unsaved changes warning:**
- Title: "Unsaved Changes"
- Content: "You have exclusion changes that haven't been saved. Close anyway?"
- Buttons: "Keep Editing" / "Discard Changes"

**Files affected:**
- `frontend/src/components/ConfirmationDialog.tsx` (new)
- `frontend/src/components/IndexingPreviewModal.tsx`

### 5. Q&A Disabled During Generation

**TopBar Ask button:**
- When generation is active (`currentJob` is not null and not complete):
  - Button rendered with `disabled` class (grayed out)
  - Tooltip on hover: "Q&A unavailable during generation"
  - Click does nothing

**AskPanel behavior when generation starts:**
- Panel stays open if already open
- Existing conversation history remains visible
- Input field disabled with visual indication
- Banner appears at top: "Q&A is unavailable while the wiki is being generated"
- Banner styling: informational (not error)

**When generation completes:**
- Ask button re-enabled automatically
- Banner in AskPanel disappears
- Input field re-enabled
- User can continue asking questions

**State tracking:**
- Uses existing `currentJob` from AppContext
- Derive disabled state from `currentJob?.status`

**Files affected:**
- `frontend/src/components/TopBar.tsx`
- `frontend/src/components/AskPanel.tsx`

### 6. Backend API Changes

**Expand `/api/repos/indexable` response:**

Current:
```typescript
{ directories: string[], files: string[] }
```

New:
```typescript
{
  included: {
    directories: string[],
    files: string[]
  },
  excludedByOyaignore: {
    directories: string[],
    files: string[]
  },
  excludedByRule: {
    directories: string[],
    files: string[]
  }
}
```

**Update `/api/repos/oyaignore` endpoint:**

Request body adds optional `removals` field:
```typescript
{
  directories: string[],   // to exclude
  files: string[],         // to exclude
  removals: string[]       // patterns to remove from .oyaignore
}
```

**Remove "up to date" check:**
- Remove `changes_made` logic from `init_repo()` endpoint
- Always proceed with generation
- Remove `showUpToDateModal` from frontend

**Files affected:**
- `backend/src/oya/api/routers/repos.py`
- `backend/src/oya/repo/file_filter.py`
- `frontend/src/api/client.ts`
- `frontend/src/context/AppContext.tsx`

### 7. Cleanup and Removal

**Remove from TopBar:**
- "Preview" button and its click handler

**Remove from AppContext:**
- `showUpToDateModal` state and related logic

**Remove from IndexingPreviewModal:**
- Separate "Save" button
- Existing nested confirmation div (replaced by `ConfirmationDialog`)

**Consider renaming:**
- `IndexingPreviewModal` to `GenerationModal` (optional)

## Implementation Order

1. Create `ConfirmationDialog` component
2. Update backend `/api/repos/indexable` to return three categories
3. Update backend `/api/repos/oyaignore` to handle removals
4. Update `IndexingPreviewModal` with new display states and flow
5. Update `TopBar` to remove Preview button, wire Generate to modal
6. Add Q&A disable logic to `TopBar` and `AskPanel`
7. Remove "up to date" logic from backend and frontend
8. Clean up unused code and state
