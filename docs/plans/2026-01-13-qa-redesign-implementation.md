# Q&A Redesign Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Redesign Q&A to remove modes, add confidence indicators, clickable citations, right-side panel UI, and fix technical debt (token budgeting, structured citations, error handling).

**Architecture:** Backend simplifies QAService to always answer with confidence levels instead of gating. Frontend replaces bottom dock with right-side AskPanel. Five phases: quick wins → token budgeting → search quality → deduplication → structured citations.

**Tech Stack:** Python/FastAPI (backend), React/TypeScript/Tailwind (frontend), ChromaDB, SQLite FTS5

---

## Phase 1: Backend Quick Wins

### Task 1.1: Add ConfidenceLevel and SearchQuality schemas

**Files:**
- Modify: `backend/src/oya/qa/schemas.py`
- Test: `backend/tests/test_qa_service.py`

**Step 1: Write the test for new enums and schemas**

```python
# Add to backend/tests/test_qa_service.py (or create test_qa_schemas.py)

def test_confidence_level_values():
    """ConfidenceLevel enum has expected values."""
    from oya.qa.schemas import ConfidenceLevel
    assert ConfidenceLevel.HIGH == "high"
    assert ConfidenceLevel.MEDIUM == "medium"
    assert ConfidenceLevel.LOW == "low"


def test_search_quality_schema():
    """SearchQuality tracks search execution metrics."""
    from oya.qa.schemas import SearchQuality
    quality = SearchQuality(
        semantic_searched=True,
        fts_searched=False,
        results_found=10,
        results_used=5,
    )
    assert quality.semantic_searched is True
    assert quality.fts_searched is False
    assert quality.results_found == 10
    assert quality.results_used == 5
```

**Step 2: Run test to verify it fails**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_qa_service.py::test_confidence_level_values tests/test_qa_service.py::test_search_quality_schema -v`

Expected: FAIL with ImportError

**Step 3: Add ConfidenceLevel and SearchQuality to schemas.py**

```python
# Add after existing imports in backend/src/oya/qa/schemas.py

