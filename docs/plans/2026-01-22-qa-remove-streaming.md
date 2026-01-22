# Q&A Remove Streaming Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Remove fake streaming from Q&A, unify response parsing so both Quick and Thorough modes display clean answers without XML tags.

**Architecture:** Backend waits for complete LLM response, extracts answer using shared `parse_answer()`, returns answer in `done` SSE event. Frontend displays answer from `done` event instead of accumulating tokens.

**Tech Stack:** Python/FastAPI (backend), React/TypeScript (frontend), Vitest (frontend tests), pytest (backend tests)

---

### Task 1: Add backend test for parse_answer

**Files:**
- Create: `backend/tests/test_qa_parsing.py`

**Step 1: Write the test file**

```python
"""Tests for Q&A response parsing utilities."""

import pytest
from oya.qa.cgrag import parse_answer


class TestParseAnswer:
    """Tests for parse_answer function."""

    def test_extracts_answer_from_tags(self):
        """Basic extraction of answer from XML tags."""
        response = "<answer>This is the answer.</answer><citations>[]</citations>"
        assert parse_answer(response) == "This is the answer."

    def test_handles_whitespace_in_tags(self):
        """Whitespace inside tags is preserved but outer whitespace trimmed."""
        response = "<answer>\n  Multiline\n  answer\n</answer>"
        assert parse_answer(response) == "Multiline\n  answer"

    def test_handles_missing_tags_returns_full_response(self):
        """When no tags present, returns the full response."""
        response = "Just plain text without tags"
        assert parse_answer(response) == "Just plain text without tags"

    def test_case_insensitive_tags(self):
        """Tag matching is case insensitive."""
        response = "<ANSWER>Works</ANSWER>"
        assert parse_answer(response) == "Works"

    def test_extracts_from_response_with_citations(self):
        """Extracts answer even when citations block follows."""
        response = """<answer>
The main function initializes the app.
</answer>

<citations>
[{"path": "main.py", "relevant_text": "def main()"}]
</citations>"""
        result = parse_answer(response)
        assert "main function initializes" in result
        assert "<citations>" not in result

    def test_extracts_from_response_with_missing_block(self):
        """Extracts answer when CGRAG missing block follows."""
        response = """<answer>
Authentication uses JWT tokens.
</answer>

<missing>
NONE
</missing>"""
        result = parse_answer(response)
        assert "JWT tokens" in result
        assert "<missing>" not in result
```

**Step 2: Run the test**

Run: `cd backend && python -m pytest tests/test_qa_parsing.py -v`

Expected: All tests PASS (parse_answer already exists in cgrag.py)

**Step 3: Commit**

```bash
git add backend/tests/test_qa_parsing.py
git commit -m "test: add parse_answer unit tests"
```

---

### Task 2: Add backend test for streaming endpoint returning answer in done event

**Files:**
- Modify: `backend/tests/test_qa_service.py`

**Step 1: Write the failing test**

Add to the end of `backend/tests/test_qa_service.py`:

```python
class TestQAServiceStreaming:
    """Tests for streaming endpoint behavior."""

    @pytest.mark.asyncio
    async def test_done_event_includes_parsed_answer(self, mock_vectorstore, mock_db, mock_llm):
        """Done event should include the parsed answer without XML tags."""
        # Configure mock to return response with XML tags
        mock_llm.generate.return_value = """<answer>
The authentication system uses JWT tokens stored in cookies.
</answer>

<citations>
[{"path": "auth.py", "relevant_text": "jwt.encode()"}]
</citations>"""

        service = QAService(mock_vectorstore, mock_db, mock_llm)
        request = QARequest(question="How does auth work?", quick_mode=True)

        events = []
        async for event in service.ask_stream(request):
            events.append(event)

        # Find the done event
        done_events = [e for e in events if e.startswith("event: done")]
        assert len(done_events) == 1

        # Parse the done event data
        done_event = done_events[0]
        data_line = [line for line in done_event.split("\n") if line.startswith("data: ")][0]
        import json
        data = json.loads(data_line[6:])  # Skip "data: " prefix

        # Verify answer is included and clean
        assert "answer" in data
        assert "JWT tokens" in data["answer"]
        assert "<answer>" not in data["answer"]
        assert "</answer>" not in data["answer"]

    @pytest.mark.asyncio
    async def test_no_token_events_in_quick_mode(self, mock_vectorstore, mock_db, mock_llm):
        """Quick mode should not emit token events."""
        mock_llm.generate.return_value = "<answer>Simple answer</answer>"

        service = QAService(mock_vectorstore, mock_db, mock_llm)
        request = QARequest(question="What is X?", quick_mode=True)

        events = []
        async for event in service.ask_stream(request):
            events.append(event)

        token_events = [e for e in events if e.startswith("event: token")]
        assert len(token_events) == 0

    @pytest.mark.asyncio
    async def test_no_token_events_in_thorough_mode(self, mock_vectorstore, mock_db, mock_llm):
        """Thorough mode should not emit token events."""
        mock_llm.generate.return_value = "<answer>Thorough answer</answer><missing>NONE</missing>"

        service = QAService(mock_vectorstore, mock_db, mock_llm)
        request = QARequest(question="What is X?", quick_mode=False)

        events = []
        async for event in service.ask_stream(request):
            events.append(event)

        token_events = [e for e in events if e.startswith("event: token")]
        assert len(token_events) == 0
```

