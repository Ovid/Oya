# Git Sync Before Generation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Automatically sync repositories to the latest default branch before wiki generation.

**Architecture:** Add new sync functions to `git_operations.py`, call them at the start of `_run_generation()` in `repos.py`, and update frontend to display syncing phase. All failures abort generation with user-friendly error messages.

**Tech Stack:** Python (subprocess for git commands), FastAPI (backend), React/TypeScript (frontend)

---

## Task 1: Add GitSyncError Exception

**Files:**
- Modify: `backend/src/oya/repo/git_operations.py:1-26`
- Test: `backend/tests/repo/test_git_operations.py`

**Step 1: Write the failing test**

Add to `backend/tests/repo/test_git_operations.py`:

```python
from oya.repo.git_operations import (
    GitCloneError,
    GitPullError,
    GitSyncError,  # New import
    clone_repo,
    get_remote_url,
    pull_repo,
)


def test_git_sync_error_has_message_and_original_error():
    """GitSyncError stores message and optional original error."""
    error = GitSyncError("User message", original_error="Raw stderr")
    assert error.message == "User message"
    assert error.original_error == "Raw stderr"
    assert str(error) == "User message"
```

**Step 2: Run test to verify it fails**

Run: `pytest backend/tests/repo/test_git_operations.py::test_git_sync_error_has_message_and_original_error -v`

Expected: FAIL with ImportError (GitSyncError not defined)

**Step 3: Write minimal implementation**

Add to `backend/src/oya/repo/git_operations.py` after `GitPullError` class (around line 26):

```python
class GitSyncError(Exception):
    """Error during git sync operation."""

    def __init__(self, message: str, original_error: Optional[str] = None):
        self.message = message
        self.original_error = original_error
        super().__init__(message)
```

**Step 4: Run test to verify it passes**

Run: `pytest backend/tests/repo/test_git_operations.py::test_git_sync_error_has_message_and_original_error -v`

Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/oya/repo/git_operations.py backend/tests/repo/test_git_operations.py
git commit -m "feat: add GitSyncError exception class"
```

---

## Task 2: Add check_working_directory_clean Function

**Files:**
- Modify: `backend/src/oya/repo/git_operations.py`
- Test: `backend/tests/repo/test_git_operations.py`

**Step 1: Write failing tests**

Add to `backend/tests/repo/test_git_operations.py`:

```python
from oya.repo.git_operations import (
    GitCloneError,
    GitPullError,
    GitSyncError,
    check_working_directory_clean,  # New import
    clone_repo,
    get_remote_url,
    pull_repo,
)


def test_check_working_directory_clean_passes_for_clean_repo(tmp_path, source_repo):
    """Clean repo passes working directory check."""
    dest = tmp_path / "dest"
    clone_repo(str(source_repo), dest)
    # Should not raise
    check_working_directory_clean(dest)


def test_check_working_directory_clean_fails_for_dirty_repo(tmp_path, source_repo):
    """Dirty repo raises GitSyncError with path in message."""
    dest = tmp_path / "dest"
    clone_repo(str(source_repo), dest)

    # Make repo dirty with uncommitted changes
    (dest / "dirty_file.txt").write_text("uncommitted content")

    with pytest.raises(GitSyncError) as exc_info:
        check_working_directory_clean(dest)

    assert str(dest) in exc_info.value.message
    assert "uncommitted changes" in exc_info.value.message.lower()
```

**Step 2: Run tests to verify they fail**

Run: `pytest backend/tests/repo/test_git_operations.py -k "check_working_directory" -v`

Expected: FAIL with ImportError

**Step 3: Write minimal implementation**

Add to `backend/src/oya/repo/git_operations.py` after the exception classes:

```python
def check_working_directory_clean(repo_path: Path) -> None:
    """
    Verify no uncommitted changes exist.

    Args:
        repo_path: Path to the git repository

    Raises:
        GitSyncError: If working directory has uncommitted changes
    """
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=repo_path,
        capture_output=True,
        text=True,
    )

    if result.stdout.strip():
        raise GitSyncError(
            f"Repository has uncommitted changes at `{repo_path}`. "
            "Oya manages this repository automatically—please don't modify files directly. "
            "To reset, delete that folder and regenerate."
        )
```

**Step 4: Run tests to verify they pass**

Run: `pytest backend/tests/repo/test_git_operations.py -k "check_working_directory" -v`

Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/oya/repo/git_operations.py backend/tests/repo/test_git_operations.py
git commit -m "feat: add check_working_directory_clean function"
```

---

