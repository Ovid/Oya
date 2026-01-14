# Config Extraction Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Extract hard-coded constants from frontend and backend into organized config files for easier tuning, documentation, and DRY principles.

**Architecture:** Create `backend/src/oya/config/` and `frontend/src/config/` directories with domain-organized modules. Each module has detailed group comments explaining the constants. Source files import from config modules. The existing `backend/src/oya/config.py` (env-based settings) remains unchanged.

**Tech Stack:** Python 3.11+, TypeScript, no external dependencies.

---

## Task 1: Create Backend Config Directory Structure

**Files:**
- Create: `backend/src/oya/config/__init__.py`

**Step 1: Create the config directory**

```bash
mkdir -p backend/src/oya/config
```

**Step 2: Create empty __init__.py**

Create `backend/src/oya/config/__init__.py`:

```python
"""Configuration constants.

Re-exports all config for convenient importing:
    from oya.config import MAX_CONTEXT_TOKENS, SYNTHESIS_TEMPERATURE
"""

# Imports will be added as each config module is created
```

**Step 3: Commit**

```bash
git add backend/src/oya/config/__init__.py
git commit -m "chore: create backend config directory structure"
```

---

## Task 2: Create qa.py Config Module

**Files:**
- Create: `backend/src/oya/config/qa.py`
- Modify: `backend/src/oya/config/__init__.py`

**Step 1: Create qa.py**

Create `backend/src/oya/config/qa.py`:

```python
"""Q&A service configuration.

These settings control the behavior of the Q&A feature, which allows users
to ask natural language questions about the codebase and receive answers
based on the generated wiki documentation.
"""

# =============================================================================
# Token Budgets
# =============================================================================
# The Q&A system builds prompts by combining the user's question with relevant
# context from the wiki. These limits prevent prompts from exceeding LLM context
# windows. MAX_CONTEXT_TOKENS caps the total context size, while MAX_RESULT_TOKENS
# prevents any single document from dominating. Values are in tokens (roughly 4
# characters per token for English text).

MAX_CONTEXT_TOKENS = 6000
MAX_RESULT_TOKENS = 1500

# =============================================================================
# Confidence Scoring
# =============================================================================
# Answers are assigned a confidence level (high/medium/low) based on how well
# search results match the question. This uses vector similarity distances where
# 0.0 = perfect match and 1.0 = completely unrelated. "High" confidence requires
# multiple strong matches below the HIGH threshold. "Medium" requires at least one
# decent match below the MEDIUM threshold. Otherwise, confidence is "low".

HIGH_CONFIDENCE_THRESHOLD = 0.3
MEDIUM_CONFIDENCE_THRESHOLD = 0.6
STRONG_MATCH_THRESHOLD = 0.5
MIN_STRONG_MATCHES_FOR_HIGH = 3
```

**Step 2: Update __init__.py**

Edit `backend/src/oya/config/__init__.py` to add the import:

```python
"""Configuration constants.

Re-exports all config for convenient importing:
    from oya.config import MAX_CONTEXT_TOKENS, SYNTHESIS_TEMPERATURE
"""

from oya.config.qa import *
```

**Step 3: Commit**

```bash
git add backend/src/oya/config/qa.py backend/src/oya/config/__init__.py
git commit -m "feat(config): add Q&A configuration constants"
```

---

## Task 3: Create generation.py Config Module

**Files:**
- Create: `backend/src/oya/config/generation.py`
- Modify: `backend/src/oya/config/__init__.py`

**Step 1: Create generation.py**

Create `backend/src/oya/config/generation.py`:

```python
"""Wiki generation configuration.

These settings control how the wiki is generated from source code, including
LLM parameters for content synthesis and token estimation.
"""

# =============================================================================
# LLM Parameters
# =============================================================================
# Temperature controls randomness in LLM output. Lower values (0.0-0.3) produce
# more deterministic, focused output suitable for structured documentation.
# Higher values (0.7-1.0) produce more creative, varied output.

SYNTHESIS_TEMPERATURE = 0.3

# =============================================================================
# Token Estimation
# =============================================================================
# When chunking code for processing, we estimate token counts from character
# counts. TOKENS_PER_CHAR is a rough multiplier (code tends to tokenize less
# efficiently than prose). DEFAULT_CONTEXT_LIMIT caps how much content is
# sent to the LLM for synthesis operations.

TOKENS_PER_CHAR = 0.25
DEFAULT_CONTEXT_LIMIT = 100_000

# =============================================================================
# Chunking
# =============================================================================
# Large files are split into chunks for processing. MAX_CHUNK_TOKENS sets the
# target chunk size. CHUNK_OVERLAP_LINES adds redundancy between chunks so
# context isn't lost at boundaries.

MAX_CHUNK_TOKENS = 1000
CHUNK_OVERLAP_LINES = 5
```

