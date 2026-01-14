# Directory Pages Redesign

## Problem Statement

Directory pages in the wiki currently have several usability and consistency issues:

1. **No standardized structure**: Directory pages vary in format, making navigation inconsistent
2. **No navigation links**: Files and subdirectories are mentioned but not clickable
3. **No parent navigation**: Users cannot easily navigate up the directory tree
4. **Non-recursive signatures may cause stale content**: When a subdirectory's role changes, parent directory pages don't regenerate

## Requirements

### Must Have

1. **Breadcrumb navigation**: Every directory page displays a clickable breadcrumb trail showing the path from project root
2. **Subdirectory section with links**: List all immediate subdirectories with one-line summaries (from child `DirectorySummary.purpose`) and clickable links
3. **Files section with links**: List all direct files with brief descriptions and clickable links to their documentation pages
4. **Standardized template**: All directory pages follow the same section order and structure
5. **Cascade regeneration for subdirectory changes**: If a child directory's `purpose` changes, parent directories regenerate

### Nice to Have

1. **Key components section**: Highlight important classes/functions from this directory and subdirectories
2. **Dependency summary**: Show what this directory depends on and what depends on it

## Design

### Directory Page Template

```markdown
# {directory_name}

{breadcrumb_trail}

## Overview
{One paragraph describing what this directory/module is responsible for}

## Subdirectories
{If subdirectories exist}
| Directory | Purpose |
|-----------|---------|
| [routes](./src-api-routes.md) | HTTP route handlers for all endpoints |
| [middleware](./src-api-middleware.md) | Request/response middleware |

## Files
| File | Purpose |
|------|---------|
| [app.py](../files/src-api-app-py.md) | FastAPI application setup |
| [__init__.py](../files/src-api-__init__-py.md) | Package initialization |

## Key Components
- `create_app()` - Factory function for FastAPI application
- `APIRouter` - Main router combining all route modules

## Dependencies
### Internal
- `src/db` - Database access layer
- `src/models` - Domain models

### External
- `fastapi` - Web framework
- `pydantic` - Data validation
```

### Breadcrumb Format

For shallow directories (depth <= 4), show full path:
```markdown
[project-name](./root.md) / [src](./src.md) / [api](./src-api.md) / routes
```

For deep directories (depth > 4), truncate the middle:
```markdown
[project-name](./root.md) / ... / [validation](./src-components-ui-forms-inputs-validation.md) / rules
```

This shows: root + `...` + parent + current directory.

For the root directory:
```markdown
project-name
```
(No links - this is the top level)

**Rules:**
- Each ancestor is a clickable link except the current directory
- The root uses the project name (from package.json, pyproject.toml, or repo folder name)
- Links use relative paths to other directory pages
- Truncation threshold: 4 levels (root, grandparent, parent, current = no truncation; anything deeper gets `...`)

### Processing Order Change

**Current**: Directories processed in arbitrary order (sorted alphabetically)

**New**: Directories processed in dependency order (children before parents)

**Critical constraint**: No directory may be processed before ALL of its subdirectories have been processed. This ensures child `DirectorySummary` objects exist before generating parent directories.

Implementation approach - process by depth level (deepest first):
```python
# Group directories by depth
dirs_by_depth = defaultdict(list)
for dir_path in all_directories:
    depth = dir_path.count('/')
    dirs_by_depth[depth].append(dir_path)

# Process deepest first - this guarantees children before parents
# depth=3: src/api/routes, src/api/middleware
# depth=2: src/api, src/models
# depth=1: src
# depth=0: (root)
for depth in sorted(dirs_by_depth.keys(), reverse=True):
    for dir_path in dirs_by_depth[depth]:
        # At this point, all child DirectorySummaries are available
        child_summaries = get_child_summaries(dir_path, all_summaries)
        page, summary = generate_directory(dir_path, child_summaries)
        all_summaries[dir_path] = summary
```

This ordering guarantees that when we generate `src/api/`, the summaries for `src/api/routes/` and `src/api/middleware/` already exist and can be included in the parent's context.

### Signature Enhancement

**Current**: Directory signature = hash of direct file contents

**New**: Directory signature = hash of (direct file contents + child directory purposes)

This ensures parent directories regenerate when:
1. Direct files change (existing behavior)
2. A child directory's purpose changes (new behavior)

```python
def compute_directory_signature(
    file_hashes: list[tuple[str, str]],
    child_summaries: list[DirectorySummary]
) -> str:
    # Include file hashes
    sorted_hashes = sorted(file_hashes, key=lambda x: x[0])
    file_part = "|".join(f"{name}:{hash}" for name, hash in sorted_hashes)

    # Include child directory purposes
    sorted_children = sorted(child_summaries, key=lambda x: x.directory_path)
    child_part = "|".join(f"{c.directory_path}:{c.purpose}" for c in sorted_children)

    combined = f"{file_part}||{child_part}"
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()
```

