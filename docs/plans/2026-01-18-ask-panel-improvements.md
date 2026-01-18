# Ask Panel Improvements Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add streaming responses, resizable panels, settings popover, and session-based follow-ups to the Ask Panel.

**Architecture:** Backend adds SSE streaming endpoint with optional quick mode (skip CGRAG). Frontend consumes SSE stream, displays tokens incrementally, persists settings to localStorage, and uses a custom hook for draggable panel resize.

**Tech Stack:** Python/FastAPI (SSE via StreamingResponse), LiteLLM async streaming, React/TypeScript, EventSource API, localStorage.

---

## Task 1: Extend QARequest Schema

**Files:**
- Modify: `backend/src/oya/qa/schemas.py`
- Test: `backend/tests/test_qa_api.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_qa_api.py`:

```python
def test_ask_accepts_quick_mode_and_temperature(client: TestClient):
    """QARequest accepts quick_mode and temperature parameters."""
    response = client.post(
        "/api/qa/ask",
        json={
            "question": "What is this?",
            "quick_mode": True,
            "temperature": 0.3,
        },
    )
    # Should not fail with validation error
    assert response.status_code in (200, 500)  # 500 if no wiki, but not 422
```

**Step 2: Run test to verify it fails**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_qa_api.py::test_ask_accepts_quick_mode_and_temperature -v`

Expected: FAIL with 422 validation error (extra fields not permitted)

**Step 3: Write minimal implementation**

In `backend/src/oya/qa/schemas.py`, modify `QARequest`:

```python
class QARequest(BaseModel):
    """Request for Q&A endpoint."""

    question: str
    session_id: str | None = None
    use_graph: bool = True
    quick_mode: bool = False
    temperature: float | None = Field(default=None, ge=0.0, le=1.0)
```

**Step 4: Run test to verify it passes**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_qa_api.py::test_ask_accepts_quick_mode_and_temperature -v`

Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/oya/qa/schemas.py backend/tests/test_qa_api.py
git commit -m "feat(qa): add quick_mode and temperature to QARequest schema"
```

---

## Task 2: Add LLMClient Streaming Method

**Files:**
- Modify: `backend/src/oya/llm/client.py`
- Test: `backend/tests/test_llm_client.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_llm_client.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_generate_stream_yields_tokens():
    """generate_stream yields tokens from LLM response."""
    from oya.llm.client import LLMClient

    # Mock streaming response
    mock_chunks = [
        MagicMock(choices=[MagicMock(delta=MagicMock(content="Hello"))]),
        MagicMock(choices=[MagicMock(delta=MagicMock(content=" world"))]),
        MagicMock(choices=[MagicMock(delta=MagicMock(content=None))]),
    ]

    async def mock_aiter():
        for chunk in mock_chunks:
            yield chunk

    with patch("oya.llm.client.acompletion") as mock_acompletion:
        mock_acompletion.return_value = mock_aiter()

        client = LLMClient(provider="openai", model="gpt-4")
        tokens = []
        async for token in client.generate_stream("test prompt"):
            tokens.append(token)

        assert tokens == ["Hello", " world"]
```

**Step 2: Run test to verify it fails**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_llm_client.py::test_generate_stream_yields_tokens -v`

Expected: FAIL with AttributeError (generate_stream not defined)

**Step 3: Write minimal implementation**

Add to `backend/src/oya/llm/client.py`:

```python
from collections.abc import AsyncGenerator

# Add this method to LLMClient class:

    async def generate_stream(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = DEFAULT_TEMPERATURE,
        max_tokens: int = MAX_TOKENS,
    ) -> AsyncGenerator[str, None]:
        """Generate completion with streaming tokens.

        Args:
            prompt: User prompt.
            system_prompt: Optional system prompt.
            temperature: Sampling temperature.
            max_tokens: Maximum response tokens.

        Yields:
            Individual tokens as they are generated.
        """
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({"role": "user", "content": prompt})

        kwargs = {
            "model": self._get_model_string(),
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }

        if self.api_key:
            kwargs["api_key"] = self.api_key

        if self.endpoint and self.provider == "ollama":
            kwargs["api_base"] = self.endpoint

        try:
            response = await acompletion(**kwargs)
            async for chunk in response:
                content = chunk.choices[0].delta.content
                if content:
                    yield content
        except AuthenticationError as e:
            raise LLMAuthenticationError(f"Authentication failed: {e}") from e
        except RateLimitError as e:
            raise LLMRateLimitError(f"Rate limit exceeded: {e}") from e
        except APIConnectionError as e:
            raise LLMConnectionError(f"Connection failed: {e}") from e
        except APIError as e:
            raise LLMError(f"LLM API error: {e}") from e
```

**Step 4: Run test to verify it passes**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_llm_client.py::test_generate_stream_yields_tokens -v`

Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/oya/llm/client.py backend/tests/test_llm_client.py
git commit -m "feat(llm): add generate_stream method for token streaming"
```

---

## Task 3: Add Quick Mode to QAService

**Files:**
- Modify: `backend/src/oya/qa/service.py`
- Test: `backend/tests/test_qa_service.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_qa_service.py`:

```python
@pytest.mark.asyncio
async def test_ask_quick_mode_skips_cgrag(
    qa_service: QAService,
    mock_llm: MagicMock,
):
    """Quick mode should make single LLM call, not multiple CGRAG passes."""
    mock_llm.generate.return_value = "<answer>Quick answer</answer><citations>[]</citations>"

    request = QARequest(question="test question", quick_mode=True)
    response = await qa_service.ask(request)

    # Quick mode should only call generate once (no CGRAG iteration)
    assert mock_llm.generate.call_count == 1
    assert response.cgrag is None or response.cgrag.passes_used == 0
```

**Step 2: Run test to verify it fails**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_qa_service.py::test_ask_quick_mode_skips_cgrag -v`

Expected: FAIL (quick_mode not implemented, CGRAG still runs)

**Step 3: Write minimal implementation**

In `backend/src/oya/qa/service.py`, modify `_ask_normal` method:

```python
    async def _ask_normal(self, request: QARequest) -> QAResponse:
        """Answer a question using search and LLM generation.

        Args:
            request: Q&A request with question.

        Returns:
            Q&A response with answer, citations, confidence, and search quality.
        """
        # Perform hybrid search
        results, semantic_ok, fts_ok = await self.search(request.question)

        # Calculate confidence from results
        confidence = self._calculate_confidence(results)

        # Build initial context with token budgeting
        initial_context, results_used = self._build_context_prompt(request.question, results)

        # Add graph context if available and enabled
        if self._graph is not None and request.use_graph and results:
            graph_context = self._build_graph_context(results)
            if graph_context:
                initial_context = graph_context + "\n\n" + initial_context

        # Quick mode: single LLM call, skip CGRAG
        if request.quick_mode:
            return await self._ask_quick(request, results, initial_context, semantic_ok, fts_ok, results_used, confidence)

        # Full mode: CGRAG iterative retrieval
        return await self._ask_with_cgrag(request, results, initial_context, semantic_ok, fts_ok, results_used, confidence)
```

Add new helper methods:

```python
    async def _ask_quick(
        self,
        request: QARequest,
        results: list[dict[str, Any]],
        context: str,
        semantic_ok: bool,
        fts_ok: bool,
        results_used: int,
        confidence: ConfidenceLevel,
    ) -> QAResponse:
        """Answer with single LLM call (no CGRAG iteration)."""
        temperature = request.temperature if request.temperature is not None else 0.7

        try:
            raw_answer = await self._llm.generate(
                prompt=context,
                system_prompt=QA_SYSTEM_PROMPT,
                temperature=temperature,
            )
        except Exception as e:
            return QAResponse(
                answer=f"Error generating answer: {str(e)}",
                citations=[],
                confidence=confidence,
                disclaimer="An error occurred while generating the answer.",
                search_quality=SearchQuality(
                    semantic_searched=semantic_ok,
                    fts_searched=fts_ok,
                    results_found=len(results),
                    results_used=results_used,
                ),
                cgrag=None,
            )

        answer = self._extract_answer(raw_answer)
        citations = self._extract_citations(raw_answer, results)

        disclaimers = {
            ConfidenceLevel.HIGH: "Based on strong evidence from the codebase.",
            ConfidenceLevel.MEDIUM: "Based on partial evidence. Verify against source code.",
            ConfidenceLevel.LOW: "Limited evidence found. This answer may be speculative.",
        }

        return QAResponse(
            answer=answer,
            citations=citations,
            confidence=confidence,
            disclaimer=disclaimers[confidence],
            search_quality=SearchQuality(
                semantic_searched=semantic_ok,
                fts_searched=fts_ok,
                results_found=len(results),
                results_used=results_used,
            ),
            cgrag=None,
        )

    async def _ask_with_cgrag(
        self,
        request: QARequest,
        results: list[dict[str, Any]],
        initial_context: str,
        semantic_ok: bool,
        fts_ok: bool,
        results_used: int,
        confidence: ConfidenceLevel,
    ) -> QAResponse:
        """Answer using CGRAG iterative retrieval."""
        # Get or create CGRAG session
        session = _session_store.get_or_create(request.session_id)
        context_from_cache = bool(session.cached_nodes) and request.session_id is not None

        try:
            # Run CGRAG iterative loop
            cgrag_result: CGRAGResult = await run_cgrag_loop(
                question=request.question,
                initial_context=initial_context,
                session=session,
                llm=self._llm,
                graph=self._graph,
                vectorstore=self._vectorstore,
            )
        except Exception as e:
            return QAResponse(
                answer=f"Error generating answer: {str(e)}",
                citations=[],
                confidence=confidence,
                disclaimer="An error occurred while generating the answer.",
                search_quality=SearchQuality(
                    semantic_searched=semantic_ok,
                    fts_searched=fts_ok,
                    results_found=len(results),
                    results_used=results_used,
                ),
                cgrag=CGRAGMetadata(
                    passes_used=0,
                    gaps_identified=[],
                    gaps_resolved=[],
                    gaps_unresolved=[],
                    session_id=session.id,
                    context_from_cache=context_from_cache,
                ),
            )

        # Extract answer from CGRAG result
        answer = cgrag_result.answer

        # Use fallback citations from search results
        citations = self._fallback_citations(results[:5])

        # Build CGRAG metadata
        cgrag_metadata = CGRAGMetadata(
            passes_used=cgrag_result.passes_used,
            gaps_identified=cgrag_result.gaps_identified,
            gaps_resolved=cgrag_result.gaps_resolved,
            gaps_unresolved=cgrag_result.gaps_unresolved,
            session_id=session.id,
            context_from_cache=context_from_cache,
        )

        # Build disclaimer based on confidence
        disclaimers = {
            ConfidenceLevel.HIGH: "Based on strong evidence from the codebase.",
            ConfidenceLevel.MEDIUM: "Based on partial evidence. Verify against source code.",
            ConfidenceLevel.LOW: "Limited evidence found. This answer may be speculative.",
        }

        return QAResponse(
            answer=answer,
            citations=citations,
            confidence=confidence,
            disclaimer=disclaimers[confidence],
            search_quality=SearchQuality(
                semantic_searched=semantic_ok,
                fts_searched=fts_ok,
                results_found=len(results),
                results_used=results_used,
            ),
            cgrag=cgrag_metadata,
        )
