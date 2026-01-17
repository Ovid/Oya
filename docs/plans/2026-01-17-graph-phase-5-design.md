# Phase 5: Iterative Retrieval (CGRAG) - Design Document

> **Status:** Approved
> **Date:** 2026-01-17
> **Prerequisite:** Phase 4 (Graph-Augmented Q&A) complete

## Overview

**Goal:** Add iterative retrieval (CGRAG) to Q&A so the LLM can request missing code context across multiple passes, producing more complete and accurate answers.

CGRAG (Contextually-Guided RAG) mimics how developers read code - following references iteratively until understanding is complete. Instead of a single retrieval pass, the LLM identifies gaps in its context ("I see `verify_user` called but don't have its definition") and the system fetches missing pieces.

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Primary constraint | Response quality | Users need accurate understanding, not quick approximations |
| Iteration limit | LLM-controlled, max 3 passes | Smart stopping with safety cap; research shows diminishing returns after 2-3 iterations |
| Gap detection | Explicit LLM prompt | LLM understands context better than parsing heuristics; can identify semantic gaps |
| Trigger condition | Always multi-pass | Consistent quality; no risk of misclassifying complex questions |
| Loop avoidance | "Not found" escalation | If code doesn't exist, stop iterating; handles stuck states gracefully |
| Caching | Session-level | Follow-up questions benefit from previous context |

## High-Level Flow

```
User Question
     │
     ▼
Pass 1: Vector search + graph expansion (Phase 4)
     │
     ▼
LLM generates answer + identifies gaps
     │
     ▼
[If gaps AND pass < 3 AND not stuck]
     │
     ▼
Pass 2: Targeted retrieval for missing items
     │
     ▼
LLM refines answer + identifies remaining gaps
     │
     ▼
[Repeat until done or max passes]
     │
     ▼
Final Answer
```

## The Iteration Loop

### Core Algorithm

```python
def ask_with_cgrag(question: str, session: Session) -> Answer:
    context = session.get_cached_context()  # From previous questions
    not_found = set()

    for pass_num in range(1, MAX_PASSES + 1):  # MAX_PASSES = 3
        # Pass 1: Full retrieval (vector + graph)
        # Pass 2+: Targeted retrieval for gaps only
        if pass_num == 1:
            new_context = full_retrieval(question)
        else:
            new_context = targeted_retrieval(gaps, not_found)

        context = merge_context(context, new_context)

        # Ask LLM for answer + gaps
        answer, gaps = llm_answer_and_identify_gaps(question, context)

        # Check termination conditions
        if not gaps:
            break  # LLM satisfied
        if all(g in not_found for g in gaps):
            break  # Stuck - everything requested was already not found

        # Track what we couldn't find this pass
        for gap in gaps:
            if gap not in context:
                not_found.add(gap)

    session.cache_context(context)  # For follow-up questions
    return answer
```

### Termination Conditions

In priority order:
1. **LLM returns no gaps** → done, sufficient context
2. **All requested gaps were previously "not found"** → stuck, answer with available context
3. **Reached max passes (3)** → forced stop, answer with available context

### Pass Types

- **Pass 1:** Same as Phase 4 - vector search → graph expansion → format context
- **Pass 2+:** Targeted - search specifically for the symbols/files the LLM requested

## Gap Detection Prompt

The LLM answers the question AND identifies missing context in a single call:

```
You are answering a question about a codebase. You have been given some context,
but it may be incomplete.

## Question
{question}

## Available Context
{context}

## Instructions
1. Answer the question as best you can with the available context
2. If your answer would be MORE COMPLETE with additional code, list what's missing
3. Format your response as:

ANSWER:
[Your answer here]

MISSING (or "NONE" if nothing needed):
- function_name in path/to/file.py
- ClassName in some/module.py
- the file that handles X
```

### Response Parsing

- Split on `MISSING:` to extract gaps section
- If "NONE" → no gaps, stop iterating
- Otherwise, extract each line as a retrieval target
- Fuzzy requests get vector-searched; specific ones get graph-looked-up

## Targeted Retrieval

In passes 2+, we find specific things the LLM requested:

```python
def targeted_retrieval(gaps: list[str], not_found: set[str]) -> Context:
    results = []

    for gap in gaps:
        if gap in not_found:
            continue  # Already failed to find this

        # Try specific lookup first (fast, exact)
        if looks_like_specific(gap):  # "function_name in file.py"
            result = graph_lookup(gap)  # Search graph nodes directly
            if result:
                results.append(result)
                continue

        # Fall back to semantic search (slower, fuzzy)
        result = vector_search(gap, top_k=3)
        if result:
            results.extend(result)
        # If nothing found, gap stays unfulfilled (tracked by caller)

    return merge_and_dedupe(results)
```