**Step 2: Update __init__.py**

Add to `backend/src/oya/config/__init__.py`:

```python
from oya.config.generation import *
```

**Step 3: Commit**

```bash
git add backend/src/oya/config/generation.py backend/src/oya/config/__init__.py
git commit -m "feat(config): add wiki generation configuration constants"
```

---

## Task 4: Create llm.py Config Module

**Files:**
- Create: `backend/src/oya/config/llm.py`
- Modify: `backend/src/oya/config/__init__.py`

**Step 1: Create llm.py**

Create `backend/src/oya/config/llm.py`:

```python
"""LLM client configuration.

Default parameters for LLM API calls. These can be overridden per-call
but provide sensible defaults for most use cases.
"""

# =============================================================================
# Generation Defaults
# =============================================================================
# MAX_TOKENS caps response length to control costs and ensure responses complete.
# DEFAULT_TEMPERATURE balances creativity and consistency (0.7 is a common default).
# JSON_TEMPERATURE is lower for structured output where consistency matters more.

MAX_TOKENS = 4096
DEFAULT_TEMPERATURE = 0.7
JSON_TEMPERATURE = 0.3
```

**Step 2: Update __init__.py**

Add to `backend/src/oya/config/__init__.py`:

```python
from oya.config.llm import *
```

**Step 3: Commit**

```bash
git add backend/src/oya/config/llm.py backend/src/oya/config/__init__.py
git commit -m "feat(config): add LLM client configuration constants"
```

---

## Task 5: Create search.py Config Module

**Files:**
- Create: `backend/src/oya/config/search.py`
- Modify: `backend/src/oya/config/__init__.py`

**Step 1: Create search.py**

Create `backend/src/oya/config/search.py`:

```python
"""Search and vector store configuration.

These settings control hybrid search (semantic + full-text) used by Q&A
and the search API. Hybrid search combines ChromaDB vector similarity
with SQLite FTS5 full-text search, then merges and ranks results.
"""

# =============================================================================
# Result Limits
# =============================================================================
# Default number of results to return from search operations. Higher values
# provide more context but increase processing time and token usage.

DEFAULT_SEARCH_LIMIT = 10
SNIPPET_MAX_LENGTH = 200

# =============================================================================
# Result Prioritization
# =============================================================================
# When ranking combined results, content type affects ordering. Human-written
# notes are prioritized over code, which is prioritized over generated wiki
# content. Lower numbers = higher priority.

TYPE_PRIORITY = {"note": 0, "code": 1, "wiki": 2}

# =============================================================================
# Deduplication
# =============================================================================
# Search results from different sources may contain duplicate content.
# We hash the first N characters of each result to detect near-duplicates.

DEDUP_HASH_LENGTH = 500
```

**Step 2: Update __init__.py**

Add to `backend/src/oya/config/__init__.py`:

```python
from oya.config.search import *
```

**Step 3: Commit**

```bash
git add backend/src/oya/config/search.py backend/src/oya/config/__init__.py
git commit -m "feat(config): add search configuration constants"
```

---

## Task 6: Create files.py Config Module

**Files:**
- Create: `backend/src/oya/config/files.py`
- Modify: `backend/src/oya/config/__init__.py`

**Step 1: Create files.py**

Create `backend/src/oya/config/files.py`:

```python
"""File filtering and processing configuration.

These settings control which files are included in wiki generation and
how they're processed. Large or binary files are excluded to keep the
wiki focused on human-readable source code.
"""

# =============================================================================
# Size Limits
# =============================================================================
# Files larger than MAX_FILE_SIZE_KB are skipped during generation. This
# prevents huge generated files, minified bundles, or data files from
# bloating the wiki and consuming excessive LLM tokens.

MAX_FILE_SIZE_KB = 500

# =============================================================================
# Binary Detection
# =============================================================================
# To detect binary files, we read the first N bytes and check for null
# characters. Binary files are always excluded from generation.

BINARY_CHECK_BYTES = 1024

# =============================================================================
# Concurrency
# =============================================================================
# Number of files to process in parallel during generation. Lower values
# are safer for local models (Ollama) which may have limited capacity.
# Cloud APIs (OpenAI, Anthropic) can handle higher concurrency.

PARALLEL_FILE_LIMIT_LOCAL = 2
PARALLEL_FILE_LIMIT_CLOUD = 10
```

