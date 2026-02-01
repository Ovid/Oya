# Dead Code Detection - Progress Summary

This document summarizes the current state of the dead code detection feature for handoff to the next Claude session.

## Reference Documents

- **Design:** `docs/plans/2026-01-30-type-annotation-tracking-design.md` - Describes the type annotation tracking approach to reduce false positives
- **Implementation Plan:** `docs/plans/2026-01-30-deadcode-detection.md` - Original 8-task implementation plan (completed)
- **Next Phase Design:** `docs/plans/2026-02-01-decorator-pattern-detection-design.md` - Decorator pattern detection to fix remaining false positives

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

## Decorator Pattern Detection - IMPLEMENTED

An accuracy report (2026-02-01) showed 94% false positive rate - 34 of 36 reported classes were actually used via FastAPI decorator arguments (`response_model=MyClass`).

**Status: IMPLEMENTED** (2026-02-01)

The decorator pattern detection was fully implemented following the design in `docs/plans/2026-02-01-decorator-pattern-detection-design.md`.

### What Was Implemented

1. **Pattern Registry** (`backend/src/oya/parsing/decorator_patterns.py`)
   - `ReferencePattern` dataclass for decorators that create type references
   - `EntryPointPattern` dataclass for decorators that mark entry points
   - Pre-configured patterns for FastAPI, pytest, Click, Celery, SQLAlchemy

2. **Base Parser Helpers** (`backend/src/oya/parsing/base.py`)
   - `_get_reference_patterns()` - returns patterns for parser's language
   - `_get_entry_point_patterns()` - returns entry point patterns
   - `_matches_decorator_pattern()` - checks decorator against pattern

3. **Python Parser AST Extraction** (`backend/src/oya/parsing/python_parser.py`)
   - `_extract_decorator_info()` - extracts decorator_name/object_name from AST
   - `_extract_decorator_argument_values()` - gets keyword argument values
   - `_process_decorator()` - extracts references and entry point status
   - Modified `_parse_function()` to process decorators and set `is_entry_point` metadata
   - Added `DECORATOR_ARGUMENT` to `ReferenceType` enum

4. **Graph Builder** (`backend/src/oya/graph/builder.py`)
   - Propagates `is_entry_point` metadata from symbols to graph nodes

5. **Dead Code Analyzer** (`backend/src/oya/generation/deadcode.py`)
   - Skips symbols with `is_entry_point=True` in analysis

6. **Documentation** (`docs/language-customization/`)
   - `README.md` - index of language customization guides
   - `extending-decorator-patterns.md` - how to add patterns for new frameworks

### Files Modified

| File | Status |
|------|--------|
| `backend/src/oya/parsing/decorator_patterns.py` | Created |
| `backend/src/oya/parsing/base.py` | Modified |
| `backend/src/oya/parsing/python_parser.py` | Modified |
| `backend/src/oya/parsing/models.py` | Modified (added DECORATOR_ARGUMENT) |
| `backend/src/oya/graph/builder.py` | Modified |
| `backend/src/oya/generation/deadcode.py` | Modified |
| `docs/language-customization/README.md` | Created |
| `docs/language-customization/extending-decorator-patterns.md` | Created |

### Test Coverage

- `tests/test_decorator_patterns.py` - 6 tests for pattern registry
- `tests/test_base_parser.py` - 7 tests for pattern matching helpers
- `tests/test_python_parser.py` - 6 new tests for decorator extraction
- `tests/test_graph_builder.py` - 1 new test for is_entry_point propagation
- `tests/test_deadcode.py` - 1 new test for entry point filtering

All 1112 backend tests pass.

### Next Steps

1. **Run full wiki regeneration** on a test repository to rebuild the graph with the new parser logic
2. **Verify false positive reduction** - FastAPI route handlers and response models should no longer appear as dead code
3. **Consider TypeScript patterns** - NestJS decorators, Jest test decorators, etc.