**Step 2: Run the test to verify it fails**

Run: `cd backend && python -m pytest tests/test_qa_service.py::TestQAServiceStreaming -v`

Expected: FAIL - `answer` key not in done event data, token events still emitted

**Step 3: Commit the failing test**

```bash
git add backend/tests/test_qa_service.py
git commit -m "test: add failing tests for streaming without token events"
```

---

### Task 3: Implement backend changes - remove streaming, add answer to done event

**Files:**
- Modify: `backend/src/oya/qa/service.py`

**Step 1: Add import for parse_answer**

At line 25, change:
```python
from oya.qa.cgrag import run_cgrag_loop, CGRAGResult
```
to:
```python
from oya.qa.cgrag import run_cgrag_loop, CGRAGResult, parse_answer
```

**Step 2: Modify ask_stream for Quick mode (lines 997-1013)**

Replace lines 997-1013:
```python
        try:
            if request.quick_mode:
                # Issue 5 fix: Match prompt format from _ask_quick()
                prompt = f"""{initial_context}

QUESTION: {request.question}

Answer the question based only on the context provided. Include citations to specific files."""

                # Single pass streaming
                async for token in self._llm.generate_stream(
                    prompt=prompt,
                    system_prompt=QA_SYSTEM_PROMPT,
                    temperature=temperature,
                ):
                    accumulated_response += token
                    yield f"event: token\ndata: {json.dumps({'text': token})}\n\n"
```

With:
```python
        try:
            if request.quick_mode:
                prompt = f"""{initial_context}

QUESTION: {request.question}

Answer the question based only on the context provided. Include citations to specific files."""

                # Wait for complete response, then extract answer
                raw_response = await self._llm.generate(
                    prompt=prompt,
                    system_prompt=QA_SYSTEM_PROMPT,
                    temperature=temperature,
                )
                accumulated_response = raw_response
                answer = parse_answer(raw_response)
```

**Step 3: Modify ask_stream for Thorough mode (lines 1014-1049)**

Replace lines 1014-1049:
```python
            else:
                # CGRAG mode - run iteration first, then send answer
                assert session is not None  # Guaranteed by check at line 941
                cgrag_result = await run_cgrag_loop(
                    question=request.question,
                    initial_context=initial_context,
                    session=session,
                    llm=self._llm,
                    graph=self._graph,
                    vectorstore=self._vectorstore,
                )
                # Stream answer in batched word chunks with flush points to prevent
                # network buffer truncation (all words yielded too fast otherwise)
                words = cgrag_result.answer.split(" ")
                batch_size = 5  # Words per SSE event (smaller batches = more flush points)
                total_chars_sent = 0
                import logging

                logger = logging.getLogger(__name__)
                logger.info(
                    f"CGRAG streaming: {len(words)} words, {len(cgrag_result.answer)} chars"
                )
                for i in range(0, len(words), batch_size):
                    batch = words[i : i + batch_size]
                    # Reconstruct with spaces, add trailing space if not last batch
                    text = " ".join(batch)
                    if i + batch_size < len(words):
                        text += " "
                    total_chars_sent += len(text)
                    yield f"event: token\ndata: {json.dumps({'text': text})}\n\n"
                    # Small delay to force network buffer flush (sleep(0) is not enough)
                    await asyncio.sleep(0.005)  # 5ms delay per batch
                logger.info(
                    f"CGRAG streaming complete: sent {total_chars_sent} chars in {(len(words) + batch_size - 1) // batch_size} batches"
                )
                accumulated_response = cgrag_result.answer
```

With:
```python
            else:
                # CGRAG mode - run full iteration loop
                assert session is not None
                cgrag_result = await run_cgrag_loop(
                    question=request.question,
                    initial_context=initial_context,
                    session=session,
                    llm=self._llm,
                    graph=self._graph,
                    vectorstore=self._vectorstore,
                )
                accumulated_response = cgrag_result.answer  # Already parsed by cgrag
                answer = cgrag_result.answer
```

**Step 4: Add answer to done_data (around line 1071)**

