# Q&A Input Textarea Design

## Summary

Replace the single-line input field in the Q&A panel with an auto-expanding textarea that grows from 1 to 4 rows as the user types longer questions.

## Requirements

- Start at 1 row (same as current input)
- Auto-expand as user types, up to 4 rows maximum
- Scroll internally when content exceeds 4 rows
- Enter key adds newline (traditional textarea behavior)
- Submit via button only
- Preserve existing disabled states (during generation, when no wiki exists)

## Implementation

### Changes to `AskPanel.tsx`

1. Replace `<input type="text">` with `<textarea>`
2. Add a ref to measure the textarea
3. Add auto-resize logic via `useEffect` that:
   - Resets height to `auto` to get accurate `scrollHeight`
   - Sets height to `min(scrollHeight, maxHeight)`
   - Enables `overflow-y: auto` when content exceeds max
4. Set `rows={1}` as starting size
5. Cap max height at ~96px (4 rows)

### Code Changes

```tsx
// Add ref
const textareaRef = useRef<HTMLTextAreaElement>(null)

// Add resize effect
useEffect(() => {
  const textarea = textareaRef.current
  if (!textarea) return

  textarea.style.height = 'auto'
  const maxHeight = 96 // ~4 rows
  const newHeight = Math.min(textarea.scrollHeight, maxHeight)
  textarea.style.height = `${newHeight}px`
  textarea.style.overflowY = textarea.scrollHeight > maxHeight ? 'auto' : 'hidden'
}, [question])

// Replace input with textarea
<textarea
  ref={textareaRef}
  value={question}
  onChange={(e) => setQuestion(e.target.value)}
  placeholder="Ask a question..."
  rows={1}
  className="flex-1 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm resize-none"
  disabled={isLoading || isGenerating || !hasWiki}
/>
```

### Styling Notes

- Add `resize-none` to prevent manual resize handle
- Change flex container from `items-center` to `items-end` so button aligns to bottom when textarea grows
- Existing disabled styling works unchanged

## Files Changed

- `frontend/src/components/AskPanel.tsx` - single file change
