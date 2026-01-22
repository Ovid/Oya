# Q&A Thinking Indicator Design

## Overview

Change the Q&A panel's loading indicator from "generating" to "Thinking" with an animated ellipsis to provide better visual feedback.

## Changes

### 1. Backend: Status Stage Rename

**File:** `backend/src/oya/qa/service.py` (line 986)

Change the SSE status event from `'generating'` to `'thinking'`:
```python
yield f"event: status\ndata: {json.dumps({'stage': 'thinking', 'pass': 1})}\n\n"
```

### 2. Frontend: ThinkingIndicator Component

**New file:** `frontend/src/components/ThinkingIndicator.tsx`

A reusable component displaying text with an animated ellipsis (three dots that fade in sequentially).

Props:
- `text` (optional): Display text, defaults to "Thinking"

Implementation:
- Pure CSS animation using `@keyframes` and staggered `animation-delay`
- Three dots fade in at 0s, 0.2s, 0.4s intervals, then repeat
- Styled to match existing italic gray text in AskPanel

### 3. Frontend: AskPanel Integration

**File:** `frontend/src/components/AskPanel.tsx`

Replace the current status display:
```tsx
{currentStatus && (
  <div className="text-xs text-gray-500 dark:text-gray-400 italic">{currentStatus}</div>
)}
```

With:
```tsx
{currentStatus && (
  <ThinkingIndicator text={currentStatus === 'thinking' ? 'Thinking' : currentStatus} />
)}
```

The check ensures "thinking" displays capitalized while other statuses (like "Searching...") pass through unchanged but still receive the animation.

## Testing

### ThinkingIndicator.test.tsx
- Renders with default "Thinking" text
- Renders with custom text prop
- Contains three animated dots
- Applies correct CSS classes for animation

### AskPanel.test.tsx
- ThinkingIndicator appears when currentStatus is set
- "thinking" status displays as "Thinking" (capitalized)
- Other statuses pass through unchanged

### Backend tests
- Verify SSE stream emits `'thinking'` as the stage
- Update any existing tests that expect `'generating'`

## Files Changed

1. `backend/src/oya/qa/service.py` - change `'generating'` → `'thinking'`
2. `frontend/src/components/ThinkingIndicator.tsx` - new component
3. `frontend/src/components/ThinkingIndicator.test.tsx` - new tests
4. `frontend/src/components/AskPanel.tsx` - use ThinkingIndicator
5. `frontend/src/components/AskPanel.test.tsx` - add/update tests
6. Backend test file(s) - update expected value if needed
