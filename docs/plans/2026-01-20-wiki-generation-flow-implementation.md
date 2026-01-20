# Wiki Generation Flow Redesign - Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Consolidate Preview and Generate into a single flow where clicking "Generate Wiki" opens a modal showing all files, with clear exclusion management and a confirmation dialog before generation starts.

**Architecture:** Single entry point (Generate Wiki button) opens modal with three file categories (included, .oyaignore excluded, rule-excluded). Users toggle inclusions, click Generate, see confirmation summary, confirm to start generation. Q&A is disabled during generation.

**Tech Stack:** React/TypeScript frontend with Tailwind CSS, Python/FastAPI backend with Pydantic schemas.

---

## Task 1: Create ConfirmationDialog Component

**Files:**
- Create: `frontend/src/components/ConfirmationDialog.tsx`
- Create: `frontend/src/components/ConfirmationDialog.test.tsx`

**Step 1: Write the failing tests**

```typescript
// frontend/src/components/ConfirmationDialog.test.tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { ConfirmationDialog } from './ConfirmationDialog'

describe('ConfirmationDialog', () => {
  const defaultProps = {
    isOpen: true,
    title: 'Test Title',
    onConfirm: vi.fn(),
    onCancel: vi.fn(),
  }

  it('renders nothing when isOpen is false', () => {
    render(<ConfirmationDialog {...defaultProps} isOpen={false}>Content</ConfirmationDialog>)
    expect(screen.queryByText('Test Title')).not.toBeInTheDocument()
  })

  it('renders title and children when open', () => {
    render(<ConfirmationDialog {...defaultProps}>Test Content</ConfirmationDialog>)
    expect(screen.getByText('Test Title')).toBeInTheDocument()
    expect(screen.getByText('Test Content')).toBeInTheDocument()
  })

  it('uses default button labels', () => {
    render(<ConfirmationDialog {...defaultProps}>Content</ConfirmationDialog>)
    expect(screen.getByText('Cancel')).toBeInTheDocument()
    expect(screen.getByText('Confirm')).toBeInTheDocument()
  })

  it('uses custom button labels', () => {
    render(
      <ConfirmationDialog {...defaultProps} cancelLabel="Go Back" confirmLabel="Proceed">
        Content
      </ConfirmationDialog>
    )
    expect(screen.getByText('Go Back')).toBeInTheDocument()
    expect(screen.getByText('Proceed')).toBeInTheDocument()
  })

  it('calls onCancel when cancel button clicked', () => {
    const onCancel = vi.fn()
    render(<ConfirmationDialog {...defaultProps} onCancel={onCancel}>Content</ConfirmationDialog>)
    fireEvent.click(screen.getByText('Cancel'))
    expect(onCancel).toHaveBeenCalledTimes(1)
  })

  it('calls onConfirm when confirm button clicked', () => {
    const onConfirm = vi.fn()
    render(<ConfirmationDialog {...defaultProps} onConfirm={onConfirm}>Content</ConfirmationDialog>)
    fireEvent.click(screen.getByText('Confirm'))
    expect(onConfirm).toHaveBeenCalledTimes(1)
  })

  it('calls onCancel when backdrop clicked', () => {
    const onCancel = vi.fn()
    render(<ConfirmationDialog {...defaultProps} onCancel={onCancel}>Content</ConfirmationDialog>)
    fireEvent.click(screen.getByTestId('confirmation-backdrop'))
    expect(onCancel).toHaveBeenCalledTimes(1)
  })

  it('does not close when dialog content clicked', () => {
    const onCancel = vi.fn()
    render(<ConfirmationDialog {...defaultProps} onCancel={onCancel}>Content</ConfirmationDialog>)
    fireEvent.click(screen.getByText('Test Content'))
    expect(onCancel).not.toHaveBeenCalled()
  })
})
```

**Step 2: Run tests to verify they fail**

Run: `cd frontend && npm test -- --run src/components/ConfirmationDialog.test.tsx`
Expected: FAIL - module not found

**Step 3: Write the implementation**

```typescript
// frontend/src/components/ConfirmationDialog.tsx
interface ConfirmationDialogProps {
  isOpen: boolean
  title: string
  onConfirm: () => void
  onCancel: () => void
  confirmLabel?: string
  cancelLabel?: string
  children: React.ReactNode
}

export function ConfirmationDialog({
  isOpen,
  title,
  onConfirm,
  onCancel,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  children,
}: ConfirmationDialogProps) {
  if (!isOpen) return null

  const handleBackdropClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (e.target === e.currentTarget) {
      onCancel()
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      onClick={handleBackdropClick}
      data-testid="confirmation-backdrop"
    >
      <div
        className="bg-white dark:bg-gray-800 rounded-lg shadow-xl p-6 mx-4 max-w-md w-full"
        onClick={(e) => e.stopPropagation()}
      >
        <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">
          {title}
        </h3>
        <div className="text-sm text-gray-600 dark:text-gray-400 mb-6">
          {children}
        </div>
        <div className="flex justify-end space-x-2">
          <button
            onClick={onCancel}
            className="px-3 py-1.5 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-md"
          >
            {cancelLabel}
          </button>
          <button
            onClick={onConfirm}
            className="px-3 py-1.5 text-sm text-white bg-indigo-600 hover:bg-indigo-700 rounded-md"
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  )
}
```