Change:
```python
        done_data = {
            "citations": [c.model_dump() for c in citations],
            "confidence": confidence.value,
            "session_id": session_id,
            "disclaimer": disclaimers[confidence],
            "search_quality": {
```

To:
```python
        done_data = {
            "answer": answer,
            "citations": [c.model_dump() for c in citations],
            "confidence": confidence.value,
            "session_id": session_id,
            "disclaimer": disclaimers[confidence],
            "search_quality": {
```

**Step 5: Run the tests**

Run: `cd backend && python -m pytest tests/test_qa_service.py::TestQAServiceStreaming -v`

Expected: All tests PASS

**Step 6: Run all Q&A tests to check for regressions**

Run: `cd backend && python -m pytest tests/test_qa_service.py tests/test_qa_api.py tests/test_qa_parsing.py -v`

Expected: All tests PASS

**Step 7: Commit**

```bash
git add backend/src/oya/qa/service.py
git commit -m "feat: remove streaming, return answer in done event

- Quick mode now waits for full LLM response
- Both modes use parse_answer() to extract clean content
- Answer included in done event for frontend consumption
- No more token events emitted"
```

---

### Task 4: Update frontend types for done event

**Files:**
- Modify: `frontend/src/api/client.ts`

**Step 1: Update StreamCallbacks interface**

At lines 165-171, change:
```typescript
  onDone: (data: {
    citations: Citation[]
    confidence: string
    session_id: string | null
    search_quality: SearchQuality
    disclaimer: string
  }) => void
```

To:
```typescript
  onDone: (data: {
    answer: string
    citations: Citation[]
    confidence: string
    session_id: string | null
    search_quality: SearchQuality
    disclaimer: string
  }) => void
```

**Step 2: Commit**

```bash
git add frontend/src/api/client.ts
git commit -m "feat: add answer field to StreamCallbacks done event type"
```

---

### Task 5: Update AskPanel to use answer from done event

**Files:**
- Modify: `frontend/src/components/AskPanel.tsx`

**Step 1: Remove streaming state variables**

At lines 67-68, remove:
```typescript
  const [currentStreamText, setCurrentStreamText] = useState('')
```

Keep `currentStatus` as it's still needed for status indicators.

At line 102-103, remove:
```typescript
    setCurrentStreamText('')
```

At line 108, remove:
```typescript
  const streamTextRef = useRef('')
```

**Step 2: Update handleSubmit - remove stream text initialization**

At lines 121-122, remove:
```typescript
    setCurrentStreamText('')
    streamTextRef.current = ''
```

**Step 3: Update onToken callback to be a no-op**

At lines 143-147, change:
```typescript
          onToken: (text) => {
            streamTextRef.current += text
            setCurrentStreamText(streamTextRef.current)
            setCurrentStatus(null)
          },
```

To:
```typescript
          onToken: () => {
            // No longer used - answer comes in done event
          },
```

**Step 4: Update onDone to use answer from data**

At lines 151-166, change:
```typescript
          onDone: (data) => {
            console.log('[AskPanel] onDone - streamTextRef length:', streamTextRef.current.length)
            const finalAnswer = streamTextRef.current
            const durationSeconds = Math.floor((Date.now() - startTimeRef.current) / 1000)
            setMessages((prev) => [
              ...prev,
              {
                question: trimmedQuestion,
                answer: finalAnswer,
                citations: data.citations,
                confidence: data.confidence as ConfidenceLevel,
                disclaimer: data.disclaimer,
                searchQuality: data.search_quality,
                durationSeconds,
              },
            ])
```

To:
```typescript
          onDone: (data) => {
            const durationSeconds = Math.floor((Date.now() - startTimeRef.current) / 1000)
            setMessages((prev) => [
              ...prev,
              {
                question: trimmedQuestion,
                answer: data.answer,
                citations: data.citations,
                confidence: data.confidence as ConfidenceLevel,
                disclaimer: data.disclaimer,
                searchQuality: data.search_quality,
                durationSeconds,
              },
            ])
```

**Step 5: Update onDone cleanup - remove stream text**

At lines 170-172, change:
```typescript
            setCurrentStreamText('')
            streamTextRef.current = ''
            setCurrentStatus(null)
```

To:
```typescript
            setCurrentStatus(null)
```

**Step 6: Update onError cleanup - remove stream text**

At lines 176-179, change:
```typescript
            setCurrentStreamText('')
            streamTextRef.current = ''
            setCurrentStatus(null)
```

To:
```typescript
            setCurrentStatus(null)
```

**Step 7: Update catch block cleanup - remove stream text**

At lines 191-194, change:
```typescript
      setCurrentStreamText('')
      streamTextRef.current = ''
      setCurrentStatus(null)
```

To:
```typescript
      setCurrentStatus(null)
```

