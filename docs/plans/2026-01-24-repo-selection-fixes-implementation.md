# Repository Selection Fixes Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix repository selection issues: persist active repo across restarts, prompt for wiki generation after adding repo, always show repo dropdown, and remove all legacy WORKSPACE_PATH code.

**Architecture:** Add `app_settings` table to existing `repos.db` for persisting active repo ID. Remove `state.py` in-memory singleton. Update frontend to always show `RepoDropdown`, remove `DirectoryPicker` entirely. Add generation prompt flow after adding repos.

**Tech Stack:** Python/FastAPI backend, React/TypeScript/Zustand frontend, SQLite for persistence.

---

## Task 1: Add app_settings table to repo_registry.py

**Files:**
- Modify: `backend/src/oya/db/repo_registry.py`
- Test: `backend/tests/test_repo_registry.py` (create)

### Step 1.1: Write failing tests for settings persistence

Create test file for the new functionality.

```python
# backend/tests/test_repo_registry.py
"""Tests for repo registry settings persistence."""

import pytest
from pathlib import Path
from oya.db.repo_registry import RepoRegistry


class TestAppSettings:
    """Tests for app_settings table operations."""

    def test_get_setting_returns_none_for_missing_key(self, tmp_path: Path):
        """get_setting returns None when key doesn't exist."""
        db_path = tmp_path / "repos.db"
        registry = RepoRegistry(db_path)
        try:
            result = registry.get_setting("nonexistent")
            assert result is None
        finally:
            registry.close()

    def test_set_and_get_setting(self, tmp_path: Path):
        """Can store and retrieve a setting."""
        db_path = tmp_path / "repos.db"
        registry = RepoRegistry(db_path)
        try:
            registry.set_setting("active_repo_id", "42")
            result = registry.get_setting("active_repo_id")
            assert result == "42"
        finally:
            registry.close()

    def test_set_setting_overwrites_existing(self, tmp_path: Path):
        """Setting a key twice overwrites the value."""
        db_path = tmp_path / "repos.db"
        registry = RepoRegistry(db_path)
        try:
            registry.set_setting("active_repo_id", "1")
            registry.set_setting("active_repo_id", "2")
            result = registry.get_setting("active_repo_id")
            assert result == "2"
        finally:
            registry.close()

    def test_delete_setting(self, tmp_path: Path):
        """Can delete a setting."""
        db_path = tmp_path / "repos.db"
        registry = RepoRegistry(db_path)
        try:
            registry.set_setting("active_repo_id", "42")
            registry.delete_setting("active_repo_id")
            result = registry.get_setting("active_repo_id")
            assert result is None
        finally:
            registry.close()

    def test_delete_nonexistent_setting_is_noop(self, tmp_path: Path):
        """Deleting a nonexistent setting doesn't raise."""
        db_path = tmp_path / "repos.db"
        registry = RepoRegistry(db_path)
        try:
            registry.delete_setting("nonexistent")  # Should not raise
        finally:
            registry.close()
```

### Step 1.2: Run tests to verify they fail

Run: `cd backend && source .venv/bin/activate && pytest tests/test_repo_registry.py -v`
Expected: FAIL with `AttributeError: 'RepoRegistry' object has no attribute 'get_setting'`

### Step 1.3: Implement settings methods in RepoRegistry

Add to `backend/src/oya/db/repo_registry.py`:

1. Update SCHEMA constant to add the app_settings table:

```python
SCHEMA = """
CREATE TABLE IF NOT EXISTS repos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    origin_url TEXT NOT NULL,
    source_type TEXT NOT NULL,
    local_path TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    head_commit TEXT,
    branch TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    last_pulled TEXT,
    last_generated TEXT,
    generation_duration_secs REAL,
    files_processed INTEGER,
    pages_generated INTEGER,
    generation_provider TEXT,
    generation_model TEXT,
    embedding_provider TEXT,
    embedding_model TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_repos_origin_url ON repos(origin_url);
CREATE INDEX IF NOT EXISTS idx_repos_status ON repos(status);
"""
```

