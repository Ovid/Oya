# Collapse Excluded Directory Children Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** When a directory is explicitly excluded by a pattern, show only that directory in the exclusion list—not its children.

**Architecture:** Add a first pass in `get_files_categorized()` to identify directories explicitly matching exclusion patterns. Then skip files whose ancestors are in those sets. The response includes excluded directories in the `directories` field.

**Tech Stack:** Python 3.11+, pytest

---

## Task 1: Add Helper Function to Check for Excluded Ancestors

**Files:**
- Modify: `backend/src/oya/repo/file_filter.py:1-18`
- Test: `backend/tests/test_file_filter.py` (new)

**Step 1: Write the failing test**

Create `backend/tests/test_file_filter.py`:

```python
"""Tests for file_filter helper functions."""

from oya.repo.file_filter import _has_excluded_ancestor


def test_has_excluded_ancestor_returns_true_for_direct_parent():
    """File in excluded directory should return True."""
    excluded_dirs = {".git"}
    assert _has_excluded_ancestor(".git/config", excluded_dirs) is True


def test_has_excluded_ancestor_returns_true_for_nested_path():
    """File nested deeply in excluded directory should return True."""
    excluded_dirs = {".git"}
    assert _has_excluded_ancestor(".git/objects/ab/1234", excluded_dirs) is True


def test_has_excluded_ancestor_returns_false_for_unrelated_path():
    """File not in excluded directory should return False."""
    excluded_dirs = {".git"}
    assert _has_excluded_ancestor("src/main.py", excluded_dirs) is False


def test_has_excluded_ancestor_returns_false_for_empty_set():
    """Empty excluded set should return False for any path."""
    excluded_dirs = set()
    assert _has_excluded_ancestor(".git/config", excluded_dirs) is False


def test_has_excluded_ancestor_handles_multiple_excluded_dirs():
    """Should check against all excluded directories."""
    excluded_dirs = {".git", "node_modules", "build"}
    assert _has_excluded_ancestor("node_modules/lodash/index.js", excluded_dirs) is True
    assert _has_excluded_ancestor("build/output.js", excluded_dirs) is True
    assert _has_excluded_ancestor("src/app.py", excluded_dirs) is False
```

**Step 2: Run test to verify it fails**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_file_filter.py -v`
Expected: FAIL with "cannot import name '_has_excluded_ancestor'"

**Step 3: Write minimal implementation**

Add to `backend/src/oya/repo/file_filter.py` after the imports (before `CategorizedFiles` class):

```python
def _has_excluded_ancestor(file_path: str, excluded_dirs: set[str]) -> bool:
    """Check if any ancestor directory of file_path is in excluded_dirs.

    Args:
        file_path: Relative file path (e.g., ".git/objects/ab/1234").
        excluded_dirs: Set of directory paths that are excluded.

    Returns:
        True if any ancestor directory is in excluded_dirs.
    """
    parts = file_path.split("/")
    # Check each ancestor (not including the file itself)
    for i in range(1, len(parts)):
        ancestor = "/".join(parts[:i])
        if ancestor in excluded_dirs:
            return True
    return False
```

**Step 4: Run test to verify it passes**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_file_filter.py -v`
Expected: PASS

**Step 5: Commit**

```bash
cd backend && git add src/oya/repo/file_filter.py tests/test_file_filter.py
git commit -m "$(cat <<'EOF'
feat: add _has_excluded_ancestor helper function

Checks if any ancestor directory of a file path is in a set of
excluded directories. This will be used to collapse children of
explicitly excluded directories in the indexing preview.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Add Helper to Check if Directory Matches Exclusion Patterns

**Files:**
- Modify: `backend/src/oya/repo/file_filter.py` (FileFilter class)
- Test: `backend/tests/test_file_filter.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_file_filter.py`:

```python
from pathlib import Path
from oya.repo.file_filter import FileFilter


def test_is_directory_excluded_by_default_rules(tmp_path):
    """Directory matching DEFAULT_EXCLUDES should be detected."""
    ff = FileFilter(tmp_path)

    # .git matches ".*" pattern
    assert ff._is_directory_excluded_by_default_rules(".git") is True
    # node_modules matches "node_modules" pattern
    assert ff._is_directory_excluded_by_default_rules("node_modules") is True
    # Regular directory should not be excluded
    assert ff._is_directory_excluded_by_default_rules("src") is False


