# Automated Git Sync Before Wiki Generation

## Problem

When users regenerate wikis, the system uses whatever code is currently in the local repository. This means:
- Remote changes not yet pulled are missing from the wiki
- Users on feature branches get documentation for the wrong code
- The wiki may be out of date without the user realizing it

Users expect regeneration to document the latest version of the default branch.

## Solution

Automatically sync the repository to the latest default branch before wiki generation begins. This includes:
1. Checking for a clean working directory
2. Detecting the repository's default branch
3. Checking out that branch
4. Pulling the latest changes from origin

If any step fails, abort generation with a clear error message.

## Behavior

### Always the Default Branch

Wiki generation **always** documents the default branch (`main`, `master`, or whatever the repository uses). This is not configurable—the wiki represents the canonical state of the codebase.

### Applies to All Repository Types

Both remote repositories (cloned by Oya) and local repositories (pointed at by the user) will have `git pull` run. Users who point Oya at a local repo are expected to have it connected to a remote.

### Abort on Failure

Any sync failure aborts generation entirely. Users must resolve the issue before regenerating. Error messages include the source path so users know which folder to inspect.

## Implementation

### New Functions in `git_operations.py`

```python
class GitSyncError(Exception):
    """Error during git sync operation."""
    def __init__(self, message: str, original_error: Optional[str] = None):
        self.message = message
        self.original_error = original_error
        super().__init__(message)


def check_working_directory_clean(repo_path: Path) -> None:
    """
    Verify no uncommitted changes exist.

    Raises GitSyncError if working directory is dirty.
    """
    # Uses: git status --porcelain


def get_default_branch(repo_path: Path, timeout: int = 30) -> str:
    """
    Detect the repository's default branch.

    Queries remote first, falls back to local refs.

    Raises GitSyncError if default branch cannot be determined.
    """
    # Primary: git remote show origin | grep "HEAD branch"
    # Fallback: git symbolic-ref refs/remotes/origin/HEAD


def sync_to_default_branch(repo_path: Path, timeout: int = 120) -> str:
    """
    Sync repository to latest default branch.

    Returns the name of the default branch.
    Raises GitSyncError with user-friendly message on failure.
    """
    check_working_directory_clean(repo_path)
    branch = get_default_branch(repo_path)
    # git checkout <branch> if not already on it
    pull_repo(repo_path, timeout)
    return branch
```

### Integration in `repos.py`

Modify `_run_generation()` to call sync before staging:

```python
async def _run_generation(job_id, repo, db, paths, settings):
    try:
        # Sync to default branch before anything else
        db.execute(
            "UPDATE generations SET status = 'running', current_phase = '0:syncing' WHERE id = ?",
            (job_id,),
        )
        db.commit()

        default_branch = sync_to_default_branch(paths.source)

        # Continue with existing staging/generation logic...
```

If `GitSyncError` is raised, mark the job as failed with the error message.

### Error Messages

All error messages include the source path (`{source_path}`) so users can locate the repository.

| Failure | Message |
|---------|---------|
| Dirty working directory | "Repository has uncommitted changes at `{source_path}`. Oya manages this repository automatically—please don't modify files directly. To reset, delete that folder and regenerate." |
| Can't detect default branch | "Could not determine the default branch for `{source_path}`. Ensure the repository has an origin remote configured." |
| Checkout fails | "Could not switch to branch '{branch}' in `{source_path}`. The repository may be in an unexpected state." |
| Network/auth error | "Could not pull latest changes for `{source_path}`: {specific error}. Check your network connection and repository access." |
| Pull conflict | "Pull failed due to conflicts in `{source_path}`. Oya manages this repository automatically—please don't modify files directly. Delete that folder and regenerate to fix this." |

### Frontend Updates

1. **Progress indicator** - Show "Syncing repository..." during the `0:syncing` phase
2. **Generate button tooltip** - Add: "Generates documentation from the latest default branch. Your repository will be synced automatically."
3. **Error display** - Show sync errors prominently with the full message

## Files to Modify

| File | Changes |
|------|---------|
| `backend/src/oya/repo/git_operations.py` | Add `GitSyncError`, `check_working_directory_clean()`, `get_default_branch()`, `sync_to_default_branch()` |
| `backend/src/oya/api/routers/repos.py` | Call `sync_to_default_branch()` at start of `_run_generation()`, handle `GitSyncError` |
| `frontend/src/components/GenerationProgress.tsx` | Display "syncing" phase |
| Frontend generate button component | Add tooltip explaining sync behavior |

## Not Changing

- No new API endpoints
- No database schema changes
- No new dependencies
- No user-facing settings (sync is always automatic)

## Test Cases

1. Clean repo on default branch - sync succeeds, generation proceeds
2. Clean repo on feature branch - switches to default, pulls, generates
3. Dirty working directory - aborts with clear error
4. Network unreachable - aborts with network error
5. Auth failure - aborts with auth error
6. No origin remote - aborts with missing remote error
7. Default branch detection via remote works
8. Fallback to local refs when remote query fails but refs exist