**Step 4: Run tests to verify they pass**

Run: `cd frontend && npm test -- --run src/components/ConfirmationDialog.test.tsx`
Expected: PASS (8 tests)

**Step 5: Commit**

```bash
git add frontend/src/components/ConfirmationDialog.tsx frontend/src/components/ConfirmationDialog.test.tsx
git commit -m "feat(frontend): add ConfirmationDialog component

Reusable modal dialog for confirmation flows with customizable
title, content, and button labels."
```

---

## Task 2: Update Backend IndexableItems Response

**Files:**
- Modify: `backend/src/oya/api/schemas.py:69-76`
- Modify: `backend/src/oya/api/routers/repos.py:209-251`
- Modify: `backend/src/oya/repo/file_filter.py`
- Create: `backend/tests/test_indexable_categories.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_indexable_categories.py
"""Tests for indexable items API with exclusion categories."""

import pytest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient

from oya.main import app
from oya.repo.file_filter import FileFilter


@pytest.fixture
def temp_workspace(tmp_path):
    """Create a temporary workspace with test files."""
    # Create included files
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('hello')")
    (tmp_path / "README.md").write_text("# README")

    # Create files that will be excluded by rules
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "dep.js").write_text("module.exports = {}")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("[core]")

    # Create .oyaignore file
    (tmp_path / ".oyaignore").write_text("excluded_dir/\nexcluded_file.txt\n")
    (tmp_path / "excluded_dir").mkdir()
    (tmp_path / "excluded_dir" / "file.py").write_text("# excluded")
    (tmp_path / "excluded_file.txt").write_text("excluded")

    return tmp_path


def test_get_indexable_items_returns_three_categories(temp_workspace, monkeypatch):
    """Test that /api/repos/indexable returns included, oyaignore, and rule-excluded items."""
    monkeypatch.setenv("WORKSPACE_PATH", str(temp_workspace))

    # Clear settings cache
    from oya.config import load_settings
    load_settings.cache_clear()

    client = TestClient(app)
    response = client.get("/api/repos/indexable")

    assert response.status_code == 200
    data = response.json()

    # Check structure has three categories
    assert "included" in data
    assert "excludedByOyaignore" in data
    assert "excludedByRule" in data

    # Check included has files and directories
    assert "files" in data["included"]
    assert "directories" in data["included"]

    # Verify some expected categorization
    included_files = data["included"]["files"]
    oyaignore_files = data["excludedByOyaignore"]["files"]
    rule_excluded_dirs = data["excludedByRule"]["directories"]

    assert "src/main.py" in included_files
    assert "README.md" in included_files
    assert "excluded_file.txt" in oyaignore_files or "excluded_dir/" in data["excludedByOyaignore"]["directories"]
    assert "node_modules" in rule_excluded_dirs or ".git" in rule_excluded_dirs
```

**Step 2: Run test to verify it fails**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_indexable_categories.py -v`
Expected: FAIL - response doesn't have expected structure

**Step 3: Update the schema**

In `backend/src/oya/api/schemas.py`, replace lines 69-76:

```python
class FileList(BaseModel):
    """List of files and directories."""

    directories: list[str] = Field(default_factory=list)
    files: list[str] = Field(default_factory=list)


class IndexableItems(BaseModel):
    """List of indexable items categorized by exclusion status."""

    included: FileList
    excludedByOyaignore: FileList
    excludedByRule: FileList
```

**Step 4: Update FileFilter to track exclusion reasons**

Add new method to `backend/src/oya/repo/file_filter.py`:

```python
def get_files_categorized(self) -> dict[str, list[str]]:
    """Get files categorized by exclusion status.

    Returns:
        Dict with keys 'included', 'excluded_by_oyaignore', 'excluded_by_rule'.
    """
    included = []
    excluded_by_oyaignore = []
    excluded_by_rule = []

    # Track which patterns came from .oyaignore
    oyaignore_patterns = set()
    oyaignore_path = self.repo_path / ".oyaignore"
    if oyaignore_path.exists():
        for line in oyaignore_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                oyaignore_patterns.add(line)

    for file_path in self.repo_path.rglob("*"):
        if not file_path.is_file():
            continue

        relative = str(file_path.relative_to(self.repo_path))

        # Check if excluded and why
        exclusion_reason = self._get_exclusion_reason(relative, oyaignore_patterns)

        if exclusion_reason == "rule":
            excluded_by_rule.append(relative)
            continue
        elif exclusion_reason == "oyaignore":
            excluded_by_oyaignore.append(relative)
            continue

        # Apply size, binary, minified checks
        try:
            if file_path.stat().st_size > self.max_file_size_bytes:
                excluded_by_rule.append(relative)
                continue
        except OSError:
            excluded_by_rule.append(relative)
            continue

        if self._is_binary(file_path):
            excluded_by_rule.append(relative)
            continue

        if self._is_minified(file_path):
            excluded_by_rule.append(relative)
            continue

        included.append(relative)

    return {
        "included": sorted(included),
        "excluded_by_oyaignore": sorted(excluded_by_oyaignore),
        "excluded_by_rule": sorted(excluded_by_rule),
    }

