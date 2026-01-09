# Rename .coretechs to .oyawiki Design

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rename all references from `.coretechs` to `.oyawiki` throughout the codebase.

**Architecture:** Pure find-and-replace rename with no structural changes. The internal directory structure (wiki/, notes/, meta/, etc.) remains identical.

**Tech Stack:** Python backend, React frontend, SQLite database

---

## Scope of Changes

| Category | Files Affected | Changes |
|----------|---------------|---------|
| **Core config** | `config.py` | Property `coretechs_path` → `oyawiki_path`, path string |
| **File filter** | `file_filter.py` | Default excludes list |
| **Backend tests** | 7 test files | Path strings in test fixtures |
| **Documentation** | PRD, design docs, comments | String references |
| **Generated wiki** | `.coretechs/wiki/*` | Directory rename (content regenerates) |

---

## Task 1: Update Core Config

**Files:**
- Modify: `backend/src/oya/config.py`

**Changes:**
1. Rename property `coretechs_path` → `oyawiki_path`
2. Update path string `.coretechs` → `.oyawiki`
3. Update all properties that reference `coretechs_path` to use `oyawiki_path`
4. Update docstrings

---

## Task 2: Update File Filter

**Files:**
- Modify: `backend/src/oya/repo/file_filter.py`

**Changes:**
1. Update `DEFAULT_EXCLUDES` list:
   - `.coretechs/wiki` → `.oyawiki/wiki`
   - `.coretechs/meta` → `.oyawiki/meta`
   - `.coretechs/index` → `.oyawiki/index`
   - `.coretechs/cache` → `.oyawiki/cache`
   - `.coretechs/config` → `.oyawiki/config`
2. Update comment about `.coretechs/notes` → `.oyawiki/notes`
3. Update code comment about path patterns

---

## Task 3: Update Database Migrations

**Files:**
- Modify: `backend/src/oya/db/migrations.py`

**Changes:**
1. Update SQL comments referencing `.coretechs/wiki/` → `.oyawiki/wiki/`
2. Update SQL comments referencing `.coretechs/notes/` → `.oyawiki/notes/`

---

## Task 4: Update Service Docstrings

**Files:**
- Modify: `backend/src/oya/notes/service.py`
- Modify: `backend/src/oya/api/routers/notes.py`
- Modify: `backend/src/oya/generation/synthesis.py`

**Changes:**
1. Update docstring references from `.coretechs` to `.oyawiki`

---

## Task 5: Update Backend Tests

**Files:**
- Modify: `backend/tests/test_config.py`
- Modify: `backend/tests/test_file_filter.py`
- Modify: `backend/tests/test_notes_api.py`
- Modify: `backend/tests/test_notes_service.py`
- Modify: `backend/tests/test_search_api.py`
- Modify: `backend/tests/test_wiki_api.py`

**Changes:**
1. Replace all `.coretechs` path strings with `.oyawiki`
2. Replace `coretechs` variable names with `oyawiki` where applicable

---

## Task 6: Update Documentation

**Files:**
- Modify: `README.md`
- Modify: `TODO.md`
- Modify: `prds/oya-v1.md`
- Modify: `docs/plans/2026-01-08-oya-v1-design.md`
- Modify: `docs/plans/2026-01-08-oya-v1-implementation.md`
- Modify: `.kiro/steering/structure.md`
- Modify: `.kiro/steering/product.md`
- Modify: `.kiro/specs/bottom-up-generation/design.md`
- Modify: `.kiro/specs/bottom-up-generation/tasks.md`
- Modify: `.kiro/specs/bottom-up-generation/requirements.md`

**Changes:**
1. Replace all `.coretechs` references with `.oyawiki`

---

## Task 7: Rename Directory

**Commands:**
```bash
git mv .coretechs .oyawiki
```

**Notes:**
- This renames the directory and all contents in one git operation
- Generated wiki content inside will be overwritten on next regeneration

---

## Task 8: Run Tests

**Commands:**
```bash
cd backend && python -m pytest
```

**Expected:** All tests pass with new `.oyawiki` paths

---

## Task 9: Build Frontend

**Commands:**
```bash
cd frontend && npm run build
```

**Expected:** Build succeeds (frontend doesn't directly reference `.coretechs`)
