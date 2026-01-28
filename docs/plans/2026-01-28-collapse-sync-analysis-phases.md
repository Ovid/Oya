# Collapse Sync & Analysis into Single "Sync" Phase — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Merge the "syncing" and "analysis" generation phases into a single "Sync" phase from the user's perspective.

**Architecture:** The backend orchestrator still runs git sync and file analysis as separate internal steps. The change is purely presentational: the `progress_callback` in `repos.py` remaps the orchestrator's `"analysis"` phase to `"syncing"`, and all phase numbers shift down by 1 (total: 8 instead of 9). Frontend removes the `analysis` entry and renames `syncing` display to "Sync".

**Tech Stack:** Python (FastAPI backend), TypeScript (React frontend), pytest

---

### Task 1: Update backend tests to expect 8 phases with no "analysis" phase

**Files:**
- Modify: `backend/tests/test_jobs_api.py`

**Step 1: Update tests to expect the new phase mapping (RED)**

In `test_jobs_api.py`, update `TestPhaseOrderConsistency` to reflect the merged phases. Every `expected_phase_numbers` dict loses `"analysis"` and renumbers subsequent phases down by 1. The total phases test expects 8 instead of 9.

Also update the `workspace_with_db` fixture: it currently inserts `current_phase = 'analysis'` — change to `'syncing'` (since analysis no longer exists as a user-visible phase). Update `test_get_job_status` assertion to match.

```python
# workspace_with_db fixture (line 18):
# Change: current_phase from 'analysis' to 'syncing'
VALUES ('test-job-123', 'full', 'running', datetime('now'), 'syncing', 6)

# test_get_job_status (line 44):
assert data["current_phase"] == "syncing"

# test_phase_numbers_match_bottom_up_order (lines 113-123):
expected_phase_numbers = {
    "syncing": 1,
    "files": 2,
    "directories": 3,
    "synthesis": 4,
    "architecture": 5,
    "overview": 6,
    "workflows": 7,
    "indexing": 8,
}

# test_total_phases_is_nine → rename to test_total_phases_is_eight (lines 138-148):
def test_total_phases_is_eight(self):
    """Total phases should be 8 for the bottom-up pipeline (including syncing and indexing)."""
    from oya.api.routers import repos
    import inspect

    source = inspect.getsource(repos.init_repo)

    # Check that total_phases is 8
    assert '"full", "pending", 8' in source or "'full', 'pending', 8" in source, (
        "Total phases should be 8 in init_repo"
    )

# test_files_before_architecture (lines 152-162):
expected_phase_numbers = {
    "syncing": 1,
    "files": 2,
    "directories": 3,
    "synthesis": 4,
    "architecture": 5,
    "overview": 6,
    "workflows": 7,
    "indexing": 8,
}

# test_synthesis_before_architecture_and_overview (lines 170-179):
expected_phase_numbers = {
    "syncing": 1,
    "files": 2,
    "directories": 3,
    "synthesis": 4,
    "architecture": 5,
    "overview": 6,
    "workflows": 7,
}

# test_phase_order_matches_orchestrator_enum: NO CHANGE (it tests the enum, which is unchanged)
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_jobs_api.py -v`
Expected: Multiple failures — tests expect 8-phase mapping but code still has 9.

**Step 3: Commit the red tests**

```bash
git add backend/tests/test_jobs_api.py
git commit -m "test: update phase order tests to expect 8 phases (no separate analysis)"
```

---

### Task 2: Update backend implementation to merge syncing and analysis

**Files:**
- Modify: `backend/src/oya/api/routers/repos.py:364-467`

**Step 1: Update `repos.py` to collapse phases (GREEN)**

Three changes in `repos.py`:

**Change A — `init_repo` total_phases (line 372):** Change `9` to `8`. Update the comment on lines 365-366.

```python
# (8 phases: sync, files, directories, synthesis, architecture,
# overview, workflows, indexing)
db.execute(
    """
    INSERT INTO generations (id, type, status, started_at, total_phases)
    VALUES (?, ?, ?, datetime('now'), ?)
    """,
    (job_id, "full", "pending", 8),
)
```

**Change B — `_run_generation` phase_numbers (lines 410-423):** Remove `"analysis"`, renumber everything down by 1.

```python
# Phase number mapping for progress tracking (bottom-up approach)
# Order: Sync → Files → Directories → Synthesis → Architecture →
# Overview → Workflows → Indexing
phase_numbers = {
    "syncing": 1,
    "files": 2,
    "directories": 3,
    "synthesis": 4,
    "architecture": 5,
    "overview": 6,
    "workflows": 7,
    "indexing": 8,
}
```

**Change C — `progress_callback` (lines 425-438):** Remap `"analysis"` to `"syncing"` so the DB stores `"1:syncing"` when the orchestrator reports analysis progress.

```python
async def progress_callback(progress: GenerationProgress) -> None:
    """Update database with current progress."""
    phase_name = progress.phase.value
    # Analysis is reported as "syncing" to the user (single "Sync" phase)
    if phase_name == "analysis":
        phase_name = "syncing"
    phase_num = phase_numbers.get(phase_name, 0)
    db.execute(
        """
        UPDATE generations
        SET current_phase = ?, status = 'running',
            current_step = ?, total_steps = ?
        WHERE id = ?
        """,
        (f"{phase_num}:{phase_name}", progress.step, progress.total_steps, job_id),
    )
    db.commit()
```

**Change D — Initial syncing phase (line 447):** Change `'0:syncing'` to `'1:syncing'` since syncing is now phase 1 (not a "phase 0" prefix).