def _get_exclusion_reason(self, path: str, oyaignore_patterns: set[str]) -> str | None:
    """Check if path is excluded and return reason.

    Args:
        path: Relative file path.
        oyaignore_patterns: Set of patterns from .oyaignore.

    Returns:
        'rule' if excluded by DEFAULT_EXCLUDES,
        'oyaignore' if excluded by .oyaignore,
        None if not excluded.
    """
    # Check allowed paths first
    for allowed in ALLOWED_PATHS:
        if path.startswith(allowed + "/") or path == allowed:
            return None

    parts = path.split("/")

    # Check against DEFAULT_EXCLUDES only
    for pattern in DEFAULT_EXCLUDES:
        if self._pattern_matches(path, parts, pattern):
            return "rule"

    # Check against .oyaignore patterns
    for pattern in oyaignore_patterns:
        if self._pattern_matches(path, parts, pattern):
            return "oyaignore"

    return None

def _pattern_matches(self, path: str, parts: list[str], pattern: str) -> bool:
    """Check if a pattern matches the given path."""
    if pattern.endswith("/"):
        dir_pattern = pattern.rstrip("/")
        for part in parts:
            if fnmatch.fnmatch(part, dir_pattern):
                return True
    elif "/" in pattern:
        if path.startswith(pattern + "/") or path == pattern:
            return True
        if fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(path, pattern + "/*"):
            return True
    else:
        for part in parts:
            if fnmatch.fnmatch(part, pattern):
                return True
        if fnmatch.fnmatch(path, pattern):
            return True
    return False
```

**Step 5: Update the API endpoint**

In `backend/src/oya/api/routers/repos.py`, update lines 209-251:

```python
@router.get("/indexable", response_model=IndexableItems)
async def get_indexable_items(
    settings: Settings = Depends(get_settings),
) -> IndexableItems:
    """Get list of directories and files categorized by exclusion status."""
    workspace_path = settings.workspace_path
    if not workspace_path.exists():
        raise HTTPException(
            status_code=400, detail=f"Repository path is invalid or inaccessible: {workspace_path}"
        )
    if not workspace_path.is_dir():
        raise HTTPException(
            status_code=400, detail=f"Repository path is not a directory: {workspace_path}"
        )

    try:
        file_filter = FileFilter(settings.workspace_path)
        categorized = file_filter.get_files_categorized()

        included_files = categorized["included"]
        oyaignore_files = categorized["excluded_by_oyaignore"]
        rule_files = categorized["excluded_by_rule"]

        from oya.api.schemas import FileList

        return IndexableItems(
            included=FileList(
                directories=extract_directories_from_files(included_files),
                files=included_files,
            ),
            excludedByOyaignore=FileList(
                directories=extract_directories_from_files(oyaignore_files),
                files=oyaignore_files,
            ),
            excludedByRule=FileList(
                directories=extract_directories_from_files(rule_files),
                files=rule_files,
            ),
        )
    except PermissionError as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to enumerate files: Permission denied - {e}"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to enumerate files: {e}")
```

**Step 6: Run test to verify it passes**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_indexable_categories.py -v`
Expected: PASS

**Step 7: Run full backend test suite**

Run: `cd backend && source .venv/bin/activate && pytest -q`
Expected: All tests pass

**Step 8: Commit**

```bash
git add backend/src/oya/api/schemas.py backend/src/oya/api/routers/repos.py backend/src/oya/repo/file_filter.py backend/tests/test_indexable_categories.py
git commit -m "feat(backend): categorize indexable items by exclusion reason

API now returns three categories: included, excludedByOyaignore, and
excludedByRule to enable clearer UI presentation of file status."
```

---

## Task 3: Update Backend Oyaignore Endpoint for Removals

**Files:**
- Modify: `backend/src/oya/api/schemas.py:78-90`
- Modify: `backend/src/oya/api/routers/repos.py:254-366`
- Create: `backend/tests/test_oyaignore_removals.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_oyaignore_removals.py
"""Tests for .oyaignore removal functionality."""

import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from oya.main import app


@pytest.fixture
def temp_workspace_with_oyaignore(tmp_path):
    """Create workspace with existing .oyaignore."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('hello')")
    (tmp_path / "excluded_dir").mkdir()
    (tmp_path / "excluded_dir" / "file.py").write_text("# excluded")
    (tmp_path / "excluded_file.txt").write_text("excluded")

    # Create existing .oyaignore
    (tmp_path / ".oyaignore").write_text("excluded_dir/\nexcluded_file.txt\nold_pattern/\n")

    return tmp_path


def test_oyaignore_removal(temp_workspace_with_oyaignore, monkeypatch):
    """Test that removals parameter removes patterns from .oyaignore."""
    monkeypatch.setenv("WORKSPACE_PATH", str(temp_workspace_with_oyaignore))

    from oya.config import load_settings
    load_settings.cache_clear()

    client = TestClient(app)
    response = client.post(
        "/api/repos/oyaignore",
        json={
            "directories": [],
            "files": [],
            "removals": ["excluded_dir/", "old_pattern/"]
        }
    )

    assert response.status_code == 200
    data = response.json()

    # Check removals are reported
    assert "removed" in data
    assert "excluded_dir/" in data["removed"] or "excluded_dir" in data["removed"]

    # Verify file content
    oyaignore_content = (temp_workspace_with_oyaignore / ".oyaignore").read_text()
    assert "excluded_file.txt" in oyaignore_content
    assert "excluded_dir" not in oyaignore_content
    assert "old_pattern" not in oyaignore_content
```

