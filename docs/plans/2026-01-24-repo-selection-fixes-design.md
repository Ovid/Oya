# Repository Selection and State Management Design

## Problem Statement

Three interrelated issues with repository management:

1. **Adding a repo doesn't switch to it** - User adds a repository, but stays viewing the previous one. No prompt to generate wiki for the new repo.

2. **Active repo state is lost on restart** - The active repo ID is stored in an in-memory singleton (`state.py`), so restarting Docker loses the selection.

3. **UI breaks when repos exist but none is active** - After restart, users see an error message ("No repository is active. Please select a repository first.") and the repo dropdown disappears entirely.

**Root cause:** False dichotomy between "multi-repo mode" and "legacy mode" in the codebase, plus in-memory-only active repo state.

## Design Decisions

### 1. Persist Active Repository ID

Store `active_repo_id` in SQLite alongside the repo registry instead of in-memory.

**Implementation:**
- Add an `app_settings` table to `repo_registry.db` with key-value pairs
- On `POST /api/v2/repos/{id}/activate`: write the ID to this table
- On app startup and `GET /api/v2/repos/active`: read from the table first
- If the stored repo ID points to a deleted repo, clear it and return `null`

**Location:** `backend/src/oya/db/repo_registry.py` (~20 lines for new table/queries)

### 2. Add Repository Flow

After successfully adding a repository:
1. Automatically switch to the new repo (already attempted, but needs fixing)
2. Show a confirmation prompt: "Repository added! Would you like to generate documentation now?"
   - "Generate Now" → Opens `IndexingPreviewModal`
   - "Later" → Dismisses, user stays on new repo with empty wiki

**Implementation:**
- Add `onRepoAdded(repo: Repo)` callback prop to `AddRepoModal`
- Handle callback in parent component to show confirmation dialog
- Trigger `IndexingPreviewModal` if user chooses to generate

### 3. Always Show Repo Dropdown

Oya is always "multi-repo" - it manages a list of repositories (0, 1, or N). Remove the conditional logic that hides the dropdown.

**Current broken logic in `TopBar.tsx`:**
```typescript
const isMultiRepoMode = activeRepo !== null
// Shows DirectoryPicker (legacy) when no active repo
```

**New logic:**
- Always render `RepoDropdown`
- Remove `DirectoryPicker` entirely
- Dropdown handles all states:
  - `repos.length === 0`: "No repositories" with "Add Repository" button
  - `repos.length > 0 && activeRepo === null`: "Select a repository" with list
  - `activeRepo !== null`: Active repo name with status indicator

### 4. Remove Legacy Mode Entirely

No users exist yet, so delete all legacy/single-repo mode code.

**Frontend deletions:**
- Delete `frontend/src/components/DirectoryPicker.tsx`
- Delete `frontend/src/components/DirectoryPicker.test.tsx`
- Remove export from `frontend/src/components/index.ts`
- Update `TopBar.tsx` - remove DirectoryPicker import and conditional
- Update `TopBar.test.tsx` - remove DirectoryPicker tests
- Update `frontend/src/stores/initialize.ts` comments

**Backend changes:**
- Remove `WORKSPACE_PATH` environment variable support from `config.py`
- Update `main.py` startup - no legacy mode check
- Update test files that set `WORKSPACE_PATH` to use repo registry approach
- Clean up "WORKSPACE_PATH not set" comments

**Documentation updates:**
- `CLAUDE.md` - Remove legacy mode section
- `README.md` - Remove "Multi-Repo vs Legacy Mode" section, remove `WORKSPACE_PATH` from env vars
- `.env.example` - Remove legacy mode comments
- `docker-compose.yml` - Remove legacy mode comments
- `backend/README.md` - Update

**Leave alone:**
- Historical plan documents in `docs/plans/`
- LLM response format "legacy" references (cgrag.py, qa/service.py) - these are about backwards-compatible parsing, not Oya modes

### 5. Graceful Error Handling

**Startup fallback chain:**
```
1. Try to load persisted active repo ID from SQLite
2. If found and repo still exists → use it
3. If not found OR repo was deleted → auto-select first repo in list
4. If no repos exist → show FirstRunWizard
```

**Page component guards:**
- Wiki pages check for `activeRepo` before rendering
- If no active repo, show friendly message instead of error toast
- Don't make API calls that require active repo context

**Status indicator:**
- When no repo selected, TopBar shows "No repository selected" instead of "Not initialized"

## Files to Modify

### Backend
| File | Change |
|------|--------|
| `backend/src/oya/db/repo_registry.py` | Add `app_settings` table, get/set active repo ID |
| `backend/src/oya/api/routers/repos_v2.py` | Persist active repo on activate, restore on get |
| `backend/src/oya/config.py` | Remove WORKSPACE_PATH support |
| `backend/src/oya/main.py` | Remove legacy mode startup check |
| `backend/src/oya/state.py` | May become unnecessary (evaluate) |
| Various test files | Update to use repo registry instead of WORKSPACE_PATH |

### Frontend
| File | Change |
|------|--------|
| `frontend/src/components/TopBar.tsx` | Always show RepoDropdown, remove DirectoryPicker |
| `frontend/src/components/AddRepoModal.tsx` | Add onRepoAdded callback |
| `frontend/src/components/RepoDropdown.tsx` | Handle generate prompt after add |
| `frontend/src/stores/initialize.ts` | Add fallback to first repo |
| `frontend/src/components/DirectoryPicker.tsx` | DELETE |
| `frontend/src/components/DirectoryPicker.test.tsx` | DELETE |
| `frontend/src/components/index.ts` | Remove DirectoryPicker export |
| `frontend/src/components/TopBar.test.tsx` | Remove DirectoryPicker tests |

### Documentation
| File | Change |
|------|--------|
| `CLAUDE.md` | Remove legacy mode, simplify storage description |
| `README.md` | Remove legacy mode section and WORKSPACE_PATH |
| `.env.example` | Remove legacy comments |
| `docker-compose.yml` | Remove legacy comments |
| `backend/README.md` | Remove WORKSPACE_PATH reference |

## Out of Scope

- Migration tooling (no existing users to migrate)
- Backwards compatibility with WORKSPACE_PATH (removing entirely)
- Changes to wiki generation logic
- Changes to Q&A functionality
