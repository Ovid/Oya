# Config Extraction Design

Extract hard-coded constants from frontend and backend into organized config files for easier tuning, documentation, and DRY principles.

## Backend Config Structure

**Location:** `backend/src/oya/config/`

### `qa.py`

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

### `generation.py`

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
DEFAULT_TEMPERATURE = 0.7

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

### `llm.py`

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

### `search.py`

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

### `files.py`

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

### `__init__.py`

```python
"""Configuration constants.

Re-exports all config for convenient importing:
    from oya.config import MAX_CONTEXT_TOKENS, SYNTHESIS_TEMPERATURE
"""

from oya.config.qa import *
from oya.config.generation import *
from oya.config.llm import *
from oya.config.search import *
from oya.config.files import *
```

## Frontend Config Structure

**Location:** `frontend/src/config/`

### `layout.ts`

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

### `qa.ts`

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

### `storage.ts`

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

### `timing.ts`

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

### `index.ts`

```typescript
/**
 * Configuration constants.
 *
 * Re-exports all config for convenient importing:
 *     import { SIDEBAR_WIDTH, CONFIDENCE_COLORS } from '../config';
 */

export * from './layout';
export * from './qa';
export * from './storage';
export * from './timing';
```

## CLAUDE.md Update

Add to the "Key Patterns" section:

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

## Implementation Notes

1. Create config directories and files
2. Update imports in source files to use new config locations
3. Remove inline constants that have been extracted
4. Update CLAUDE.md with the new guidance
5. Run tests to verify nothing broke