**Step 2: Run test to verify it fails**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_oyaignore_removals.py -v`
Expected: FAIL - removals not supported

**Step 3: Update the schema**

In `backend/src/oya/api/schemas.py`, update the request/response:

```python
class OyaignoreUpdateRequest(BaseModel):
    """Request to update .oyaignore with exclusions and removals."""

    directories: list[str] = Field(default_factory=list)
    files: list[str] = Field(default_factory=list)
    removals: list[str] = Field(default_factory=list, description="Patterns to remove from .oyaignore")


class OyaignoreUpdateResponse(BaseModel):
    """Response after updating .oyaignore."""

    added_directories: list[str]
    added_files: list[str]
    removed: list[str]
    total_added: int
    total_removed: int
```

**Step 4: Update the endpoint**

In `backend/src/oya/api/routers/repos.py`, update the `update_oyaignore` function to handle removals:

```python
@router.post("/oyaignore", response_model=OyaignoreUpdateResponse)
async def update_oyaignore(
    request: OyaignoreUpdateRequest,
    settings: Settings = Depends(get_settings),
) -> OyaignoreUpdateResponse:
    """Update .oyaignore: add new exclusions and remove specified patterns."""
    oyaignore_path = settings.ignore_path

    try:
        # Read existing content
        existing_entries: list[str] = []
        comments_and_blanks: list[tuple[int, str]] = []

        if oyaignore_path.exists():
            for i, line in enumerate(oyaignore_path.read_text().splitlines()):
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    comments_and_blanks.append((len(existing_entries), line))
                else:
                    existing_entries.append(stripped)

        # Process removals first
        removals_set = set(request.removals)
        # Normalize removals (handle with/without trailing slash)
        normalized_removals = set()
        for r in removals_set:
            normalized_removals.add(r)
            normalized_removals.add(r.rstrip("/"))
            normalized_removals.add(r.rstrip("/") + "/")

        removed: list[str] = []
        remaining_entries: list[str] = []
        for entry in existing_entries:
            if entry in normalized_removals or entry.rstrip("/") in normalized_removals:
                removed.append(entry)
            else:
                remaining_entries.append(entry)

        existing_entries = remaining_entries
        existing_set = set(existing_entries)

        # Process additions (same logic as before)
        added_directories: list[str] = []
        added_files: list[str] = []
        all_dir_patterns: set[str] = set()

        for dir_path in request.directories:
            dir_pattern = dir_path.rstrip("/") + "/"
            all_dir_patterns.add(dir_pattern)
            if dir_pattern not in existing_set:
                existing_entries.append(dir_pattern)
                existing_set.add(dir_pattern)
                added_directories.append(dir_pattern)

        for entry in existing_set:
            if entry.endswith("/"):
                all_dir_patterns.add(entry)

        for file_path in request.files:
            if file_path not in existing_set:
                is_within_excluded_dir = False
                for dir_pattern in all_dir_patterns:
                    dir_prefix = dir_pattern.rstrip("/") + "/"
                    if file_path.startswith(dir_prefix):
                        is_within_excluded_dir = True
                        break
                if not is_within_excluded_dir:
                    existing_entries.append(file_path)
                    existing_set.add(file_path)
                    added_files.append(file_path)

        # Rebuild file with comments preserved
        final_lines: list[str] = []
        entry_idx = 0
        comment_idx = 0

        while entry_idx < len(existing_entries) or comment_idx < len(comments_and_blanks):
            while (
                comment_idx < len(comments_and_blanks)
                and comments_and_blanks[comment_idx][0] <= entry_idx
            ):
                final_lines.append(comments_and_blanks[comment_idx][1])
                comment_idx += 1

            if entry_idx < len(existing_entries):
                final_lines.append(existing_entries[entry_idx])
                entry_idx += 1

        while comment_idx < len(comments_and_blanks):
            final_lines.append(comments_and_blanks[comment_idx][1])
            comment_idx += 1

        # Write updated content
        with oyaignore_path.open("w") as f:
            if final_lines:
                f.write("\n".join(final_lines))
                f.write("\n")

        return OyaignoreUpdateResponse(
            added_directories=added_directories,
            added_files=added_files,
            removed=removed,
            total_added=len(added_directories) + len(added_files),
            total_removed=len(removed),
        )
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=f"Permission denied writing to .oyaignore: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update .oyaignore: {e}")
```

**Step 5: Run test to verify it passes**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_oyaignore_removals.py -v`
Expected: PASS