**Step 8: Update auto-scroll useEffect**

At lines 74-77, change:
```typescript
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, currentStreamText])
```

To:
```typescript
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, currentStatus])
```

**Step 9: Remove streaming display in render**

Find where `currentStreamText` is rendered (search for it in the JSX section) and remove it. The ThinkingIndicator should remain for showing status.

**Step 10: Run frontend tests**

Run: `cd frontend && npm run test`

Expected: Tests pass (may need minor updates)

**Step 11: Commit**

```bash
git add frontend/src/components/AskPanel.tsx
git commit -m "feat: use answer from done event instead of streaming

- Remove currentStreamText state and streamTextRef
- onToken callback now a no-op
- Answer comes directly from done event data
- Keep status indicator for searching/thinking states"
```

---

### Task 6: Add frontend test for answer from done event

**Files:**
- Modify: `frontend/src/components/AskPanel.test.tsx`

**Step 1: Add test for displaying answer from done event**

Add to the `describe('AskPanel')` block:

```typescript
  describe('answer display', () => {
    it('displays answer from done event', async () => {
      const { userEvent } = await import('@testing-library/user-event')

      vi.mocked(api.askQuestionStream).mockImplementation(async (_req, callbacks) => {
        callbacks.onStatus('searching', 1)
        callbacks.onStatus('thinking', 1)
        callbacks.onDone({
          answer: 'This is the parsed answer without XML tags.',
          citations: [],
          confidence: 'high',
          disclaimer: 'Based on strong evidence.',
          session_id: null,
          search_quality: {
            semantic_searched: true,
            fts_searched: true,
            results_found: 5,
            results_used: 3,
          },
        })
      })

      renderAskPanel({ isOpen: true })

      await waitFor(() => {
        expect(screen.getByPlaceholderText('Ask a question...')).toBeInTheDocument()
      })

      const input = screen.getByPlaceholderText('Ask a question...')
      const user = userEvent.setup()
      await user.type(input, 'What is this codebase?')
      await user.click(screen.getByRole('button', { name: /ask/i }))

      await waitFor(() => {
        expect(screen.getByText('This is the parsed answer without XML tags.')).toBeInTheDocument()
      })
    })

    it('does not display XML tags in answer', async () => {
      const { userEvent } = await import('@testing-library/user-event')

      vi.mocked(api.askQuestionStream).mockImplementation(async (_req, callbacks) => {
        callbacks.onStatus('thinking', 1)
        callbacks.onDone({
          answer: 'Clean answer text',
          citations: [],
          confidence: 'medium',
          disclaimer: 'Based on partial evidence.',
          session_id: null,
          search_quality: {
            semantic_searched: true,
            fts_searched: true,
            results_found: 3,
            results_used: 2,
          },
        })
      })

      renderAskPanel({ isOpen: true })

      await waitFor(() => {
        expect(screen.getByPlaceholderText('Ask a question...')).toBeInTheDocument()
      })

      const input = screen.getByPlaceholderText('Ask a question...')
      const user = userEvent.setup()
      await user.type(input, 'Test question')
      await user.click(screen.getByRole('button', { name: /ask/i }))

      await waitFor(() => {
        expect(screen.getByText('Clean answer text')).toBeInTheDocument()
      })

      // Verify no XML tags are displayed
      expect(screen.queryByText(/<answer>/)).not.toBeInTheDocument()
      expect(screen.queryByText(/<\/answer>/)).not.toBeInTheDocument()
    })
  })
```

**Step 2: Run the tests**

Run: `cd frontend && npm run test`

Expected: All tests PASS

**Step 3: Commit**

```bash
git add frontend/src/components/AskPanel.test.tsx
git commit -m "test: add tests for answer display from done event"
```

---

### Task 7: Manual verification and final cleanup

**Step 1: Start the backend**

Run: `cd backend && source .venv/bin/activate && WORKSPACE_PATH=/Users/poecurt/projects/oya uvicorn oya.main:app --reload`

**Step 2: Start the frontend**

Run: `cd frontend && npm run dev`

**Step 3: Test Quick mode**

1. Open http://localhost:5173
2. Open the Q&A panel
3. Ensure "Quick" mode is selected in settings
4. Ask a question
5. Verify the answer displays without `<answer>` or `<citations>` XML tags

**Step 4: Test Thorough mode**

1. Switch to "Thorough" mode in settings
2. Ask a question
3. Verify the answer displays cleanly

**Step 5: Run full test suite**

Run: `cd backend && python -m pytest tests/ -v`
Run: `cd frontend && npm run test`

Expected: All tests pass

**Step 6: Final commit**

```bash
git add -A
git commit -m "chore: cleanup any remaining changes from Q&A streaming removal"
```
