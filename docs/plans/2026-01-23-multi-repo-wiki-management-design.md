# Multi-Repo Wiki Management Design

**Date:** 2026-01-23
**Status:** Draft

## Problem Statement

CGRAG and deep research need access to actual source code for precise answers, not just wiki summaries. Additionally, users don't want Oya artifacts (`.oyawiki/`, `.oyaignore`, `.oya-logs/`) polluting their repositories.

## Solution Overview

Centralize all Oya data in `~/.oya/` (or `$OYA_DATA_DIR`), storing cloned repos alongside their generated wikis. This enables:
- Source file access for CGRAG
- Clean separation from user repositories
- Multi-repo management from a single Oya instance

## Data Architecture

### Directory Structure

```
~/.oya/
├── repos.db                                    # Central SQLite registry
└── wikis/
    ├── github.com/
    │   └── Ovid/
    │       └── Oya/
    │           ├── source/                     # Cloned repo (untouched)
    │           │   └── <git clone contents>
    │           └── meta/                       # Oya artifacts
    │               ├── .oyawiki/
    │               ├── .oyaignore
    │               └── .oya-logs/
    ├── gitlab.com/...
    ├── git/                                    # Unrecognized git hosts
    │   └── github.mycompany.com/org/repo/
    └── local/
        └── Users/alice/projects/foo/
            ├── source/
            └── meta/
```

Key design decisions:
- `source/` contains pure git clone, never modified by Oya
- `meta/` contains all Oya-generated artifacts
- Separation prevents git conflicts on pull
- Remote repos organized by host/owner/repo
- Local repos mirror original path under `local/`

### Database Schema (repos.db)

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| origin_url | TEXT | Git remote URL or original local path |
| source_type | TEXT | github, gitlab, bitbucket, git, local |
| local_path | TEXT | Path within ~/.oya/wikis/ |
| display_name | TEXT | User-friendly label |
| head_commit | TEXT | Current SHA |
| branch | TEXT | Checked out branch |
| created_at | DATETIME | When first added |
| last_pulled | DATETIME | When source last updated |
| last_generated | DATETIME | When wiki last built |
| generation_duration_secs | REAL | How long regeneration took |
| files_processed | INTEGER | Files analyzed |
| pages_generated | INTEGER | Wiki pages created |
| generation_provider | TEXT | LLM provider used |
| generation_model | TEXT | LLM model used |
| embedding_provider | TEXT | Embedding provider |
| embedding_model | TEXT | Embedding model |
| status | TEXT | pending, cloning, generating, ready, failed |
| error_message | TEXT | Error details if failed |

## Repo Lifecycle

### Adding a Repo

1. User enters URL or local path in single input field
2. Smart detection determines source type:
   - `github.com/...` or `git@github.com:...` → github
   - `gitlab.com/...` → gitlab
   - `bitbucket.org/...` → bitbucket
   - Other URLs → generic "git" type
   - `/path/...` or `~/...` → local
3. Check `repos.db` for duplicates → error if exists, offer to switch
4. Create directory structure under `~/.oya/wikis/`
5. Run `git clone <url> source/` (let git handle auth)
6. On failure: parse error, show friendly message with guidance
7. On success: insert into `repos.db` with status "pending"

### Regenerating a Repo

1. User clicks "Regenerate" on current repo
2. `git pull` in `source/` directory
3. On pull failure: show error, abort regeneration
4. Update `repos.db`: `head_commit`, `last_pulled`
5. Run generation pipeline, writing to `meta/.oyawiki/`
6. Update `repos.db`: `last_generated`, `generation_duration_secs`, stats, status

### Deleting a Repo

1. Check if generation in progress → block with message
2. Confirmation dialog with warning
3. Delete entire directory under `~/.oya/wikis/`
4. Remove row from `repos.db`
5. If deleted repo was active, switch to another or show empty state

## API Design

### New Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/repos` | List all repos from repos.db |
| POST | `/api/repos` | Add new repo (triggers clone) |
| GET | `/api/repos/{id}` | Get single repo details |
| DELETE | `/api/repos/{id}` | Delete repo and all artifacts |
| POST | `/api/repos/{id}/activate` | Set as active/current repo |
| POST | `/api/repos/{id}/regenerate` | Pull + regenerate wiki |

### Request/Response Examples

**POST /api/repos**
```json
{
  "url": "https://github.com/Ovid/Oya",
  "display_name": "Oya Wiki Generator"
}
```

**Response**
```json
{
  "id": 1,
  "status": "cloning",
  "stream_url": "/api/repos/1/clone-stream"
}
```

### Modified Endpoints

All existing endpoints use active repo context instead of WORKSPACE_PATH:
- `/api/wiki/tree` - returns tree for active repo
- `/api/wiki/page/{path}` - returns page from active repo
- `/api/jobs/*` - jobs for active repo
- `/api/search/*` - search active repo
- `/api/qa/*` - Q&A against active repo