**Step 6: Run full backend test suite**

Run: `cd backend && source .venv/bin/activate && pytest -q`
Expected: All tests pass

**Step 7: Commit**

```bash
git add backend/src/oya/api/schemas.py backend/src/oya/api/routers/repos.py backend/tests/test_oyaignore_removals.py
git commit -m "feat(backend): add removal support to oyaignore endpoint

Allows re-including files that were previously excluded via .oyaignore
by specifying patterns in the 'removals' field."
```

---

## Task 4: Update Frontend Types for New API

**Files:**
- Modify: `frontend/src/types/index.ts:173-190`
- Modify: `frontend/src/api/client.ts:73-84`

**Step 1: Update types**

In `frontend/src/types/index.ts`, replace lines 173-190:

```typescript
// Indexing Preview Types
export interface FileList {
  directories: string[]
  files: string[]
}

export interface IndexableItems {
  included: FileList
  excludedByOyaignore: FileList
  excludedByRule: FileList
}

export interface OyaignoreUpdateRequest {
  directories: string[]
  files: string[]
  removals: string[]
}

export interface OyaignoreUpdateResponse {
  added_directories: string[]
  added_files: string[]
  removed: string[]
  total_added: number
  total_removed: number
}
```

**Step 2: Update API client**

In `frontend/src/api/client.ts`, the `getIndexableItems` and `updateOyaignore` functions don't need changes - they use the imported types. Verify imports at top of file include the new types.

**Step 3: Run type check**

Run: `cd frontend && npm run build`
Expected: No TypeScript errors

**Step 4: Commit**

```bash
git add frontend/src/types/index.ts frontend/src/api/client.ts
git commit -m "feat(frontend): update types for new indexable API response

Types now support three file categories and oyaignore removals."
```

---

## Task 5: Update IndexingPreviewModal Display States

**Files:**
- Modify: `frontend/src/components/IndexingPreviewModal.tsx`
- Modify: `frontend/src/components/IndexingPreviewModal.test.tsx`

**Step 1: Write the failing tests**

Add to `frontend/src/components/IndexingPreviewModal.test.tsx`:

```typescript
describe('file display states', () => {
  it('shows included files as checked by default', async () => {
    vi.mocked(api.getIndexableItems).mockResolvedValue({
      included: { directories: ['src'], files: ['src/main.ts'] },
      excludedByOyaignore: { directories: [], files: [] },
      excludedByRule: { directories: [], files: [] },
    })

    render(<IndexingPreviewModal isOpen={true} onClose={vi.fn()} onGenerate={vi.fn()} />)

    await waitFor(() => {
      const checkbox = screen.getByRole('checkbox', { name: /src\/main.ts/i })
      expect(checkbox).toBeChecked()
    })
  })

  it('shows oyaignore-excluded files as unchecked with badge', async () => {
    vi.mocked(api.getIndexableItems).mockResolvedValue({
      included: { directories: [], files: [] },
      excludedByOyaignore: { directories: [], files: ['excluded.ts'] },
      excludedByRule: { directories: [], files: [] },
    })

    render(<IndexingPreviewModal isOpen={true} onClose={vi.fn()} onGenerate={vi.fn()} />)

    await waitFor(() => {
      const checkbox = screen.getByRole('checkbox', { name: /excluded.ts/i })
      expect(checkbox).not.toBeChecked()
      expect(screen.getByText('(from .oyaignore)')).toBeInTheDocument()
    })
  })

  it('shows rule-excluded files as disabled with badge', async () => {
    vi.mocked(api.getIndexableItems).mockResolvedValue({
      included: { directories: [], files: [] },
      excludedByOyaignore: { directories: [], files: [] },
      excludedByRule: { directories: ['node_modules'], files: [] },
    })

    render(<IndexingPreviewModal isOpen={true} onClose={vi.fn()} onGenerate={vi.fn()} />)

    await waitFor(() => {
      const checkbox = screen.getByRole('checkbox', { name: /node_modules/i })
      expect(checkbox).toBeDisabled()
      expect(screen.getByText('(excluded by rule)')).toBeInTheDocument()
    })
  })
})
```

**Step 2: Run tests to verify they fail**

Run: `cd frontend && npm test -- --run src/components/IndexingPreviewModal.test.tsx`
Expected: FAIL - tests don't match current implementation

**Step 3: Update the component state and rendering**

This is a significant rewrite. The key changes:

1. Change state to track `pendingInclusions` (items to re-include from .oyaignore) and `pendingExclusions` (items to exclude from included)
2. Render three sections or unified list with visual differentiation
3. Update checkbox logic for inverted behavior (checked = included)

See the full implementation in the design doc. The modal now:
- Shows all files from three categories
- Included files: checked, can uncheck to exclude
- Oyaignore files: unchecked with "(from .oyaignore)" badge, can check to re-include
- Rule files: unchecked and disabled with "(excluded by rule)" badge

