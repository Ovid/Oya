# Call-Site Synopses Design

**Date:** 2026-01-28
**Status:** Design Complete

## Overview

Enhance file wiki page synopses by extracting real code snippets from the codebase showing how each file's public API is actually called. Instead of AI-generated examples, show developers real usage patterns pulled from production code.

## Goals

1. Show developers how code is *actually* used in this codebase
2. Extract ~20-line workflow snippets with imports, setup, call, and result handling
3. Prioritize production code over test code
4. Detect and note when no internal callers exist
5. Integrate with existing synopsis system (docs > call-site > AI)

## Synopsis Priority Order

```
1. Author-written documentation (Perl POD, Python docstrings, Rust doc examples)
   → Use verbatim, as implemented in current synopsis feature

2. Call-site extraction (this design)
   → Find real callers in the codebase
   → Extract representative code snippet
   → Note other caller locations

3. AI-generated synopsis
   → When no docs and no callers found
   → Add note: "No internal callers found in this codebase"
```

## Data Availability

The infrastructure already exists:

- **Parsers** extract `Reference` objects with exact `line` numbers for each call
- **Graph builder** preserves this as edge data: `source`, `target`, `line`
- **Graph is built in Analysis phase**, before Files phase runs
- All data needed is available during file page generation

No new generation phase required.

## Component Design

### 1. Graph Query Helper

**File:** `backend/src/oya/graph/query.py`

```python
@dataclass
class CallSite:
    caller_file: str      # File containing the call
    caller_symbol: str    # Function/method making the call
    line: int             # Exact line of the call
    target_symbol: str    # What's being called

def get_call_sites(graph: nx.DiGraph, target_file: str) -> list[CallSite]:
    """Find all call sites targeting symbols defined in a file.

    Args:
        graph: The code graph with edges containing line numbers
        target_file: Path to the file whose callers we want

    Returns:
        List of CallSite objects with file, symbol, and line info
    """
```

### 2. Snippet Extractor

**File:** `backend/src/oya/generation/snippets.py`

```python
def extract_call_snippet(
    file_path: str,
    call_line: int,
    file_contents: dict[str, str],
    context_before: int = 10,
    context_after: int = 10
) -> str:
    """Extract code context around a call site.

    Expansion logic:
    - Start at call_line, expand up to context_before lines above
    - Expand up to context_after lines below
    - Stop at function/class boundaries if encountered
    - Include relevant imports at file top if referenced

    Returns:
        Code snippet as string, ready for markdown code block
    """

def is_test_file(file_path: str) -> bool:
    """Check if a file is a test file.

    Patterns:
    - test_*.py, *_test.py
    - tests/, test/, spec/
    - conftest.py, fixtures.py
    """
```

### 3. Call Site Selector

**File:** `backend/src/oya/generation/snippets.py`

```python
def select_best_call_site(
    call_sites: list[CallSite],
    file_contents: dict[str, str]
) -> tuple[CallSite | None, list[CallSite]]:
    """Select the best call site for synopsis, return others for reference.

    Selection criteria:
    1. Filter out test files
    2. Prefer simpler call patterns (fewer arguments)
    3. Prefer different files over multiple calls in same file

    Returns:
        (best_site, other_sites) - best_site is None if no production callers
    """
```

### 4. Synopsis Generator Integration

**File:** `backend/src/oya/generation/file.py`

Update `FileGenerator.generate()`:

```python
async def generate(
    self,
    file_path: str,
    content: str,
    symbols: list[dict],
    imports: list[str],
    architecture_summary: str = "",
    notes: list[dict] | None = None,
    synopsis: str | None = None,           # Existing: from docs
    call_sites: list[CallSite] | None = None,  # New: from graph
    file_contents: dict[str, str] | None = None  # New: for snippet extraction
) -> WikiPage:
```

### 5. Prompt Template Updates

**File:** `backend/src/oya/generation/prompts.py`

New constant for call-site synopses:

