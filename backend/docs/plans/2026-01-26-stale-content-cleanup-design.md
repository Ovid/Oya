# Stale Content Cleanup Design

## Overview

When regenerating wikis, stale content can accumulate from files and directories that no longer exist in the repository. This design adds cleanup during the syncing phase and introduces frontmatter to wiki pages for reliable orphan detection.

## Problem Statement

Currently, when source files or directories are deleted from a repository:
- Their wiki pages remain in `wiki/files/` and `wiki/directories/`
- Associated notes remain in `notes/files/` and `notes/directories/`
- Workflow pages may reference entry points that no longer exist
- The vector store and FTS index may contain stale entries

## Design Decisions

| Aspect | Decision |
|--------|----------|
| Notes for deleted files/dirs | Delete automatically during cleanup |
| Workflows | Delete all and regenerate from scratch each time |
| Cleanup timing | During syncing phase, after git sync, before generation |
| Orphan detection | Filesystem scanning with frontmatter parsing |
| Pages without frontmatter | Treat as orphaned and delete (forces regeneration) |
| Frontmatter fields | source, type, generated, commit, layer (full metadata) |
| Frontmatter generation | Backend adds it, not LLM |
| Frontend display | Parse frontmatter, show in collapsible "Page Info" section |
| Vector/FTS indexing | Keep full reindex approach |

## Frontmatter Format

All generated wiki pages will include YAML frontmatter:

```markdown
---
source: src/api/routes.py
type: file
generated: 2026-01-26T10:30:00Z
commit: a1b2c3d4e5f6
layer: api
---

# routes.py

REST API route definitions...
```

### Fields by Page Type

| Page Type | source | type | generated | commit | layer |
|-----------|--------|------|-----------|--------|-------|
| file | file path | `file` | yes | yes | yes |
| directory | directory path | `directory` | yes | yes | no |
| workflow | workflow name/slug | `workflow` | yes | yes | no |
| overview | (empty) | `overview` | yes | yes | no |
| architecture | (empty) | `architecture` | yes | yes | no |

## Cleanup Logic (Syncing Phase)

After git sync completes, before generation starts:

### Step 1: Delete All Workflow Pages

- Remove everything in `wiki/workflows/` directory
- Workflows will be regenerated fresh from current entry points
- This ensures no stale workflows referencing removed entry points

### Step 2: Scan File Pages for Orphans

- Walk `wiki/files/*.md`
- For each file:
  - Parse frontmatter to extract `source` field
  - If no frontmatter → treat as orphaned
  - If `source` path doesn't exist in repo → orphaned
- Delete orphaned `.md` files

### Step 3: Scan Directory Pages for Orphans

- Walk `wiki/directories/*.md`
- Same logic as file pages
- Delete orphaned `.md` files

### Step 4: Delete Orphaned Notes

- For each note in `notes/files/` → check if source file exists
- For each note in `notes/directories/` → check if source directory exists
- Delete notes whose targets no longer exist
- Remove from database as well as filesystem

## Backend Implementation

### Centralized Frontmatter Generation

Create a utility function to build frontmatter from page metadata:

```python
def build_frontmatter(
    source: str | None,
    page_type: str,
    commit: str,
    generated: datetime,
    layer: str | None = None,
) -> str:
    """Build YAML frontmatter for a wiki page.

    Args:
        source: Source file/directory path (None for overview/architecture)
        page_type: One of 'file', 'directory', 'workflow', 'overview', 'architecture'
        commit: Git commit hash when generated
        generated: Generation timestamp
        layer: Architectural layer (for file pages only)

    Returns:
        Formatted YAML frontmatter string with trailing newline
    """
    lines = ["---"]
    if source:
        lines.append(f"source: {source}")
    lines.append(f"type: {page_type}")
    lines.append(f"generated: {generated.isoformat()}Z")
    lines.append(f"commit: {commit}")
    if layer:
        lines.append(f"layer: {layer}")
    lines.append("---")
    lines.append("")  # Blank line after frontmatter
    return "\n".join(lines)
```