class ConfidenceLevel(str, Enum):
    """Confidence level for Q&A answers."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class SearchQuality(BaseModel):
    """Transparency about search execution."""

    semantic_searched: bool = Field(..., description="Did vector search succeed?")
    fts_searched: bool = Field(..., description="Did FTS search succeed?")
    results_found: int = Field(..., description="Total results before dedup")
    results_used: int = Field(..., description="Results after dedup, within token budget")
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_qa_service.py::test_confidence_level_values tests/test_qa_service.py::test_search_quality_schema -v`

Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/oya/qa/schemas.py backend/tests/test_qa_service.py
git commit -m "feat(qa): add ConfidenceLevel enum and SearchQuality schema"
```

---

### Task 1.2: Update QARequest and QAResponse schemas

**Files:**
- Modify: `backend/src/oya/qa/schemas.py`
- Test: `backend/tests/test_qa_service.py`

**Step 1: Write the test for updated schemas**

```python
def test_qa_request_no_mode_or_context():
    """QARequest only has question field."""
    from oya.qa.schemas import QARequest
    request = QARequest(question="How does auth work?")
    assert request.question == "How does auth work?"
    # Verify mode and context don't exist
    assert not hasattr(request, 'mode')
    assert not hasattr(request, 'context')


def test_qa_response_has_confidence_and_search_quality():
    """QAResponse uses confidence instead of evidence_sufficient."""
    from oya.qa.schemas import QAResponse, ConfidenceLevel, SearchQuality, Citation
    response = QAResponse(
        answer="Auth uses JWT tokens.",
        citations=[],
        confidence=ConfidenceLevel.HIGH,
        disclaimer="Based on strong evidence.",
        search_quality=SearchQuality(
            semantic_searched=True,
            fts_searched=True,
            results_found=5,
            results_used=3,
        ),
    )
    assert response.confidence == ConfidenceLevel.HIGH
    assert response.search_quality.results_used == 3
    assert not hasattr(response, 'evidence_sufficient')
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_qa_service.py::test_qa_request_no_mode_or_context tests/test_qa_service.py::test_qa_response_has_confidence_and_search_quality -v`

Expected: FAIL (mode/context still exist, evidence_sufficient exists)

**Step 3: Update QARequest and QAResponse**

```python
# Replace existing QARequest in schemas.py

class QARequest(BaseModel):
    """Request for Q&A endpoint."""

    question: str = Field(..., min_length=1, description="The question to answer")


# Replace existing QAResponse in schemas.py

class QAResponse(BaseModel):
    """Response from Q&A endpoint."""

    answer: str = Field(..., description="The generated answer")
    citations: list[Citation] = Field(
        default_factory=list,
        description="Citations referenced in the answer",
    )
    confidence: ConfidenceLevel = Field(
        ...,
        description="Confidence level: high, medium, or low",
    )
    disclaimer: str = Field(
        ...,
        description="Disclaimer about AI-generated content",
    )
    search_quality: SearchQuality = Field(
        ...,
        description="Metrics about search execution",
    )
```

**Step 4: Remove QAMode enum**

Delete the `QAMode` class entirely from schemas.py.

**Step 5: Run test to verify it passes**

Run: `pytest tests/test_qa_service.py::test_qa_request_no_mode_or_context tests/test_qa_service.py::test_qa_response_has_confidence_and_search_quality -v`

Expected: PASS

**Step 6: Commit**

```bash
git add backend/src/oya/qa/schemas.py backend/tests/test_qa_service.py
git commit -m "feat(qa): update QARequest/QAResponse, remove QAMode"
```

---

### Task 1.3: Add url field to Citation schema

**Files:**
- Modify: `backend/src/oya/qa/schemas.py`
- Test: `backend/tests/test_qa_service.py`

**Step 1: Write the test**

```python
def test_citation_has_url_field():
    """Citation includes url for frontend routing."""
    from oya.qa.schemas import Citation
    citation = Citation(
        path="files/src_main-py.md",
        title="Main Module",
        lines="10-20",
        url="/files/src_main-py",
    )
    assert citation.url == "/files/src_main-py"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_qa_service.py::test_citation_has_url_field -v`

Expected: FAIL with validation error (url not defined)

**Step 3: Add url field to Citation**

```python
# Update Citation class in schemas.py

class Citation(BaseModel):
    """Citation reference in an answer."""

    path: str = Field(..., description="Wiki-relative path of the cited source")
    title: str = Field(..., description="Display title for the citation")
    lines: str | None = Field(None, description="Line range if applicable (e.g., '10-20')")
    url: str = Field(..., description="Frontend route (e.g., '/files/src_main-py')")
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_qa_service.py::test_citation_has_url_field -v`

Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/oya/qa/schemas.py backend/tests/test_qa_service.py
git commit -m "feat(qa): add url field to Citation for frontend routing"
```

---

### Task 1.4: Add confidence calculation to QAService

**Files:**
- Modify: `backend/src/oya/qa/service.py`
- Test: `backend/tests/test_qa_service.py`

**Step 1: Write tests for confidence calculation**

```python
def test_calculate_confidence_high():
    """HIGH confidence requires 3+ strong matches and best < 0.3."""
    from oya.qa.service import QAService
    from oya.qa.schemas import ConfidenceLevel

    # Mock service (we only need the method)
    service = QAService.__new__(QAService)

    results = [
        {"distance": 0.2},  # strong
        {"distance": 0.3},  # strong
        {"distance": 0.4},  # strong
        {"distance": 0.7},
    ]
    assert service._calculate_confidence(results) == ConfidenceLevel.HIGH


def test_calculate_confidence_medium():
    """MEDIUM confidence requires 1+ decent match and best < 0.6."""
    from oya.qa.service import QAService
    from oya.qa.schemas import ConfidenceLevel

    service = QAService.__new__(QAService)

    results = [
        {"distance": 0.4},  # decent
        {"distance": 0.7},
        {"distance": 0.8},
    ]
    assert service._calculate_confidence(results) == ConfidenceLevel.MEDIUM


def test_calculate_confidence_low():
    """LOW confidence when no good matches."""
    from oya.qa.service import QAService
    from oya.qa.schemas import ConfidenceLevel

    service = QAService.__new__(QAService)

    results = [
        {"distance": 0.7},
        {"distance": 0.9},
    ]
    assert service._calculate_confidence(results) == ConfidenceLevel.LOW


def test_calculate_confidence_empty():
    """LOW confidence with no results."""
    from oya.qa.service import QAService
    from oya.qa.schemas import ConfidenceLevel

    service = QAService.__new__(QAService)
    assert service._calculate_confidence([]) == ConfidenceLevel.LOW
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_qa_service.py -k "calculate_confidence" -v`

Expected: FAIL with AttributeError

**Step 3: Add _calculate_confidence method**

```python
# Add to QAService class in service.py

def _calculate_confidence(self, results: list[dict[str, Any]]) -> ConfidenceLevel:
    """Calculate confidence level from search results.

    Args:
        results: Search results with distance scores.

    Returns:
        HIGH if 3+ strong matches and best < 0.3
        MEDIUM if 1+ decent match and best < 0.6
        LOW otherwise
    """
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

Also add import at top of service.py:
```python
from oya.qa.schemas import Citation, ConfidenceLevel, QARequest, QAResponse, SearchQuality
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_qa_service.py -k "calculate_confidence" -v`

Expected: PASS (4 tests)

**Step 5: Commit**

```bash
git add backend/src/oya/qa/service.py backend/tests/test_qa_service.py
git commit -m "feat(qa): add confidence calculation based on search results"
```

---

### Task 1.5: Add path_to_url helper

**Files:**
- Modify: `backend/src/oya/qa/service.py`
- Test: `backend/tests/test_qa_service.py`

**Step 1: Write tests**

```python
def test_path_to_url_files():
    """File paths convert to /files/slug route."""
    from oya.qa.service import QAService
    service = QAService.__new__(QAService)

    assert service._path_to_url("files/src_main-py.md") == "/files/src_main-py"


def test_path_to_url_directories():
    """Directory paths convert to /directories/slug route."""
    from oya.qa.service import QAService
    service = QAService.__new__(QAService)

    assert service._path_to_url("directories/backend_src.md") == "/directories/backend_src"


def test_path_to_url_overview():
    """Overview converts to root route."""
    from oya.qa.service import QAService
    service = QAService.__new__(QAService)

    assert service._path_to_url("overview.md") == "/"


def test_path_to_url_architecture():
    """Architecture converts to /architecture route."""
    from oya.qa.service import QAService
    service = QAService.__new__(QAService)

    assert service._path_to_url("architecture.md") == "/architecture"
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_qa_service.py -k "path_to_url" -v`

Expected: FAIL with AttributeError

**Step 3: Add _path_to_url method**

```python
# Add to QAService class in service.py

def _path_to_url(self, wiki_path: str) -> str:
    """Convert wiki path to frontend route.

    Args:
        wiki_path: Path relative to wiki (e.g., 'files/src_main-py.md')

    Returns:
        Frontend route (e.g., '/files/src_main-py')
    """
    route = wiki_path.removesuffix(".md")

    if route == "overview":
        return "/"
    elif route == "architecture":
        return "/architecture"
    else:
        return f"/{route}"
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_qa_service.py -k "path_to_url" -v`

Expected: PASS (4 tests)

**Step 5: Commit**

```bash
git add backend/src/oya/qa/service.py backend/tests/test_qa_service.py
git commit -m "feat(qa): add path_to_url helper for citation URLs"
```

---

### Task 1.6: Lower temperature and update ask() method signature

**Files:**
- Modify: `backend/src/oya/qa/service.py`
- Test: `backend/tests/test_qa_service.py`

**Step 1: Update the ask() method**

This is a larger refactor. Update the `ask()` method to:
1. Remove mode handling
2. Use `_calculate_confidence()` instead of `_evaluate_evidence()`
3. Return new response format with SearchQuality
4. Lower temperature to 0.2

```python
async def ask(self, request: QARequest) -> QAResponse:
    """Answer a question about the codebase.

    Args:
        request: Q&A request with question.

    Returns:
        Q&A response with answer, citations, confidence, and search quality.
    """
    # Perform hybrid search
    results = await self.search(request.question)

    # Calculate confidence from results
    confidence = self._calculate_confidence(results)

    # Build prompt and generate answer
    prompt = self._build_context_prompt(request.question, results)

    try:
        raw_answer = await self._llm.generate(
            prompt=prompt,
            system_prompt=QA_SYSTEM_PROMPT,
            temperature=0.2,  # Lower for factual Q&A
        )
    except Exception as e:
        return QAResponse(
            answer=f"Error generating answer: {str(e)}",
            citations=[],
            confidence=confidence,
            disclaimer="An error occurred while generating the answer.",
            search_quality=SearchQuality(
                semantic_searched=True,  # We don't track this yet
                fts_searched=True,
                results_found=len(results),
                results_used=len(results),
            ),
        )

    # Extract citations and clean answer
    citations = self._extract_citations(raw_answer, results)
    answer = self._clean_answer(raw_answer)

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
            semantic_searched=True,
            fts_searched=True,
            results_found=len(results),
            results_used=len(results),
        ),
    )
```

**Step 2: Update _extract_citations to include url**

```python
def _extract_citations(
    self,
    answer: str,
    results: list[dict[str, Any]],
) -> list[Citation]:
    """Extract citations from LLM response."""
    citations: list[Citation] = []
    seen_paths: set[str] = set()

    # Look for [CITATIONS] section in response
    citations_match = re.search(r"\[CITATIONS\](.*?)(?:\n\n|$)", answer, re.DOTALL | re.IGNORECASE)

    if citations_match:
        citations_text = citations_match.group(1)
        for line in citations_text.strip().split("\n"):
            line = line.strip().lstrip("-").strip()
            if not line:
                continue

            if ":" in line:
                parts = line.split(":", 1)
                path = parts[0].strip()
                lines = parts[1].strip() if len(parts) > 1 else None
            else:
                path = line
                lines = None

            if path and path not in seen_paths:
                seen_paths.add(path)
                title = path
                for r in results:
                    if r.get("path") == path:
                        title = r.get("title") or path
                        break

                citations.append(Citation(
                    path=path,
                    title=title,
                    lines=lines,
                    url=self._path_to_url(path),
                ))

    # If no explicit citations, use top 3 results
    if not citations:
        for r in results[:3]:
            path = r.get("path", "")
            if path and path not in seen_paths:
                seen_paths.add(path)
                citations.append(Citation(
                    path=path,
                    title=r.get("title") or path,
                    lines=None,
                    url=self._path_to_url(path),
                ))

    return citations
```

**Step 3: Remove _evaluate_evidence method and old constants**

Delete:
- `MIN_EVIDENCE_RESULTS` constant
- `MAX_DISTANCE_THRESHOLD` constant
- `_evaluate_evidence()` method

**Step 4: Run all QA tests**

Run: `pytest tests/test_qa_service.py tests/test_qa_api.py -v`

Expected: Some failures due to API changes - fix in next task

**Step 5: Commit**

```bash
git add backend/src/oya/qa/service.py
git commit -m "feat(qa): update ask() to use confidence, remove mode handling"
```

---

### Task 1.7: Update QA API router

**Files:**
- Modify: `backend/src/oya/api/routers/qa.py`
- Test: `backend/tests/test_qa_api.py`

**Step 1: Read current qa.py router**

**Step 2: Update router to use new schemas**

```python
"""Q&A API router."""

from fastapi import APIRouter, Depends

from oya.api.deps import get_qa_service
from oya.qa.schemas import QARequest, QAResponse
from oya.qa.service import QAService

router = APIRouter(prefix="/api/qa", tags=["qa"])


@router.post("/ask", response_model=QAResponse)
async def ask_question(
    request: QARequest,
    qa_service: QAService = Depends(get_qa_service),
) -> QAResponse:
    """Ask a question about the codebase."""
    return await qa_service.ask(request)
```

**Step 3: Update tests in test_qa_api.py**

Update tests to not send `mode` or `context`, and expect `confidence` instead of `evidence_sufficient`.

**Step 4: Run tests**

Run: `pytest tests/test_qa_api.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/oya/api/routers/qa.py backend/tests/test_qa_api.py
git commit -m "feat(qa): update API router for new schema"
```

---

### Task 1.8: Run full backend test suite

**Step 1: Run all tests**

Run: `pytest`

Expected: All 352+ tests pass

**Step 2: Fix any failures**

Address any test failures from schema changes.

**Step 3: Commit fixes**

```bash
git add -A
git commit -m "fix(qa): update remaining tests for new schema"
```

---

## Phase 2: Token Budget Management

### Task 2.1: Add token budgeting to context building

**Files:**
- Modify: `backend/src/oya/qa/service.py`
- Test: `backend/tests/test_qa_service.py`

**Step 1: Write tests for token-aware truncation**

```python
def test_truncate_at_sentence_short_text():
    """Short text passes through unchanged."""
    from oya.qa.service import QAService
    service = QAService.__new__(QAService)

    text = "This is a short sentence."
    result = service._truncate_at_sentence(text, max_tokens=100)
    assert result == text


def test_truncate_at_sentence_preserves_boundary():
    """Long text truncates at sentence boundary."""
    from oya.qa.service import QAService
    service = QAService.__new__(QAService)

    text = "First sentence. Second sentence. Third sentence that is very long."
    result = service._truncate_at_sentence(text, max_tokens=20)
    assert result.endswith(".")
    assert "Third" not in result
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_qa_service.py -k "truncate_at_sentence" -v`

**Step 3: Add _truncate_at_sentence method**

```python
def _truncate_at_sentence(self, text: str, max_tokens: int) -> str:
    """Truncate text at sentence boundary within token limit.

    Args:
        text: Text to truncate.
        max_tokens: Maximum tokens allowed.

    Returns:
        Truncated text ending at sentence boundary.
    """
    from oya.generation.chunking import estimate_tokens

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

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_qa_service.py -k "truncate_at_sentence" -v`

**Step 5: Commit**

```bash
git add backend/src/oya/qa/service.py backend/tests/test_qa_service.py
git commit -m "feat(qa): add sentence-boundary truncation"
```

---

### Task 2.2: Update _build_context_prompt with token budgeting

**Files:**
- Modify: `backend/src/oya/qa/service.py`

**Step 1: Update method to use token budgeting**

```python
# Add constant at top of file
MAX_CONTEXT_TOKENS = 6000

def _build_context_prompt(
    self,
    question: str,
    results: list[dict[str, Any]],
) -> tuple[str, int]:
    """Build prompt with token-aware truncation.

    Args:
        question: User's question.
        results: Search results to include as context.

    Returns:
        Tuple of (formatted prompt, number of results used).
    """
    from oya.generation.chunking import estimate_tokens

    context_parts = []
    total_tokens = 0
    results_used = 0

    for r in results:
        source_type = r.get("type", "unknown")
        path = r.get("path", "unknown")
        content = r.get("content", "")

        # Truncate individual result at sentence boundary
        content = self._truncate_at_sentence(content, max_tokens=1500)

        part = f"[{source_type.upper()}] {path}\n{content}"
        part_tokens = estimate_tokens(part)

        if total_tokens + part_tokens > MAX_CONTEXT_TOKENS:
            break

        context_parts.append(part)
        total_tokens += part_tokens
        results_used += 1

    context_str = "\n\n---\n\n".join(context_parts)

    prompt = f"""Based on the following context from the codebase, answer the question.

