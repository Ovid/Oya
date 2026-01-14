# Phase 1 Analysis Improvements - Design Document

## Overview

Fix 5 limitations in Phase 1 Analysis (the code scanning phase that runs before LLM generation). These issues were identified in `docs/notes/phase-1-analysis.md`.

**Out of scope:** Limited language support, incremental analysis.

## Fix 1: Parse Error Recovery

**Problem:** Bare `except Exception: pass` hides real bugs and provides no feedback. Currently hiding 3 attribute bugs (`result.symbols` should be `result.file.symbols`, etc.).

**Solution:**
- Check `ParseResult.ok` to detect parse failures
- Fall back to regex-based `FallbackParser` for partial symbol extraction
- Track parse errors in analysis results for visibility
- Fix attribute bugs: `result.file.symbols`, `symbol.symbol_type`, `symbol.start_line`

**Behavior:**
- AST parse succeeds: Use full symbol data
- AST parse fails: Log error, use fallback regex parser for partial data
- Parse errors included in returned analysis dict

## Fix 2: Smarter File Filtering

**Problem:** Hard 500KB limit excludes large source files while including useless minified bundles.

**Solution:**
- Add default excludes for known non-source patterns
- Add content-based minified detection via average line length
- Make threshold configurable

**New default excludes:**
```
*.min.js, *.min.css, *.bundle.js, *.chunk.js, *.map
package-lock.json, yarn.lock, pnpm-lock.yaml
Cargo.lock, poetry.lock, Gemfile.lock, composer.lock
```

**New config:** `MINIFIED_AVG_LINE_LENGTH = 500`

**Detection logic:** Sample first 20 lines, if average length > threshold, treat as minified.

## Fix 3: Granular Progress Reporting

**Problem:** Progress updates every 10 files regardless of repo size. File/directory generation waits for entire batch before reporting.

**Solution:**
- Analysis phase: Make interval configurable (default 1 for per-file updates)
- File/Directory phases: Switch from `asyncio.gather` to `asyncio.as_completed` for per-file progress

**New configs:**
- `PROGRESS_REPORT_INTERVAL = 1`
- `PARALLEL_LIMIT_DEFAULT = 10`

**Behavior:** Progress bar updates as each file completes, not after each batch.

## Fix 4: Use Parser Imports

**Problem:** `_extract_imports()` uses string matching on first 50 lines, duplicating work parsers already do properly.

**Solution:**
- Preserve `ParsedFile.imports` in analysis results as `file_imports` dict
- Delete redundant `_extract_imports()` method
- File generation uses pre-extracted imports

**Benefits:**
- Proper AST/tree-sitter parsing instead of string matching
- Extracts imports from entire file, not just first 50 lines
- No duplicate parsing work

## Fix 5: Keep ParsedSymbol Objects

**Problem:** Converting `ParsedSymbol` to dicts loses type safety and IDE support.

**Solution:**
- Pass `ParsedSymbol` objects instead of converting to dicts
- Store file path in `symbol.metadata["file"]` for filtering
- Update consumer locations to use attributes

**Consumer updates needed:**
- `orchestrator.py` - symbol filtering
- `workflows.py` - `symbol_type`, `decorators`, `name`
- `chunking.py` - `start_line`, `end_line`

## Files to Modify

| File | Changes |
|------|---------|
| `backend/src/oya/constants/files.py` | Add `MINIFIED_AVG_LINE_LENGTH` |
| `backend/src/oya/constants/generation.py` | Add `PROGRESS_REPORT_INTERVAL`, `PARALLEL_LIMIT_DEFAULT` |
| `backend/src/oya/repo/file_filter.py` | New excludes, `_is_minified()` method |
| `backend/src/oya/generation/orchestrator.py` | Fixes 1, 3, 4, 5 - main changes |
| `backend/src/oya/generation/workflows.py` | Fix 5 - symbol attribute access |
| `backend/src/oya/generation/chunking.py` | Fix 5 - symbol attribute access |

## Testing Strategy

- Existing tests should continue to pass
- Add test for parse error recovery (file with syntax error still yields partial symbols)
- Add test for minified file detection
- Verify progress callbacks fire per-file, not per-batch