def test_is_directory_excluded_by_oyaignore(tmp_path):
    """Directory matching .oyaignore patterns should be detected."""
    # Create .oyaignore with directory pattern
    (tmp_path / ".oyaignore").write_text("build/\ndocs\n")
    ff = FileFilter(tmp_path)

    # build/ explicitly targets directory
    assert ff._is_directory_excluded_by_oyaignore("build") is True
    # docs matches as directory too
    assert ff._is_directory_excluded_by_oyaignore("docs") is True
    # src not in oyaignore
    assert ff._is_directory_excluded_by_oyaignore("src") is False
```

**Step 2: Run test to verify it fails**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_file_filter.py::test_is_directory_excluded_by_default_rules tests/test_file_filter.py::test_is_directory_excluded_by_oyaignore -v`
Expected: FAIL with "has no attribute '_is_directory_excluded_by_default_rules'"

**Step 3: Write minimal implementation**

Add these methods to the `FileFilter` class in `backend/src/oya/repo/file_filter.py`:

```python
    def _is_directory_excluded_by_default_rules(self, dir_path: str) -> bool:
        """Check if a directory is explicitly excluded by DEFAULT_EXCLUDES patterns.

        This checks if the directory itself matches a pattern, not if files
        within it would be excluded.

        Args:
            dir_path: Relative directory path (e.g., ".git", "node_modules").

        Returns:
            True if directory matches a default exclusion pattern.
        """
        return self._is_excluded_by_patterns(dir_path, self.default_exclude_patterns)

    def _is_directory_excluded_by_oyaignore(self, dir_path: str) -> bool:
        """Check if a directory is explicitly excluded by .oyaignore patterns.

        Args:
            dir_path: Relative directory path.

        Returns:
            True if directory matches an oyaignore pattern.
        """
        return self._is_excluded_by_patterns(dir_path, self.oyaignore_patterns)
```

**Step 4: Run test to verify it passes**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_file_filter.py -v`
Expected: PASS

**Step 5: Commit**

```bash
cd backend && git add src/oya/repo/file_filter.py tests/test_file_filter.py
git commit -m "$(cat <<'EOF'
feat: add directory exclusion check methods to FileFilter

Add _is_directory_excluded_by_default_rules and
_is_directory_excluded_by_oyaignore to check if a directory
itself matches exclusion patterns (vs checking files within it).

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Modify get_files_categorized to Collect Excluded Directories First

**Files:**
- Modify: `backend/src/oya/repo/file_filter.py:311-371` (get_files_categorized method)
- Test: `backend/tests/test_file_filter.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_file_filter.py`:

```python
def test_get_files_categorized_collects_excluded_directories(tmp_path):
    """get_files_categorized should identify explicitly excluded directories."""
    # Create directory structure
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("git config")
    (tmp_path / ".git" / "objects").mkdir()
    (tmp_path / ".git" / "objects" / "ab").mkdir()
    (tmp_path / ".git" / "objects" / "ab" / "1234").write_text("blob")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('hello')")

    ff = FileFilter(tmp_path)
    result = ff.get_files_categorized()

    # .git should be in excluded_by_rule (directory only)
    # but individual files inside .git should NOT be listed
    assert ".git" in result.excluded_dirs_by_rule
    assert ".git/config" not in result.excluded_by_rule
    assert ".git/objects/ab/1234" not in result.excluded_by_rule

    # src/main.py should still be included
    assert "src/main.py" in result.included
```

**Step 2: Run test to verify it fails**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_file_filter.py::test_get_files_categorized_collects_excluded_directories -v`
Expected: FAIL with "has no attribute 'excluded_dirs_by_rule'"

**Step 3: Update CategorizedFiles dataclass**

Modify `CategorizedFiles` in `backend/src/oya/repo/file_filter.py`:

```python
@dataclass
class CategorizedFiles:
    """Files categorized by exclusion reason."""

    included: list[str] = field(default_factory=list)
    excluded_by_oyaignore: list[str] = field(default_factory=list)
    excluded_by_rule: list[str] = field(default_factory=list)
    # Directories explicitly excluded (shown instead of their children)
    excluded_dirs_by_rule: list[str] = field(default_factory=list)
    excluded_dirs_by_oyaignore: list[str] = field(default_factory=list)