**Step 4: Run tests to verify they pass**

Run: `cd frontend && npm test -- --run src/components/IndexingPreviewModal.test.tsx`
Expected: PASS

**Step 5: Commit**

```bash
git add frontend/src/components/IndexingPreviewModal.tsx frontend/src/components/IndexingPreviewModal.test.tsx
git commit -m "feat(frontend): update modal to show three file categories

Files now display with clear visual distinction between included,
.oyaignore excluded (re-includable), and rule excluded (disabled)."
```

---

## Task 6: Update IndexingPreviewModal Flow

**Files:**
- Modify: `frontend/src/components/IndexingPreviewModal.tsx`
- Modify: `frontend/src/components/IndexingPreviewModal.test.tsx`

**Step 1: Write the failing tests**

```typescript
describe('generation flow', () => {
  it('shows Generate Wiki button instead of Save', async () => {
    vi.mocked(api.getIndexableItems).mockResolvedValue({
      included: { directories: [], files: ['main.ts'] },
      excludedByOyaignore: { directories: [], files: [] },
      excludedByRule: { directories: [], files: [] },
    })

    render(<IndexingPreviewModal isOpen={true} onClose={vi.fn()} onGenerate={vi.fn()} />)

    await waitFor(() => {
      expect(screen.getByText('Generate Wiki')).toBeInTheDocument()
      expect(screen.queryByText('Save')).not.toBeInTheDocument()
    })
  })

  it('shows confirmation dialog with summary when Generate clicked', async () => {
    vi.mocked(api.getIndexableItems).mockResolvedValue({
      included: { directories: ['src'], files: ['main.ts', 'utils.ts'] },
      excludedByOyaignore: { directories: [], files: [] },
      excludedByRule: { directories: [], files: [] },
    })

    render(<IndexingPreviewModal isOpen={true} onClose={vi.fn()} onGenerate={vi.fn()} />)

    await waitFor(() => screen.getByText('Generate Wiki'))
    fireEvent.click(screen.getByText('Generate Wiki'))

    expect(screen.getByText(/2 files will be indexed/i)).toBeInTheDocument()
  })

  it('calls onGenerate and closes after confirmation', async () => {
    const onGenerate = vi.fn()
    const onClose = vi.fn()
    vi.mocked(api.getIndexableItems).mockResolvedValue({
      included: { directories: [], files: ['main.ts'] },
      excludedByOyaignore: { directories: [], files: [] },
      excludedByRule: { directories: [], files: [] },
    })
    vi.mocked(api.updateOyaignore).mockResolvedValue({
      added_directories: [],
      added_files: [],
      removed: [],
      total_added: 0,
      total_removed: 0,
    })

    render(<IndexingPreviewModal isOpen={true} onClose={onClose} onGenerate={onGenerate} />)

    await waitFor(() => screen.getByText('Generate Wiki'))
    fireEvent.click(screen.getByText('Generate Wiki'))
    fireEvent.click(screen.getByText('Generate'))

    await waitFor(() => {
      expect(onGenerate).toHaveBeenCalled()
      expect(onClose).toHaveBeenCalled()
    })
  })

  it('warns about unsaved changes when closing with pending exclusions', async () => {
    vi.mocked(api.getIndexableItems).mockResolvedValue({
      included: { directories: [], files: ['main.ts'] },
      excludedByOyaignore: { directories: [], files: [] },
      excludedByRule: { directories: [], files: [] },
    })

    render(<IndexingPreviewModal isOpen={true} onClose={vi.fn()} onGenerate={vi.fn()} />)

    await waitFor(() => screen.getByText('main.ts'))

    // Uncheck a file to create pending exclusion
    fireEvent.click(screen.getByRole('checkbox', { name: /main.ts/i }))

    // Try to close
    fireEvent.click(screen.getByLabelText('Close'))

    expect(screen.getByText('Unsaved Changes')).toBeInTheDocument()
  })
})
```

**Step 2: Run tests to verify they fail**

Run: `cd frontend && npm test -- --run src/components/IndexingPreviewModal.test.tsx`
Expected: FAIL

**Step 3: Update component with new flow**

Update props interface to include `onGenerate`:

```typescript
interface IndexingPreviewModalProps {
  isOpen: boolean
  onClose: () => void
  onGenerate: () => void
}
```

Add confirmation states and logic:

```typescript
const [showGenerateConfirm, setShowGenerateConfirm] = useState(false)
const [showUnsavedWarning, setShowUnsavedWarning] = useState(false)

const handleGenerateClick = () => {
  setShowGenerateConfirm(true)
}

const handleConfirmGenerate = async () => {
  // Save exclusion changes
  if (hasChanges) {
    await api.updateOyaignore({
      directories: Array.from(pendingExclusions.directories),
      files: Array.from(pendingExclusions.files),
      removals: Array.from(pendingInclusions),
    })
  }
  onGenerate()
  onClose()
}

const handleClose = () => {
  if (hasChanges) {
    setShowUnsavedWarning(true)
  } else {
    onClose()
  }
}
```