```python
SYNOPSIS_INSTRUCTIONS_WITH_CALL_SITE = """
A real usage example from this codebase has been extracted and is shown above.

**Include it verbatim in the Synopsis section**, formatted as:

## 2. Synopsis

**From `{caller_file}` line {line}:**
```{language}
{snippet}
```

{other_callers_note}

Do NOT modify the extracted code. It shows actual usage in this codebase.
"""

SYNOPSIS_NO_CALLERS_NOTE = """
**Note:** No internal callers found in this codebase. This may be:
- A public API intended for external consumers
- An entry point (CLI command, API route, etc.)
- Potentially unused code
"""
```

## Orchestrator Integration

**File:** `backend/src/oya/generation/orchestrator.py`

In `_run_files()` phase:

```python
# After graph is available, before file generation loop:
graph = self._get_or_build_graph()

async def generate_file_page(file_path, ...):
    # Existing: get synopsis from parsed file
    synopsis = parsed_file.synopsis

    # New: if no doc synopsis, try call-site extraction
    call_site_synopsis = None
    if not synopsis:
        call_sites = get_call_sites(graph, file_path)
        best_site, other_sites = select_best_call_site(call_sites, file_contents)
        if best_site:
            call_site_synopsis = extract_call_snippet(
                best_site.caller_file,
                best_site.line,
                file_contents
            )

    # Pass to file generator
    result = await self.file_generator.generate(
        file_path=file_path,
        content=content,
        synopsis=synopsis,
        call_site_synopsis=call_site_synopsis,
        other_callers=other_sites,
        ...
    )
```

## Presentation Format

### With Call-Site Synopsis

```markdown
## 2. Synopsis

**From `orchestrator.py` line 1432:**
```python
from oya.generation.file import FileGenerator

generator = FileGenerator(llm_client, wiki_dir)
result = await generator.generate(
    file_path=parsed_file.path,
    content=file_contents[parsed_file.path],
    synopsis=parsed_file.synopsis
)
wiki_pages.append(result)
```

Also called from: `integration.py:89`, `cli/generate.py:156`
```

### With No Callers

```markdown
## 2. Synopsis

**AI-Generated Synopsis**

```python
from mylib.utils import format_date

formatted = format_date(datetime.now(), locale="en-US")
```

**Note:** No internal callers found in this codebase.
```

## Test File Handling

Test files are excluded from primary synopsis selection because:
- Test code often uses mocks: `frobnicate(database_mock, sql, params)`
- Test fixtures don't represent real usage patterns
- Test assertions clutter the example

**Detection patterns:**
- `test_*.py`, `*_test.py`, `*_spec.py`
- Paths containing: `tests/`, `test/`, `spec/`, `__tests__/`
- Special files: `conftest.py`, `fixtures.py`

**Fallback behavior:**
If ONLY test callers exist, show test example with note: "Only test usage found in this codebase."

## Edge Cases

### No Public API

Files with only private functions (all `_prefixed`) may have no meaningful synopsis. Let LLM decide whether to include a synopsis or note "This file has no public API."

### Circular Dependencies

If file A calls file B and file B calls file A, both can have call-site synopses. No special handling needed.

### Large Number of Callers

If a utility function has 50+ callers:
- Select 1 best example for synopsis
- List up to 5 other callers by name
- Note "and N more callers" if > 5

### Binary/Config Files

Non-code files (images, JSON, YAML) don't have call sites. Use existing logic (AI-generated or "no public API").

## Implementation Tasks

1. Add `CallSite` dataclass and `get_call_sites()` to `graph/query.py`
2. Create `snippets.py` module with extraction and selection logic
3. Add test file detection
4. Update `FileGenerator` signature
5. Add new prompt template constants
6. Wire up in orchestrator's file generation loop
7. Update existing synopsis tests
8. Add integration tests for call-site extraction

## Success Criteria

1. File pages show real code snippets when callers exist
2. Test files are excluded from primary synopsis
3. Falls back gracefully to AI-generated when no callers
4. "No internal callers" note appears when appropriate
5. Performance: graph query adds minimal overhead to file generation
6. Existing doc-based synopses continue to work (they take priority)
