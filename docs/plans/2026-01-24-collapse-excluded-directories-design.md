# Collapse Excluded Directory Children in Indexing Preview

## Problem

The Indexing Preview modal shows every file individually, even when a parent directory is excluded by rules or `.oyaignore`. This creates noise—for example, showing hundreds of files under `.git/` when the user just needs to know `.git` is excluded.

## Solution

When a directory is explicitly excluded by a pattern, show only the directory in the exclusion list—not its children.

## Scope

- Applies to **excluded_by_rule** and **excluded_by_oyaignore** sections
- Does **not** apply to the **included** section (users need file-level detail there)
- Only collapses directories explicitly matched by patterns, not directories where all files happen to be excluded by file-level patterns

## Implementation

### Data Flow

1. Walk all files in repo
2. **First pass:** Identify directories explicitly excluded by pattern (DEFAULT_EXCLUDES or .oyaignore)
3. **Second pass:** For each file, skip if any parent directory is already marked as excluded
4. Categorize remaining files into three buckets
5. Return files + explicitly-excluded directories in each bucket

### Files to Modify

**`backend/src/oya/repo/file_filter.py`:**

Add helper function:
```python
def _has_excluded_ancestor(file_path: str, excluded_dirs: set[str]) -> bool:
    parts = Path(file_path).parts
    for i in range(len(parts)):
        ancestor = str(Path(*parts[:i+1]))
        if ancestor in excluded_dirs:
            return True
    return False
```

Modify `get_files_categorized()`:
- Collect explicitly excluded directories into `excluded_dirs_by_rule` and `excluded_dirs_by_oyaignore` sets
- Skip files whose ancestors are in the appropriate excluded set
- Include excluded directories in `FileList.directories`

**`backend/tests/test_indexable_categories.py`:**

Add test cases (see below).

### Frontend Changes

None required. The modal already renders `directories` and `files` from each category.

### Schema Changes

None required. Existing `FileList` schema already has `directories` and `files` fields.

## Edge Cases

1. **Nested excluded directories** - If both `.git` and `.git/hooks` match patterns, only `.git` appears
2. **Directory vs file patterns** - `*.log` excludes files; `logs` or `logs/` excludes directory
3. **Root directory** - Never collapse root, even if somehow matched
4. **Trailing slashes** - `build/` targets directories explicitly; handled by existing pattern matching

## Test Cases

1. Files under `.git/` don't appear when `.git` is excluded by rule
2. Files under `node_modules/` don't appear when `node_modules` is excluded by rule
3. Files under user-excluded directory (via .oyaignore) don't appear in `excluded_by_oyaignore`
4. Partially-excluded directories still show individual files (e.g., `*.test.js` pattern)
5. Nested exclusions only show outermost parent
