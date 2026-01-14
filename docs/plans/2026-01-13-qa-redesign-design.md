# Q&A System Redesign

## Overview

Redesign the Q&A feature to remove the confusing "evidence-gated" vs "loose mode" distinction, add confidence indicators, make citations clickable, improve the UI with a right-side panel, and fix underlying technical issues identified in `docs/notes/ai-questions-feature.md`.

## Goals

1. Single unified behavior - always answer questions
2. Traffic-light confidence indicator (High/Medium/Low) instead of binary gating
3. Citations link to wiki pages
4. Right-side chat panel replacing bottom dock
5. Fix technical debt: token budgeting, structured citations, error handling

## API Changes

### Request (simplified)

Remove `mode` and unused `context` fields:

```python
class QARequest(BaseModel):
    question: str
    # mode field removed - always answer
    # context field removed - was never implemented
```

### Response (updated)

Replace `evidence_sufficient: bool` with `confidence: ConfidenceLevel`, add `search_quality`:

```python
class ConfidenceLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class SearchQuality(BaseModel):
    """Transparency about search execution."""
    semantic_searched: bool  # Did vector search succeed?
    fts_searched: bool       # Did FTS search succeed?
    results_found: int       # Total results before dedup
    results_used: int        # Results after dedup, within token budget

class QAResponse(BaseModel):
    answer: str  # Always populated
    citations: list[Citation]
    confidence: ConfidenceLevel
    disclaimer: str
    search_quality: SearchQuality  # Surface any search degradation
```

### Citation (add URL)

```python
class Citation(BaseModel):
    path: str      # Wiki-relative: "files/src_oya_main-py.md"
    title: str
    lines: str | None
    url: str       # Frontend route: "/files/src_oya_main-py"
```

## Confidence Calculation

```python
def _calculate_confidence(self, results: list[dict]) -> ConfidenceLevel:
    if not results:
        return ConfidenceLevel.LOW

    # Count results with good relevance (distance < 0.5)
    strong_matches = sum(1 for r in results if r.get("distance", 1.0) < 0.5)

    # Check best result quality
    best_distance = min(r.get("distance", 1.0) for r in results)

    if strong_matches >= 3 and best_distance < 0.3:
        return ConfidenceLevel.HIGH
    elif strong_matches >= 1 and best_distance < 0.6:
        return ConfidenceLevel.MEDIUM
    else:
        return ConfidenceLevel.LOW
```

**Thresholds:**
- HIGH: 3+ strong matches AND best result < 0.3 distance
- MEDIUM: 1+ decent match AND best result < 0.6 distance
- LOW: Everything else

**Disclaimer text:**
- HIGH: "Based on strong evidence from the codebase."
- MEDIUM: "Based on partial evidence. Verify against source code."
- LOW: "Limited evidence found. This answer may be speculative."

## Citation URL Mapping

```python
def _path_to_url(self, wiki_path: str) -> str:
    route = wiki_path.removesuffix(".md")

    if route == "overview":
        return "/"
    elif route == "architecture":
        return "/architecture"
    else:
        return f"/{route}"
```

Examples:
- `files/src_oya_main-py.md` → `/files/src_oya_main-py`
- `directories/backend_src.md` → `/directories/backend_src`
- `overview.md` → `/`

## UI Layout

```
┌─────────────────────────────────────────────────────────────────────┐
│ TopBar                                              [Ask toggle]    │
├──────────┬────────────────────────────────────┬─────────────────────┤
│          │                                    │                     │
│ Sidebar  │     Wiki Content                   │   AskPanel          │
│ (nav)    │     (adjusts width)                │   (~350px)          │
│          │                                    │                     │
│          │                                    │  ┌───────────────┐  │
│          │                                    │  │ Q&A history   │  │
│          │                                    │  │ (scrollable)  │  │
│          │                                    │  │               │  │
│          │                                    │  ├───────────────┤  │
│          │                                    │  │ [Input box]   │  │
│          │                                    │  └───────────────┘  │
└──────────┴────────────────────────────────────┴─────────────────────┘
```

**AskPanel behavior:**
- Collapsible via toggle button in TopBar
- State persisted in localStorage
- Session-based conversation history (not persisted to disk)
- Clicking a citation navigates to that wiki page and closes panel

**Confidence display:**
- Colored banner above each answer
- GREEN for HIGH, YELLOW for MEDIUM, RED for LOW
- Same answer format regardless of confidence level

## Files to Change

### Backend

| File | Change |
|------|--------|
| `backend/src/oya/qa/schemas.py` | Remove QAMode enum, add ConfidenceLevel enum, add `url` field to Citation, replace `evidence_sufficient` with `confidence` |
| `backend/src/oya/qa/service.py` | Remove mode logic, add `_calculate_confidence()`, add `_path_to_url()`, always generate answer |
| `backend/src/oya/api/routers/qa.py` | Remove mode parameter handling |