```

**Step 4: Modify get_files_categorized to collect directories first**

Replace the `get_files_categorized` method:

```python
    def get_files_categorized(self) -> CategorizedFiles:
        """Get files categorized by exclusion reason.

        Returns files in three categories:
        - included: Files that will be indexed
        - excluded_by_oyaignore: Files excluded via .oyaignore (user can re-include)
        - excluded_by_rule: Files excluded via built-in rules (cannot be changed)

        When a directory is explicitly excluded by a pattern, only the directory
        is listed (not its children). This reduces noise in the indexing preview.

        Note: Files excluded by rule take precedence. A file excluded by both
        default rules AND oyaignore will appear only in excluded_by_rule.

        Returns:
            CategorizedFiles with files in each category.
        """
        result = CategorizedFiles()

        # First pass: collect directories that are explicitly excluded by patterns
        excluded_dirs_by_rule: set[str] = set()
        excluded_dirs_by_oyaignore: set[str] = set()

        for dir_path in self.repo_path.rglob("*"):
            if not dir_path.is_dir():
                continue

            relative = str(dir_path.relative_to(self.repo_path))

            # Check if this directory is explicitly excluded by default rules
            if self._is_directory_excluded_by_default_rules(relative):
                # Only add if no ancestor is already excluded
                if not _has_excluded_ancestor(relative, excluded_dirs_by_rule):
                    excluded_dirs_by_rule.add(relative)
            # Check if excluded by oyaignore (only if not already by rules)
            elif self._is_directory_excluded_by_oyaignore(relative):
                if not _has_excluded_ancestor(relative, excluded_dirs_by_oyaignore):
                    excluded_dirs_by_oyaignore.add(relative)

        # Second pass: categorize files, skipping those in excluded directories
        for file_path in self.repo_path.rglob("*"):
            if not file_path.is_file():
                continue

            relative = str(file_path.relative_to(self.repo_path))

            # Skip files in directories excluded by rule
            if _has_excluded_ancestor(relative, excluded_dirs_by_rule):
                continue

            # Skip files in directories excluded by oyaignore
            if _has_excluded_ancestor(relative, excluded_dirs_by_oyaignore):
                continue

            # Check if excluded by default rules first (takes precedence)
            if self._is_excluded_by_default_rules(relative):
                result.excluded_by_rule.append(relative)
                continue

            # Check file properties that are "rule" based exclusions
            # Check size
            try:
                if file_path.stat().st_size > self.max_file_size_bytes:
                    result.excluded_by_rule.append(relative)
                    continue
            except OSError:
                result.excluded_by_rule.append(relative)
                continue

            # Check binary
            if self._is_binary(file_path):
                result.excluded_by_rule.append(relative)
                continue

            # Check minified (only for text files that passed other checks)
            if self._is_minified(file_path):
                result.excluded_by_rule.append(relative)
                continue

            # Check if excluded by oyaignore (user-configurable)
            if self._is_excluded_by_oyaignore(relative):
                result.excluded_by_oyaignore.append(relative)
                continue

            # File is included
            result.included.append(relative)

        # Store excluded directories
        result.excluded_dirs_by_rule = sorted(excluded_dirs_by_rule)
        result.excluded_dirs_by_oyaignore = sorted(excluded_dirs_by_oyaignore)

        # Sort all lists
        result.included.sort()
        result.excluded_by_oyaignore.sort()
        result.excluded_by_rule.sort()

        return result
```

**Step 5: Run test to verify it passes**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_file_filter.py::test_get_files_categorized_collects_excluded_directories -v`
Expected: PASS

**Step 6: Commit**

```bash
cd backend && git add src/oya/repo/file_filter.py tests/test_file_filter.py
git commit -m "$(cat <<'EOF'
feat: collapse excluded directory children in get_files_categorized

When a directory is explicitly excluded by a pattern (DEFAULT_EXCLUDES
or .oyaignore), only the directory is returned - not its children.
This dramatically reduces noise in the indexing preview for directories
like .git that contain many files.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Update API Router to Include Excluded Directories

**Files:**
- Modify: `backend/src/oya/api/routers/repos.py:38-89`
- Modify: `backend/src/oya/api/schemas.py` (if needed)
- Test: `backend/tests/test_indexable_categories.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_indexable_categories.py`:

```python
async def test_excluded_directory_children_not_listed(client, temp_workspace):
    """Files inside explicitly excluded directories should not appear individually."""
    # Create a deeply nested structure in node_modules
    (temp_workspace / "node_modules" / "lodash").mkdir(parents=True)
    (temp_workspace / "node_modules" / "lodash" / "index.js").write_text("module.exports = {}")
    (temp_workspace / "node_modules" / "lodash" / "fp.js").write_text("module.exports = {}")

    response = await client.get("/api/repos/indexable")

    assert response.status_code == 200
    data = response.json()

    # node_modules directory should be in excluded_by_rule directories
    assert "node_modules" in data["excluded_by_rule"]["directories"]

    # Individual files inside should NOT be listed
    assert "node_modules/dep.js" not in data["excluded_by_rule"]["files"]
    assert "node_modules/lodash/index.js" not in data["excluded_by_rule"]["files"]
    assert "node_modules/lodash/fp.js" not in data["excluded_by_rule"]["files"]