```python
db.execute(
    "UPDATE generations SET status = 'running', current_phase = '1:syncing' WHERE id = ?",
    (job_id,),
)
```

**Change E — Remove `'0:starting'` intermediate (lines 462-467):** Delete the `'0:starting'` update entirely. The phase stays at `'1:syncing'` from the git sync through the orchestrator's analysis phase.

Delete these lines:
```python
# Update status to starting (after sync)
db.execute(
    "UPDATE generations SET current_phase = '0:starting' WHERE id = ?",
    (job_id,),
)
db.commit()
```

**Change F — Full-regen reconnect (line 481-484):** Change `total_phases` from `9` to `8`, and `current_phase` from `'0:starting'` to `'1:syncing'`.

```python
db.execute(
    """
    INSERT INTO generations (id, type, status, started_at, total_phases, current_phase)
    VALUES (?, ?, ?, datetime('now'), ?, '1:syncing')
    """,
    (job_id, "full", "running", 8),
)
```

**Step 2: Run tests to verify they pass**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_jobs_api.py -v`
Expected: All pass.

**Step 3: Commit**

```bash
git add backend/src/oya/api/routers/repos.py
git commit -m "feat: merge syncing and analysis into single Sync phase (8 total)"
```

---

### Task 3: Update remaining backend tests that reference 9 phases or `0:starting`

**Files:**
- Modify: `backend/tests/test_sse_streaming.py:180`
- Modify: `backend/tests/test_reconnect_db.py:276,320`

**Step 1: Update test data (GREEN)**

In `test_sse_streaming.py` line 180, change `9` to `8` and `'0:starting'` to `'1:syncing'`:

```sql
VALUES ('promo-stream-job', 'full', 'running', datetime('now'), 8, '1:syncing')
```

In `test_reconnect_db.py` line 276, change `9` to `8` and `'0:starting'` to `'1:syncing'`:

```sql
VALUES ('stale-job', 'full', 'running', datetime('now'), 8, '1:syncing')
```

In `test_reconnect_db.py` line 320, same change:

```sql
VALUES ('fixed-job', 'full', 'running', datetime('now'), 8, '1:syncing')
```

**Step 2: Run all backend tests to verify nothing is broken**

Run: `cd backend && source .venv/bin/activate && pytest -v`
Expected: All pass.

**Step 3: Commit**

```bash
git add backend/tests/test_sse_streaming.py backend/tests/test_reconnect_db.py
git commit -m "test: update SSE and reconnect tests for 8-phase pipeline"
```

---

### Task 4: Update frontend phase constants

**Files:**
- Modify: `frontend/src/components/generationConstants.ts`

**Step 1: Run frontend tests to establish baseline**

Run: `cd frontend && npm run test`
Expected: All pass.

**Step 2: Update constants (GREEN)**

Remove the `analysis` entry from `PHASES`, rename `syncing` display to "Sync", update description, remove `analysis` from `PHASE_ORDER`, update comment.

```typescript
export const PHASES: Record<string, PhaseInfo> = {
  starting: { name: 'Starting', description: 'Initializing generation...' },
  syncing: { name: 'Sync', description: 'Syncing repository and scanning code...' },
  files: { name: 'Files', description: 'Generating file-level documentation...' },
  directories: { name: 'Directories', description: 'Generating directory documentation...' },
  synthesis: { name: 'Synthesis', description: 'Synthesizing codebase understanding...' },
  architecture: { name: 'Architecture', description: 'Analyzing and documenting architecture...' },
  overview: { name: 'Overview', description: 'Generating project overview page...' },
  workflows: { name: 'Workflows', description: 'Discovering and documenting workflows...' },
  indexing: { name: 'Indexing', description: 'Indexing content for search and Q&A...' },
}

// Ordered list of phases for progress display (bottom-up approach)
// Order: Sync → Files → Directories → Synthesis → Architecture → Overview → Workflows → Indexing
export const PHASE_ORDER = [
  'syncing',
  'files',
  'directories',
  'synthesis',
  'architecture',
  'overview',
  'workflows',
  'indexing',
]
```

**Step 3: Run frontend tests**

Run: `cd frontend && npm run test`
Expected: All pass.

**Step 4: Commit**

```bash
git add frontend/src/components/generationConstants.ts
git commit -m "feat: show Sync as single phase, remove separate Analysis phase"
```

---

### Task 5: Remove TODO item and remove `starting` from frontend PHASES

**Files:**
- Modify: `TODO.md:5`
- Modify: `frontend/src/components/generationConstants.ts:14`

**Step 1: Remove completed TODO**

Delete line 5 from `TODO.md`:

```
* Should compress syncing and analysis into a single phase
```

**Step 2: Remove `starting` from PHASES**

The `starting` entry in PHASES was only needed as a transitional state between syncing and analysis. Since those are now one phase, `starting` is no longer set by the backend. Remove it:

```typescript
export const PHASES: Record<string, PhaseInfo> = {
  syncing: { name: 'Sync', description: 'Syncing repository and scanning code...' },
  files: { name: 'Files', description: 'Generating file-level documentation...' },
  // ... rest unchanged
}
```

**Step 3: Run frontend tests to confirm nothing breaks**

Run: `cd frontend && npm run test`
Expected: All pass.

**Step 4: Commit**

```bash
git add TODO.md frontend/src/components/generationConstants.ts
git commit -m "chore: remove completed TODO, remove unused 'starting' phase"
```