## UI Design

### Top Bar Changes

- Repo dropdown showing `display_name` for all repos
- Current repo highlighted/selected
- "Add repository..." option at bottom
- Search filter appears when repo count > 10

### First-Run Wizard

When `repos.db` is empty:

1. **Welcome screen** - Brief intro, "Get Started" button
2. **Add repository** - Single input field with examples
3. **Cloning progress** - Progress indicator, cancel option
4. **Select files** - File tree with checkboxes (existing IndexingPreviewModal)
5. **Generation progress** - Existing SSE streaming component
6. **Done** - Redirect to generated wiki

### Regeneration UI

- If wiki doesn't exist: "Generate Wiki" button
- If wiki exists: "Regenerate Wiki" button
- Triggers pull + full generation

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OYA_DATA_DIR` | `~/.oya` | Root directory for all Oya data |
| `ACTIVE_PROVIDER` | (auto-detect) | LLM provider |
| `ACTIVE_MODEL` | (provider default) | LLM model |

### Removed Variables

- `WORKSPACE_PATH` - replaced by OYA_DATA_DIR + repo selection
- `WORKSPACE_DISPLAY_PATH` - no longer needed
- `WORKSPACE_BASE_PATH` - no longer needed

### Docker Usage

```bash
docker run -d \
  -v /host/path/to/oya-data:/data/oya \
  -v ~/.ssh:/root/.ssh:ro \
  -e OYA_DATA_DIR=/data/oya \
  -e ANTHROPIC_API_KEY=sk-... \
  -p 5173:5173 \
  oya
```

## Error Handling

### Clone Failures

| Git Error | User-Friendly Message |
|-----------|----------------------|
| Repository not found | "Repository not found. Check the URL or ensure you have access." |
| Authentication failed | "Authentication failed. For private repos, ensure your SSH keys are configured or try an HTTPS URL with credentials." |
| Network error | "Network error. Check your internet connection and try again." |
| Invalid URL | "This doesn't look like a valid git URL or local path." |

### Pull Failures

| Scenario | Handling |
|----------|----------|
| Origin no longer exists | "Original repository no longer exists at {path}. Delete and re-add from new location." |
| Auth expired | "Authentication failed. Check your credentials and try again." |
| Network error | "Network error. Try again later." |

### Database Recovery

If `repos.db` is corrupted:
1. Scan `~/.oya/wikis/` for directories containing `source/.git`
2. Run `git remote get-url origin` to recover origin URL
3. Infer `source_type` from URL
4. Rebuild entries with appropriate status
5. User re-enters `display_name` values

## CGRAG Integration

### Source Access Pattern

When CGRAG needs source files:
1. Get active repo from backend state
2. Look up `local_path` in `repos.db`
3. Construct path: `$OYA_DATA_DIR/wikis/{local_path}/source/{file_path}`
4. Read file contents directly

### Enhanced Q&A Flow

1. CGRAG searches vector store, finds relevant wiki page
2. Wiki page references source file
3. CGRAG reads actual source from `source/` directory
4. Response includes precise code snippets and line numbers

## Implementation Phases

### Phase 1: Data Layer
- Create `repos.db` schema and repository
- Implement `OYA_DATA_DIR` configuration
- Directory structure utilities
- Git operations wrapper

### Phase 2: Backend API
- New `/api/repos` endpoints
- Refactor existing endpoints for active repo context
- Remove `WORKSPACE_PATH` dependencies
- Startup checks and initialization

### Phase 3: Frontend
- Repo dropdown in top bar
- Add repo modal with smart input
- First-run wizard
- Update components for repo switching

### Phase 4: CGRAG Integration
- Update vectorstore for source file access
- Enhance Q&A to include source snippets
- Integration testing

### Phase 5: Polish
- Error handling refinements
- Documentation updates
- Docker configuration updates

## Out of Scope (v1)

| Feature | Reason |
|---------|--------|
| Incremental regeneration | Complex, needs separate design |
| Branch switching | Default branch sufficient |
| Pinned/favorite repos | Use localStorage if needed |
| Windows support | Path complexity, low priority |
| Automatic sync | Manual regeneration is predictable |

## Documentation Requirements

### Files to Update
- `README.md` - New setup flow, OYA_DATA_DIR
- `docker-compose.yml` - Volume mounts, env vars
- `CLAUDE.md` - Architecture section

### New Documentation
- Private repo access (SSH keys, Docker mounting)
- Multi-repo workflow
- Data directory and backups
- Troubleshooting guide

## Breaking Changes

- `WORKSPACE_PATH` no longer recognized
- `.oyawiki/` no longer created in user repos
- Existing in-repo wikis are not migrated

Since there are no existing users, no migration path is needed.
