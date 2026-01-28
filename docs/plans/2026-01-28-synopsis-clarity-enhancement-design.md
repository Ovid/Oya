# Synopsis Clarity Enhancement Design

**Date:** 2026-01-28
**Status:** Design Complete

## Overview

Ensure synopses help humans understand how to use a module by showing clear import + usage patterns. The current call-site synopsis extraction can show confusing snippets (e.g., internal function definitions rather than external usage).

## Problem

The deps.py wiki page showed a synopsis containing the function definition from *within* deps.py:

```python
def get_active_repo_paths() -> RepoPaths:
    repo = get_active_repo()
    ...
```

This doesn't help a reader understand how to *use* deps.py. A useful synopsis would show:

```python
from oya.api.deps import get_active_repo_paths, get_db

paths = get_active_repo_paths()
db = get_db()
```

## Design

### Tier 1: Human-Written Synopses

**No changes.** Use as-is. Trust the author to provide clear documentation.

These come from:
- Perl POD `SYNOPSIS` sections
- Python docstrings with `Example:` or `Usage:` sections
- Similar patterns in other languages

### Tier 2: Call-Site Extracted Synopses

**Change:** Prefer callers from *different* files over same-file callers.

Current behavior:
- `select_best_call_site()` prefers production over test files
- Does not distinguish internal vs external callers

New behavior:
1. Prefer callers from **different files** (external usage)
2. Fall back to **same-file callers** only if no external callers exist
3. Fall back to **AI-generated** if no callers at all

This ensures the synopsis shows how *other* code imports and uses the module, not internal implementation details.

### Tier 3: AI-Generated Synopses

**Change:** Update the prompt to encourage including import statements.

Current prompt excerpt:
```
**You MUST generate a caller-perspective code example** showing:
- How to import/use this file's public API
- The most common/important use case
```

Updated prompt:
```
**You MUST generate a caller-perspective code example** showing:
- How to import/use this file's public API
- The most common/important use case
- Include the import statement when it helps clarify what's being used
```

Trust AI judgment on when imports add clarity vs. when they're redundant.

## Implementation Tasks

1. **Update `select_best_call_site()` in `snippets.py`**
   - Add logic to prefer external callers (different file) over internal callers (same file)
   - Sort candidates: external production > external test > internal production > internal test

2. **Update `SYNOPSIS_INSTRUCTIONS_WITHOUT_EXTRACTED` in `prompts.py`**
   - Add guidance about including import statements when helpful

3. **Add tests for external caller preference**

## Success Criteria

1. Call-site synopses prefer external callers that show import + usage patterns
2. Internal callers are only used when no external callers exist
3. AI-generated synopses include imports when the AI judges it helpful
4. Human-written synopses remain unchanged