2. Add methods to RepoRegistry class (after the `close` method):

```python
    def get_setting(self, key: str) -> Optional[str]:
        """Get an app setting by key. Returns None if not found."""
        cursor = self._conn.execute(
            "SELECT value FROM app_settings WHERE key = ?", (key,)
        )
        row = cursor.fetchone()
        return row["value"] if row else None

    def set_setting(self, key: str, value: str) -> None:
        """Set an app setting. Creates or updates."""
        self._conn.execute(
            "INSERT OR REPLACE INTO app_settings (key, value) VALUES (?, ?)",
            (key, value),
        )
        self._conn.commit()

    def delete_setting(self, key: str) -> None:
        """Delete an app setting."""
        self._conn.execute("DELETE FROM app_settings WHERE key = ?", (key,))
        self._conn.commit()
```

### Step 1.4: Run tests to verify they pass

Run: `cd backend && source .venv/bin/activate && pytest tests/test_repo_registry.py -v`
Expected: PASS (5 tests)

### Step 1.5: Commit

```bash
git add backend/src/oya/db/repo_registry.py backend/tests/test_repo_registry.py
git commit -m "feat(db): add app_settings table to repo registry

Adds key-value storage for app-level settings like active_repo_id.
Supports get, set, and delete operations."
```

---

## Task 2: Persist active repo in repos_v2.py

**Files:**
- Modify: `backend/src/oya/api/routers/repos_v2.py`
- Test: `backend/tests/api/test_repos_v2.py`

### Step 2.1: Write failing tests for persistence

Add to `backend/tests/api/test_repos_v2.py`:

```python
class TestActiveRepoPersistence:
    """Tests for active repo persistence across restarts."""

    def test_activate_repo_persists_to_db(self, client, sample_repo):
        """Activating a repo persists the ID to the database."""
        repo_id = sample_repo["id"]

        # Activate the repo
        response = client.post(f"/api/v2/repos/{repo_id}/activate")
        assert response.status_code == 200

        # Verify it's persisted by checking the registry directly
        from oya.config import load_settings
        from oya.db.repo_registry import RepoRegistry

        settings = load_settings()
        registry = RepoRegistry(settings.repos_db_path)
        try:
            stored_id = registry.get_setting("active_repo_id")
            assert stored_id == str(repo_id)
        finally:
            registry.close()

    def test_get_active_repo_reads_from_db(self, client, sample_repo):
        """Getting active repo reads from database, not just memory."""
        repo_id = sample_repo["id"]

        # Set the active repo directly in database
        from oya.config import load_settings
        from oya.db.repo_registry import RepoRegistry

        settings = load_settings()
        registry = RepoRegistry(settings.repos_db_path)
        try:
            registry.set_setting("active_repo_id", str(repo_id))
        finally:
            registry.close()

        # Get active repo through API
        response = client.get("/api/v2/repos/active")
        assert response.status_code == 200
        data = response.json()
        assert data["active_repo"] is not None
        assert data["active_repo"]["id"] == repo_id

    def test_get_active_repo_clears_invalid_id(self, client, sample_repo):
        """Getting active repo clears persisted ID if repo was deleted."""
        from oya.config import load_settings
        from oya.db.repo_registry import RepoRegistry

        settings = load_settings()
        registry = RepoRegistry(settings.repos_db_path)
        try:
            # Set a nonexistent repo ID
            registry.set_setting("active_repo_id", "99999")
        finally:
            registry.close()

        # Get active repo should return None and clear the invalid ID
        response = client.get("/api/v2/repos/active")
        assert response.status_code == 200
        data = response.json()
        assert data["active_repo"] is None

        # Verify the setting was cleared
        registry = RepoRegistry(settings.repos_db_path)
        try:
            stored_id = registry.get_setting("active_repo_id")
            assert stored_id is None
        finally:
            registry.close()
```

### Step 2.2: Run tests to verify they fail