**Step 2: Update __init__.py**

Add to `backend/src/oya/config/__init__.py`:

```python
from oya.config.files import *
```

**Step 3: Commit**

```bash
git add backend/src/oya/config/files.py backend/src/oya/config/__init__.py
git commit -m "feat(config): add file processing configuration constants"
```

---

## Task 7: Update qa/service.py to Use Config

**Files:**
- Modify: `backend/src/oya/qa/service.py:12-15` (remove constants)
- Modify: `backend/src/oya/qa/service.py:144` (type_priority)
- Modify: `backend/src/oya/qa/service.py:167` (dedup hash)
- Modify: `backend/src/oya/qa/service.py:189-197` (confidence thresholds)

**Step 1: Run tests to verify baseline**

```bash
cd backend && source .venv/bin/activate && pytest tests/test_qa_service.py -v
```

Expected: All tests pass.

**Step 2: Update imports and remove inline constants**

In `backend/src/oya/qa/service.py`:

Replace lines 12-15:
```python
# Token budget for context in LLM prompt
MAX_CONTEXT_TOKENS = 6000
# Maximum tokens per individual search result
MAX_RESULT_TOKENS = 1500
```

With:
```python
from oya.config.qa import (
    MAX_CONTEXT_TOKENS,
    MAX_RESULT_TOKENS,
    HIGH_CONFIDENCE_THRESHOLD,
    MEDIUM_CONFIDENCE_THRESHOLD,
    STRONG_MATCH_THRESHOLD,
    MIN_STRONG_MATCHES_FOR_HIGH,
)
from oya.config.search import DEDUP_HASH_LENGTH, TYPE_PRIORITY
```

Replace line 144:
```python
        type_priority = {"note": 0, "code": 1, "wiki": 2}
```

With:
```python
        type_priority = TYPE_PRIORITY
```

Replace line 167:
```python
            content_hash = hash(content[:500].strip().lower())
```

With:
```python
            content_hash = hash(content[:DEDUP_HASH_LENGTH].strip().lower())
```

Replace lines 189-197:
```python
        # Count results with good relevance (distance < 0.5)
        strong_matches = sum(1 for r in results if r.get("distance", 1.0) < 0.5)

        # Check best result quality
        best_distance = min(r.get("distance", 1.0) for r in results)

        if strong_matches >= 3 and best_distance < 0.3:
            return ConfidenceLevel.HIGH
        elif strong_matches >= 1 and best_distance < 0.6:
            return ConfidenceLevel.MEDIUM
```

With:
```python
        # Count results with good relevance
        strong_matches = sum(
            1 for r in results if r.get("distance", 1.0) < STRONG_MATCH_THRESHOLD
        )

        # Check best result quality
        best_distance = min(r.get("distance", 1.0) for r in results)

        if strong_matches >= MIN_STRONG_MATCHES_FOR_HIGH and best_distance < HIGH_CONFIDENCE_THRESHOLD:
            return ConfidenceLevel.HIGH
        elif strong_matches >= 1 and best_distance < MEDIUM_CONFIDENCE_THRESHOLD:
            return ConfidenceLevel.MEDIUM
```

**Step 3: Run tests to verify**

```bash
pytest tests/test_qa_service.py -v
```

Expected: All tests pass.

**Step 4: Commit**

```bash
git add backend/src/oya/qa/service.py
git commit -m "refactor(qa): use config constants instead of inline values"
```

---

## Task 8: Update generation/synthesis.py to Use Config

**Files:**
- Modify: `backend/src/oya/generation/synthesis.py:23` (remove TOKENS_PER_CHAR)
- Modify: `backend/src/oya/generation/synthesis.py:130` (temperature)

**Step 1: Run tests to verify baseline**

```bash
pytest tests/test_synthesis.py -v
```

Expected: All tests pass.

**Step 2: Update imports and remove inline constants**