### Modified Page Writing Flow

In `orchestrator.py` around line 1489:

```python
# Current
page_path.write_text(page.content, encoding="utf-8")

# New
frontmatter = build_frontmatter(
    source=page.target,
    page_type=page.page_type,
    commit=current_commit,
    generated=datetime.utcnow(),
    layer=file_summary.layer if page.page_type == "file" else None
)
page_path.write_text(frontmatter + page.content, encoding="utf-8")
```

### Getting Current Commit

- Use `GitRepo` class method to get current HEAD commit
- Capture once at start of generation, reuse for all pages

### Cleanup Implementation

Add cleanup functions in a new module or within `orchestrator.py`:

```python
def cleanup_stale_content(
    wiki_path: Path,
    notes_path: Path,
    source_path: Path,
    db: Database,
) -> CleanupResult:
    """Remove stale wiki pages and notes.

    Args:
        wiki_path: Path to wiki directory (.oyawiki/wiki)
        notes_path: Path to notes directory (.oyawiki/notes)
        source_path: Path to source repository
        db: Database connection for notes cleanup

    Returns:
        CleanupResult with counts of deleted items
    """
    # Step 1: Delete all workflows
    workflows_deleted = delete_all_workflows(wiki_path / "workflows")

    # Step 2: Delete orphaned file pages
    files_deleted = delete_orphaned_pages(
        wiki_path / "files",
        source_path,
        is_file=True,
    )

    # Step 3: Delete orphaned directory pages
    dirs_deleted = delete_orphaned_pages(
        wiki_path / "directories",
        source_path,
        is_file=False,
    )

    # Step 4: Delete orphaned notes
    notes_deleted = delete_orphaned_notes(notes_path, source_path, db)

    return CleanupResult(
        workflows_deleted=workflows_deleted,
        files_deleted=files_deleted,
        directories_deleted=dirs_deleted,
        notes_deleted=notes_deleted,
    )
```

## Frontend Implementation

### Parsing Frontmatter

When wiki page content is received:
1. Detect `---` YAML block at start of content
2. Parse YAML into structured metadata object
3. Pass remaining markdown to renderer

```typescript
interface WikiPageMeta {
  source?: string;
  type: 'file' | 'directory' | 'workflow' | 'overview' | 'architecture';
  generated: string;  // ISO timestamp
  commit: string;
  layer?: string;
}

function parseFrontmatter(content: string): { meta: WikiPageMeta | null; content: string } {
  const match = content.match(/^---\n([\s\S]*?)\n---\n([\s\S]*)$/);
  if (!match) {
    return { meta: null, content };
  }
  const meta = parseYaml(match[1]) as WikiPageMeta;
  return { meta, content: match[2] };
}
```

### Collapsible "Page Info" Section

- Hidden by default
- Toggle button labeled "Page Info" in page header area
- When expanded, displays:
  - **Source**: `src/api/routes.py`
  - **Type**: File / Directory / Workflow / etc.
  - **Layer**: API / Domain / Infrastructure (for file pages)
  - **Generated**: Jan 26, 2026 at 10:30 AM (formatted)
  - **Commit**: `a1b2c3d` (short hash)

## Migration

Existing wikis without frontmatter will have all pages treated as orphaned on first regeneration after this feature is deployed. This forces full regeneration with proper frontmatter, ensuring a clean state going forward.

## Files to Modify

### Backend
- `backend/src/oya/generation/orchestrator.py` - Add frontmatter to page writing, add cleanup calls
- `backend/src/oya/generation/cleanup.py` (new) - Cleanup logic and frontmatter utilities
- `backend/src/oya/api/routers/repos.py` - Call cleanup in syncing phase

### Frontend
- `frontend/src/utils/frontmatter.ts` (new) - Frontmatter parsing utility
- `frontend/src/components/WikiPage.tsx` (or equivalent) - Parse frontmatter, add Page Info section
- `frontend/src/components/PageInfo.tsx` (new) - Collapsible metadata display component