Run: `cd backend && source .venv/bin/activate && pytest tests/api/test_repos_v2.py::TestActiveRepoPersistence -v`
Expected: FAIL (tests expect persistence but current code uses in-memory state)

### Step 2.3: Update repos_v2.py to persist active repo

Modify `backend/src/oya/api/routers/repos_v2.py`:

1. Update `get_active_repo` function (around line 122):

```python
@router.get("/active", response_model=ActiveRepoResponse)
async def get_active_repo() -> ActiveRepoResponse:
    """
    Get the currently active repository.

    Reads from persisted storage, falling back to None if not set
    or if the stored repo no longer exists.
    """
    registry = get_registry()
    try:
        # Read from persistent storage
        stored_id = registry.get_setting("active_repo_id")

        if stored_id is None:
            return ActiveRepoResponse(active_repo=None)

        try:
            active_id = int(stored_id)
        except ValueError:
            # Invalid stored value, clear it
            registry.delete_setting("active_repo_id")
            return ActiveRepoResponse(active_repo=None)

        repo = registry.get(active_id)
        if not repo:
            # Repo was deleted, clear the stored ID
            registry.delete_setting("active_repo_id")
            return ActiveRepoResponse(active_repo=None)

        return ActiveRepoResponse(active_repo=_repo_to_response(repo))
    finally:
        registry.close()
```

2. Update `activate_repo` function (around line 203):

```python
@router.post("/{repo_id}/activate", response_model=ActivateRepoResponse)
async def activate_repo(repo_id: int) -> ActivateRepoResponse:
    """
    Activate a repository by ID.

    Sets the repository as the currently active one and persists the selection.

    Returns 404 if the repository is not found.
    """
    registry = get_registry()
    try:
        repo = registry.get(repo_id)
        if not repo:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Repository {repo_id} not found",
            )

        # Persist to database
        registry.set_setting("active_repo_id", str(repo_id))

        return ActivateRepoResponse(active_repo_id=repo_id)
    finally:
        registry.close()
```

3. Remove the import of `get_app_state` from the imports section (line 16) - it's no longer needed.

### Step 2.4: Run tests to verify they pass

Run: `cd backend && source .venv/bin/activate && pytest tests/api/test_repos_v2.py::TestActiveRepoPersistence -v`
Expected: PASS (3 tests)

### Step 2.5: Commit

```bash
git add backend/src/oya/api/routers/repos_v2.py backend/tests/api/test_repos_v2.py
git commit -m "feat(api): persist active repo ID to database

Active repo selection now survives server restarts.
Stored in app_settings table of repos.db."
```

---

## Task 3: Delete state.py (no longer needed)

**Files:**
- Delete: `backend/src/oya/state.py`
- Modify: Any files that import from state.py

### Step 3.1: Find all imports of state.py

Run: `grep -r "from oya.state import\|from oya import state" backend/src`

Expected files using state.py (based on earlier analysis):
- `backend/src/oya/api/routers/repos_v2.py` (already updated in Task 2)

### Step 3.2: Remove state.py import from repos_v2.py if not already done

The import `from oya.state import get_app_state` should already be removed in Task 2.3. Verify it's gone.

### Step 3.3: Delete state.py

```bash
rm backend/src/oya/state.py
```

### Step 3.4: Run backend tests to verify nothing is broken

Run: `cd backend && source .venv/bin/activate && pytest tests/api/test_repos_v2.py -v`
Expected: PASS

### Step 3.5: Commit

```bash
git add -A
git commit -m "refactor(backend): remove state.py singleton

Active repo is now persisted in SQLite, making the in-memory
singleton unnecessary."
```

---

## Task 4: Delete DirectoryPicker from frontend

**Files:**
- Delete: `frontend/src/components/DirectoryPicker.tsx`
- Delete: `frontend/src/components/DirectoryPicker.test.tsx`
- Modify: `frontend/src/components/index.ts`
- Modify: `frontend/src/components/TopBar.tsx`
- Modify: `frontend/src/components/TopBar.test.tsx`

### Step 4.1: Remove DirectoryPicker export from index.ts