CONTEXT:
{context_str}

QUESTION: {question}

Answer the question based only on the context provided. Include citations to specific files."""

    return prompt, results_used
```

**Step 2: Update ask() to use results_used**

Update `ask()` to capture results_used from `_build_context_prompt()` and include in SearchQuality.

**Step 3: Run tests**

Run: `pytest tests/test_qa_service.py -v`

**Step 4: Commit**

```bash
git add backend/src/oya/qa/service.py
git commit -m "feat(qa): implement token budget management"
```

---

## Phase 3: Search Quality Tracking

### Task 3.1: Update search() to return SearchQuality

**Files:**
- Modify: `backend/src/oya/qa/service.py`
- Test: `backend/tests/test_qa_service.py`

**Step 1: Write test**

```python
@pytest.mark.asyncio
async def test_search_returns_quality_metrics(mock_qa_service):
    """Search returns quality metrics alongside results."""
    results, quality = await mock_qa_service.search("test query")

    assert isinstance(quality.semantic_searched, bool)
    assert isinstance(quality.fts_searched, bool)
    assert quality.results_found >= 0
```

**Step 2: Update search() signature and implementation**

```python
async def search(
    self,
    query: str,
    limit: int = 10,
) -> tuple[list[dict[str, Any]], SearchQuality]:
    """Perform hybrid search combining semantic and full-text search.

    Args:
        query: Search query.
        limit: Maximum results to return.

    Returns:
        Tuple of (search results, quality metrics).
    """
    results: list[dict[str, Any]] = []
    seen_paths: set[str] = set()
    semantic_ok = False
    fts_ok = False

    # Semantic search via ChromaDB
    try:
        semantic_results = self._vectorstore.query(
            query_text=query,
            n_results=limit,
        )
        semantic_ok = True
        # ... process results (existing code)
    except Exception as e:
        import logging
        logging.warning(f"Semantic search failed: {e}")

    # Full-text search via SQLite FTS5
    try:
        # ... existing FTS code
        fts_ok = True
    except Exception as e:
        import logging
        logging.warning(f"FTS search failed: {e}")

    results_found = len(results)

    # Sort by type priority then distance
    type_priority = {"note": 0, "code": 1, "wiki": 2}
    results.sort(key=lambda r: (type_priority.get(r["type"], 3), r["distance"]))

    quality = SearchQuality(
        semantic_searched=semantic_ok,
        fts_searched=fts_ok,
        results_found=results_found,
        results_used=0,  # Set by caller after token budgeting
    )

    return results[:limit], quality
```

**Step 3: Update ask() to use new search() signature**

**Step 4: Run tests**

Run: `pytest tests/test_qa_service.py -v`

**Step 5: Commit**

```bash
git add backend/src/oya/qa/service.py backend/tests/test_qa_service.py
git commit -m "feat(qa): track and expose search quality metrics"
```

---

## Phase 4: Content Deduplication

### Task 4.1: Add content deduplication

**Files:**
- Modify: `backend/src/oya/qa/service.py`
- Test: `backend/tests/test_qa_service.py`

**Step 1: Write test**

```python
def test_deduplicate_results_removes_similar_content():
    """Deduplication removes near-duplicate content."""
    from oya.qa.service import QAService
    service = QAService.__new__(QAService)

    results = [
        {"path": "file1.md", "content": "This is the same content here."},
        {"path": "file2.md", "content": "This is the same content here."},  # Duplicate
        {"path": "file3.md", "content": "This is different content."},
    ]

    deduped = service._deduplicate_results(results)
    assert len(deduped) == 2
    assert deduped[0]["path"] == "file1.md"
    assert deduped[1]["path"] == "file3.md"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_qa_service.py::test_deduplicate_results_removes_similar_content -v`

**Step 3: Add _deduplicate_results method**

```python
def _deduplicate_results(self, results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Remove duplicate/near-duplicate content.

    Args:
        results: Search results to deduplicate.

    Returns:
        Deduplicated results preserving order.
    """
    seen_content_hashes: set[int] = set()
    deduplicated: list[dict[str, Any]] = []

    for r in results:
        content = r.get("content", "")
        # Hash first 500 chars (covers most duplicates)
        content_hash = hash(content[:500].strip().lower())

        if content_hash not in seen_content_hashes:
            seen_content_hashes.add(content_hash)
            deduplicated.append(r)

    return deduplicated