```

**Step 4: Run test to verify it passes**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_qa_service.py::test_ask_quick_mode_skips_cgrag -v`

Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/oya/qa/service.py backend/tests/test_qa_service.py
git commit -m "feat(qa): add quick mode to skip CGRAG iteration"
```

---

## Task 4: Add SSE Streaming Endpoint

**Files:**
- Modify: `backend/src/oya/api/routers/qa.py`
- Modify: `backend/src/oya/qa/service.py`
- Test: `backend/tests/test_qa_api.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_qa_api.py`:

```python
def test_ask_stream_returns_sse(client: TestClient, monkeypatch):
    """Streaming endpoint returns SSE content type."""
    # Mock the service to return immediately
    async def mock_stream(request):
        yield 'event: token\ndata: {"text": "Hello"}\n\n'
        yield 'event: done\ndata: {"citations": []}\n\n'

    monkeypatch.setattr(
        "oya.api.routers.qa.get_qa_service",
        lambda: MagicMock(ask_stream=mock_stream),
    )

    response = client.post(
        "/api/qa/ask/stream",
        json={"question": "test"},
    )
    assert response.headers["content-type"].startswith("text/event-stream")
```

**Step 2: Run test to verify it fails**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_qa_api.py::test_ask_stream_returns_sse -v`