In `backend/src/oya/generation/synthesis.py`:

Add import near top (after other imports):
```python
from oya.config.generation import TOKENS_PER_CHAR, SYNTHESIS_TEMPERATURE
```

Remove line 23:
```python
TOKENS_PER_CHAR = 0.25
```

Replace line ~130 (temperature in generate_json call):
```python
                temperature=0.3,  # Lower temperature for structured output
```

With:
```python
                temperature=SYNTHESIS_TEMPERATURE,
```

**Step 3: Run tests to verify**

```bash
pytest tests/test_synthesis.py -v
```

Expected: All tests pass.

**Step 4: Commit**

```bash
git add backend/src/oya/generation/synthesis.py
git commit -m "refactor(synthesis): use config constants instead of inline values"
```

---

## Task 9: Update generation/chunking.py to Use Config

**Files:**
- Modify: `backend/src/oya/generation/chunking.py:46-47` (default params)
- Modify: `backend/src/oya/generation/chunking.py:119` (default params)

**Step 1: Run tests to verify baseline**

```bash
pytest tests/test_chunking.py -v
```

Expected: All tests pass.

**Step 2: Update imports and default params**

In `backend/src/oya/generation/chunking.py`:

Add import near top:
```python
from oya.config.generation import MAX_CHUNK_TOKENS, CHUNK_OVERLAP_LINES
```

Replace function signature at line ~43:
```python
def chunk_file_content(
    content: str,
    file_path: str,
    max_tokens: int = 1000,
    overlap_lines: int = 5,
) -> list[Chunk]:
```

With:
```python
def chunk_file_content(
    content: str,
    file_path: str,
    max_tokens: int = MAX_CHUNK_TOKENS,
    overlap_lines: int = CHUNK_OVERLAP_LINES,
) -> list[Chunk]:
```

Find and update the second function with same defaults (around line 119).

**Step 3: Run tests to verify**

```bash
pytest tests/test_chunking.py -v
```

Expected: All tests pass.

**Step 4: Commit**

```bash
git add backend/src/oya/generation/chunking.py
git commit -m "refactor(chunking): use config constants for default values"
```

---

## Task 10: Update llm/client.py to Use Config

**Files:**
- Modify: `backend/src/oya/llm/client.py:132-133` (default params)
- Modify: `backend/src/oya/llm/client.py:223` (json temperature)

**Step 1: Run tests to verify baseline**

```bash
pytest tests/test_llm_client.py -v
```

Expected: All tests pass.

**Step 2: Update imports and default params**

In `backend/src/oya/llm/client.py`:

Add import near top:
```python
from oya.config.llm import MAX_TOKENS, DEFAULT_TEMPERATURE, JSON_TEMPERATURE
```

Replace function signature at line ~128:
```python
    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
```

With:
```python
    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = DEFAULT_TEMPERATURE,
        max_tokens: int = MAX_TOKENS,
    ) -> str:
```

Replace line ~223:
```python
            temperature=0.3,  # Lower temperature for structured output
```

With:
```python
            temperature=JSON_TEMPERATURE,
```

**Step 3: Run tests to verify**

```bash
pytest tests/test_llm_client.py -v
```

Expected: All tests pass.

**Step 4: Commit**

```bash
git add backend/src/oya/llm/client.py
git commit -m "refactor(llm): use config constants for default values"
```

---

## Task 11: Update api/routers/search.py to Use Config

**Files:**
- Modify: `backend/src/oya/api/routers/search.py:32` (default limit)
- Modify: `backend/src/oya/api/routers/search.py:80` (snippet length)

**Step 1: Run tests to verify baseline**

```bash
pytest tests/test_search_api.py -v
```

Expected: All tests pass.

**Step 2: Update imports and default values**

In `backend/src/oya/api/routers/search.py`:

Add import:
```python
from oya.config.search import SNIPPET_MAX_LENGTH
```

Replace line ~80:
```python
def _create_snippet(content: str, query: str, max_length: int = 200) -> str:
```

With:
```python
def _create_snippet(content: str, query: str, max_length: int = SNIPPET_MAX_LENGTH) -> str:
```

**Step 3: Run tests to verify**

```bash
pytest tests/test_search_api.py -v
```

Expected: All tests pass.

**Step 4: Commit**

```bash
git add backend/src/oya/api/routers/search.py
git commit -m "refactor(search): use config constants for default values"
```