```

**Step 4: Integrate into search()**

Call `_deduplicate_results()` before returning results.

**Step 5: Run tests**

Run: `pytest tests/test_qa_service.py -v`

**Step 6: Commit**

```bash
git add backend/src/oya/qa/service.py backend/tests/test_qa_service.py
git commit -m "feat(qa): add content deduplication to search"
```

---

## Phase 5: Structured Citation Extraction

### Task 5.1: Update system prompt for structured output

**Files:**
- Modify: `backend/src/oya/qa/service.py`

**Step 1: Update QA_SYSTEM_PROMPT**

```python
QA_SYSTEM_PROMPT = """You are a helpful assistant that answers questions about a codebase.
You have access to documentation, code, and notes from the repository.

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

**Step 2: Commit**

```bash
git add backend/src/oya/qa/service.py
git commit -m "feat(qa): update system prompt for structured citations"
```

---

### Task 5.2: Update citation extraction for structured output

**Files:**
- Modify: `backend/src/oya/qa/service.py`
- Test: `backend/tests/test_qa_service.py`

**Step 1: Write test**

```python
def test_extract_citations_structured_format():
    """Extract citations from structured JSON output."""
    from oya.qa.service import QAService
    service = QAService.__new__(QAService)

    response = """<answer>
The auth module handles JWT tokens.
</answer>