## Task 3: Add get_default_branch Function

**Files:**
- Modify: `backend/src/oya/repo/git_operations.py`
- Test: `backend/tests/repo/test_git_operations.py`

**Step 1: Write failing tests**

Add to `backend/tests/repo/test_git_operations.py`:

```python
from oya.repo.git_operations import (
    GitCloneError,
    GitPullError,
    GitSyncError,
    check_working_directory_clean,
    get_default_branch,  # New import
    clone_repo,
    get_remote_url,
    pull_repo,
)


def test_get_default_branch_returns_main(tmp_path, source_repo):
    """get_default_branch returns the default branch name."""
    dest = tmp_path / "dest"
    clone_repo(str(source_repo), dest)

    branch = get_default_branch(dest)
    # source_repo fixture creates repo on master (git default) or main
    assert branch in ("main", "master")


def test_get_default_branch_no_remote_raises(tmp_path):
    """get_default_branch raises GitSyncError when no origin remote."""
    repo_path = tmp_path / "no-origin"
    repo_path.mkdir()
    subprocess.run(["git", "init"], cwd=repo_path, check=True, capture_output=True)

    with pytest.raises(GitSyncError) as exc_info:
        get_default_branch(repo_path)

    assert str(repo_path) in exc_info.value.message
    assert "default branch" in exc_info.value.message.lower()
```

**Step 2: Run tests to verify they fail**

Run: `pytest backend/tests/repo/test_git_operations.py -k "get_default_branch" -v`

Expected: FAIL with ImportError

**Step 3: Write minimal implementation**

Add to `backend/src/oya/repo/git_operations.py`:

```python
def get_default_branch(repo_path: Path, timeout: int = 30) -> str:
    """
    Detect the repository's default branch.

    Queries remote first, falls back to local refs.

    Args:
        repo_path: Path to the git repository
        timeout: Timeout in seconds for remote query

    Returns:
        Name of the default branch (e.g., 'main' or 'master')

    Raises:
        GitSyncError: If default branch cannot be determined
    """
    # Try querying remote first (authoritative)
    try:
        result = subprocess.run(
            ["git", "remote", "show", "origin"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                if "HEAD branch:" in line:
                    return line.split(":")[-1].strip()
    except subprocess.TimeoutExpired:
        pass  # Fall through to local refs

    # Fallback: check local symbolic ref
    result = subprocess.run(
        ["git", "symbolic-ref", "refs/remotes/origin/HEAD"],
        cwd=repo_path,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        # Output is like "refs/remotes/origin/main"
        return result.stdout.strip().split("/")[-1]

    raise GitSyncError(
        f"Could not determine the default branch for `{repo_path}`. "
        "Ensure the repository has an origin remote configured."
    )
```

**Step 4: Run tests to verify they pass**

Run: `pytest backend/tests/repo/test_git_operations.py -k "get_default_branch" -v`

Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/oya/repo/git_operations.py backend/tests/repo/test_git_operations.py
git commit -m "feat: add get_default_branch function"
```

---

## Task 4: Add get_current_branch and checkout_branch Functions

**Files:**
- Modify: `backend/src/oya/repo/git_operations.py`
- Test: `backend/tests/repo/test_git_operations.py`

**Step 1: Write failing tests**

Add to `backend/tests/repo/test_git_operations.py`:

```python
from oya.repo.git_operations import (
    GitCloneError,
    GitPullError,
    GitSyncError,
    check_working_directory_clean,
    checkout_branch,  # New import
    get_current_branch,  # New import
    get_default_branch,
    clone_repo,
    get_remote_url,
    pull_repo,
)


def test_get_current_branch_returns_branch_name(tmp_path, source_repo):
    """get_current_branch returns the current branch name."""
    dest = tmp_path / "dest"
    clone_repo(str(source_repo), dest)

    branch = get_current_branch(dest)
    assert branch in ("main", "master")


def test_checkout_branch_switches_branch(tmp_path, source_repo):
    """checkout_branch switches to specified branch."""
    dest = tmp_path / "dest"
    clone_repo(str(source_repo), dest)

    # Create and switch to a feature branch
    subprocess.run(
        ["git", "checkout", "-b", "feature-test"],
        cwd=dest, check=True, capture_output=True
    )
    assert get_current_branch(dest) == "feature-test"

    # Use checkout_branch to switch back
    default = get_default_branch(dest)
    checkout_branch(dest, default)
    assert get_current_branch(dest) == default