Edit `frontend/src/components/index.ts`, remove line 9:

```typescript
export { Layout } from './Layout'
export { TopBar } from './TopBar'
export { Sidebar } from './Sidebar'
export { RightSidebar } from './RightSidebar'
export { WikiContent } from './WikiContent'
export { PageLoader } from './PageLoader'
export { AskPanel } from './AskPanel'
export { NoteEditor } from './NoteEditor'
export { InterruptedGenerationBanner } from './InterruptedGenerationBanner'
export { IndexingPreviewModal } from './IndexingPreviewModal'
export { ConfirmationDialog } from './ConfirmationDialog'
```

### Step 4.2: Update TopBar.tsx to always show RepoDropdown

Edit `frontend/src/components/TopBar.tsx`:

1. Remove the DirectoryPicker import (line 9):
```typescript
// DELETE THIS LINE: import { DirectoryPicker } from './DirectoryPicker'
```

2. Remove `isMultiRepoMode` variable (lines 54-55):
```typescript
// DELETE THESE LINES:
// // Check if we're in multi-repo mode (has repos in store)
// const isMultiRepoMode = activeRepo !== null
```

3. Remove `handleWorkspaceSwitch` function (lines 44-52):
```typescript
// DELETE THIS FUNCTION:
// const handleWorkspaceSwitch = async (path: string) => { ... }
```

4. Remove `switchWorkspace` from store destructuring (line 29):
```typescript
// Change from:
const switchWorkspace = useWikiStore((s) => s.switchWorkspace)
// To: DELETE this line entirely
```

5. Update the JSX to always render RepoDropdown (lines 116-131):

Change from:
```typescript
{isMultiRepoMode ? (
  <RepoDropdown onAddRepo={() => setIsAddRepoModalOpen(true)} disabled={isGenerating} />
) : (
  repoStatus && (
    <DirectoryPicker
      currentPath={repoStatus.path}
      isDocker={repoStatus.is_docker}
      onSwitch={handleWorkspaceSwitch}
      disabled={isGenerating}
      disabledReason={isGenerating ? 'Cannot switch during generation' : undefined}
    />
  )
)}
```

To:
```typescript
<RepoDropdown onAddRepo={() => setIsAddRepoModalOpen(true)} disabled={isGenerating} />
```

### Step 4.3: Update TopBar.test.tsx to remove DirectoryPicker tests

Edit `frontend/src/components/TopBar.test.tsx`:

Remove or update tests that reference DirectoryPicker. This includes:
- `describe('TopBar with DirectoryPicker', ...)` block
- Any tests mentioning `DirectoryPicker`
- The test `'disables DirectoryPicker when job is pending'`

Keep tests for RepoDropdown functionality.

### Step 4.4: Delete DirectoryPicker files

```bash
rm frontend/src/components/DirectoryPicker.tsx
rm frontend/src/components/DirectoryPicker.test.tsx
```

### Step 4.5: Run frontend tests

Run: `cd frontend && npm run test`
Expected: Tests should pass (DirectoryPicker tests are gone, TopBar tests updated)

### Step 4.6: Commit

```bash
git add -A
git commit -m "feat(frontend): always show RepoDropdown, remove DirectoryPicker

Oya always manages a list of repos. Remove the legacy single-repo
DirectoryPicker component entirely."
```

---

## Task 5: Add generation prompt after adding repo

**Files:**
- Modify: `frontend/src/components/AddRepoModal.tsx`
- Modify: `frontend/src/components/TopBar.tsx`

### Step 5.1: Add onRepoAdded callback to AddRepoModal

Edit `frontend/src/components/AddRepoModal.tsx`:

1. Update props interface:
```typescript
interface AddRepoModalProps {
  isOpen: boolean
  onClose: () => void
  onSuccess?: () => void
  onRepoAdded?: (repo: Repo) => void  // NEW
}
```

2. Update function signature:
```typescript
export function AddRepoModal({ isOpen, onClose, onSuccess, onRepoAdded }: AddRepoModalProps) {
```