---

## Task 12: Run Full Backend Test Suite

**Step 1: Run all backend tests**

```bash
cd backend && source .venv/bin/activate && pytest -v
```

Expected: All 369+ tests pass.

**Step 2: Commit if any cleanup needed**

If tests reveal issues, fix and commit.

---

## Task 13: Create Frontend Config Directory Structure

**Files:**
- Create: `frontend/src/config/index.ts`

**Step 1: Create the config directory**

```bash
mkdir -p frontend/src/config
```

**Step 2: Create empty index.ts**

Create `frontend/src/config/index.ts`:

```typescript
/**
 * Configuration constants.
 *
 * Re-exports all config for convenient importing:
 *     import { SIDEBAR_WIDTH, CONFIDENCE_COLORS } from '../config';
 */

// Exports will be added as each config module is created
```

**Step 3: Commit**

```bash
git add frontend/src/config/index.ts
git commit -m "chore: create frontend config directory structure"
```

---

## Task 14: Create layout.ts Config Module

**Files:**
- Create: `frontend/src/config/layout.ts`
- Modify: `frontend/src/config/index.ts`

**Step 1: Create layout.ts**

Create `frontend/src/config/layout.ts`:

```typescript
/**
 * Layout configuration.
 *
 * Dimensions and spacing for the main application shell. The layout consists
 * of a fixed top bar, collapsible left sidebar (navigation), collapsible right
 * sidebar (table of contents), and an optional ask panel that replaces the
 * right sidebar when open.
 */

// =============================================================================
// Panel Dimensions
// =============================================================================
// Width values for the main layout panels. These are used for both the panel
// itself and the margin applied to the main content area when panels are open.
// Values are in pixels and correspond to Tailwind classes (w-64 = 256px, etc.)

export const SIDEBAR_WIDTH = 256;        // w-64 - Left navigation sidebar
export const RIGHT_SIDEBAR_WIDTH = 224;  // w-56 - Table of contents
export const ASK_PANEL_WIDTH = 350;      // w-[350px] - Q&A panel
export const TOP_BAR_HEIGHT = 56;        // h-14 - Fixed header height

// =============================================================================
// Z-Index Layers
// =============================================================================
// Stacking order for overlapping elements. Higher values appear on top.
// Modals and their backdrops should be above all other content.

export const Z_INDEX_TOP_BAR = 50;
export const Z_INDEX_MODAL_BACKDROP = 50;
export const Z_INDEX_MODAL = 50;
```

**Step 2: Update index.ts**

Edit `frontend/src/config/index.ts`:

```typescript
/**
 * Configuration constants.
 *
 * Re-exports all config for convenient importing:
 *     import { SIDEBAR_WIDTH, CONFIDENCE_COLORS } from '../config';
 */

export * from './layout';
```

**Step 3: Commit**

```bash
git add frontend/src/config/layout.ts frontend/src/config/index.ts
git commit -m "feat(config): add layout configuration constants"
```

---

## Task 15: Create qa.ts Config Module

**Files:**
- Create: `frontend/src/config/qa.ts`
- Modify: `frontend/src/config/index.ts`

**Step 1: Create qa.ts**

Create `frontend/src/config/qa.ts`:

```typescript
/**
 * Q&A panel configuration.
 *
 * Styling for the Ask panel, which displays answers with confidence levels.
 * Confidence indicates how well the search results matched the question:
 * high = strong matches found, medium = partial matches, low = weak/no matches.
 */

// =============================================================================
// Confidence Level Colors
// =============================================================================
// Tailwind classes for styling the confidence banner on each answer.
// Green = high confidence, yellow = medium, red = low. Includes dark mode variants.

export const CONFIDENCE_COLORS = {
  high: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200',
  medium: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200',
  low: 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200',
} as const;
```

**Step 2: Update index.ts**

Add to `frontend/src/config/index.ts`:

```typescript
export * from './qa';
```

**Step 3: Commit**

```bash
git add frontend/src/config/qa.ts frontend/src/config/index.ts
git commit -m "feat(config): add Q&A panel configuration constants"
```

---

## Task 16: Create storage.ts Config Module

**Files:**
- Create: `frontend/src/config/storage.ts`
- Modify: `frontend/src/config/index.ts`

**Step 1: Create storage.ts**

Create `frontend/src/config/storage.ts`:

```typescript
/**
 * Local storage configuration.
 *
 * Keys for browser localStorage used to persist user preferences across
 * sessions. All keys are prefixed with 'oya-' to avoid collisions with
 * other applications on the same domain.
 */

// =============================================================================
// Preference Keys
// =============================================================================
// These preferences are restored when the app loads and persisted when changed.

export const STORAGE_KEY_DARK_MODE = 'oya-dark-mode';
export const STORAGE_KEY_ASK_PANEL_OPEN = 'oya-ask-panel-open';
```

**Step 2: Update index.ts**

Add to `frontend/src/config/index.ts`:

```typescript
export * from './storage';
```

**Step 3: Commit**

```bash
git add frontend/src/config/storage.ts frontend/src/config/index.ts
git commit -m "feat(config): add storage configuration constants"
```

---

## Task 17: Create timing.ts Config Module

**Files:**
- Create: `frontend/src/config/timing.ts`
- Modify: `frontend/src/config/index.ts`

**Step 1: Create timing.ts**

Create `frontend/src/config/timing.ts`:

```typescript
/**
 * Timing configuration.
 *
 * Intervals and thresholds for time-based operations like polling,
 * animations, and relative time formatting ("5 minutes ago").
 */

// =============================================================================
// Polling Intervals
// =============================================================================
// How frequently to check for updates during long-running operations.
// Values in milliseconds.

export const ELAPSED_TIME_UPDATE_MS = 1000;  // Update elapsed time display

// =============================================================================
// Relative Time Thresholds
// =============================================================================
// Thresholds for formatting timestamps as relative time ("just now", "5 min ago").
// When the time difference exceeds a threshold, we use the next larger unit.
// Values in milliseconds.

export const MS_PER_MINUTE = 60_000;
export const MS_PER_HOUR = 3_600_000;
export const MS_PER_DAY = 86_400_000;

export const RELATIVE_TIME_MINUTES_THRESHOLD = 60;   // Show minutes until 60 min
export const RELATIVE_TIME_HOURS_THRESHOLD = 24;     // Show hours until 24 hours
export const RELATIVE_TIME_DAYS_THRESHOLD = 7;       // Show days until 7 days

// =============================================================================
// API Defaults
// =============================================================================
// Default parameters for API calls.

export const DEFAULT_JOBS_LIST_LIMIT = 20;
```

**Step 2: Update index.ts**

Add to `frontend/src/config/index.ts`:

```typescript
export * from './timing';
```

**Step 3: Commit**

```bash
git add frontend/src/config/timing.ts frontend/src/config/index.ts
git commit -m "feat(config): add timing configuration constants"
```

---

## Task 18: Update AskPanel.tsx to Use Config

**Files:**
- Modify: `frontend/src/components/AskPanel.tsx:19-21` (remove CONFIDENCE_COLORS)

**Step 1: Run tests to verify baseline**

```bash
cd frontend && npm run test
```

Expected: All tests pass.

**Step 2: Update imports and remove inline constant**

In `frontend/src/components/AskPanel.tsx`:

Add import near top:
```typescript
import { CONFIDENCE_COLORS } from '../config';
```

Remove lines 19-22:
```typescript
const CONFIDENCE_COLORS = {
  high: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200',
  medium: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200',
  low: 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200',
} as const;
```

**Step 3: Run tests to verify**

```bash
npm run test
```

Expected: All tests pass.

**Step 4: Commit**

```bash
git add frontend/src/components/AskPanel.tsx
git commit -m "refactor(AskPanel): use config constants for confidence colors"
```

---

## Task 19: Update AppContext.tsx to Use Config

**Files:**
- Modify: `frontend/src/context/AppContext.tsx:41,48` (storage keys)
- Modify: `frontend/src/context/AppContext.tsx:185,190` (storage keys)

**Step 1: Run tests to verify baseline**

```bash
npm run test
```

Expected: All tests pass.

**Step 2: Update imports and storage key references**

In `frontend/src/context/AppContext.tsx`:

Add import near top:
```typescript
import { STORAGE_KEY_DARK_MODE, STORAGE_KEY_ASK_PANEL_OPEN } from '../config';
```

Replace all occurrences of:
- `'oya-dark-mode'` with `STORAGE_KEY_DARK_MODE`
- `'oya-ask-panel-open'` with `STORAGE_KEY_ASK_PANEL_OPEN`