### Frontend

| File | Change |
|------|--------|
| `frontend/src/components/QADock.tsx` | DELETE - replaced by AskPanel |
| `frontend/src/components/AskPanel.tsx` | NEW - right sidebar with chat history, input, confidence banners, clickable citations |
| `frontend/src/components/Layout.tsx` | Add AskPanel, make content width responsive to panel state |
| `frontend/src/components/TopBar.tsx` | Add toggle button for AskPanel |
| `frontend/src/types/index.ts` | Remove QAMode, add ConfidenceLevel, update Citation type |
| `frontend/src/api/client.ts` | Remove mode from askQuestion() |
| `frontend/src/context/AppContext.tsx` | Add askPanelOpen state with localStorage persistence |

## What Gets Removed

- `QAMode` enum (backend and frontend)
- Mode toggle buttons in UI
- "Switch to loose mode" messaging
- `evidence_sufficient` boolean field
- Empty answer responses (we always answer now)
- Bottom dock UI pattern
- Unused `context` parameter

---

## Implementation Phases

### Phase 1: Quick Wins

**1.1 Lower temperature for factual Q&A**

Current: `temperature=0.5` in `service.py:306`

Change to `temperature=0.2` for more deterministic, factual answers.

**1.2 Remove unused context parameter**

The `context` parameter in `QARequest` is stubbed out and does nothing (`service.py:74-77`). Remove it from the API contract.

**1.3 Remove mode parameter and enum**

Delete `QAMode` enum, remove `mode` from request, always generate an answer.

---

### Phase 2: Token Budget Management

**Problem:** Current code truncates each result to 2000 characters (`service.py:181`) with no consideration of:
- Actual token count (chars ≠ tokens)
- Total context window limits
- Cutting mid-sentence

**Solution:** Use `estimate_tokens()` from `generation/chunking.py` for proper budgeting.

```python
from oya.generation.chunking import estimate_tokens

# Token budget for context (leave room for system prompt + response)
MAX_CONTEXT_TOKENS = 6000  # Configurable based on model

def _build_context_prompt(self, question: str, results: list[dict]) -> tuple[str, int]:
    """Build prompt with token-aware truncation.

    Returns:
        Tuple of (prompt, results_used_count)
    """
    context_parts = []
    total_tokens = 0
    results_used = 0

    for r in results:
        content = r.get("content", "")

        # Truncate at sentence boundary if needed
        content = self._truncate_at_sentence(content, max_tokens=1500)

        part = f"[{r.get('type', 'wiki').upper()}] {r.get('path', 'unknown')}\n{content}"
        part_tokens = estimate_tokens(part)

        if total_tokens + part_tokens > MAX_CONTEXT_TOKENS:
            break  # Stop adding results

        context_parts.append(part)
        total_tokens += part_tokens
        results_used += 1

    context_str = "\n\n---\n\n".join(context_parts)
    prompt = f"Based on the following context...\n\nCONTEXT:\n{context_str}\n\nQUESTION: {question}"

    return prompt, results_used

def _truncate_at_sentence(self, text: str, max_tokens: int) -> str:
    """Truncate text at sentence boundary within token limit."""
    if estimate_tokens(text) <= max_tokens:
        return text

    sentences = text.replace('\n', ' ').split('. ')
    result = []
    for sentence in sentences:
        candidate = '. '.join(result + [sentence])
        if estimate_tokens(candidate) > max_tokens:
            break
        result.append(sentence)

    return '. '.join(result) + ('.' if result else '')
```

---

### Phase 3: Search Quality & Error Handling

**Problem:** Search failures are silent (`service.py:104-106`, `service.py:136-138`). Users don't know if their search was degraded.

**Solution:** Track and expose search quality metrics.

```python
async def search(self, query: str, limit: int = 10) -> tuple[list[dict], SearchQuality]:
    """Perform hybrid search, returning results and quality metrics."""
    results = []
    seen_paths = set()
    semantic_ok = False
    fts_ok = False

    # Semantic search
    try:
        semantic_results = self._vectorstore.query(...)
        semantic_ok = True
        # ... process results
    except Exception as e:
        logger.warning(f"Semantic search failed: {e}")

    # FTS search
    try:
        # ... FTS query
        fts_ok = True
    except Exception as e:
        logger.warning(f"FTS search failed: {e}")

    results_found = len(results)

    # Deduplicate and sort
    results = self._deduplicate_results(results)

    quality = SearchQuality(
        semantic_searched=semantic_ok,
        fts_searched=fts_ok,
        results_found=results_found,
        results_used=0,  # Set later after token budgeting
    )

    return results[:limit], quality
```

**Frontend:** Show degraded search warning if `!semantic_searched || !fts_searched`:

```tsx
{!response.search_quality.semantic_searched && (
  <span className="text-xs text-yellow-600">Vector search unavailable</span>
)}
```