3. Add import for Repo type at top:
```typescript
import type { Repo } from '../types'
```

4. Update handleSubmit to call onRepoAdded:
```typescript
const handleSubmit = async (e: React.FormEvent) => {
  e.preventDefault()
  setLocalError(null)
  clearError()

  if (!url.trim()) {
    setLocalError('URL or path is required')
    return
  }

  try {
    const repo = await addRepo(url.trim(), displayName.trim() || undefined)
    // Activate the newly created repo
    await setActiveRepo(repo.id)
    // Reset form
    setUrl('')
    setDisplayName('')
    onClose()
    onSuccess?.()
    onRepoAdded?.(repo)  // NEW - call with the new repo
  } catch {
    // Error is handled by store or localError
  }
}
```

### Step 5.2: Handle onRepoAdded in TopBar to show generation prompt

Edit `frontend/src/components/TopBar.tsx`:

1. Add state for showing generation confirmation:
```typescript
const [showGeneratePrompt, setShowGeneratePrompt] = useState(false)
```

2. Add handler for when repo is added:
```typescript
const handleRepoAdded = () => {
  // Show prompt to generate wiki
  setShowGeneratePrompt(true)
}
```

3. Update AddRepoModal to pass the callback:
```typescript
<AddRepoModal
  isOpen={isAddRepoModalOpen}
  onClose={() => setIsAddRepoModalOpen(false)}
  onRepoAdded={handleRepoAdded}
/>
```

4. Add a simple confirmation dialog after the AddRepoModal:
```typescript
{/* Generate Wiki Prompt */}
{showGeneratePrompt && (
  <div className="fixed inset-0 z-50 flex items-center justify-center">
    <div className="absolute inset-0 bg-black/50" onClick={() => setShowGeneratePrompt(false)} />
    <div className="relative bg-white dark:bg-gray-800 rounded-lg shadow-xl w-full max-w-sm mx-4 p-6">
      <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-2">
        Repository Added
      </h3>
      <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
        Would you like to generate documentation for this repository now?
      </p>
      <div className="flex justify-end space-x-3">
        <button
          onClick={() => setShowGeneratePrompt(false)}
          className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 rounded-md"
        >
          Later
        </button>
        <button
          onClick={() => {
            setShowGeneratePrompt(false)
            setIsPreviewModalOpen(true)
          }}
          className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 rounded-md"
        >
          Generate Now
        </button>
      </div>
    </div>
  </div>
)}
```

### Step 5.3: Run frontend to verify

Run: `cd frontend && npm run dev`
Manual test: Add a repository, verify the prompt appears, verify clicking "Generate Now" opens the IndexingPreviewModal.

### Step 5.4: Commit

```bash
git add frontend/src/components/AddRepoModal.tsx frontend/src/components/TopBar.tsx
git commit -m "feat(frontend): prompt to generate wiki after adding repo

After successfully adding a repository, show a confirmation dialog
asking if user wants to generate documentation now."
```

---

## Task 6: Add fallback to first repo on startup

**Files:**
- Modify: `frontend/src/stores/initialize.ts`

### Step 6.1: Update initializeApp to auto-select first repo

Edit `frontend/src/stores/initialize.ts`:

```typescript
import { useWikiStore } from './wikiStore'
import { useGenerationStore } from './generationStore'
import { useReposStore } from './reposStore'
import * as api from '../api/client'

export async function initializeApp(): Promise<void> {
  const wikiStore = useWikiStore.getState()
  const generationStore = useGenerationStore.getState()
  const reposStore = useReposStore.getState()

  wikiStore.setLoading(true)

  // Fetch repos and active repo
  try {
    await reposStore.fetchRepos()
    await reposStore.fetchActiveRepo()

    // If repos exist but none is active, auto-select the first one
    const { repos, activeRepo } = useReposStore.getState()
    if (repos.length > 0 && activeRepo === null) {
      await reposStore.setActiveRepo(repos[0].id)
    }
  } catch {
    // Ignore errors during repo initialization
  }

  // Refresh repo status
  await wikiStore.refreshStatus()

  // Check for incomplete build FIRST
  let hasIncompleteBuild = false
  try {
    const genStatus = await api.getGenerationStatus()
    if (genStatus && genStatus.status === 'incomplete') {
      generationStore.setGenerationStatus(genStatus)
      hasIncompleteBuild = true
      // Clear wiki tree when build is incomplete
      useWikiStore.setState({
        wikiTree: {
          overview: false,
          architecture: false,
          workflows: [],
          directories: [],
          files: [],
        },
      })
    }
  } catch {
    // Ignore errors when checking generation status
  }

  // Only load wiki tree if build is complete
  if (!hasIncompleteBuild) {
    await wikiStore.refreshTree()
  }

  // Check for any active jobs (pending or running) to restore generation progress after refresh
  try {
    const jobs = await api.listJobs(1)
    const activeJob = jobs.find((job) => job.status === 'running' || job.status === 'pending')
    if (activeJob) {
      generationStore.setCurrentJob(activeJob)
    }
  } catch {
    // Ignore errors when checking for running jobs
  }

  wikiStore.setLoading(false)
}
```

### Step 6.2: Run frontend to verify

Run: `cd frontend && npm run dev`

Manual test:
1. Start with a repo in the database but no active repo
2. Refresh the page
3. Verify the first repo is automatically selected

### Step 6.3: Commit

```bash
git add frontend/src/stores/initialize.ts
git commit -m "feat(frontend): auto-select first repo if none active

On app startup, if repos exist but none is active, automatically
select the first repo in the list to prevent broken UI state."
```

---

## Task 7: Remove WORKSPACE_PATH from config.py

**Files:**
- Modify: `backend/src/oya/config.py`

### Step 7.1: Simplify load_settings to remove WORKSPACE_PATH

Edit `backend/src/oya/config.py`, update the `load_settings` function:

```python
@lru_cache(maxsize=1)
def load_settings() -> Config:
    """Load settings from environment variables and config file.

    Settings are cached for the lifetime of the application.
    Use load_settings.cache_clear() to reload settings.

    Returns:
        Config object populated from environment variables.
    """
    # Load default config (no workspace-specific config file)
    base_config = _load_config(None)

    # Get provider and model, auto-detecting if not explicitly set
    active_provider = os.getenv("ACTIVE_PROVIDER")
    active_model = os.getenv("ACTIVE_MODEL")

    if not active_provider:
        detected_provider, detected_model = _detect_provider_from_keys()
        active_provider = detected_provider
        if not active_model:
            active_model = detected_model
    elif not active_model:
        # Provider set but model not - use default for that provider
        provider_defaults = {
            "openai": "gpt-4o",
            "anthropic": "claude-3-5-sonnet-20241022",
            "google": "gemini-1.5-pro",
            "ollama": "llama2",
        }
        active_model = provider_defaults.get(active_provider, "llama2")

    # Determine parallel limit based on provider
    parallel_limit_env = os.getenv("PARALLEL_FILE_LIMIT")
    if parallel_limit_env:
        parallel_file_limit = int(parallel_limit_env)
    elif active_provider == "ollama":
        parallel_file_limit = base_config.files.parallel_limit_local
    else:
        parallel_file_limit = base_config.files.parallel_limit_cloud

    # Get max_file_size_kb from env or config
    max_file_size_kb = int(os.getenv("MAX_FILE_SIZE_KB", str(base_config.files.max_file_size_kb)))

    # Get OYA_DATA_DIR from env, defaulting to ~/.oya
    data_dir_str = os.getenv("OYA_DATA_DIR")
    data_dir = Path(data_dir_str) if data_dir_str else Path.home() / ".oya"

    return Config(
        workspace_path=None,  # Always None - use active repo context instead
        data_dir=data_dir,
        workspace_display_path=None,
        active_provider=active_provider,
        active_model=active_model,
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
        google_api_key=os.getenv("GOOGLE_API_KEY"),
        ollama_endpoint=os.getenv("OLLAMA_ENDPOINT", "http://localhost:11434"),
        max_file_size_kb=max_file_size_kb,
        parallel_file_limit=parallel_file_limit,
        chunk_size=int(os.getenv("CHUNK_SIZE", "4096")),
        generation=base_config.generation,
        files=base_config.files,
        ask=base_config.ask,
        search=base_config.search,
        llm=base_config.llm,
        paths=base_config.paths,
    )
```

