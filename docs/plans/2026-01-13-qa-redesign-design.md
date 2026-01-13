# Q&A System Redesign

## Overview

Redesign the Q&A feature to remove the confusing "evidence-gated" vs "loose mode" distinction, add confidence indicators, make citations clickable, and improve the UI with a right-side panel (inspired by DeepWiki).

## Goals

1. Single unified behavior - always answer questions
2. Traffic-light confidence indicator (High/Medium/Low) instead of binary gating
3. Citations link to wiki pages
4. Right-side chat panel replacing bottom dock

## API Changes

### Request (simplified)

Remove the `mode` field entirely:

```python
class QARequest(BaseModel):
    question: str
    context: dict[str, Any] | None = None
```

### Response (updated)

Replace `evidence_sufficient: bool` with `confidence: ConfidenceLevel`:

```python
class ConfidenceLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class QAResponse(BaseModel):
    answer: str  # Always populated
    citations: list[Citation]
    confidence: ConfidenceLevel
    disclaimer: str
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
