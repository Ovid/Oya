# Q&A: Remove Streaming and Unify Response Formatting

## Problem

When using "Quick" mode for Q&A, the response displays raw XML tags:

```
<answer> Oya is a full-stack system... </answer> <citations> [...] </citations>
```

This happens because:
1. Quick mode streams raw LLM tokens directly to the frontend, including the XML structure
2. Thorough mode extracts the answer with `parse_answer()` before "fake streaming" it in word batches
3. The two modes don't share response parsing logic

## Solution

Remove streaming entirely from both modes and unify response handling:
1. Both modes wait for the complete LLM response
2. Both modes use shared `parse_answer()` to extract clean content
3. Return the parsed answer in the `done` SSE event
4. Frontend displays the final answer without accumulating tokens

## Design

### Backend Changes

#### 1. Share `parse_answer()` between modes

The function already exists in `backend/src/oya/qa/cgrag.py`. Import and use it in `service.py` for Quick mode.

```python
# In service.py
from oya.qa.cgrag import parse_answer
```

#### 2. Modify `ask_stream()` to not stream tokens

Current Quick mode flow:
```python
async for token in self._llm.generate_stream(...):
    accumulated_response += token
    yield f"event: token\ndata: {json.dumps({'text': token})}\n\n"
```

New Quick mode flow:
```python
response = await self._llm.generate(...)
answer = parse_answer(response)
# No token events - answer sent in done event
```

Current Thorough mode flow:
```python
cgrag_result = await run_cgrag_loop(...)
words = cgrag_result.answer.split(" ")
for batch in batches:
    yield f"event: token\ndata: {json.dumps({'text': batch})}\n\n"
    await asyncio.sleep(0.005)
```

New Thorough mode flow:
```python
cgrag_result = await run_cgrag_loop(...)
answer = cgrag_result.answer  # Already extracted by parse_answer() in cgrag.py
# No token events - answer sent in done event
```

#### 3. Add `answer` field to `done` event

Current `done` event:
```python
done_data = {
    "citations": [...],
    "confidence": "...",
    "session_id": "...",
    "disclaimer": "...",
    "search_quality": {...},
}
```

New `done` event:
```python
done_data = {
    "answer": answer,  # NEW: the clean, parsed answer text
    "citations": [...],
    "confidence": "...",
    "session_id": "...",
    "disclaimer": "...",
    "search_quality": {...},
}
```

#### 4. Keep prompt formats separate

- Quick mode continues using `QA_SYSTEM_PROMPT` with `<answer>` + `<citations>` format
- CGRAG mode continues using `CGRAG_QA_TEMPLATE` with `<answer>` + `<missing>` format

The prompts serve different purposes (citations vs. gap detection), but both use `<answer>` tags, so `parse_answer()` works for both.

### Frontend Changes

#### 1. Update `StreamCallbacks` interface

```typescript
// In client.ts
interface DoneData {
  answer: string  // NEW
  citations: Citation[]
  confidence: ConfidenceLevel
  session_id: string | null
  disclaimer: string
  search_quality: SearchQuality
}
```

#### 2. Simplify `AskPanel.tsx`

Remove:
- `currentStreamText` state
- `streamTextRef` ref
- Token accumulation logic in `onToken` callback

Update `handleSubmit`:
```typescript
onToken: () => {}, // No-op, tokens no longer sent
onDone: (data) => {
  const newMessage: QAMessage = {
    question: pendingQuestion,
    answer: data.answer,  // Use answer from done event
    citations: data.citations,
    // ... rest unchanged
  }
  setMessages(prev => [...prev, newMessage])
}
```

#### 3. Keep SSE infrastructure

SSE remains useful for:
- `status` events: "Searching...", "Thinking..." indicators
- `error` events: Clean error handling
- `done` event: Final response delivery

### File Changes Summary

| File | Changes |
|------|---------|
| `backend/src/oya/qa/service.py` | Import `parse_answer`, modify `ask_stream()` to use non-streaming LLM call, add `answer` to done event |
| `frontend/src/api/client.ts` | Update `DoneData` interface to include `answer` field |
| `frontend/src/components/AskPanel.tsx` | Remove streaming state, use `answer` from done event |

## Testing

### Backend Tests

**File: `backend/tests/test_qa_response_parsing.py`**

```python
import pytest
from oya.qa.cgrag import parse_answer

class TestParseAnswer:
    def test_extracts_answer_from_tags(self):
        response = "<answer>This is the answer.</answer><citations>[]</citations>"
        assert parse_answer(response) == "This is the answer."

    def test_handles_whitespace(self):
        response = "<answer>\n  Multiline\n  answer\n</answer>"
        assert parse_answer(response) == "Multiline\n  answer"

    def test_handles_missing_tags(self):
        response = "Just plain text without tags"
        assert parse_answer(response) == "Just plain text without tags"

    def test_case_insensitive(self):
        response = "<ANSWER>Works</ANSWER>"
        assert parse_answer(response) == "Works"
```

**File: `backend/tests/test_qa_stream.py`** (modify existing)

```python
@pytest.mark.asyncio
async def test_quick_mode_no_token_events():
    """Verify streaming endpoint doesn't emit token events."""
    events = []
    async for event in qa_service.ask_stream(quick_mode_request):
        events.append(parse_sse_event(event))

    token_events = [e for e in events if e["type"] == "token"]
    assert len(token_events) == 0

@pytest.mark.asyncio
async def test_done_event_includes_answer():
    """Verify done event contains parsed answer."""
    events = []
    async for event in qa_service.ask_stream(request):
        events.append(parse_sse_event(event))

    done_event = next(e for e in events if e["type"] == "done")
    assert "answer" in done_event["data"]
    assert "<answer>" not in done_event["data"]["answer"]
    assert "</answer>" not in done_event["data"]["answer"]

@pytest.mark.asyncio
async def test_thorough_mode_no_token_events():
    """Verify CGRAG mode also doesn't emit token events."""
    events = []
    async for event in qa_service.ask_stream(thorough_mode_request):
        events.append(parse_sse_event(event))

    token_events = [e for e in events if e["type"] == "token"]
    assert len(token_events) == 0
```

### Frontend Tests

**File: `frontend/src/components/__tests__/AskPanel.test.tsx`** (add to existing)

```typescript
it('displays answer from done event', async () => {
  // Mock SSE that sends status then done (no tokens)
  mockAskQuestionStream.mockImplementation((req, callbacks) => {
    callbacks.onStatus('searching', 1)
    callbacks.onStatus('thinking', 1)
    callbacks.onDone({
      answer: 'This is the parsed answer.',
      citations: [],
      confidence: 'high',
      disclaimer: 'Based on strong evidence.',
      session_id: null,
      search_quality: { semantic_searched: true, fts_searched: true, results_found: 5, results_used: 3 }
    })
    return Promise.resolve()
  })

  render(<AskPanel isOpen={true} onClose={() => {}} />)

  // Submit a question
  const input = screen.getByPlaceholderText(/ask a question/i)
  await userEvent.type(input, 'What is this codebase?')
  await userEvent.click(screen.getByRole('button', { name: /send/i }))

  // Verify answer displays
  await waitFor(() => {
    expect(screen.getByText('This is the parsed answer.')).toBeInTheDocument()
  })
})
```

## Implementation Order

1. Backend: Add `answer` field to done event (backwards compatible - frontend can ignore)
2. Backend: Switch Quick mode to non-streaming with `parse_answer()`
3. Backend: Remove fake-streaming from Thorough mode
4. Backend: Add/update tests
5. Frontend: Update to use `answer` from done event
6. Frontend: Remove streaming state management
7. Frontend: Add/update tests