Also update the docstring for `_load_config` function to remove WORKSPACE_PATH references.

### Step 7.2: Run backend tests

Run: `cd backend && source .venv/bin/activate && pytest tests/test_config.py -v`
Expected: Some tests may fail due to WORKSPACE_PATH expectations - these need updating in Task 8.

### Step 7.3: Commit

```bash
git add backend/src/oya/config.py
git commit -m "refactor(config): remove WORKSPACE_PATH support

Config now always returns workspace_path=None. All workspace-relative
paths come from the active repo context via deps.py."
```

---

## Task 8: Update backend tests to use repo registry

**Files:**
- Modify: Multiple test files in `backend/tests/`

### Step 8.1: Identify tests that need updating

Tests that set `WORKSPACE_PATH` environment variable need to be updated to use the repo registry approach instead.

Key test files to update:
- `backend/tests/test_config.py`
- `backend/tests/test_api_deps.py`
- `backend/tests/test_wiki_api.py`
- `backend/tests/test_jobs_api.py`
- `backend/tests/test_search_api.py`
- `backend/tests/test_qa_api.py`
- `backend/tests/test_notes_api.py`
- `backend/tests/test_startup.py`

### Step 8.2: Update test_config.py

Remove tests that expect WORKSPACE_PATH to work:
- `test_load_settings_without_workspace_path` - update to verify workspace_path is always None
- Remove any tests that set WORKSPACE_PATH and expect it to be used

### Step 8.3: Create shared test fixture for repo setup

Create `backend/tests/conftest.py` (or update if exists) with a reusable fixture:

```python
import pytest
from pathlib import Path
from oya.db.repo_registry import RepoRegistry
from oya.config import load_settings


@pytest.fixture
def repo_with_wiki(tmp_path: Path, monkeypatch):
    """Set up a repo with wiki directory structure for testing."""
    # Set OYA_DATA_DIR to temp directory
    data_dir = tmp_path / ".oya"
    monkeypatch.setenv("OYA_DATA_DIR", str(data_dir))

    # Clear settings cache
    load_settings.cache_clear()

    # Create directory structure
    wikis_dir = data_dir / "wikis"
    wikis_dir.mkdir(parents=True)

    # Create a test repo directory
    repo_path = wikis_dir / "test-repo"
    source_path = repo_path / "source"
    meta_path = repo_path / "meta"
    source_path.mkdir(parents=True)
    meta_path.mkdir(parents=True)

    # Create wiki structure
    wiki_path = meta_path / ".oyawiki"
    wiki_path.mkdir()
    (wiki_path / "wiki").mkdir()
    (wiki_path / "meta").mkdir()

    # Register the repo
    registry = RepoRegistry(data_dir / "repos.db")
    repo_id = registry.add(
        origin_url="file://" + str(source_path),
        source_type="local",
        local_path="test-repo",
        display_name="Test Repo",
    )
    registry.update(repo_id, status="ready")

    # Activate the repo
    registry.set_setting("active_repo_id", str(repo_id))
    registry.close()

    yield {
        "repo_id": repo_id,
        "data_dir": data_dir,
        "source_path": source_path,
        "meta_path": meta_path,
        "wiki_path": wiki_path,
    }

    # Cleanup
    load_settings.cache_clear()
```

### Step 8.4: Run all backend tests

Run: `cd backend && source .venv/bin/activate && pytest -v`

Fix any remaining failures one by one. Many tests will need to:
1. Remove `monkeypatch.setenv("WORKSPACE_PATH", ...)`
2. Use the `repo_with_wiki` fixture instead

