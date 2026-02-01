# Dead Code Detection - Progress Summary

This document summarizes the current state of the dead code detection feature for handoff to the next Claude session.

## Reference Documents

- **Design:** `docs/plans/2026-01-30-type-annotation-tracking-design.md` - Describes the type annotation tracking approach to reduce false positives
- **Implementation Plan:** `docs/plans/2026-01-30-deadcode-detection.md` - Original 8-task implementation plan (completed)

## Current Branch

`ovid/find-dead-code`

## What Was Implemented

### Initial Implementation (per the plan)

The 8-task plan was fully implemented:
1. DeadcodeReport and UnusedSymbol data models
2. Exclusion pattern matching (test functions, dunders, entry points, private)
3. Core `analyze_deadcode()` function
4. Markdown page generation with cautious language
5. Orchestrator integration
6. Wiki navigation (automatic)
7. Full test suite passes (1091 tests)
8. Integration tested

### Post-Plan Fixes

After initial implementation, many false positives remained. Two additional fixes were applied:

#### Fix 1: Type Annotation Scope Bug (commit d8d6de7)

**Problem:** Type annotation references were created with wrong source scope. References used `file_path` (e.g., `repos.py`) but graph nodes use `file_path::symbol_name` (e.g., `repos.py::create_repo`). The graph builder's `has_node()` check failed, so edges weren't created.

**Solution:**
- `python_parser.py`: Build method_to_class map, compute proper scope (`file_path::ClassName.method_name` for methods, `file_path::function_name` for functions)
- `typescript_parser.py`: Pass already-computed scope to `_extract_type_annotation_references()`

#### Fix 2: Test Code Filtering (commit 939c036)

**Problem:** Code only called by tests appeared "used" when it's effectively dead from a production perspective.

**Solution:**
- Added `is_test_file()` with language-agnostic patterns:
  - Files in `test/`, `tests/`, `__tests__/`, `spec/`, `specs/` directories
  - Files named `test_*`, `*_test.*`, `*.test.*`, `*.spec.*`, `*_spec.*`
- Modified `analyze_deadcode()`:
  - Skip symbols in test files (don't report test code as dead)
  - Skip edges from test files (test calls don't count as "usage")

## Files Modified (Beyond Original Plan)

| File | Changes |
|------|---------|
| `backend/src/oya/parsing/models.py` | Added `TYPE_ANNOTATION` to ReferenceType enum |
| `backend/src/oya/parsing/python_parser.py` | Added type annotation extraction with correct scope |
| `backend/src/oya/parsing/typescript_parser.py` | Added type annotation extraction with correct scope |
| `backend/src/oya/generation/deadcode.py` | Added `is_test_file()`, filter test code in analysis |

## What Still Needs Testing

After the scope fix, a **full wiki regeneration** is required to rebuild the graph with the new parser logic. Incremental regeneration won't re-parse unchanged files.

After full regen, verify that:
- Pydantic models used as type annotations (e.g., `CreateRepoRequest`) no longer appear as dead code
- Test classes no longer appear in the report
- API schemas used in FastAPI route handlers are properly connected

## Known Limitations

Even with these fixes, false positives will remain for:
- Route handlers (decorator-based registration, not calls)
- Event listeners and plugin hooks
- Reflection-based calls (`getattr`, `importlib`)
- Cross-language calls

The page content is deliberately cautious, framing results as "review candidates" rather than confirmed dead code.