def test_checkout_branch_nonexistent_raises(tmp_path, source_repo):
    """checkout_branch raises GitSyncError for nonexistent branch."""
    dest = tmp_path / "dest"
    clone_repo(str(source_repo), dest)

    with pytest.raises(GitSyncError) as exc_info:
        checkout_branch(dest, "nonexistent-branch-xyz")

    assert str(dest) in exc_info.value.message
    assert "nonexistent-branch-xyz" in exc_info.value.message
```

**Step 2: Run tests to verify they fail**

Run: `pytest backend/tests/repo/test_git_operations.py -k "checkout_branch or get_current_branch" -v`

Expected: FAIL with ImportError

**Step 3: Write minimal implementation**

Add to `backend/src/oya/repo/git_operations.py`:

```python
def get_current_branch(repo_path: Path) -> str:
    """
    Get the name of the currently checked out branch.

    Args:
        repo_path: Path to the git repository

    Returns:
        Name of the current branch
    """
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=repo_path,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def checkout_branch(repo_path: Path, branch: str) -> None:
    """
    Checkout a specific branch.

    Args:
        repo_path: Path to the git repository
        branch: Name of the branch to checkout

    Raises:
        GitSyncError: If checkout fails
    """
    result = subprocess.run(
        ["git", "checkout", branch],
        cwd=repo_path,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise GitSyncError(
            f"Could not switch to branch '{branch}' in `{repo_path}`. "
            "The repository may be in an unexpected state.",
            original_error=result.stderr,
        )
```

**Step 4: Run tests to verify they pass**

Run: `pytest backend/tests/repo/test_git_operations.py -k "checkout_branch or get_current_branch" -v`

Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/oya/repo/git_operations.py backend/tests/repo/test_git_operations.py
git commit -m "feat: add get_current_branch and checkout_branch functions"
```

---

## Task 5: Add sync_to_default_branch Function

**Files:**
- Modify: `backend/src/oya/repo/git_operations.py`
- Test: `backend/tests/repo/test_git_operations.py`

**Step 1: Write failing tests**

Add to `backend/tests/repo/test_git_operations.py`:

```python
from oya.repo.git_operations import (
    GitCloneError,
    GitPullError,
    GitSyncError,
    check_working_directory_clean,
    checkout_branch,
    get_current_branch,
    get_default_branch,
    sync_to_default_branch,  # New import
    clone_repo,
    get_remote_url,
    pull_repo,
)


def test_sync_to_default_branch_from_default(tmp_path, source_repo):
    """sync_to_default_branch works when already on default branch."""
    dest = tmp_path / "dest"
    clone_repo(str(source_repo), dest)

    branch = sync_to_default_branch(dest)
    assert branch in ("main", "master")
    assert get_current_branch(dest) == branch


def test_sync_to_default_branch_from_feature(tmp_path, source_repo):
    """sync_to_default_branch switches from feature branch to default."""
    dest = tmp_path / "dest"
    clone_repo(str(source_repo), dest)

    # Switch to a feature branch
    subprocess.run(
        ["git", "checkout", "-b", "feature-branch"],
        cwd=dest, check=True, capture_output=True
    )
    assert get_current_branch(dest) == "feature-branch"

    # Sync should switch to default
    branch = sync_to_default_branch(dest)
    assert branch in ("main", "master")
    assert get_current_branch(dest) == branch


def test_sync_to_default_branch_pulls_changes(tmp_path, source_repo):
    """sync_to_default_branch pulls latest changes from origin."""
    dest = tmp_path / "dest"
    clone_repo(str(source_repo), dest)

    # Add a commit to source after clone
    (source_repo / "new_after_clone.txt").write_text("new content")
    subprocess.run(["git", "add", "."], cwd=source_repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "New commit"],
        cwd=source_repo, check=True, capture_output=True
    )

    # File doesn't exist yet in dest
    assert not (dest / "new_after_clone.txt").exists()

    # Sync should pull the new file
    sync_to_default_branch(dest)
    assert (dest / "new_after_clone.txt").exists()


def test_sync_to_default_branch_dirty_repo_raises(tmp_path, source_repo):
    """sync_to_default_branch raises GitSyncError for dirty repo."""
    dest = tmp_path / "dest"
    clone_repo(str(source_repo), dest)

    # Make repo dirty
    (dest / "dirty.txt").write_text("uncommitted")

    with pytest.raises(GitSyncError) as exc_info:
        sync_to_default_branch(dest)

    assert "uncommitted changes" in exc_info.value.message.lower()
```

**Step 2: Run tests to verify they fail**

Run: `pytest backend/tests/repo/test_git_operations.py -k "sync_to_default_branch" -v`

Expected: FAIL with ImportError

**Step 3: Write minimal implementation**

Add to `backend/src/oya/repo/git_operations.py`:

```python
def sync_to_default_branch(repo_path: Path, timeout: int = 120) -> str:
    """
    Sync repository to latest default branch.

    Checks for clean working directory, detects default branch,
    checks it out if needed, and pulls latest changes.

    Args:
        repo_path: Path to the git repository
        timeout: Timeout in seconds for network operations

    Returns:
        Name of the default branch

    Raises:
        GitSyncError: If any step fails, with user-friendly message
    """
    # Step 1: Ensure working directory is clean
    check_working_directory_clean(repo_path)

    # Step 2: Detect default branch
    default_branch = get_default_branch(repo_path, timeout=timeout)

    # Step 3: Checkout default branch if not already on it
    current = get_current_branch(repo_path)
    if current != default_branch:
        checkout_branch(repo_path, default_branch)

    # Step 4: Pull latest changes
    try:
        pull_repo(repo_path, timeout=timeout)
    except GitPullError as e:
        # Convert to GitSyncError with path included
        if "conflict" in e.message.lower():
            raise GitSyncError(
                f"Pull failed due to conflicts in `{repo_path}`. "
                "Oya manages this repository automatically—please don't modify files directly. "
                "Delete that folder and regenerate to fix this.",
                original_error=e.original_error,
            )
        raise GitSyncError(
            f"Could not pull latest changes for `{repo_path}`: {e.message}. "
            "Check your network connection and repository access.",
            original_error=e.original_error,
        )

    return default_branch
```

**Step 4: Run tests to verify they pass**

Run: `pytest backend/tests/repo/test_git_operations.py -k "sync_to_default_branch" -v`

Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/oya/repo/git_operations.py backend/tests/repo/test_git_operations.py
git commit -m "feat: add sync_to_default_branch function"
```

---

## Task 6: Integrate Sync into Generation Flow

**Files:**
- Modify: `backend/src/oya/api/routers/repos.py:289-350`
- Test: Integration test (manual or via existing test infrastructure)

**Step 1: Read current imports in repos.py**

Check imports at top of file to understand what's already imported.

**Step 2: Add import for sync function**

At the top of `backend/src/oya/api/routers/repos.py`, add:

```python
from oya.repo.git_operations import GitSyncError, sync_to_default_branch
```

**Step 3: Modify _run_generation function**

In `_run_generation()` function around line 340-350, add sync call right after the status update to "running" and before `prepare_staging_directory`:

Find this code (around line 340-349):

```python
    try:
        # Update status to running
        db.execute(
            "UPDATE generations SET status = 'running', current_phase = '0:starting' WHERE id = ?",
            (job_id,),
        )
        db.commit()

        # Prepare staging directory (copies production for incremental, or creates empty)
        prepare_staging_directory(staging_path, production_path)
```

Replace with:

```python
    try:
        # Sync repository to default branch before generation
        db.execute(
            "UPDATE generations SET status = 'running', current_phase = '0:syncing' WHERE id = ?",
            (job_id,),
        )
        db.commit()

        try:
            sync_to_default_branch(paths.source)
        except GitSyncError as e:
            db.execute(
                "UPDATE generations SET status = 'failed', error_message = ? WHERE id = ?",
                (e.message, job_id),
            )
            db.commit()
            return

        # Update status to starting (after sync)
        db.execute(
            "UPDATE generations SET current_phase = '0:starting' WHERE id = ?",
            (job_id,),
        )
        db.commit()

        # Prepare staging directory (copies production for incremental, or creates empty)
        prepare_staging_directory(staging_path, production_path)
```

**Step 4: Run existing tests to ensure no regressions**

Run: `pytest backend/tests/ -v --tb=short`

Expected: All tests pass

**Step 5: Commit**

```bash
git add backend/src/oya/api/routers/repos.py
git commit -m "feat: sync repository to default branch before wiki generation"
```

---

## Task 7: Add Syncing Phase to Frontend Constants

**Files:**
- Modify: `frontend/src/components/generationConstants.ts`

**Step 1: Add syncing phase to PHASES object**

Edit `frontend/src/components/generationConstants.ts`. Add syncing to PHASES:

```typescript
export const PHASES: Record<string, PhaseInfo> = {
  starting: { name: 'Starting', description: 'Initializing generation...' },
  syncing: { name: 'Syncing', description: 'Fetching latest code from repository...' },
  analysis: { name: 'Analysis', description: 'Scanning repository and parsing code...' },
  // ... rest unchanged
}
```

**Step 2: Add syncing to PHASE_ORDER**

```typescript
export const PHASE_ORDER = [
  'syncing',
  'analysis',
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

Run: `cd frontend && npm test`

Expected: All tests pass

**Step 4: Commit**

```bash
git add frontend/src/components/generationConstants.ts
git commit -m "feat: add syncing phase to frontend progress display"
```

---

## Task 8: Update Backend Phase Count

**Files:**
- Modify: `backend/src/oya/api/routers/repos.py:260-286`

**Step 1: Update total_phases in init_repo**

Find this code in `init_repo()` (around line 272-279):

```python
    # Record job in database
    # (8 phases: analysis, files, directories, synthesis, architecture,
    # overview, workflows, indexing)
    db.execute(
        """
        INSERT INTO generations (id, type, status, started_at, total_phases)
        VALUES (?, ?, ?, datetime('now'), ?)
        """,
        (job_id, "full", "pending", 8),
    )
```

Change to 9 phases and update comment:

```python
    # Record job in database
    # (9 phases: syncing, analysis, files, directories, synthesis, architecture,
    # overview, workflows, indexing)
    db.execute(
        """
        INSERT INTO generations (id, type, status, started_at, total_phases)
        VALUES (?, ?, ?, datetime('now'), ?)
        """,
        (job_id, "full", "pending", 9),
    )
```

**Step 2: Update phase_numbers mapping in _run_generation**

Find the `phase_numbers` dict (around line 310-319):

```python
    phase_numbers = {
        "analysis": 1,
        "files": 2,
        "directories": 3,
        "synthesis": 4,
        "architecture": 5,
        "overview": 6,
        "workflows": 7,
        "indexing": 8,
    }
```

Update to include syncing:

```python
    phase_numbers = {
        "syncing": 1,
        "analysis": 2,
        "files": 3,
        "directories": 4,
        "synthesis": 5,
        "architecture": 6,
        "overview": 7,
        "workflows": 8,
        "indexing": 9,
    }
```

**Step 3: Run tests**

Run: `pytest backend/tests/ -v --tb=short`

Expected: All tests pass

**Step 4: Commit**

```bash
git add backend/src/oya/api/routers/repos.py
git commit -m "feat: update phase numbering to include syncing phase"
```

---

## Task 9: Export New Functions from git_operations Module

**Files:**
- Modify: `backend/src/oya/repo/__init__.py` (if it exists and exports symbols)

**Step 1: Check if __init__.py exports symbols**

Read `backend/src/oya/repo/__init__.py` to see if it re-exports from git_operations.

**Step 2: If it does, add new exports**

If the file exports git_operations symbols, add:

```python
from oya.repo.git_operations import (
    GitCloneError,
    GitPullError,
    GitSyncError,
    check_working_directory_clean,
    checkout_branch,
    clone_repo,
    get_current_branch,
    get_default_branch,
    get_remote_url,
    pull_repo,
    sync_to_default_branch,
)
```

**Step 3: Run tests**

Run: `pytest backend/tests/ -v --tb=short`

Expected: All tests pass

**Step 4: Commit (if changes made)**

```bash
git add backend/src/oya/repo/__init__.py
git commit -m "feat: export new git sync functions from repo module"
```

---

## Task 10: Run Full Test Suite and Verify

**Files:** None (verification only)

**Step 1: Run all backend tests**

Run: `pytest backend/tests/ -v`

Expected: All tests pass

**Step 2: Run all frontend tests**

Run: `cd frontend && npm test`

Expected: All tests pass

**Step 3: Manual verification (optional)**

1. Start the backend: `cd backend && uvicorn oya.main:app --reload`
2. Start the frontend: `cd frontend && npm run dev`
3. Add a repository and trigger generation
4. Verify "Syncing" phase appears in progress UI
5. Verify generation completes successfully

**Step 4: Final commit if any cleanup needed**

If any adjustments were needed during verification, commit them.

---

## Summary

| Task | Description |
|------|-------------|
| 1 | Add GitSyncError exception |
| 2 | Add check_working_directory_clean function |
| 3 | Add get_default_branch function |
| 4 | Add get_current_branch and checkout_branch functions |
| 5 | Add sync_to_default_branch function |
| 6 | Integrate sync into generation flow |
| 7 | Add syncing phase to frontend constants |
| 8 | Update backend phase count |
| 9 | Export new functions (if needed) |
| 10 | Run full test suite and verify |