Expected: FAIL with 404 (endpoint doesn't exist)

**Step 3: Write minimal implementation**

In `backend/src/oya/api/routers/qa.py`, add:

```python
from fastapi.responses import StreamingResponse

@router.post("/ask/stream")
async def ask_question_stream(
    request: QARequest,
    service: QAService = Depends(get_qa_service),
) -> StreamingResponse:
    """Stream Q&A response as Server-Sent Events.

    Returns SSE events:
    - event: token, data: {"text": "..."}
    - event: status, data: {"stage": "...", "pass": N}
    - event: done, data: {"citations": [...], "confidence": "...", "session_id": "..."}
    - event: error, data: {"message": "..."}
    """
    return StreamingResponse(
        service.ask_stream(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
```

In `backend/src/oya/qa/service.py`, add `ask_stream` method:

```python
import json
from collections.abc import AsyncGenerator

    async def ask_stream(self, request: QARequest) -> AsyncGenerator[str, None]:
        """Stream Q&A response as SSE events.

        Args:
            request: Q&A request with question.

        Yields:
            SSE-formatted event strings.
        """
        # Perform hybrid search
        results, semantic_ok, fts_ok = await self.search(request.question)
        confidence = self._calculate_confidence(results)
        initial_context, results_used = self._build_context_prompt(request.question, results)

        # Add graph context if available
        if self._graph is not None and request.use_graph and results:
            graph_context = self._build_graph_context(results)
            if graph_context:
                initial_context = graph_context + "\n\n" + initial_context

        yield f'event: status\ndata: {json.dumps({"stage": "searching", "pass": 1})}\n\n'

        temperature = request.temperature if request.temperature is not None else 0.7
        accumulated_response = ""

        try:
            if request.quick_mode:
                # Single pass streaming
                async for token in self._llm.generate_stream(
                    prompt=initial_context,
                    system_prompt=QA_SYSTEM_PROMPT,
                    temperature=temperature,
                ):
                    accumulated_response += token
                    yield f'event: token\ndata: {json.dumps({"text": token})}\n\n'
            else:
                # CGRAG mode - stream final answer after iteration
                session = _session_store.get_or_create(request.session_id)
                cgrag_result = await run_cgrag_loop(
                    question=request.question,
                    initial_context=initial_context,
                    session=session,
                    llm=self._llm,
                    graph=self._graph,
                    vectorstore=self._vectorstore,
                )
                # Stream the final answer token by token (simulated for non-streaming CGRAG)
                for char in cgrag_result.answer:
                    yield f'event: token\ndata: {json.dumps({"text": char})}\n\n'
                accumulated_response = cgrag_result.answer

        except Exception as e:
            yield f'event: error\ndata: {json.dumps({"message": str(e)})}\n\n'
            return

        # Extract citations and build final response
        answer = self._extract_answer(accumulated_response) if "<answer>" in accumulated_response else accumulated_response
        citations = self._extract_citations(accumulated_response, results) if "<citations>" in accumulated_response else self._fallback_citations(results[:5])

        session_id = None
        if not request.quick_mode:
            session = _session_store.get_or_create(request.session_id)
            session_id = session.id

        done_data = {
            "citations": [c.model_dump() for c in citations],
            "confidence": confidence.value,
            "session_id": session_id,
            "search_quality": {
                "semantic_searched": semantic_ok,
                "fts_searched": fts_ok,
                "results_found": len(results),
                "results_used": results_used,
            },
        }
        yield f'event: done\ndata: {json.dumps(done_data)}\n\n'
```

**Step 4: Run test to verify it passes**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_qa_api.py::test_ask_stream_returns_sse -v`

Expected: PASS

**Step 5: Run full test suite**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_qa_api.py tests/test_qa_service.py -v`

Expected: All tests PASS

**Step 6: Commit**

```bash
git add backend/src/oya/api/routers/qa.py backend/src/oya/qa/service.py backend/tests/test_qa_api.py
git commit -m "feat(qa): add SSE streaming endpoint for Q&A"
```

---

## Task 5: Add QA Settings Constants

**Files:**
- Modify: `frontend/src/config/qa.ts`

**Step 1: Add settings constants**

In `frontend/src/config/qa.ts`, add:

```typescript
// Q&A Settings Defaults
export const QA_DEFAULTS = {
  quickMode: true,
  temperature: 0.5,
  timeoutMinutes: 3,
}

export const QA_CONSTRAINTS = {
  temperature: { min: 0, max: 1, step: 0.1 },
  timeout: { min: 1, max: 5, step: 1 },
}

export const QA_STORAGE_KEY = 'oya-qa-settings'
```

**Step 2: Commit**

```bash
git add frontend/src/config/qa.ts
git commit -m "feat(config): add QA settings defaults and constraints"
```

---

## Task 6: Create QASettingsPopover Component

**Files:**
- Create: `frontend/src/components/QASettingsPopover.tsx`
- Test: `frontend/src/components/QASettingsPopover.test.tsx`

**Step 1: Write the failing test**

Create `frontend/src/components/QASettingsPopover.test.tsx`:

```typescript
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { QASettingsPopover } from './QASettingsPopover'
import { QA_DEFAULTS } from '../config/qa'

describe('QASettingsPopover', () => {
  const defaultSettings = { ...QA_DEFAULTS }
  const mockOnChange = vi.fn()

  it('renders gear icon button', () => {
    render(
      <QASettingsPopover settings={defaultSettings} onChange={mockOnChange} />
    )
    expect(screen.getByRole('button', { name: /settings/i })).toBeInTheDocument()
  })

  it('opens popover on click', () => {
    render(
      <QASettingsPopover settings={defaultSettings} onChange={mockOnChange} />
    )
    fireEvent.click(screen.getByRole('button', { name: /settings/i }))
    expect(screen.getByText('Answer Settings')).toBeInTheDocument()
  })

  it('calls onChange when quick mode toggled', () => {
    render(
      <QASettingsPopover settings={defaultSettings} onChange={mockOnChange} />
    )
    fireEvent.click(screen.getByRole('button', { name: /settings/i }))
    fireEvent.click(screen.getByLabelText(/thorough/i))
    expect(mockOnChange).toHaveBeenCalledWith(
      expect.objectContaining({ quickMode: false })
    )
  })
})
```

**Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- --run QASettingsPopover`

Expected: FAIL (module not found)

**Step 3: Write minimal implementation**

Create `frontend/src/components/QASettingsPopover.tsx`:

```typescript
import { useState, useRef, useEffect } from 'react'
import { QA_CONSTRAINTS } from '../config/qa'

export interface QASettings {
  quickMode: boolean
  temperature: number
  timeoutMinutes: number
}

interface QASettingsPopoverProps {
  settings: QASettings
  onChange: (settings: QASettings) => void
}

export function QASettingsPopover({ settings, onChange }: QASettingsPopoverProps) {
  const [isOpen, setIsOpen] = useState(false)
  const popoverRef = useRef<HTMLDivElement>(null)

  // Close on outside click
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (popoverRef.current && !popoverRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }
    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside)
      return () => document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [isOpen])

  const temperatureLabel = settings.temperature <= 0.3 ? 'Precise' : settings.temperature <= 0.6 ? 'Balanced' : 'Creative'

  return (
    <div className="relative" ref={popoverRef}>
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="p-2 text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
        aria-label="Answer settings"
      >
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
        </svg>
      </button>

      {isOpen && (
        <div className="absolute right-0 bottom-full mb-2 w-64 bg-white dark:bg-gray-800 rounded-lg shadow-lg border border-gray-200 dark:border-gray-700 z-50">
          <div className="p-3 border-b border-gray-200 dark:border-gray-700 flex justify-between items-center">
            <span className="font-medium text-gray-900 dark:text-white text-sm">Answer Settings</span>
            <button onClick={() => setIsOpen(false)} className="text-gray-400 hover:text-gray-600">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          <div className="p-3 space-y-4">
            {/* Mode Selection */}
            <div>
              <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-2">Mode</label>
              <div className="space-y-1">
                <label className="flex items-center cursor-pointer">
                  <input
                    type="radio"
                    name="mode"
                    checked={settings.quickMode}
                    onChange={() => onChange({ ...settings, quickMode: true })}
                    className="mr-2"
                  />
                  <span className="text-sm text-gray-700 dark:text-gray-300">Quick (~40s)</span>
                </label>
                <label className="flex items-center cursor-pointer">
                  <input
                    type="radio"
                    name="mode"
                    checked={!settings.quickMode}
                    onChange={() => onChange({ ...settings, quickMode: false })}
                    className="mr-2"
                    aria-label="Thorough mode"
                  />
                  <span className="text-sm text-gray-700 dark:text-gray-300">Thorough (~2min)</span>
                </label>
              </div>
            </div>

            {/* Temperature Slider */}
            <div>
              <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-2">
                Temperature <span className="text-gray-500">[{settings.temperature.toFixed(1)}]</span>
              </label>
              <input
                type="range"
                min={QA_CONSTRAINTS.temperature.min}
                max={QA_CONSTRAINTS.temperature.max}
                step={QA_CONSTRAINTS.temperature.step}
                value={settings.temperature}
                onChange={(e) => onChange({ ...settings, temperature: parseFloat(e.target.value) })}
                className="w-full"
              />
              <div className="flex justify-between text-xs text-gray-500">
                <span>Precise</span>
                <span>{temperatureLabel}</span>
                <span>Creative</span>
              </div>
            </div>

            {/* Timeout Slider */}
            <div>
              <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-2">
                Timeout <span className="text-gray-500">[{settings.timeoutMinutes}min]</span>
              </label>
              <input
                type="range"
                min={QA_CONSTRAINTS.timeout.min}
                max={QA_CONSTRAINTS.timeout.max}
                step={QA_CONSTRAINTS.timeout.step}
                value={settings.timeoutMinutes}
                onChange={(e) => onChange({ ...settings, timeoutMinutes: parseInt(e.target.value) })}
                className="w-full"
              />
              <div className="flex justify-between text-xs text-gray-500">
                <span>1min</span>
                <span>5min</span>
              </div>
            </div>

            {/* Reset Button */}
            <button
              onClick={() => onChange({ quickMode: true, temperature: 0.5, timeoutMinutes: 3 })}
              className="w-full text-xs text-blue-600 hover:text-blue-700 dark:text-blue-400"
            >
              Reset to defaults
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
```

**Step 4: Run test to verify it passes**

Run: `cd frontend && npm test -- --run QASettingsPopover`

Expected: PASS

**Step 5: Commit**

```bash
git add frontend/src/components/QASettingsPopover.tsx frontend/src/components/QASettingsPopover.test.tsx
git commit -m "feat(ui): add QASettingsPopover component"
```

---

## Task 7: Create useResizablePanel Hook

**Files:**
- Create: `frontend/src/hooks/useResizablePanel.ts`
- Test: `frontend/src/hooks/useResizablePanel.test.ts`

**Step 1: Write the failing test**

Create `frontend/src/hooks/useResizablePanel.test.ts`:

```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useResizablePanel } from './useResizablePanel'

describe('useResizablePanel', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('returns default width initially', () => {
    const { result } = renderHook(() =>
      useResizablePanel({
        side: 'left',
        defaultWidth: 256,
        minWidth: 180,
        maxWidth: 400,
        storageKey: 'test-width',
      })
    )
    expect(result.current.width).toBe(256)
  })

  it('loads width from localStorage', () => {
    localStorage.setItem('test-width', '300')
    const { result } = renderHook(() =>
      useResizablePanel({
        side: 'left',
        defaultWidth: 256,
        minWidth: 180,
        maxWidth: 400,
        storageKey: 'test-width',
      })
    )
    expect(result.current.width).toBe(300)
  })

  it('clamps width to min/max bounds', () => {
    localStorage.setItem('test-width', '999')
    const { result } = renderHook(() =>
      useResizablePanel({
        side: 'left',
        defaultWidth: 256,
        minWidth: 180,
        maxWidth: 400,
        storageKey: 'test-width',
      })
    )
    expect(result.current.width).toBe(400)
  })
})
```

**Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- --run useResizablePanel`

Expected: FAIL (module not found)

**Step 3: Write minimal implementation**

Create `frontend/src/hooks/useResizablePanel.ts`:

```typescript
import { useState, useCallback, useEffect } from 'react'

interface UseResizablePanelOptions {
  side: 'left' | 'right'
  defaultWidth: number
  minWidth: number
  maxWidth: number
  storageKey: string
}

interface UseResizablePanelResult {
  width: number
  isDragging: boolean
  handleMouseDown: (e: React.MouseEvent) => void
}

export function useResizablePanel({
  side,
  defaultWidth,
  minWidth,
  maxWidth,
  storageKey,
}: UseResizablePanelOptions): UseResizablePanelResult {
  const [width, setWidth] = useState(() => {
    const stored = localStorage.getItem(storageKey)
    if (stored) {
      const parsed = parseInt(stored, 10)
      if (!isNaN(parsed)) {
        return Math.min(maxWidth, Math.max(minWidth, parsed))
      }
    }
    return defaultWidth
  })
  const [isDragging, setIsDragging] = useState(false)

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    setIsDragging(true)
  }, [])

  useEffect(() => {
    if (!isDragging) return

    const handleMouseMove = (e: MouseEvent) => {
      let newWidth: number
      if (side === 'left') {
        newWidth = e.clientX
      } else {
        newWidth = window.innerWidth - e.clientX
      }
      newWidth = Math.min(maxWidth, Math.max(minWidth, newWidth))
      setWidth(newWidth)
    }

    const handleMouseUp = () => {
      setIsDragging(false)
      localStorage.setItem(storageKey, width.toString())
    }

    document.addEventListener('mousemove', handleMouseMove)
    document.addEventListener('mouseup', handleMouseUp)

    return () => {
      document.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseup', handleMouseUp)
    }
  }, [isDragging, side, minWidth, maxWidth, storageKey, width])

  // Persist on width change (debounced via mouseup)
  useEffect(() => {
    if (!isDragging) {
      localStorage.setItem(storageKey, width.toString())
    }
  }, [width, isDragging, storageKey])

  return { width, isDragging, handleMouseDown }
}
```

**Step 4: Run test to verify it passes**

Run: `cd frontend && npm test -- --run useResizablePanel`

Expected: PASS

**Step 5: Commit**

```bash
git add frontend/src/hooks/useResizablePanel.ts frontend/src/hooks/useResizablePanel.test.ts
git commit -m "feat(hooks): add useResizablePanel for draggable panel widths"
```

---

## Task 8: Update AskPanel with Streaming and Settings

**Files:**
- Modify: `frontend/src/components/AskPanel.tsx`
- Modify: `frontend/src/api/client.ts`
- Test: `frontend/src/components/AskPanel.test.tsx`

**Step 1: Add streaming API function**

In `frontend/src/api/client.ts`, add:

```typescript
export interface StreamCallbacks {
  onToken: (text: string) => void
  onStatus: (stage: string, pass: number) => void
  onDone: (data: {
    citations: Citation[]
    confidence: string
    session_id: string | null
    search_quality: SearchQuality
  }) => void
  onError: (message: string) => void
}

export async function askQuestionStream(
  request: {
    question: string
    session_id?: string | null
    quick_mode?: boolean
    temperature?: number
  },
  callbacks: StreamCallbacks,
  signal?: AbortSignal
): Promise<void> {
  const response = await fetch('/api/qa/ask/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
    signal,
  })

  if (!response.ok) {
    throw new Error(`HTTP error: ${response.status}`)
  }

  const reader = response.body?.getReader()
  if (!reader) throw new Error('No response body')

  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''

    let currentEvent = ''
    for (const line of lines) {
      if (line.startsWith('event: ')) {
        currentEvent = line.slice(7)
      } else if (line.startsWith('data: ')) {
        const data = JSON.parse(line.slice(6))
        switch (currentEvent) {
          case 'token':
            callbacks.onToken(data.text)
            break
          case 'status':
            callbacks.onStatus(data.stage, data.pass)
            break
          case 'done':
            callbacks.onDone(data)
            break
          case 'error':
            callbacks.onError(data.message)
            break
        }
      }
    }
  }
}
```

**Step 2: Update AskPanel component**

Replace `frontend/src/components/AskPanel.tsx`:

```typescript
import { useState, useRef, useEffect } from 'react'
import { Link } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { askQuestionStream } from '../api/client'
import { CONFIDENCE_COLORS } from '../config'
import { QA_DEFAULTS, QA_STORAGE_KEY } from '../config/qa'
import { QASettingsPopover, type QASettings } from './QASettingsPopover'
import type { Citation } from '../types'

interface QAMessage {
  question: string
  answer: string
  citations: Citation[]
  confidence: string
  isStreaming: boolean
}

interface AskPanelProps {
  isOpen: boolean
  onClose: () => void
}

export function AskPanel({ isOpen, onClose }: AskPanelProps) {
  const [question, setQuestion] = useState('')
  const [messages, setMessages] = useState<QAMessage[]>([])
  const [error, setError] = useState<string | null>(null)
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [settings, setSettings] = useState<QASettings>(() => {
    const stored = localStorage.getItem(QA_STORAGE_KEY)
    if (stored) {
      try {
        return { ...QA_DEFAULTS, ...JSON.parse(stored) }
      } catch {
        return QA_DEFAULTS
      }
    }
    return QA_DEFAULTS
  })
  const abortControllerRef = useRef<AbortController | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  // Persist settings
  useEffect(() => {
    localStorage.setItem(QA_STORAGE_KEY, JSON.stringify(settings))
  }, [settings])

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const isStreaming = messages.some((m) => m.isStreaming)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!question.trim() || isStreaming) return

    const currentQuestion = question.trim()
    setQuestion('')
    setError(null)

    // Add placeholder message
    const messageIndex = messages.length
    setMessages((prev) => [
      ...prev,
      { question: currentQuestion, answer: '', citations: [], confidence: '', isStreaming: true },
    ])

    // Set up abort controller with timeout
    abortControllerRef.current = new AbortController()
    const timeoutId = setTimeout(() => {
      abortControllerRef.current?.abort()
    }, settings.timeoutMinutes * 60 * 1000)

    try {
      await askQuestionStream(
        {
          question: currentQuestion,
          session_id: sessionId,
          quick_mode: settings.quickMode,
          temperature: settings.temperature,
        },
        {
          onToken: (text) => {
            setMessages((prev) => {
              const updated = [...prev]
              updated[messageIndex] = {
                ...updated[messageIndex],
                answer: updated[messageIndex].answer + text,
              }
              return updated
            })
          },
          onStatus: () => {
            // Could show status indicator if desired
          },
          onDone: (data) => {
            setMessages((prev) => {
              const updated = [...prev]
              updated[messageIndex] = {
                ...updated[messageIndex],
                citations: data.citations,
                confidence: data.confidence,
                isStreaming: false,
              }
              return updated
            })
            if (data.session_id) {
              setSessionId(data.session_id)
            }
          },
          onError: (message) => {
            setError(message)
            setMessages((prev) => {
              const updated = [...prev]
              updated[messageIndex] = { ...updated[messageIndex], isStreaming: false }
              return updated
            })
          },
        },
        abortControllerRef.current.signal
      )
    } catch (err) {
      if (err instanceof Error && err.name === 'AbortError') {
        setError('Request timed out')
      } else {
        setError(err instanceof Error ? err.message : 'Failed to get answer')
      }
      setMessages((prev) => {
        const updated = [...prev]
        if (updated[messageIndex]) {
          updated[messageIndex] = { ...updated[messageIndex], isStreaming: false }
        }
        return updated
      })
    } finally {
      clearTimeout(timeoutId)
      abortControllerRef.current = null
    }
  }

  const handleClearConversation = () => {
    setMessages([])
    setSessionId(null)
    setError(null)
  }

  const renderCitation = (citation: Citation, index: number) => (
    <Link
      key={index}
      to={citation.url}
      className="text-blue-600 hover:underline text-sm mr-2"
    >
      {citation.title}
    </Link>
  )

  if (!isOpen) return null

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="p-4 border-b border-gray-200 dark:border-gray-700 flex justify-between items-center">
        <h2 className="font-semibold text-gray-900 dark:text-white">Ask about this codebase</h2>
        <div className="flex items-center gap-2">
          {messages.length > 0 && (
            <button
              onClick={handleClearConversation}
              className="text-xs text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
            >
              Clear
            </button>
          )}
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && (
          <div className="text-center text-gray-500 dark:text-gray-400 text-sm py-8">
            <p>Ask any question about the codebase.</p>
            <p className="mt-2 text-xs">Answers are based on the generated documentation.</p>
          </div>
        )}

        {messages.map((msg, idx) => (
          <div key={idx} className="space-y-2">
            {/* Question */}
            <div className="bg-gray-100 dark:bg-gray-700 rounded-lg p-3">
              <p className="text-sm text-gray-900 dark:text-white">{msg.question}</p>
            </div>

            {/* Answer */}
            <div className="space-y-2">
              {msg.confidence && (
                <div className={`px-3 py-1 rounded text-xs ${CONFIDENCE_COLORS[msg.confidence] || ''}`}>
                  {msg.confidence} confidence
                </div>
              )}

              <div className="prose prose-sm dark:prose-invert max-w-none">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {msg.answer || (msg.isStreaming ? '...' : '')}
                </ReactMarkdown>
                {msg.isStreaming && <span className="animate-pulse">|</span>}
              </div>

              {msg.citations.length > 0 && !msg.isStreaming && (
                <div className="pt-2 border-t border-gray-200 dark:border-gray-700">
                  <span className="text-xs text-gray-500 mr-2">Sources:</span>
                  {msg.citations.map(renderCitation)}
                </div>
              )}
            </div>
          </div>
        ))}

        {error && (
          <div className="p-3 bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 rounded-lg text-sm">
            {error}
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <form onSubmit={handleSubmit} className="p-4 border-t border-gray-200 dark:border-gray-700">
        <div className="flex gap-2 items-center">
          <input
            type="text"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Ask a question..."
            className="flex-1 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
            disabled={isStreaming}
          />
          <QASettingsPopover settings={settings} onChange={setSettings} />
          <button
            type="submit"
            disabled={isStreaming || !question.trim()}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed text-sm"
          >
            {isStreaming ? '...' : 'Ask'}
          </button>
        </div>
      </form>
    </div>
  )
}
```

**Step 3: Run tests**

Run: `cd frontend && npm test -- --run`

Expected: All tests PASS

**Step 4: Commit**

```bash
git add frontend/src/components/AskPanel.tsx frontend/src/api/client.ts
git commit -m "feat(ui): update AskPanel with streaming, settings, and session support"
```

---

## Task 9: Update Layout with Resizable Sidebars

**Files:**
- Modify: `frontend/src/components/Layout.tsx`

**Step 1: Update Layout component**

In `frontend/src/components/Layout.tsx`, integrate resizable panels:

```typescript
import { useState, type ReactNode } from 'react'
import { Sidebar } from './Sidebar'
import { TopBar } from './TopBar'
import { RightSidebar } from './RightSidebar'
import { AskPanel } from './AskPanel'
import { NoteEditor } from './NoteEditor'
import { InterruptedGenerationBanner } from './InterruptedGenerationBanner'
import { useApp } from '../context/useApp'
import { useResizablePanel } from '../hooks/useResizablePanel'

interface LayoutProps {
  children: ReactNode
}

export function Layout({ children }: LayoutProps) {
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [rightSidebarOpen, setRightSidebarOpen] = useState(true)
  const { state, closeNoteEditor, refreshTree, setAskPanelOpen } = useApp()
  const { noteEditor, askPanelOpen } = state

  const leftPanel = useResizablePanel({
    side: 'left',
    defaultWidth: 256,
    minWidth: 180,
    maxWidth: 400,
    storageKey: 'oya-sidebar-left-width',
  })

  const rightPanel = useResizablePanel({
    side: 'right',
    defaultWidth: 350,
    minWidth: 280,
    maxWidth: 600,
    storageKey: 'oya-sidebar-right-width',
  })

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      <TopBar
        onToggleSidebar={() => setSidebarOpen(!sidebarOpen)}
        onToggleRightSidebar={() => setRightSidebarOpen(!rightSidebarOpen)}
        onToggleAskPanel={() => setAskPanelOpen(!askPanelOpen)}
        askPanelOpen={askPanelOpen}
      />

      <div className="pt-14">
        <InterruptedGenerationBanner />

        <div className="flex">
          {/* Left Sidebar */}
          {sidebarOpen && (
            <>
              <aside
                style={{ width: leftPanel.width }}
                className="fixed left-0 top-14 bottom-0 overflow-y-auto border-r border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800"
              >
                <Sidebar />
              </aside>
              {/* Left resize handle */}
              <div
                onMouseDown={leftPanel.handleMouseDown}
                className={`fixed top-14 bottom-0 w-1 cursor-col-resize hover:bg-blue-400 transition-colors ${
                  leftPanel.isDragging ? 'bg-blue-500' : 'bg-transparent hover:bg-blue-300'
                }`}
                style={{ left: leftPanel.width - 2 }}
              />
            </>
          )}

          {/* Main Content */}
          <main
            className="flex-1 min-h-[calc(100vh-3.5rem)]"
            style={{
              marginLeft: sidebarOpen ? leftPanel.width : 0,
              marginRight: askPanelOpen ? rightPanel.width : rightSidebarOpen ? 224 : 0,
            }}
          >
            <div className="max-w-4xl mx-auto px-6 py-8">{children}</div>
          </main>

          {/* Right Sidebar - TOC (when Ask Panel closed) */}
          {rightSidebarOpen && !askPanelOpen && (
            <aside className="w-56 fixed right-0 top-14 bottom-0 overflow-y-auto border-l border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800">
              <RightSidebar />
            </aside>
          )}

          {/* Ask Panel */}
          {askPanelOpen && (
            <>
              {/* Right resize handle */}
              <div
                onMouseDown={rightPanel.handleMouseDown}
                className={`fixed top-14 bottom-0 w-1 cursor-col-resize transition-colors ${
                  rightPanel.isDragging ? 'bg-blue-500' : 'bg-transparent hover:bg-blue-300'
                }`}
                style={{ right: rightPanel.width - 2 }}
              />
              <aside
                style={{ width: rightPanel.width }}
                className="fixed right-0 top-14 bottom-0 overflow-hidden border-l border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800"
              >
                <AskPanel isOpen={askPanelOpen} onClose={() => setAskPanelOpen(false)} />
              </aside>
            </>
          )}
        </div>
      </div>

      <NoteEditor
        isOpen={noteEditor.isOpen}
        onClose={closeNoteEditor}
        onNoteCreated={() => refreshTree()}
        defaultScope={noteEditor.defaultScope}
        defaultTarget={noteEditor.defaultTarget}
      />
    </div>
  )
}
```

**Step 2: Run tests**

Run: `cd frontend && npm test -- --run`

Expected: All tests PASS

**Step 3: Commit**

```bash
git add frontend/src/components/Layout.tsx
git commit -m "feat(ui): add resizable sidebars with draggable handles"
```

---

## Task 10: Final Integration Test

**Step 1: Run all backend tests**

Run: `cd backend && source .venv/bin/activate && pytest -v`

Expected: All tests PASS

**Step 2: Run all frontend tests**

Run: `cd frontend && npm test -- --run`

Expected: All tests PASS

**Step 3: Run type checks**

Run: `cd frontend && npm run build`

Expected: Build succeeds with no type errors

**Step 4: Manual smoke test**

1. Start backend: `cd backend && source .venv/bin/activate && WORKSPACE_PATH=. uvicorn oya.main:app --reload`
2. Start frontend: `cd frontend && npm run dev`
3. Open http://localhost:5173
4. Open Ask Panel
5. Verify settings gear icon works
6. Ask a question with Quick mode
7. Verify streaming tokens appear
8. Ask a follow-up question
9. Verify conversation persists
10. Resize left and right panels
11. Verify widths persist after refresh

**Step 5: Final commit**

```bash
git add -A
git commit -m "test: verify all integration points working"
```

---

## Summary

| Task | Description | Est. Time |
|------|-------------|-----------|
| 1 | Extend QARequest schema | 5 min |
| 2 | Add LLMClient streaming | 10 min |
| 3 | Add quick mode to QAService | 15 min |
| 4 | Add SSE streaming endpoint | 15 min |
| 5 | Add QA settings constants | 2 min |
| 6 | Create QASettingsPopover | 15 min |
| 7 | Create useResizablePanel hook | 10 min |
| 8 | Update AskPanel | 20 min |
| 9 | Update Layout | 10 min |
| 10 | Integration testing | 15 min |

**Total: ~2 hours**
