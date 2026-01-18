# Ask Panel Improvements Design

## Overview

Comprehensive improvements to the "Ask a question" functionality addressing UX issues, performance, and user control.

## Problems Addressed

1. **Links destroy answers** - Clicking citation links closes the panel, losing conversation
2. **No follow-up questions** - Each question is one-shot, no session continuity
3. **Slow response time** - CGRAG makes 3 sequential LLM calls (~2.5 min total)
4. **Poor loading indicator** - Only "..." shown during long waits
5. **No user control** - Temperature, timeout, and search depth are hard-coded
6. **Fixed panel widths** - Cannot resize sidebars to see content better

## Solution Summary

| Problem | Solution |
|---------|----------|
| Links destroy answers | Remove `onClick={onClose}` from citations |
| No follow-ups | Wire up existing `session_id` support |
| Slow response | Optional Quick mode (single LLM call) |
| Poor loading | Stream tokens via SSE |
| No user control | Settings popover with temperature, timeout, mode |
| Fixed widths | Draggable resize handles on both sidebars |

---

## Backend Changes

### New Streaming Endpoint

**`POST /api/qa/ask/stream`**

Returns Server-Sent Events instead of JSON response.

```python
@router.post("/ask/stream")
async def ask_question_stream(
    request: QARequest,
    service: QAService = Depends(get_qa_service),
) -> StreamingResponse:
    """Stream Q&A response as Server-Sent Events."""
    return StreamingResponse(
        service.ask_stream(request),
        media_type="text/event-stream"
    )
```

### Extended QARequest Schema

```python
class QARequest(BaseModel):
    question: str
    session_id: str | None = None      # Existing, now used by frontend
    use_graph: bool = True             # Existing
    quick_mode: bool = False           # NEW: Skip CGRAG
    temperature: float | None = None   # NEW: Override default (0.0-1.0)
```

### SSE Event Format

```
event: token
data: {"text": "The"}

event: token
data: {"text": " function"}

event: status
data: {"stage": "searching", "pass": 1}

event: done
data: {"citations": [...], "confidence": "high", "session_id": "abc123", "cgrag": {...}}

event: error
data: {"message": "Rate limit exceeded"}
```

### LLMClient Streaming Method

New method `generate_stream()` using LiteLLM's async streaming:

```python
async def generate_stream(
    self,
    prompt: str,
    system_prompt: str | None = None,
    temperature: float = DEFAULT_TEMPERATURE,
    max_tokens: int = MAX_TOKENS,
) -> AsyncGenerator[str, None]:
    """Generate completion with streaming tokens."""
    # Uses acompletion(..., stream=True)
    # Yields individual tokens as they arrive
```

### Quick Mode Logic

When `quick_mode=True`:
- Skip `run_cgrag_loop()` entirely
- Single call to `llm.generate_stream()` with initial search context
- Response time ~40s instead of ~2.5min

---

## Frontend Changes

### AskPanel State

```typescript
interface AskPanelState {
  messages: QAMessage[]
  sessionId: string | null
  isStreaming: boolean
  currentStreamText: string
  settings: {
    quickMode: boolean      // Default: true
    temperature: number     // Default: 0.5
    timeoutMinutes: number  // Default: 3
  }
}
```

### Streaming Implementation

1. User submits question
2. Add placeholder message with empty answer
3. Open EventSource to `/api/qa/ask/stream`
4. On `token` events: Append to `currentStreamText`, re-render
5. On `done` event: Finalize message with citations/confidence, store `session_id`
6. On `error` event: Show error inline, close stream
7. Timeout via `AbortController` based on user setting

### Key Bug Fixes

- **Remove `onClick={onClose}` from citation links** (line 47-48)
- Links now navigate without closing panel
- Add "Clear conversation" button to reset session

### Settings Popover Component

`QASettingsPopover.tsx` - Gear icon next to Ask button:

```
┌─────────────────────────────┐
│ Answer Settings         ✕  │
├─────────────────────────────┤
│ Mode                        │
│ ○ Quick (~40s)              │
│ ● Thorough (~2min)          │
│                             │
│ Temperature        [0.5]    │
│ ├──────────●──────────┤     │
│ Precise          Creative   │
│                             │
│ Timeout            [3min]   │
│ ├────────────●────────┤     │
│ 1min                 5min   │
│                             │
│ [Reset to defaults]         │
└─────────────────────────────┘
```

Settings persist to localStorage (`oya-qa-settings`).

### Resizable Sidebars

**New hook: `useResizablePanel.ts`**

```typescript
function useResizablePanel(options: {
  side: 'left' | 'right'
  defaultWidth: number
  minWidth: number
  maxWidth: number
  storageKey: string
}) => {
  width: number
  isDragging: boolean
  handleMouseDown: (e: MouseEvent) => void
}
```

**Width constraints:**
- Left sidebar: min 180px, max 400px, default 256px
- Right panel: min 280px, max 600px, default 350px

**Drag handle styling:**
- 4px invisible hit area, 2px visible line on hover
- `col-resize` cursor
- Highlight while dragging

---

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Network disconnect mid-stream | Show partial answer + "Connection lost" + Retry button |
| LLM rate limit | Inline error, suggest Quick mode |
| Timeout exceeded | Client-side abort, "Request timed out" + Retry |
| Session expired (30min TTL) | Backend returns new session_id seamlessly |
| Invalid localStorage | Fall back to defaults |

---

## Backward Compatibility

- Existing `/api/qa/ask` endpoint unchanged
- New `/api/qa/ask/stream` is additive
- Old frontends continue to work

---

## Files to Modify

### Backend
- `backend/src/oya/api/routers/qa.py` - Add streaming endpoint
- `backend/src/oya/qa/service.py` - Add `ask_stream()` method
- `backend/src/oya/qa/schemas.py` - Extend QARequest
- `backend/src/oya/llm/client.py` - Add `generate_stream()` method

### Frontend
- `frontend/src/components/AskPanel.tsx` - Streaming, session, bug fixes
- `frontend/src/components/Layout.tsx` - Resizable sidebar wiring
- `frontend/src/components/QASettingsPopover.tsx` - New component
- `frontend/src/hooks/useResizablePanel.ts` - New hook
- `frontend/src/config/qa.ts` - Add default settings constants

---

## Settings Defaults

```typescript
// frontend/src/config/qa.ts
export const QA_DEFAULTS = {
  quickMode: true,
  temperature: 0.5,
  timeoutMinutes: 3,
}

export const QA_CONSTRAINTS = {
  temperature: { min: 0, max: 1, step: 0.1 },
  timeout: { min: 1, max: 5, step: 1 },
}
```

---

## Non-Goals

- Cross-tab session sync (each tab independent)
- Mobile-specific resize UI (use fixed widths on narrow viewports)
- Changing existing wiki generation behavior
- Persisting conversation history across page reloads (session is in-memory)