**Step 4: Run tests to verify they pass**

Run: `cd frontend && npm test -- --run src/components/IndexingPreviewModal.test.tsx`
Expected: PASS

**Step 5: Commit**

```bash
git add frontend/src/components/IndexingPreviewModal.tsx frontend/src/components/IndexingPreviewModal.test.tsx
git commit -m "feat(frontend): update modal with generate flow and confirmations

Modal now has Generate Wiki button that shows confirmation dialog.
Warns about unsaved changes when closing with pending exclusions."
```

---

## Task 7: Update TopBar

**Files:**
- Modify: `frontend/src/components/TopBar.tsx`
- Modify: `frontend/src/components/TopBar.test.tsx`

**Step 1: Write the failing tests**

```typescript
describe('generation button', () => {
  it('shows single Generate Wiki button (no Preview)', () => {
    render(<TopBar {...defaultProps} />)
    expect(screen.getByText('Generate Wiki')).toBeInTheDocument()
    expect(screen.queryByText('Preview')).not.toBeInTheDocument()
  })

  it('opens modal when Generate Wiki clicked', () => {
    render(<TopBar {...defaultProps} />)
    fireEvent.click(screen.getByText('Generate Wiki'))
    expect(screen.getByText('Indexing Preview')).toBeInTheDocument()
  })

  it('calls startGeneration when modal confirms', async () => {
    // Mock the modal confirmation flow
    // ...
  })
})
```

**Step 2: Run tests to verify they fail**

Run: `cd frontend && npm test -- --run src/components/TopBar.test.tsx`
Expected: FAIL

**Step 3: Update TopBar**

Remove Preview button, make Generate Wiki open modal, pass `onGenerate={startGeneration}` to modal:

```typescript
// Remove lines 122-129 (Preview button when initialized)
// Remove lines 140-147 (Preview button when not initialized)

// Update the remaining Generate/Regenerate button to open modal:
<button
  onClick={() => setIsPreviewModalOpen(true)}
  disabled={isGenerating}
  className="px-3 py-1.5 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 rounded-md disabled:opacity-50"
>
  Generate Wiki
</button>

// Update modal props:
<IndexingPreviewModal
  isOpen={isPreviewModalOpen}
  onClose={() => setIsPreviewModalOpen(false)}
  onGenerate={() => startGeneration()}
/>
```

**Step 4: Run tests to verify they pass**

Run: `cd frontend && npm test -- --run src/components/TopBar.test.tsx`
Expected: PASS

**Step 5: Commit**

```bash
git add frontend/src/components/TopBar.tsx frontend/src/components/TopBar.test.tsx
git commit -m "feat(frontend): consolidate Preview and Generate into single button

Single 'Generate Wiki' button now opens modal. Generation starts
from modal after user reviews files and confirms."
```

---

## Task 8: Add Q&A Disable During Generation

**Files:**
- Modify: `frontend/src/components/TopBar.tsx`
- Modify: `frontend/src/components/AskPanel.tsx`
- Modify: `frontend/src/components/TopBar.test.tsx`
- Create: `frontend/src/components/AskPanel.test.tsx`

**Step 1: Write the failing tests**

For TopBar:

```typescript
describe('Ask button during generation', () => {
  it('disables Ask button when generation is running', () => {
    const stateWithJob = {
      ...mockState,
      currentJob: { status: 'running', job_id: '123' },
    }
    // Mock useApp to return generating state
    render(<TopBar {...defaultProps} />)

    const askButton = screen.getByText('Ask')
    expect(askButton).toBeDisabled()
    expect(askButton).toHaveAttribute('title', 'Q&A unavailable during generation')
  })
})
```

For AskPanel:

```typescript
// frontend/src/components/AskPanel.test.tsx
describe('AskPanel during generation', () => {
  it('shows disabled banner when generation is running', () => {
    // Mock context with currentJob.status === 'running'
    render(<AskPanel isOpen={true} onClose={vi.fn()} />)

    expect(screen.getByText(/Q&A is unavailable while the wiki is being generated/i)).toBeInTheDocument()
  })

  it('disables input field during generation', () => {
    render(<AskPanel isOpen={true} onClose={vi.fn()} />)

    const input = screen.getByPlaceholderText('Ask a question...')
    expect(input).toBeDisabled()
  })
})
```

**Step 2: Run tests to verify they fail**

Run: `cd frontend && npm test -- --run src/components/TopBar.test.tsx src/components/AskPanel.test.tsx`
Expected: FAIL

**Step 3: Update TopBar Ask button**

```typescript
const isGenerating = currentJob?.status === 'running'

// Update Ask button:
<button
  onClick={onToggleAskPanel}
  disabled={isGenerating}
  className={`px-3 py-1.5 text-sm font-medium rounded-md ${
    isGenerating
      ? 'opacity-50 cursor-not-allowed'
      : askPanelOpen
        ? 'text-white bg-indigo-600 hover:bg-indigo-700'
        : 'text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600'
  }`}
  title={isGenerating ? 'Q&A unavailable during generation' : 'Ask about the codebase'}
>
  Ask
</button>
```