### Specific vs Fuzzy Detection

- Contains `::` or "in `path`" → specific (graph lookup)
- Contains "function", "class", "method" + name → specific
- Everything else → fuzzy (vector search)

### Graph Lookup

- Search node names for exact/partial match
- If found, return node + 1-hop neighborhood (provides immediate context)

### Vector Search for Gaps

- Use gap text as query
- Lower top_k (3 vs 10) since looking for something specific
- Still apply graph expansion to results

## Session Caching

Session caching remembers retrieved context across questions in a conversation.

### What We Cache

- Retrieved code snippets (node IDs + content)
- The subgraph of traversed relationships
- "Not found" set (avoid re-searching for missing items)

### What We Don't Cache

- LLM answers (user might want different phrasing)
- The question itself

### Session Structure

```python
@dataclass
class CGRAGSession:
    id: str
    cached_nodes: dict[str, Node]      # node_id → node data
    cached_subgraph: Subgraph          # accumulated relationships
    not_found: set[str]                # gaps we failed to retrieve
    created_at: datetime
    last_accessed: datetime
```

### Session Lifecycle

- Created on first Q&A request (or explicit session start)
- Session ID passed in request header or body
- Expires after 30 minutes of inactivity
- User can start fresh session anytime

### Cache Size Limit

- Cap at ~50 nodes to prevent context explosion
- Evict oldest nodes when limit reached (LRU)

## Integration with Existing Q&A

### Current Phase 4 Flow

```
QAService.ask()
  → search() (vector + FTS)
  → _build_graph_context() (graph expansion)
  → LLM.generate() (single call)
  → return QAResponse
```

### New Phase 5 Flow

```
QAService.ask()
  → _ask_with_cgrag()        # Replaces single-pass logic
      → Pass 1: search() + _build_graph_context()
      → LLM call with gap detection prompt
      → [Loop: targeted_retrieval() + LLM call]
  → return QAResponse
```

### New/Modified Files

| File | Change |
|------|--------|
| `qa/service.py` | Add `_ask_with_cgrag()` method, modify `ask()` to use it |
| `qa/cgrag.py` | **NEW:** Core CGRAG loop, gap parsing, targeted retrieval |
| `qa/session.py` | **NEW:** `CGRAGSession` class, session store |
| `qa/schemas.py` | Add `session_id` to `QARequest`, iteration metadata to `QAResponse` |
| `api/routers/qa.py` | Wire session management |
| `generation/prompts.py` | Add gap detection prompt template |
| `constants/qa.py` | Add `CGRAG_MAX_PASSES`, `CGRAG_SESSION_TTL`, etc. |

### Backward Compatibility

- If no session_id provided → create ephemeral session (single-question)
- Existing API contract unchanged, just richer responses

## Response Metadata

### Updated QAResponse Schema

```python
class CGRAGMetadata(BaseModel):
    """Metadata about the iterative retrieval process."""
    passes_used: int                    # 1-3
    gaps_identified: list[str]          # What LLM asked for
    gaps_resolved: list[str]            # What we found
    gaps_unresolved: list[str]          # What we couldn't find
    session_id: str | None              # For follow-up questions
    context_from_cache: bool            # Whether session cache was used

class QAResponse(BaseModel):
    answer: str
    citations: list[Citation]
    confidence: ConfidenceLevel
    disclaimer: str
    search_quality: SearchQuality
    cgrag: CGRAGMetadata | None         # None if CGRAG disabled
```

### Why Expose This

- **Transparency:** User sees "2 passes, found 3/4 requested items"
- **Debugging:** If answer is poor, user can see what was missing
- **Trust:** `gaps_unresolved` explains limitations honestly

## Constants

```python
# backend/src/oya/constants/qa.py

# CGRAG (Phase 5)
CGRAG_MAX_PASSES = 3
CGRAG_SESSION_TTL_MINUTES = 30
CGRAG_SESSION_MAX_NODES = 50
CGRAG_TARGETED_TOP_K = 3
```

## Future Considerations

- **Frontend UX:** Show "Retrieving additional context..." during iteration
- **Streaming:** Stream partial answers as passes complete
- **Analytics:** Track pass counts, gap resolution rates to tune parameters
- **User control:** "Deep analysis" toggle for users who want to opt out of CGRAG for simple questions