### Data Flow Changes

```
Phase 2 (Files)
    ↓
    FileSummary objects
    ↓
Phase 3 (Directories) - NEW: bottom-up processing
    ↓
    For each directory (deepest first):
        1. Get FileSummaries for direct files
        2. Get DirectorySummaries for immediate child directories
        3. Generate page with both contexts
        4. Extract DirectorySummary
        5. Store for parent directory use
    ↓
    DirectorySummary objects
    ↓
Phase 4 (Synthesis)
```

### Prompt Template Changes

Update `DIRECTORY_TEMPLATE` in `prompts.py`:

```python
DIRECTORY_TEMPLATE = PromptTemplate(
    """Generate a directory documentation page for "{directory_path}" in "{repo_name}".

## Breadcrumb
{breadcrumb}

## Direct Files
{file_list}

## File Summaries
{file_summaries}

## Subdirectories
{subdirectory_summaries}

## Symbols Defined
{symbols}

---

IMPORTANT: Generate documentation following this EXACT structure:

1. Start with a YAML summary block:
```
---
directory_summary:
  purpose: "One-sentence description of what this directory/module is responsible for"
  contains:
    - "file1.py"
    - "file2.py"
  role_in_system: "Description of how this directory fits into the overall architecture"
---
```

2. Then the page content with these sections IN ORDER:
   - **Overview**: One paragraph describing the directory's purpose
   - **Subdirectories**: Table with Directory and Purpose columns (if subdirectories exist)
   - **Files**: Table with File and Purpose columns
   - **Key Components**: Bullet list of important classes/functions
   - **Dependencies**: Internal and External subsections

Use the breadcrumb, file summaries, and subdirectory summaries provided to generate accurate content.
Do NOT invent files or subdirectories that aren't listed above.
Format all file and directory names as markdown links using the paths shown."""
)
```

### Link Path Resolution

The generator needs to produce correct relative links:

| From | To | Link Format |
|------|-----|-------------|
| Directory page | Child directory page | `./child-slug.md` |
| Directory page | File page | `../files/file-slug.md` |
| Directory page | Parent directory page | `./parent-slug.md` |

Helper function:
```python
def generate_directory_links(directory_path: str, subdirs: list[str], files: list[str]) -> dict:
    """Generate markdown links for navigation."""
    return {
        "breadcrumb": _build_breadcrumb(directory_path),
        "subdir_links": {d: f"./{path_to_slug(d)}.md" for d in subdirs},
        "file_links": {f: f"../files/{path_to_slug(f)}.md" for f in files},
    }
```

## Files to Modify

1. `backend/src/oya/generation/orchestrator.py`
   - Add root directory ("") to the directory list explicitly
   - Change directory processing order to depth-first (children before parents)
   - Pass child DirectorySummaries to parent directory generation
   - Update signature computation to include child purposes
   - Store DirectorySummaries as they're generated for parent access

2. `backend/src/oya/generation/prompts.py`
   - Update `DIRECTORY_TEMPLATE` with new structure (breadcrumb, subdirectories table, files table)
   - Add helper for formatting subdirectory summaries
   - Add helper for generating breadcrumb markdown

3. `backend/src/oya/generation/directory.py`
   - Accept child DirectorySummaries as input
   - Accept project name for breadcrumb generation
   - Generate breadcrumb trail
   - Format subdirectory table with links
   - Format file table with links

4. `backend/src/oya/generation/summaries.py`
   - No changes expected (DirectorySummary already has needed fields)

5. `backend/src/oya/repo/file_filter.py`
   - Update `extract_directories_from_files()` to include root directory

## Testing

1. **Unit tests**:
   - Breadcrumb generation for various depths
   - Link path generation
   - Signature computation with child summaries
   - Bottom-up ordering logic

2. **Integration tests**:
   - Generate wiki for test repo, verify all links work
   - Modify child directory, verify parent regenerates
   - Verify consistent page structure across all directories

## Migration

Existing wikis will regenerate all directory pages on next run due to:
1. Template structure change
2. Signature algorithm change

This is acceptable as directory generation is fast relative to file generation.

## Design Decisions

1. **Root directory page**: Yes, there will be an explicit root directory page. This requires special handling since the root isn't extracted from file paths like other directories. The root page will:
   - Have no breadcrumb (or just show the project name)
   - List all top-level directories as subdirectories
   - List all top-level files
   - Serve as the entry point for directory navigation

2. **Large directories**: Show all files regardless of count. No pagination or collapsing. Users need the complete picture, and search/ctrl+F can help find specific files.