<citations>
[
  {"path": "files/auth-py.md", "relevant_text": "JWT token generation"},
  {"path": "files/config-py.md", "relevant_text": "auth settings"}
]
</citations>"""

    results = [
        {"path": "files/auth-py.md", "title": "Auth Module"},
        {"path": "files/config-py.md", "title": "Config"},
        {"path": "files/other.md", "title": "Other"},
    ]

    citations = service._extract_citations(response, results)
    assert len(citations) == 2
    assert citations[0].path == "files/auth-py.md"
    assert citations[0].url == "/files/auth-py"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_qa_service.py::test_extract_citations_structured_format -v`

**Step 3: Update _extract_citations method**

```python
def _extract_citations(
    self,
    response: str,
    results: list[dict[str, Any]],
) -> list[Citation]:
    """Extract citations from structured JSON output.

    Args:
        response: LLM response with <citations> block.
        results: Search results for validation.

    Returns:
        Validated citations with URLs.
    """
    import json

    citations: list[Citation] = []

    # Parse JSON citations block
    match = re.search(r'<citations>\s*(\[.*?\])\s*</citations>', response, re.DOTALL)
    if not match:
        return self._fallback_citations(results[:3])

    try:
        raw_citations = json.loads(match.group(1))
    except json.JSONDecodeError:
        return self._fallback_citations(results[:3])

    # Validate each citation exists in search results
    result_paths = {r.get("path") for r in results}
    seen_paths: set[str] = set()

    for cite in raw_citations:
        path = cite.get("path", "")
        if path and path in result_paths and path not in seen_paths:
            seen_paths.add(path)
            title = path
            for r in results:
                if r.get("path") == path:
                    title = r.get("title") or path
                    break

            citations.append(Citation(
                path=path,
                title=title,
                lines=None,
                url=self._path_to_url(path),
            ))

    return citations if citations else self._fallback_citations(results[:3])


def _fallback_citations(self, results: list[dict[str, Any]]) -> list[Citation]:
    """Create citations from top results as fallback."""
    citations: list[Citation] = []
    seen_paths: set[str] = set()

    for r in results:
        path = r.get("path", "")
        if path and path not in seen_paths:
            seen_paths.add(path)
            citations.append(Citation(
                path=path,
                title=r.get("title") or path,
                lines=None,
                url=self._path_to_url(path),
            ))

    return citations
```

**Step 4: Add _extract_answer method**

```python
def _extract_answer(self, response: str) -> str:
    """Extract answer text from structured response."""
    match = re.search(r'<answer>\s*(.*?)\s*</answer>', response, re.DOTALL)
    return match.group(1).strip() if match else response.strip()
```

**Step 5: Update _clean_answer to use _extract_answer**

Replace `_clean_answer` usage with `_extract_answer` in `ask()`.

**Step 6: Run tests**

Run: `pytest tests/test_qa_service.py -v`

**Step 7: Commit**

```bash
git add backend/src/oya/qa/service.py backend/tests/test_qa_service.py
git commit -m "feat(qa): implement structured citation extraction with validation"
```

---

## Phase 6: Frontend - Types and API Client

### Task 6.1: Update TypeScript types

**Files:**
- Modify: `frontend/src/types/index.ts`

**Step 1: Read current types file**

**Step 2: Update types**

Remove `QAMode`, add `ConfidenceLevel`, update `Citation` and `QAResponse`:

```typescript
// Remove QAMode type

export type ConfidenceLevel = 'high' | 'medium' | 'low';

export interface SearchQuality {
  semantic_searched: boolean;
  fts_searched: boolean;
  results_found: number;
  results_used: number;
}

export interface Citation {
  path: string;
  title: string;
  lines: string | null;
  url: string;  // New field
}

export interface QAResponse {
  answer: string;
  citations: Citation[];
  confidence: ConfidenceLevel;  // Was evidence_sufficient
  disclaimer: string;
  search_quality: SearchQuality;  // New field
}

export interface QARequest {
  question: string;
  // mode and context removed
}
```

**Step 3: Commit**

```bash
git add frontend/src/types/index.ts
git commit -m "feat(frontend): update types for new Q&A schema"
```

---

### Task 6.2: Update API client

**Files:**
- Modify: `frontend/src/api/client.ts`

**Step 1: Update askQuestion function**

```typescript
export async function askQuestion(request: QARequest): Promise<QAResponse> {
  const response = await fetch(`${API_BASE}/api/qa/ask`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question: request.question }),
  });

  if (!response.ok) {
    throw new Error(`Failed to ask question: ${response.statusText}`);
  }

  return response.json();
}
```

**Step 2: Commit**

```bash
git add frontend/src/api/client.ts
git commit -m "feat(frontend): simplify askQuestion API call"
```

---

## Phase 7: Frontend - AskPanel Component

### Task 7.1: Create AskPanel component

**Files:**
- Create: `frontend/src/components/AskPanel.tsx`

**Step 1: Create the component**

```typescript
import { useState } from 'react';
import { Link } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { askQuestion } from '../api/client';
import type { QAResponse, Citation, ConfidenceLevel } from '../types';

interface QAMessage {
  question: string;
  response: QAResponse;
}

interface AskPanelProps {
  isOpen: boolean;
  onClose: () => void;
}

const confidenceColors: Record<ConfidenceLevel, string> = {
  high: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200',
  medium: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200',
  low: 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200',
};

export function AskPanel({ isOpen, onClose }: AskPanelProps) {
  const [question, setQuestion] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [messages, setMessages] = useState<QAMessage[]>([]);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!question.trim() || isLoading) return;

    setIsLoading(true);
    setError(null);

    try {
      const response = await askQuestion({ question: question.trim() });
      setMessages(prev => [...prev, { question: question.trim(), response }]);
      setQuestion('');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to get answer');
    } finally {
      setIsLoading(false);
    }
  };

  const renderCitation = (citation: Citation, index: number) => (
    <Link
      key={index}
      to={citation.url}
      onClick={onClose}
      className="text-blue-600 hover:underline text-sm mr-2"
    >
      {citation.title}
    </Link>
  );

  if (!isOpen) return null;

  return (
    <div className="w-[350px] border-l border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 flex flex-col h-full">
      {/* Header */}
      <div className="p-4 border-b border-gray-200 dark:border-gray-700 flex justify-between items-center">
        <h2 className="font-semibold text-gray-900 dark:text-white">Ask about this codebase</h2>
        <button
          onClick={onClose}
          className="text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((msg, idx) => (
          <div key={idx} className="space-y-2">
            {/* Question */}
            <div className="bg-gray-100 dark:bg-gray-700 rounded-lg p-3">
              <p className="text-sm text-gray-900 dark:text-white">{msg.question}</p>
            </div>

            {/* Answer */}
            <div className="space-y-2">
              {/* Confidence banner */}
              <div className={`px-3 py-1 rounded text-xs ${confidenceColors[msg.response.confidence]}`}>
                {msg.response.disclaimer}
              </div>

              {/* Answer content */}
              <div className="prose prose-sm dark:prose-invert max-w-none">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {msg.response.answer}
                </ReactMarkdown>
              </div>

              {/* Citations */}
              {msg.response.citations.length > 0 && (
                <div className="pt-2 border-t border-gray-200 dark:border-gray-700">
                  <span className="text-xs text-gray-500 mr-2">Sources:</span>
                  {msg.response.citations.map(renderCitation)}
                </div>
              )}

              {/* Search quality warning */}
              {(!msg.response.search_quality.semantic_searched || !msg.response.search_quality.fts_searched) && (
                <div className="text-xs text-yellow-600 dark:text-yellow-400">
                  {!msg.response.search_quality.semantic_searched && 'Vector search unavailable. '}
                  {!msg.response.search_quality.fts_searched && 'Text search unavailable.'}
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
      </div>

      {/* Input */}
      <form onSubmit={handleSubmit} className="p-4 border-t border-gray-200 dark:border-gray-700">
        <div className="flex gap-2">
          <input
            type="text"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Ask a question..."
            className="flex-1 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
            disabled={isLoading}
          />
          <button
            type="submit"
            disabled={isLoading || !question.trim()}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed text-sm"
          >
            {isLoading ? '...' : 'Ask'}
          </button>
        </div>
      </form>
    </div>
  );
}
```

**Step 2: Commit**

```bash
git add frontend/src/components/AskPanel.tsx
git commit -m "feat(frontend): create AskPanel component"
```

---

### Task 7.2: Update Layout to include AskPanel

**Files:**
- Modify: `frontend/src/components/Layout.tsx`

**Step 1: Import and add AskPanel**

Add AskPanel to the layout, controlled by context state.

**Step 2: Update Layout structure**

```typescript
// Add to imports
import { AskPanel } from './AskPanel';
import { useApp } from '../context/AppContext';

// In Layout component
export function Layout({ children }: { children: React.ReactNode }) {
  const { askPanelOpen, setAskPanelOpen } = useApp();

  return (
    <div className="flex h-screen">
      <Sidebar />
      <div className="flex flex-1 flex-col">
        <TopBar />
        <div className="flex flex-1 overflow-hidden">
          <main className="flex-1 overflow-y-auto p-6">
            {children}
          </main>
          <AskPanel isOpen={askPanelOpen} onClose={() => setAskPanelOpen(false)} />
        </div>
      </div>
    </div>
  );
}
```

**Step 3: Commit**

```bash
git add frontend/src/components/Layout.tsx
git commit -m "feat(frontend): integrate AskPanel into Layout"
```

---

### Task 7.3: Add panel toggle to TopBar

**Files:**
- Modify: `frontend/src/components/TopBar.tsx`

**Step 1: Add toggle button**

```typescript
// Add to TopBar component
const { askPanelOpen, setAskPanelOpen } = useApp();

// Add button in TopBar JSX
<button
  onClick={() => setAskPanelOpen(!askPanelOpen)}
  className={`p-2 rounded-lg ${askPanelOpen ? 'bg-blue-100 text-blue-600' : 'text-gray-500 hover:bg-gray-100'}`}
  title="Toggle Q&A panel"
>
  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
  </svg>
</button>
```

**Step 2: Commit**

```bash
git add frontend/src/components/TopBar.tsx
git commit -m "feat(frontend): add Q&A panel toggle to TopBar"
```

---

### Task 7.4: Add askPanelOpen state to AppContext

**Files:**
- Modify: `frontend/src/context/AppContext.tsx`

**Step 1: Add state with localStorage persistence**

```typescript
// Add to context state
const [askPanelOpen, setAskPanelOpen] = useState<boolean>(() => {
  const saved = localStorage.getItem('askPanelOpen');
  return saved ? JSON.parse(saved) : false;
});

// Add effect to persist
useEffect(() => {
  localStorage.setItem('askPanelOpen', JSON.stringify(askPanelOpen));
}, [askPanelOpen]);

// Add to context value
const value = {
  // ... existing values
  askPanelOpen,
  setAskPanelOpen,
};
```

**Step 2: Update context type**

```typescript
interface AppContextType {
  // ... existing types
  askPanelOpen: boolean;
  setAskPanelOpen: (open: boolean) => void;
}
```

**Step 3: Commit**

```bash
git add frontend/src/context/AppContext.tsx
git commit -m "feat(frontend): add askPanelOpen state to AppContext"
```

---

### Task 7.5: Delete QADock component

**Files:**
- Delete: `frontend/src/components/QADock.tsx`
- Modify: `frontend/src/components/index.ts` (remove export)

**Step 1: Remove QADock from Layout imports if present**

**Step 2: Delete QADock.tsx**

```bash
rm frontend/src/components/QADock.tsx
```

**Step 3: Update index.ts exports**

Remove QADock from exports.

**Step 4: Commit**

```bash
git add -A
git commit -m "feat(frontend): remove QADock, replaced by AskPanel"
```

---

## Phase 8: Testing and Cleanup

### Task 8.1: Run full test suite

**Step 1: Run backend tests**

Run: `cd backend && pytest`

Expected: All tests pass

**Step 2: Run frontend tests**

Run: `cd frontend && npm test`

Expected: All tests pass (some may need updates for removed QADock)

**Step 3: Fix any failures**

**Step 4: Commit fixes**

```bash
git add -A
git commit -m "fix: update tests for Q&A redesign"
```

---

### Task 8.2: Manual testing

**Step 1: Start backend**

```bash
cd backend
source .venv/bin/activate
export WORKSPACE_PATH=/path/to/test/repo
uvicorn oya.main:app --reload
```

**Step 2: Start frontend**

```bash
cd frontend
npm run dev
```

**Step 3: Test Q&A flow**

1. Open browser to http://localhost:5173
2. Click Q&A toggle in TopBar
3. Ask a question
4. Verify confidence banner shows correct color
5. Click a citation link - should navigate to wiki page
6. Verify panel closes on navigation

**Step 4: Test edge cases**

- Empty results (LOW confidence)
- Search failures (check warning appears)
- Long answers (scrolling works)

---

### Task 8.3: Final commit

```bash
git add -A
git commit -m "feat: complete Q&A redesign implementation"
```

---

## Summary

| Phase | Tasks | Description |
|-------|-------|-------------|
| 1 | 1.1-1.8 | Backend quick wins: schemas, confidence, temperature |
| 2 | 2.1-2.2 | Token budget management |
| 3 | 3.1 | Search quality tracking |
| 4 | 4.1 | Content deduplication |
| 5 | 5.1-5.2 | Structured citation extraction |
| 6 | 6.1-6.2 | Frontend types and API |
| 7 | 7.1-7.5 | AskPanel component and integration |
| 8 | 8.1-8.3 | Testing and cleanup |