### Step 8.5: Commit incrementally

Commit as you fix each test file:
```bash
git add backend/tests/conftest.py backend/tests/test_config.py
git commit -m "test: update test_config.py to remove WORKSPACE_PATH"
```

---

## Task 9: Update documentation

**Files:**
- Modify: `CLAUDE.md`
- Modify: `README.md`
- Modify: `.env.example`
- Modify: `docker-compose.yml`
- Modify: `backend/README.md`

### Step 9.1: Update CLAUDE.md

Remove all references to "legacy mode", "WORKSPACE_PATH", and "multi-repo mode" as a mode switch. Update to describe Oya as always managing a list of repositories.

Key changes:
- Remove "Storage modes" section with multi-repo vs legacy
- Update dev commands to remove legacy mode comments
- Update env vars section to remove WORKSPACE_PATH
- Simplify architecture description

### Step 9.2: Update README.md

Remove:
- "Multi-Repo vs Legacy Mode" section
- `WORKSPACE_PATH` from environment variables table
- References to `.oyawiki/` in repo root (legacy mode)
- Any "legacy" mode references

### Step 9.3: Update .env.example

Remove legacy mode comments:
```bash
# Oya Data Directory (default: ~/.oya)
# OYA_DATA_DIR=~/.oya

# LLM Provider Configuration
# ...
```

### Step 9.4: Update docker-compose.yml

Remove legacy mode comments:
```yaml
services:
  backend:
    # ...
    volumes:
      # Oya data directory (persistent across restarts)
      - ~/.oya:/root/.oya
```

### Step 9.5: Update backend/README.md

Remove WORKSPACE_PATH reference.

### Step 9.6: Commit

```bash
git add CLAUDE.md README.md .env.example docker-compose.yml backend/README.md
git commit -m "docs: remove legacy mode references

Oya now only supports the repo registry approach. All legacy mode
documentation and WORKSPACE_PATH references removed."
```

---

## Task 10: Update main.py startup log

**Files:**
- Modify: `backend/src/oya/main.py`

### Step 10.1: Remove "multi-repo mode" log message

Edit `backend/src/oya/main.py`, line 95:

Change from:
```python
logger.info("Running in multi-repo mode")
```

To:
```python
logger.info("Oya backend started")
```

### Step 10.2: Commit

```bash
git add backend/src/oya/main.py
git commit -m "refactor(main): update startup log message"
```

---

## Task 11: Final verification

### Step 11.1: Run all backend tests

Run: `cd backend && source .venv/bin/activate && pytest -v`
Expected: All tests pass (or known pre-existing failures only)

### Step 11.2: Run all frontend tests

Run: `cd frontend && npm run test`
Expected: All tests pass

### Step 11.3: Manual integration test

1. Start fresh (delete `~/.oya` if exists)
2. `docker-compose up`
3. Open http://localhost:5173
4. Verify FirstRunWizard shows
5. Add a repository
6. Verify prompt to generate wiki appears
7. Click "Later"
8. Verify repo dropdown shows the repo
9. Restart docker-compose
10. Verify the same repo is still selected (persistence works)
11. Add another repo
12. Verify it switches and prompts for generation

### Step 11.4: Final commit if any cleanup needed

```bash
git status
# If any remaining changes, commit them
```

---

## Summary of Changes

| Component | Change |
|-----------|--------|
| `repo_registry.py` | Add `app_settings` table for key-value storage |
| `repos_v2.py` | Persist/restore active repo from database |
| `state.py` | DELETED - no longer needed |
| `config.py` | Remove WORKSPACE_PATH support |
| `TopBar.tsx` | Always show RepoDropdown, add generation prompt |
| `AddRepoModal.tsx` | Add onRepoAdded callback |
| `DirectoryPicker.tsx` | DELETED |
| `initialize.ts` | Auto-select first repo if none active |
| Documentation | Remove all legacy mode references |
| Tests | Update to use repo registry instead of WORKSPACE_PATH |