---

### Phase 4: Content Deduplication

**Problem:** Same content can appear from multiple sources (e.g., code file and its wiki page), wasting context tokens.

**Solution:** Deduplicate by content similarity, not just path.

```python
def _deduplicate_results(self, results: list[dict]) -> list[dict]:
    """Remove duplicate/near-duplicate content."""
    seen_content_hashes = set()
    deduplicated = []

    for r in results:
        content = r.get("content", "")
        # Simple hash of first 500 chars (covers most duplicates)
        content_hash = hash(content[:500].strip().lower())

        if content_hash not in seen_content_hashes:
            seen_content_hashes.add(content_hash)
            deduplicated.append(r)

    return deduplicated
```

---

### Phase 5: Structured Citation Extraction

**Problem:** Current regex parsing (`service.py:196-256`) is fragile:
- Expects specific `[CITATIONS]` format
- Fails on whitespace variations
- Falls back to top 3 results without validation

**Solution:** Request structured JSON output from LLM.

**Updated system prompt:**

```python
QA_SYSTEM_PROMPT = """You are a helpful assistant that answers questions about a codebase.

When answering:
1. Be concise and accurate
2. Base your answer only on the provided context
3. After your answer, output a JSON block with citations

Format your response as:
<answer>
Your answer here...
</answer>

<citations>
[
  {"path": "files/example-py.md", "relevant_text": "brief quote showing relevance"},
  {"path": "directories/src.md", "relevant_text": "another brief quote"}
]
</citations>

Only cite sources that directly support your answer. Include 1-5 citations.
"""
```

**Updated extraction:**

```python
import json

def _extract_citations(self, response: str, results: list[dict]) -> list[Citation]:
    """Extract citations from structured JSON output."""
    citations = []

    # Parse JSON citations block
    match = re.search(r'<citations>\s*(\[.*?\])\s*</citations>', response, re.DOTALL)
    if not match:
        # Fallback: use top 3 results
        return self._fallback_citations(results[:3])

    try:
        raw_citations = json.loads(match.group(1))
    except json.JSONDecodeError:
        return self._fallback_citations(results[:3])

    # Validate each citation exists in search results
    result_paths = {r.get("path") for r in results}

    for cite in raw_citations:
        path = cite.get("path", "")
        if path in result_paths:  # Only include validated citations
            citations.append(Citation(
                path=path,
                title=self._get_title_for_path(path, results),
                lines=None,
                url=self._path_to_url(path),
            ))

    return citations if citations else self._fallback_citations(results[:3])

def _extract_answer(self, response: str) -> str:
    """Extract answer text from structured response."""
    match = re.search(r'<answer>\s*(.*?)\s*</answer>', response, re.DOTALL)
    return match.group(1).strip() if match else response.strip()
```

**Benefits:**
- Explicit structure is easier to parse than markdown conventions
- Citations are validated against actual search results
- `relevant_text` field helps verify the LLM isn't hallucinating

---

## Updated Files to Change

### Backend

| File | Phase | Change |
|------|-------|--------|
| `backend/src/oya/qa/schemas.py` | 1, 3 | Remove QAMode, add ConfidenceLevel, add SearchQuality, add url to Citation, remove context from request |
| `backend/src/oya/qa/service.py` | 1-5 | All technical improvements: temperature, token budgeting, dedup, search quality tracking, structured citations |
| `backend/src/oya/api/routers/qa.py` | 1 | Simplify endpoint |

### Frontend

| File | Phase | Change |
|------|-------|--------|
| `frontend/src/components/QADock.tsx` | 1 | DELETE |
| `frontend/src/components/AskPanel.tsx` | 1, 3 | NEW - includes search quality indicator |
| `frontend/src/components/Layout.tsx` | 1 | Add AskPanel |
| `frontend/src/components/TopBar.tsx` | 1 | Add toggle |
| `frontend/src/types/index.ts` | 1, 3 | Update types |
| `frontend/src/api/client.ts` | 1 | Simplify API call |
| `frontend/src/context/AppContext.tsx` | 1 | Add panel state |

---

## Summary of Technical Fixes

| Issue | Fix | Phase |
|-------|-----|-------|
| Temperature too high (0.5) | Lower to 0.2 | 1 |
| Unused context parameter | Remove from API | 1 |
| Mode complexity | Remove entirely | 1 |
| Hard 2000 char truncation | Token budgeting with estimate_tokens() | 2 |
| Mid-sentence truncation | Truncate at sentence boundaries | 2 |
| No context window management | Track total tokens, stop when budget exceeded | 2 |
| Silent search failures | Track and expose SearchQuality | 3 |
| No content deduplication | Hash-based dedup before token budgeting | 4 |
| Fragile regex citation parsing | Structured JSON output with validation | 5 |
| Unvalidated citations | Check citations exist in search results | 5 |