**Step 4: Update AskPanel**

```typescript
import { useApp } from '../context/useApp'

export function AskPanel({ isOpen, onClose }: AskPanelProps) {
  const { state } = useApp()
  const isGenerating = state.currentJob?.status === 'running'

  // ... existing state ...

  // Add banner at top of panel content:
  {isGenerating && (
    <div className="p-3 bg-yellow-50 dark:bg-yellow-900/20 text-yellow-800 dark:text-yellow-200 text-sm border-b border-yellow-200 dark:border-yellow-800">
      Q&A is unavailable while the wiki is being generated.
    </div>
  )}

  // Update input disabled state:
  <input
    ...
    disabled={isLoading || isGenerating}
  />

  // Update submit button:
  <button
    ...
    disabled={isLoading || !question.trim() || isGenerating}
  >
```

**Step 5: Run tests to verify they pass**

Run: `cd frontend && npm test -- --run src/components/TopBar.test.tsx src/components/AskPanel.test.tsx`
Expected: PASS

**Step 6: Commit**

```bash
git add frontend/src/components/TopBar.tsx frontend/src/components/AskPanel.tsx frontend/src/components/TopBar.test.tsx frontend/src/components/AskPanel.test.tsx
git commit -m "feat(frontend): disable Q&A during wiki generation

Ask button grayed out with tooltip during generation.
AskPanel shows banner and disables input while generating."
```

---

## Task 9: Remove Up-to-Date Logic

**Files:**
- Modify: `frontend/src/context/AppContext.tsx`
- Modify: `frontend/src/components/UpToDateModal.tsx` (delete)
- Modify: `frontend/src/components/Layout.tsx` (remove modal)
- Modify: `backend/src/oya/api/routers/repos.py`

**Step 1: Remove frontend up-to-date state**

In `frontend/src/context/AppContext.tsx`:
- Remove `showUpToDateModal` from `AppState` interface (line 31)
- Remove from `initialState` (line 78)
- Remove `SET_UP_TO_DATE_MODAL` action type and case
- Remove lines 179-183 (the check for `changes_made === false`)
- Remove `dismissUpToDateModal` function
- Remove from context value

**Step 2: Delete UpToDateModal component**

```bash
rm frontend/src/components/UpToDateModal.tsx
rm frontend/src/components/UpToDateModal.test.tsx
```

**Step 3: Remove modal from Layout**

In `frontend/src/components/Layout.tsx`, remove the UpToDateModal import and usage.

**Step 4: Backend - remove changes_made check**

In `backend/src/oya/api/routers/repos.py`, the `init_repo` endpoint doesn't need changes - it already proceeds with generation. The `changes_made` field in the job status can remain for informational purposes.

**Step 5: Run frontend tests**

Run: `cd frontend && npm test`
Expected: PASS (some tests may need updates if they reference the modal)

**Step 6: Commit**

```bash
git add -A
git commit -m "feat: remove up-to-date modal and always allow regeneration

Users can now always regenerate the wiki regardless of whether
files have changed since the last generation."
```

---

## Task 10: Final Integration and Cleanup

**Files:**
- All modified files for final review
- Run full test suites

**Step 1: Run full frontend test suite**

Run: `cd frontend && npm test`
Expected: All tests pass

**Step 2: Run full backend test suite**

Run: `cd backend && source .venv/bin/activate && pytest`
Expected: All tests pass

**Step 3: Run type checks**

Run: `cd frontend && npm run build`
Expected: No errors

**Step 4: Manual testing checklist**

- [ ] Click "Generate Wiki" opens modal
- [ ] Modal shows files in three categories with correct styling
- [ ] Included files are checked, can uncheck to exclude
- [ ] .oyaignore files show badge, can check to re-include
- [ ] Rule-excluded files are disabled with badge
- [ ] Click "Generate Wiki" in modal shows confirmation with summary
- [ ] Confirmation shows .oyaignore changes if any
- [ ] Confirming starts generation and closes modal
- [ ] Closing modal with pending changes shows warning
- [ ] Ask button disabled during generation with tooltip
- [ ] AskPanel shows banner during generation
- [ ] AskPanel input disabled during generation

**Step 5: Final commit**

```bash
git add -A
git commit -m "chore: final cleanup for generation flow redesign"
```

---

## Summary

This plan implements the wiki generation flow redesign in 10 tasks:

1. **ConfirmationDialog** - Reusable confirmation component
2. **Backend IndexableItems** - Three-category API response
3. **Backend Oyaignore Removals** - Support re-including files
4. **Frontend Types** - Update TypeScript types
5. **Modal Display States** - Three visual file states
6. **Modal Flow** - Generate button, confirmations
7. **TopBar** - Single entry point
8. **Q&A Disable** - Prevent Q&A during generation
9. **Remove Up-to-Date** - Always allow regeneration
10. **Integration** - Final testing and cleanup

Each task follows TDD with explicit test-first steps and frequent commits.