**Step 3: Run tests to verify**

```bash
npm run test
```

Expected: All tests pass.

**Step 4: Commit**

```bash
git add frontend/src/context/AppContext.tsx
git commit -m "refactor(AppContext): use config constants for storage keys"
```

---

## Task 20: Update RightSidebar.tsx to Use Config

**Files:**
- Modify: `frontend/src/components/RightSidebar.tsx:9-11` (time constants)

**Step 1: Run tests to verify baseline**

```bash
npm run test
```

Expected: All tests pass.

**Step 2: Update imports and time calculations**

In `frontend/src/components/RightSidebar.tsx`:

Add import:
```typescript
import { MS_PER_MINUTE, MS_PER_HOUR, MS_PER_DAY } from '../config';
```

Replace:
```typescript
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);
```

With:
```typescript
  const diffMins = Math.floor(diffMs / MS_PER_MINUTE);
  const diffHours = Math.floor(diffMs / MS_PER_HOUR);
  const diffDays = Math.floor(diffMs / MS_PER_DAY);
```

**Step 3: Run tests to verify**

```bash
npm run test
```

Expected: All tests pass.

**Step 4: Commit**

```bash
git add frontend/src/components/RightSidebar.tsx
git commit -m "refactor(RightSidebar): use config constants for time calculations"
```

---

## Task 21: Update GenerationProgress.tsx to Use Config

**Files:**
- Modify: `frontend/src/components/GenerationProgress.tsx:32` (polling interval)

**Step 1: Run tests to verify baseline**

```bash
npm run test
```

Expected: All tests pass.

**Step 2: Update imports and interval**

In `frontend/src/components/GenerationProgress.tsx`:

Add import:
```typescript
import { ELAPSED_TIME_UPDATE_MS } from '../config';
```

Replace:
```typescript
    }, 1000);
```

With:
```typescript
    }, ELAPSED_TIME_UPDATE_MS);
```

**Step 3: Run tests to verify**

```bash
npm run test
```

Expected: All tests pass.

**Step 4: Commit**

```bash
git add frontend/src/components/GenerationProgress.tsx
git commit -m "refactor(GenerationProgress): use config constant for update interval"
```

---

## Task 22: Run Full Frontend Test Suite and Type Check

**Step 1: Run all tests**

```bash
cd frontend && npm run test
```

Expected: All 92+ tests pass.

**Step 2: Run type check and build**

```bash
npm run build
```

Expected: Build succeeds with no errors.

**Step 3: Commit if any cleanup needed**

If issues found, fix and commit.

---

## Task 23: Update CLAUDE.md

**Files:**
- Modify: `CLAUDE.md` (add Configuration Constants section)

**Step 1: Add configuration section to CLAUDE.md**

Add to the "Key Patterns" section in `CLAUDE.md`:

```markdown
### Configuration Constants

Hard-coded values that control application behavior should be extracted to config files, not scattered through the codebase. This makes tuning easier and documents what each value does.

**Backend:** `backend/src/oya/config/`
- `qa.py` - Q&A token budgets, confidence thresholds
- `generation.py` - LLM temperatures, chunking parameters
- `llm.py` - Default LLM client settings
- `search.py` - Result limits, prioritization, deduplication
- `files.py` - File size limits, concurrency

**Frontend:** `frontend/src/config/`
- `layout.ts` - Panel dimensions, z-index layers
- `qa.ts` - Confidence level colors
- `storage.ts` - localStorage keys
- `timing.ts` - Polling intervals, relative time thresholds

**What belongs in config:**
- Numeric limits (tokens, sizes, timeouts)
- Thresholds (confidence scores, time boundaries)
- Styling constants (colors, dimensions)
- Keys and identifiers (storage keys)

**What stays inline:**
- Tailwind utility classes
- System prompts (they're code, not config)
- Schema versions
- One-off string literals
```

**Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add configuration constants guidance to CLAUDE.md"
```

---

## Task 24: Final Verification

**Step 1: Run full backend tests**

```bash
cd backend && source .venv/bin/activate && pytest -v
```

Expected: All tests pass.

**Step 2: Run full frontend tests and build**

```bash
cd frontend && npm run test && npm run build
```

Expected: All tests pass, build succeeds.

**Step 3: Review git log**

```bash
git log --oneline -20
```

Verify all commits are present and well-formed.