async def test_oyaignore_directory_children_not_listed(client, temp_workspace):
    """Files inside directories excluded by .oyaignore should not appear individually."""
    # Create nested files in excluded_dir (already excluded by .oyaignore in fixture)
    (temp_workspace / "excluded_dir" / "subdir").mkdir()
    (temp_workspace / "excluded_dir" / "subdir" / "deep.py").write_text("# deep file")

    response = await client.get("/api/repos/indexable")

    assert response.status_code == 200
    data = response.json()

    # excluded_dir should be in directories
    assert "excluded_dir" in data["excluded_by_oyaignore"]["directories"]

    # Individual files should NOT be listed
    assert "excluded_dir/file.py" not in data["excluded_by_oyaignore"]["files"]
    assert "excluded_dir/subdir/deep.py" not in data["excluded_by_oyaignore"]["files"]
```

**Step 2: Run test to verify it fails**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_indexable_categories.py::test_excluded_directory_children_not_listed tests/test_indexable_categories.py::test_oyaignore_directory_children_not_listed -v`
Expected: FAIL (files still appear in the lists)

**Step 3: Update the API router**

Modify `backend/src/oya/api/routers/repos.py` `get_indexable_items` function. Find where it calls `extract_directories_from_files` and update to include the new excluded directories:

```python
@router.get("/indexable", response_model=IndexableItems)
async def get_indexable_items():
    """Get indexable items categorized by exclusion status."""
    settings = load_settings()
    source_path = get_active_repo_source_path()
    if not source_path.exists():
        raise HTTPException(status_code=404, detail="No active repository")

    file_filter = FileFilter(source_path)
    categorized = file_filter.get_files_categorized()

    # For included and rule-excluded, derive directories from files
    # For excluded directories, add them explicitly
    included_dirs = extract_directories_from_files(categorized.included)

    # Combine file-derived directories with explicitly excluded directories
    rule_dirs = list(
        set(extract_directories_from_files(categorized.excluded_by_rule))
        | set(categorized.excluded_dirs_by_rule)
    )
    rule_dirs.sort()

    oyaignore_dirs = list(
        set(extract_directories_from_files(categorized.excluded_by_oyaignore))
        | set(categorized.excluded_dirs_by_oyaignore)
    )
    oyaignore_dirs.sort()

    return IndexableItems(
        included=FileList(
            directories=included_dirs,
            files=categorized.included,
        ),
        excluded_by_oyaignore=FileList(
            directories=oyaignore_dirs,
            files=categorized.excluded_by_oyaignore,
        ),
        excluded_by_rule=FileList(
            directories=rule_dirs,
            files=categorized.excluded_by_rule,
        ),
    )
```

**Step 4: Run test to verify it passes**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_indexable_categories.py -v`
Expected: PASS

**Step 5: Commit**

```bash
cd backend && git add src/oya/api/routers/repos.py tests/test_indexable_categories.py
git commit -m "$(cat <<'EOF'
feat: include explicitly excluded directories in API response

The /api/repos/indexable endpoint now returns excluded directories
in the directories field, and files within those directories are
no longer listed individually. This reduces the payload size and
makes the indexing preview cleaner.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Add Edge Case Tests

**Files:**
- Test: `backend/tests/test_file_filter.py`
- Test: `backend/tests/test_indexable_categories.py`

**Step 1: Write edge case tests**

Add to `backend/tests/test_file_filter.py`:

```python
def test_nested_excluded_dirs_only_show_outermost(tmp_path):
    """When both parent and child match patterns, only parent appears."""
    # .git matches ".*", .git/hooks also matches but shouldn't appear
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "hooks").mkdir()
    (tmp_path / ".git" / "hooks" / "pre-commit").write_text("#!/bin/bash")

    ff = FileFilter(tmp_path)
    result = ff.get_files_categorized()

    # Only .git should appear, not .git/hooks
    assert ".git" in result.excluded_dirs_by_rule
    assert ".git/hooks" not in result.excluded_dirs_by_rule


def test_file_pattern_does_not_collapse_directory(tmp_path):
    """File patterns like *.log should not collapse directories."""
    (tmp_path / "logs").mkdir()
    (tmp_path / "logs" / "app.log").write_text("log content")
    (tmp_path / "logs" / "error.log").write_text("error content")
    (tmp_path / "logs" / "readme.txt").write_text("log readme")

    # Add *.log to oyaignore (file pattern, not directory)
    (tmp_path / ".oyaignore").write_text("*.log\n")

    ff = FileFilter(tmp_path)
    result = ff.get_files_categorized()

    # logs directory should NOT be collapsed
    assert "logs" not in result.excluded_dirs_by_oyaignore

    # Individual .log files should be listed
    assert "logs/app.log" in result.excluded_by_oyaignore
    assert "logs/error.log" in result.excluded_by_oyaignore

    # readme.txt should be included
    assert "logs/readme.txt" in result.included


def test_root_directory_never_collapsed(tmp_path):
    """Root directory should never be collapsed even if it somehow matches."""
    (tmp_path / "main.py").write_text("print('hello')")

    ff = FileFilter(tmp_path)
    result = ff.get_files_categorized()

    # Root should not appear in excluded dirs
    assert "" not in result.excluded_dirs_by_rule
    assert "" not in result.excluded_dirs_by_oyaignore

    # Files should still be processed
    assert "main.py" in result.included
```

**Step 2: Run all tests**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_file_filter.py tests/test_indexable_categories.py -v`
Expected: PASS

**Step 3: Commit**

```bash
cd backend && git add tests/test_file_filter.py
git commit -m "$(cat <<'EOF'
test: add edge case tests for directory collapsing

- Nested excluded directories only show outermost parent
- File patterns (*.log) don't collapse directories
- Root directory is never collapsed

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Run Full Test Suite and Verify

**Files:**
- None (verification only)

**Step 1: Run all backend tests**

Run: `cd backend && source .venv/bin/activate && pytest -v`
Expected: All tests pass

**Step 2: Run frontend tests**

Run: `cd frontend && npm run test`
Expected: All tests pass (frontend unchanged, but verify no regressions)

**Step 3: Manual verification (optional)**

Start the dev server and verify the indexing preview modal shows:
- `.git` as a single directory, not hundreds of files
- `node_modules` as a single directory
- Other explicitly excluded directories collapsed

---

## Task 7: Update Existing Tests That Expect Old Behavior

**Files:**
- Modify: `backend/tests/test_indexable_categories.py:107-118`

**Step 1: Check if existing tests need updates**

The test `test_rule_excluded_files_are_correct` currently asserts:
```python
assert "node_modules/dep.js" in data["excluded_by_rule"]["files"]
```

This will fail with our new behavior. Update it:

```python
async def test_rule_excluded_files_are_correct(client, temp_workspace):
    """Test that excluded_by_rule category contains directories excluded via DEFAULT_EXCLUDES."""
    response = await client.get("/api/repos/indexable")

    assert response.status_code == 200
    data = response.json()

    # node_modules directory should be in excluded_by_rule directories
    # (files inside are no longer listed individually)
    assert "node_modules" in data["excluded_by_rule"]["directories"]

    # Individual files inside excluded directories are NOT listed
    assert "node_modules/dep.js" not in data["excluded_by_rule"]["files"]
```

Similarly update `test_oyaignore_excluded_files_are_correct`:

```python
async def test_oyaignore_excluded_files_are_correct(client, temp_workspace):
    """Test that excluded_by_oyaignore category contains directories excluded via .oyaignore."""
    response = await client.get("/api/repos/indexable")

    assert response.status_code == 200
    data = response.json()

    # Files excluded by file pattern (not directory) are still listed
    assert "excluded_file.txt" in data["excluded_by_oyaignore"]["files"]

    # Directory excluded by pattern - directory listed, not individual files
    assert "excluded_dir" in data["excluded_by_oyaignore"]["directories"]
    assert "excluded_dir/file.py" not in data["excluded_by_oyaignore"]["files"]
```

**Step 2: Run tests to verify**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_indexable_categories.py -v`
Expected: PASS

**Step 3: Commit**

```bash
cd backend && git add tests/test_indexable_categories.py
git commit -m "$(cat <<'EOF'
test: update tests for new directory collapsing behavior

Tests now expect excluded directories to appear in directories field
with their children not listed individually in files.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

## Summary

After completing all tasks:
1. Helper function `_has_excluded_ancestor` checks if a file is inside an excluded directory
2. `FileFilter` has methods to check if directories match exclusion patterns
3. `get_files_categorized()` identifies excluded directories first, then skips their children
4. API returns excluded directories in the `directories` field
5. Frontend receives fewer files, cleaner UI with no code changes needed
