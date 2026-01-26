# Stale Content Cleanup Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Clean up stale wiki pages and notes during regeneration, with frontmatter for reliable orphan detection.

**Architecture:** Add frontmatter to all generated wiki pages containing source path metadata. During syncing phase, scan wiki files, parse frontmatter, and delete pages whose sources no longer exist. Frontend parses frontmatter and displays metadata in collapsible section.

**Tech Stack:** Python/FastAPI backend, React/TypeScript frontend, YAML frontmatter parsing

---

### Task 1: Create Frontmatter Utility Module

**Files:**
- Create: `backend/src/oya/generation/frontmatter.py`
- Test: `backend/tests/generation/test_frontmatter.py`

**Step 1: Write the failing test**

```python
# backend/tests/generation/test_frontmatter.py
"""Tests for frontmatter generation and parsing."""

from datetime import datetime, timezone

import pytest

from oya.generation.frontmatter import build_frontmatter, parse_frontmatter


class TestBuildFrontmatter:
    """Tests for build_frontmatter function."""

    def test_build_file_frontmatter(self):
        """Test building frontmatter for a file page."""
        result = build_frontmatter(
            source="src/api/routes.py",
            page_type="file",
            commit="a1b2c3d4e5f6",
            generated=datetime(2026, 1, 26, 10, 30, 0, tzinfo=timezone.utc),
            layer="api",
        )

        assert "---" in result
        assert "source: src/api/routes.py" in result
        assert "type: file" in result
        assert "commit: a1b2c3d4e5f6" in result
        assert "generated: 2026-01-26T10:30:00" in result
        assert "layer: api" in result

    def test_build_directory_frontmatter_no_layer(self):
        """Test building frontmatter for a directory page (no layer)."""
        result = build_frontmatter(
            source="src/api",
            page_type="directory",
            commit="a1b2c3d",
            generated=datetime(2026, 1, 26, 10, 30, 0, tzinfo=timezone.utc),
            layer=None,
        )

        assert "source: src/api" in result
        assert "type: directory" in result
        assert "layer:" not in result

    def test_build_overview_frontmatter_no_source(self):
        """Test building frontmatter for overview page (no source)."""
        result = build_frontmatter(
            source=None,
            page_type="overview",
            commit="a1b2c3d",
            generated=datetime(2026, 1, 26, 10, 30, 0, tzinfo=timezone.utc),
        )

        assert "source:" not in result
        assert "type: overview" in result


class TestParseFrontmatter:
    """Tests for parse_frontmatter function."""

    def test_parse_valid_frontmatter(self):
        """Test parsing content with valid frontmatter."""
        content = """---
source: src/api/routes.py
type: file
generated: 2026-01-26T10:30:00Z
commit: a1b2c3d
layer: api
---

# routes.py

Content here.
"""
        meta, body = parse_frontmatter(content)

        assert meta is not None
        assert meta["source"] == "src/api/routes.py"
        assert meta["type"] == "file"
        assert meta["layer"] == "api"
        assert "# routes.py" in body

    def test_parse_no_frontmatter(self):
        """Test parsing content without frontmatter."""
        content = "# Just a heading\n\nSome content."

        meta, body = parse_frontmatter(content)

        assert meta is None
        assert body == content

    def test_parse_frontmatter_no_source(self):
        """Test parsing frontmatter without source field."""
        content = """---
type: overview
generated: 2026-01-26T10:30:00Z
commit: a1b2c3d
---

# Overview
"""
        meta, body = parse_frontmatter(content)

        assert meta is not None
        assert meta.get("source") is None
        assert meta["type"] == "overview"
```

**Step 2: Run test to verify it fails**

Run: `cd backend && source .venv/bin/activate && pytest tests/generation/test_frontmatter.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'oya.generation.frontmatter'"

**Step 3: Write minimal implementation**

```python
# backend/src/oya/generation/frontmatter.py
"""Frontmatter utilities for wiki pages.

Provides functions to build YAML frontmatter for generated wiki pages
and parse frontmatter from existing pages for cleanup detection.
"""

from datetime import datetime
from typing import Any

import yaml


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
        Formatted YAML frontmatter string with trailing newlines
    """
    lines = ["---"]
    if source:
        lines.append(f"source: {source}")
    lines.append(f"type: {page_type}")
    lines.append(f"generated: {generated.isoformat()}")
    lines.append(f"commit: {commit}")
    if layer:
        lines.append(f"layer: {layer}")
    lines.append("---")
    lines.append("")  # Blank line after frontmatter
    return "\n".join(lines)


def parse_frontmatter(content: str) -> tuple[dict[str, Any] | None, str]:
    """Parse YAML frontmatter from wiki page content.

    Args:
        content: Full page content potentially containing frontmatter

    Returns:
        Tuple of (metadata dict or None, remaining content)
    """
    if not content.startswith("---"):
        return None, content

    # Find the closing ---
    lines = content.split("\n")
    end_index = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_index = i
            break

    if end_index is None:
        return None, content

    # Parse YAML
    yaml_content = "\n".join(lines[1:end_index])
    try:
        meta = yaml.safe_load(yaml_content)
        if not isinstance(meta, dict):
            return None, content
    except yaml.YAMLError:
        return None, content

    # Get remaining content (skip blank line after frontmatter if present)
    remaining_start = end_index + 1
    if remaining_start < len(lines) and lines[remaining_start].strip() == "":
        remaining_start += 1

    body = "\n".join(lines[remaining_start:])
    return meta, body
```

**Step 4: Run test to verify it passes**

Run: `cd backend && source .venv/bin/activate && pytest tests/generation/test_frontmatter.py -v`
Expected: PASS (3 tests)

**Step 5: Commit**

```bash
git add backend/src/oya/generation/frontmatter.py backend/tests/generation/test_frontmatter.py
git commit -m "feat: add frontmatter utilities for wiki pages"
```

---

### Task 2: Create Cleanup Module with Workflow Deletion

**Files:**
- Create: `backend/src/oya/generation/cleanup.py`
- Test: `backend/tests/generation/test_cleanup.py`

**Step 1: Write the failing test**

```python
# backend/tests/generation/test_cleanup.py
"""Tests for stale content cleanup."""

from pathlib import Path

import pytest

from oya.generation.cleanup import delete_all_workflows, CleanupResult


class TestDeleteAllWorkflows:
    """Tests for delete_all_workflows function."""

    def test_delete_all_workflows(self, tmp_path):
        """Test deleting all workflow files."""
        workflows_dir = tmp_path / "workflows"
        workflows_dir.mkdir()

        # Create some workflow files
        (workflows_dir / "user-auth.md").write_text("# User Auth")
        (workflows_dir / "checkout.md").write_text("# Checkout")

        count = delete_all_workflows(workflows_dir)

        assert count == 2
        assert not (workflows_dir / "user-auth.md").exists()
        assert not (workflows_dir / "checkout.md").exists()
        # Directory should still exist (empty)
        assert workflows_dir.exists()

    def test_delete_workflows_empty_dir(self, tmp_path):
        """Test with empty workflows directory."""
        workflows_dir = tmp_path / "workflows"
        workflows_dir.mkdir()

        count = delete_all_workflows(workflows_dir)

        assert count == 0

    def test_delete_workflows_nonexistent_dir(self, tmp_path):
        """Test with non-existent directory."""
        workflows_dir = tmp_path / "workflows"

        count = delete_all_workflows(workflows_dir)

        assert count == 0
```

**Step 2: Run test to verify it fails**

Run: `cd backend && source .venv/bin/activate && pytest tests/generation/test_cleanup.py::TestDeleteAllWorkflows -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'oya.generation.cleanup'"

**Step 3: Write minimal implementation**

```python
# backend/src/oya/generation/cleanup.py
"""Cleanup utilities for stale wiki content.

Provides functions to detect and remove orphaned wiki pages and notes
during the syncing phase of wiki regeneration.
"""

import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class CleanupResult:
    """Result of cleanup operation."""

    workflows_deleted: int = 0
    files_deleted: int = 0
    directories_deleted: int = 0
    notes_deleted: int = 0


def delete_all_workflows(workflows_dir: Path) -> int:
    """Delete all workflow files in the workflows directory.

    Args:
        workflows_dir: Path to wiki/workflows directory

    Returns:
        Number of files deleted
    """
    if not workflows_dir.exists():
        return 0

    count = 0
    for md_file in workflows_dir.glob("*.md"):
        logger.info(f"Deleting workflow: {md_file.name}")
        md_file.unlink()
        count += 1

    return count
```

**Step 4: Run test to verify it passes**

Run: `cd backend && source .venv/bin/activate && pytest tests/generation/test_cleanup.py::TestDeleteAllWorkflows -v`
Expected: PASS (3 tests)

**Step 5: Commit**

```bash
git add backend/src/oya/generation/cleanup.py backend/tests/generation/test_cleanup.py
git commit -m "feat: add cleanup module with workflow deletion"
```

---

### Task 3: Add Orphaned File/Directory Page Detection

**Files:**
- Modify: `backend/src/oya/generation/cleanup.py`
- Test: `backend/tests/generation/test_cleanup.py`

**Step 1: Write the failing test**

```python
# Add to backend/tests/generation/test_cleanup.py

from oya.generation.cleanup import delete_orphaned_pages


class TestDeleteOrphanedPages:
    """Tests for delete_orphaned_pages function."""

    def test_delete_orphaned_file_pages(self, tmp_path):
        """Test deleting file pages whose sources no longer exist."""
        wiki_files_dir = tmp_path / "wiki" / "files"
        wiki_files_dir.mkdir(parents=True)
        source_dir = tmp_path / "source"
        source_dir.mkdir()

        # Create source file
        (source_dir / "exists.py").write_text("print('hello')")

        # Create wiki pages - one valid, one orphaned
        (wiki_files_dir / "exists-py.md").write_text("""---
source: exists.py
type: file
generated: 2026-01-26T10:30:00Z
commit: abc123
---

# exists.py
""")
        (wiki_files_dir / "deleted-py.md").write_text("""---
source: deleted.py
type: file
generated: 2026-01-26T10:30:00Z
commit: abc123
---

# deleted.py
""")

        deleted = delete_orphaned_pages(wiki_files_dir, source_dir, is_file=True)

        assert deleted == ["deleted.py"]
        assert (wiki_files_dir / "exists-py.md").exists()
        assert not (wiki_files_dir / "deleted-py.md").exists()

    def test_delete_page_without_frontmatter(self, tmp_path):
        """Test that pages without frontmatter are treated as orphaned."""
        wiki_files_dir = tmp_path / "wiki" / "files"
        wiki_files_dir.mkdir(parents=True)
        source_dir = tmp_path / "source"
        source_dir.mkdir()

        # Page without frontmatter
        (wiki_files_dir / "old-page.md").write_text("# Old Page\n\nNo frontmatter here.")

        deleted = delete_orphaned_pages(wiki_files_dir, source_dir, is_file=True)

        assert len(deleted) == 1
        assert not (wiki_files_dir / "old-page.md").exists()

    def test_delete_orphaned_directory_pages(self, tmp_path):
        """Test deleting directory pages whose sources no longer exist."""
        wiki_dirs_dir = tmp_path / "wiki" / "directories"
        wiki_dirs_dir.mkdir(parents=True)
        source_dir = tmp_path / "source"
        (source_dir / "src" / "api").mkdir(parents=True)

        # Valid directory page
        (wiki_dirs_dir / "src-api.md").write_text("""---
source: src/api
type: directory
generated: 2026-01-26T10:30:00Z
commit: abc123
---

# src/api
""")
        # Orphaned directory page
        (wiki_dirs_dir / "deleted-module.md").write_text("""---
source: deleted/module
type: directory
generated: 2026-01-26T10:30:00Z
commit: abc123
---

# deleted/module
""")

        deleted = delete_orphaned_pages(wiki_dirs_dir, source_dir, is_file=False)

        assert deleted == ["deleted/module"]
        assert (wiki_dirs_dir / "src-api.md").exists()
        assert not (wiki_dirs_dir / "deleted-module.md").exists()
```

**Step 2: Run test to verify it fails**

Run: `cd backend && source .venv/bin/activate && pytest tests/generation/test_cleanup.py::TestDeleteOrphanedPages -v`
Expected: FAIL with "ImportError: cannot import name 'delete_orphaned_pages'"

**Step 3: Write minimal implementation**

```python
# Add to backend/src/oya/generation/cleanup.py

from oya.generation.frontmatter import parse_frontmatter


def delete_orphaned_pages(
    pages_dir: Path,
    source_dir: Path,
    is_file: bool,
) -> list[str]:
    """Delete wiki pages whose source files/directories no longer exist.

    Args:
        pages_dir: Path to wiki/files or wiki/directories
        source_dir: Path to source repository
        is_file: True if checking files, False if checking directories

    Returns:
        List of deleted source paths
    """
    if not pages_dir.exists():
        return []

    deleted = []
    for md_file in pages_dir.glob("*.md"):
        content = md_file.read_text(encoding="utf-8")
        meta, _ = parse_frontmatter(content)

        # No frontmatter = treat as orphaned
        if meta is None:
            logger.info(f"Deleting page without frontmatter: {md_file.name}")
            md_file.unlink()
            deleted.append(f"(no frontmatter: {md_file.name})")
            continue

        source_path = meta.get("source")
        if not source_path:
            logger.info(f"Deleting page without source: {md_file.name}")
            md_file.unlink()
            deleted.append(f"(no source: {md_file.name})")
            continue

        # Check if source exists
        full_source = source_dir / source_path
        source_exists = full_source.is_file() if is_file else full_source.is_dir()

        if not source_exists:
            logger.info(f"Deleting orphaned page: {source_path}")
            md_file.unlink()
            deleted.append(source_path)

    return deleted
```

**Step 4: Run test to verify it passes**

Run: `cd backend && source .venv/bin/activate && pytest tests/generation/test_cleanup.py::TestDeleteOrphanedPages -v`
Expected: PASS (3 tests)

**Step 5: Commit**

```bash
git add backend/src/oya/generation/cleanup.py backend/tests/generation/test_cleanup.py
git commit -m "feat: add orphaned file/directory page detection and deletion"
```

---

### Task 4: Add Orphaned Notes Cleanup

**Files:**
- Modify: `backend/src/oya/generation/cleanup.py`
- Test: `backend/tests/generation/test_cleanup.py`

**Step 1: Write the failing test**

```python
# Add to backend/tests/generation/test_cleanup.py

from unittest.mock import MagicMock

from oya.generation.cleanup import delete_orphaned_notes
from oya.notes.service import NoteScope


class TestDeleteOrphanedNotes:
    """Tests for delete_orphaned_notes function."""

    def test_delete_orphaned_file_notes(self, tmp_path):
        """Test deleting notes for files that no longer exist."""
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        (source_dir / "exists.py").write_text("print('hello')")

        # Mock NotesService
        mock_notes_service = MagicMock()
        mock_notes_service.list.return_value = [
            MagicMock(scope=NoteScope.FILE, target="exists.py"),
            MagicMock(scope=NoteScope.FILE, target="deleted.py"),
        ]

        deleted = delete_orphaned_notes(mock_notes_service, source_dir)

        assert deleted == 1
        mock_notes_service.delete.assert_called_once_with(NoteScope.FILE, "deleted.py")

    def test_delete_orphaned_directory_notes(self, tmp_path):
        """Test deleting notes for directories that no longer exist."""
        source_dir = tmp_path / "source"
        (source_dir / "src" / "api").mkdir(parents=True)

        mock_notes_service = MagicMock()
        mock_notes_service.list.return_value = [
            MagicMock(scope=NoteScope.DIRECTORY, target="src/api"),
            MagicMock(scope=NoteScope.DIRECTORY, target="deleted/module"),
        ]

        deleted = delete_orphaned_notes(mock_notes_service, source_dir)

        assert deleted == 1
        mock_notes_service.delete.assert_called_once_with(NoteScope.DIRECTORY, "deleted/module")

    def test_skip_general_and_workflow_notes(self, tmp_path):
        """Test that general and workflow notes are not checked."""
        source_dir = tmp_path / "source"
        source_dir.mkdir()

        mock_notes_service = MagicMock()
        mock_notes_service.list.return_value = [
            MagicMock(scope=NoteScope.GENERAL, target=""),
            MagicMock(scope=NoteScope.WORKFLOW, target="some-workflow"),
        ]

        deleted = delete_orphaned_notes(mock_notes_service, source_dir)

        assert deleted == 0
        mock_notes_service.delete.assert_not_called()
```

**Step 2: Run test to verify it fails**

Run: `cd backend && source .venv/bin/activate && pytest tests/generation/test_cleanup.py::TestDeleteOrphanedNotes -v`
Expected: FAIL with "ImportError: cannot import name 'delete_orphaned_notes'"

**Step 3: Write minimal implementation**

```python
# Add to backend/src/oya/generation/cleanup.py

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from oya.notes.service import NotesService

from oya.notes.service import NoteScope


def delete_orphaned_notes(
    notes_service: "NotesService",
    source_dir: Path,
) -> int:
    """Delete notes whose target files/directories no longer exist.

    Args:
        notes_service: NotesService instance
        source_dir: Path to source repository

    Returns:
        Number of notes deleted
    """
    deleted_count = 0

    # Get all notes
    all_notes = notes_service.list()

    for note in all_notes:
        # Skip general and workflow notes (not tied to specific source paths)
        if note.scope in (NoteScope.GENERAL, NoteScope.WORKFLOW):
            continue

        # Check if source exists
        full_path = source_dir / note.target

        if note.scope == NoteScope.FILE:
            exists = full_path.is_file()
        elif note.scope == NoteScope.DIRECTORY:
            exists = full_path.is_dir()
        else:
            continue

        if not exists:
            logger.info(f"Deleting orphaned note: {note.scope.value}/{note.target}")
            notes_service.delete(note.scope, note.target)
            deleted_count += 1

    return deleted_count
```

**Step 4: Run test to verify it passes**

Run: `cd backend && source .venv/bin/activate && pytest tests/generation/test_cleanup.py::TestDeleteOrphanedNotes -v`
Expected: PASS (3 tests)

**Step 5: Commit**

```bash
git add backend/src/oya/generation/cleanup.py backend/tests/generation/test_cleanup.py
git commit -m "feat: add orphaned notes cleanup"
```

---

### Task 5: Add Main Cleanup Function

**Files:**
- Modify: `backend/src/oya/generation/cleanup.py`
- Test: `backend/tests/generation/test_cleanup.py`

**Step 1: Write the failing test**

```python
# Add to backend/tests/generation/test_cleanup.py

from oya.generation.cleanup import cleanup_stale_content


class TestCleanupStaleContent:
    """Tests for main cleanup_stale_content function."""

    def test_cleanup_stale_content_full(self, tmp_path):
        """Test full cleanup with workflows, files, dirs, and notes."""
        # Set up wiki structure
        wiki_path = tmp_path / "wiki"
        (wiki_path / "files").mkdir(parents=True)
        (wiki_path / "directories").mkdir(parents=True)
        (wiki_path / "workflows").mkdir(parents=True)

        # Source with one file
        source_path = tmp_path / "source"
        source_path.mkdir()
        (source_path / "exists.py").write_text("print('hello')")

        # Workflow to delete
        (wiki_path / "workflows" / "old-workflow.md").write_text("# Old")

        # Valid file page
        (wiki_path / "files" / "exists-py.md").write_text("""---
source: exists.py
type: file
generated: 2026-01-26T10:30:00Z
commit: abc123
---
# exists.py
""")
        # Orphaned file page
        (wiki_path / "files" / "deleted-py.md").write_text("""---
source: deleted.py
type: file
generated: 2026-01-26T10:30:00Z
commit: abc123
---
# deleted.py
""")

        # Mock notes service
        mock_notes_service = MagicMock()
        mock_notes_service.list.return_value = []

        result = cleanup_stale_content(
            wiki_path=wiki_path,
            source_path=source_path,
            notes_service=mock_notes_service,
        )

        assert result.workflows_deleted == 1
        assert result.files_deleted == 1
        assert result.directories_deleted == 0
        assert (wiki_path / "files" / "exists-py.md").exists()
        assert not (wiki_path / "files" / "deleted-py.md").exists()
        assert not (wiki_path / "workflows" / "old-workflow.md").exists()
```

**Step 2: Run test to verify it fails**

Run: `cd backend && source .venv/bin/activate && pytest tests/generation/test_cleanup.py::TestCleanupStaleContent -v`
Expected: FAIL with "ImportError: cannot import name 'cleanup_stale_content'"

**Step 3: Write minimal implementation**

```python
# Add to backend/src/oya/generation/cleanup.py

def cleanup_stale_content(
    wiki_path: Path,
    source_path: Path,
    notes_service: "NotesService | None" = None,
) -> CleanupResult:
    """Remove stale wiki pages and notes.

    This function should be called during the syncing phase, after git sync
    completes and before generation starts.

    Args:
        wiki_path: Path to wiki directory (.oyawiki/wiki)
        source_path: Path to source repository
        notes_service: Optional NotesService for notes cleanup

    Returns:
        CleanupResult with counts of deleted items
    """
    result = CleanupResult()

    # Step 1: Delete all workflows (they'll be regenerated)
    workflows_dir = wiki_path / "workflows"
    result.workflows_deleted = delete_all_workflows(workflows_dir)
    logger.info(f"Deleted {result.workflows_deleted} workflow pages")

    # Step 2: Delete orphaned file pages
    files_dir = wiki_path / "files"
    deleted_files = delete_orphaned_pages(files_dir, source_path, is_file=True)
    result.files_deleted = len(deleted_files)
    logger.info(f"Deleted {result.files_deleted} orphaned file pages")

    # Step 3: Delete orphaned directory pages
    dirs_dir = wiki_path / "directories"
    deleted_dirs = delete_orphaned_pages(dirs_dir, source_path, is_file=False)
    result.directories_deleted = len(deleted_dirs)
    logger.info(f"Deleted {result.directories_deleted} orphaned directory pages")

    # Step 4: Delete orphaned notes
    if notes_service:
        result.notes_deleted = delete_orphaned_notes(notes_service, source_path)
        logger.info(f"Deleted {result.notes_deleted} orphaned notes")

    return result
```

**Step 4: Run test to verify it passes**

Run: `cd backend && source .venv/bin/activate && pytest tests/generation/test_cleanup.py::TestCleanupStaleContent -v`
Expected: PASS (1 test)

**Step 5: Commit**

```bash
git add backend/src/oya/generation/cleanup.py backend/tests/generation/test_cleanup.py
git commit -m "feat: add main cleanup_stale_content function"
```

---

### Task 6: Integrate Frontmatter into Page Writing

**Files:**
- Modify: `backend/src/oya/generation/orchestrator.py`
- Test: `backend/tests/test_orchestrator.py` (add test)

**Step 1: Write the failing test**

```python
# Add to backend/tests/test_orchestrator.py (find appropriate location)

class TestFrontmatterIntegration:
    """Tests for frontmatter in generated pages."""

    async def test_saved_page_has_frontmatter(self, tmp_path):
        """Test that saved pages include frontmatter with metadata."""
        from datetime import datetime, timezone
        from unittest.mock import MagicMock, AsyncMock

        from oya.generation.orchestrator import GenerationOrchestrator
        from oya.generation.overview import GeneratedPage

        # Minimal setup
        wiki_path = tmp_path / "wiki"
        wiki_path.mkdir()
        (wiki_path / "files").mkdir()

        mock_llm = MagicMock()
        mock_repo = MagicMock()
        mock_repo.get_head_commit.return_value = "abc123def456"
        mock_db = MagicMock()
        mock_db.execute = MagicMock()
        mock_db.commit = MagicMock()

        orchestrator = GenerationOrchestrator(
            llm_client=mock_llm,
            repo=mock_repo,
            db=mock_db,
            wiki_path=wiki_path,
        )

        # Create a test page
        page = GeneratedPage(
            content="# Test File\n\nContent here.",
            page_type="file",
            path="files/test-py.md",
            word_count=4,
            target="test.py",
        )

        # Save with layer info
        await orchestrator._save_page_with_frontmatter(
            page=page,
            layer="api",
        )

        # Read back and verify frontmatter
        saved_content = (wiki_path / "files" / "test-py.md").read_text()

        assert saved_content.startswith("---\n")
        assert "source: test.py" in saved_content
        assert "type: file" in saved_content
        assert "commit: abc123def456" in saved_content
        assert "layer: api" in saved_content
        assert "# Test File" in saved_content
```

**Step 2: Run test to verify it fails**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_orchestrator.py::TestFrontmatterIntegration -v`
Expected: FAIL with "AttributeError: 'GenerationOrchestrator' object has no attribute '_save_page_with_frontmatter'"

**Step 3: Write minimal implementation**

Modify `backend/src/oya/generation/orchestrator.py`:

1. Add import at top:
```python
from datetime import datetime, timezone
from oya.generation.frontmatter import build_frontmatter
```

2. Add new method after existing `_save_page` method (around line 1517):
```python
    async def _save_page_with_frontmatter(
        self,
        page: GeneratedPage,
        layer: str | None = None,
    ) -> None:
        """Save a generated page with frontmatter metadata.

        Args:
            page: Generated page to save.
            layer: Architectural layer (for file pages).
        """
        # Determine full path
        page_path = self.wiki_path / page.path

        # Ensure parent directory exists
        page_path.parent.mkdir(parents=True, exist_ok=True)

        # Get current commit
        commit = self.repo.get_head_commit()[:12]  # Short hash

        # Build frontmatter
        frontmatter = build_frontmatter(
            source=page.target,
            page_type=page.page_type,
            commit=commit,
            generated=datetime.now(timezone.utc),
            layer=layer,
        )

        # Write content with frontmatter
        page_path.write_text(frontmatter + page.content, encoding="utf-8")

        # Build metadata JSON with source hash for incremental regeneration
        metadata = {}
        if page.source_hash:
            metadata["source_hash"] = page.source_hash

        # Record in database (if method exists)
        if hasattr(self.db, "execute"):
            try:
                self.db.execute(
                    """
                    INSERT OR REPLACE INTO wiki_pages
                    (path, type, word_count, target, metadata, generated_at)
                    VALUES (?, ?, ?, ?, ?, datetime('now'))
                    """,
                    (
                        page.path,
                        page.page_type,
                        page.word_count,
                        page.target,
                        json.dumps(metadata) if metadata else None,
                    ),
                )
                self.db.commit()
            except Exception:
                # Table might not exist yet, skip recording
                pass
```

**Step 4: Run test to verify it passes**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_orchestrator.py::TestFrontmatterIntegration -v`
Expected: PASS (1 test)

**Step 5: Commit**

```bash
git add backend/src/oya/generation/orchestrator.py backend/tests/test_orchestrator.py
git commit -m "feat: add _save_page_with_frontmatter method to orchestrator"
```

---

### Task 7: Update All Page Saves to Use Frontmatter

**Files:**
- Modify: `backend/src/oya/generation/orchestrator.py`

**Step 1: Identify all _save_page calls**

Search for `_save_page(` in orchestrator.py and update each to use `_save_page_with_frontmatter`.

**Step 2: Update file page saves**

Find the file generation loop (around line 1390-1420) and update to pass layer:

```python
# Before:
await self._save_page(page)

# After (for file pages):
await self._save_page_with_frontmatter(page, layer=file_summary.layer)
```

**Step 3: Update directory page saves**

Find directory generation (around line 1440-1470) and update:

```python
# For directory pages (no layer):
await self._save_page_with_frontmatter(page, layer=None)
```

**Step 4: Update overview, architecture, workflow page saves**

Find each and update:

```python
# For overview/architecture/workflow pages:
await self._save_page_with_frontmatter(page, layer=None)
```

**Step 5: Run all orchestrator tests**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_orchestrator.py -v`
Expected: PASS (all tests)

**Step 6: Commit**

```bash
git add backend/src/oya/generation/orchestrator.py
git commit -m "refactor: use _save_page_with_frontmatter for all page saves"
```

---

### Task 8: Integrate Cleanup into Syncing Phase

**Files:**
- Modify: `backend/src/oya/api/routers/repos.py`
- Test: Integration test

**Step 1: Add import to repos.py**

At top of file, add:
```python
from oya.generation.cleanup import cleanup_stale_content
from oya.notes.service import NotesService
```

**Step 2: Add cleanup call after git sync**

In `_run_generation` function, after `sync_to_default_branch(paths.source)` succeeds (around line 358), add:

```python
        # Cleanup stale content before generation
        try:
            # Create notes service for cleanup
            notes_service = NotesService(
                notes_path=staging_path / "notes",
                db=staging_db,
            ) if staging_db else None

            cleanup_result = cleanup_stale_content(
                wiki_path=staging_wiki_path,
                source_path=paths.source,
                notes_service=notes_service,
            )
            logger.info(
                f"Cleanup complete: {cleanup_result.workflows_deleted} workflows, "
                f"{cleanup_result.files_deleted} files, "
                f"{cleanup_result.directories_deleted} directories, "
                f"{cleanup_result.notes_deleted} notes deleted"
            )
        except Exception as e:
            logger.warning(f"Cleanup failed (continuing with generation): {e}")
```

**Step 3: Run existing tests**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_repos_api.py -v`
Expected: PASS (all tests)

**Step 4: Commit**

```bash
git add backend/src/oya/api/routers/repos.py
git commit -m "feat: integrate cleanup into syncing phase"
```

---

### Task 9: Create Frontend Frontmatter Parser

**Files:**
- Create: `frontend/src/utils/frontmatter.ts`
- Test: `frontend/src/utils/frontmatter.test.ts`

**Step 1: Write the failing test**

```typescript
// frontend/src/utils/frontmatter.test.ts
import { describe, it, expect } from 'vitest'
import { parseFrontmatter, WikiPageMeta } from './frontmatter'

describe('parseFrontmatter', () => {
  it('parses valid frontmatter', () => {
    const content = `---
source: src/api/routes.py
type: file
generated: 2026-01-26T10:30:00Z
commit: abc123
layer: api
---

# routes.py

Content here.`

    const { meta, content: body } = parseFrontmatter(content)

    expect(meta).not.toBeNull()
    expect(meta?.source).toBe('src/api/routes.py')
    expect(meta?.type).toBe('file')
    expect(meta?.layer).toBe('api')
    expect(body).toContain('# routes.py')
    expect(body).not.toContain('---')
  })

  it('returns null meta for content without frontmatter', () => {
    const content = '# Just a heading\n\nSome content.'

    const { meta, content: body } = parseFrontmatter(content)

    expect(meta).toBeNull()
    expect(body).toBe(content)
  })

  it('handles frontmatter without source field', () => {
    const content = `---
type: overview
generated: 2026-01-26T10:30:00Z
commit: abc123
---

# Overview`

    const { meta } = parseFrontmatter(content)

    expect(meta).not.toBeNull()
    expect(meta?.source).toBeUndefined()
    expect(meta?.type).toBe('overview')
  })
})
```

**Step 2: Run test to verify it fails**

Run: `cd frontend && npm run test -- src/utils/frontmatter.test.ts`
Expected: FAIL with "Cannot find module './frontmatter'"

**Step 3: Write minimal implementation**

```typescript
// frontend/src/utils/frontmatter.ts
import yaml from 'js-yaml'

export interface WikiPageMeta {
  source?: string
  type: 'file' | 'directory' | 'workflow' | 'overview' | 'architecture'
  generated: string
  commit: string
  layer?: string
}

export interface ParsedPage {
  meta: WikiPageMeta | null
  content: string
}

/**
 * Parse YAML frontmatter from wiki page content.
 */
export function parseFrontmatter(content: string): ParsedPage {
  if (!content.startsWith('---')) {
    return { meta: null, content }
  }

  const lines = content.split('\n')
  let endIndex = -1

  for (let i = 1; i < lines.length; i++) {
    if (lines[i].trim() === '---') {
      endIndex = i
      break
    }
  }

  if (endIndex === -1) {
    return { meta: null, content }
  }

  const yamlContent = lines.slice(1, endIndex).join('\n')

  try {
    const meta = yaml.load(yamlContent) as WikiPageMeta
    if (typeof meta !== 'object' || meta === null) {
      return { meta: null, content }
    }

    // Skip blank line after frontmatter if present
    let bodyStart = endIndex + 1
    if (bodyStart < lines.length && lines[bodyStart].trim() === '') {
      bodyStart++
    }

    const body = lines.slice(bodyStart).join('\n')
    return { meta, content: body }
  } catch {
    return { meta: null, content }
  }
}
```

**Step 4: Install js-yaml if needed**

Run: `cd frontend && npm install js-yaml && npm install -D @types/js-yaml`

**Step 5: Run test to verify it passes**

Run: `cd frontend && npm run test -- src/utils/frontmatter.test.ts`
Expected: PASS (3 tests)

**Step 6: Commit**

```bash
git add frontend/src/utils/frontmatter.ts frontend/src/utils/frontmatter.test.ts frontend/package.json frontend/package-lock.json
git commit -m "feat: add frontend frontmatter parser"
```

---

### Task 10: Create PageInfo Component

**Files:**
- Create: `frontend/src/components/PageInfo.tsx`

**Step 1: Create the component**

```typescript
// frontend/src/components/PageInfo.tsx
import { useState } from 'react'
import type { WikiPageMeta } from '../utils/frontmatter'

interface PageInfoProps {
  meta: WikiPageMeta
}

function formatDate(isoString: string): string {
  try {
    const date = new Date(isoString)
    return date.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return isoString
  }
}

function formatType(type: string): string {
  return type.charAt(0).toUpperCase() + type.slice(1)
}

function formatLayer(layer: string): string {
  const labels: Record<string, string> = {
    api: 'API',
    domain: 'Domain',
    infrastructure: 'Infrastructure',
    utility: 'Utility',
    config: 'Config',
    test: 'Test',
  }
  return labels[layer] || layer
}

export function PageInfo({ meta }: PageInfoProps) {
  const [isExpanded, setIsExpanded] = useState(false)

  return (
    <div className="mb-4">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="flex items-center gap-1 text-sm text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300"
      >
        <span>{isExpanded ? '▼' : '▶'}</span>
        <span>Page Info</span>
      </button>

      {isExpanded && (
        <div className="mt-2 p-3 bg-gray-50 dark:bg-gray-800 rounded-lg text-sm">
          <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1">
            {meta.source && (
              <>
                <dt className="text-gray-500 dark:text-gray-400">Source</dt>
                <dd className="font-mono text-gray-900 dark:text-gray-100">
                  {meta.source}
                </dd>
              </>
            )}
            <dt className="text-gray-500 dark:text-gray-400">Type</dt>
            <dd className="text-gray-900 dark:text-gray-100">
              {formatType(meta.type)}
            </dd>
            {meta.layer && (
              <>
                <dt className="text-gray-500 dark:text-gray-400">Layer</dt>
                <dd className="text-gray-900 dark:text-gray-100">
                  <span className="inline-block px-2 py-0.5 bg-indigo-100 dark:bg-indigo-900 text-indigo-800 dark:text-indigo-200 rounded text-xs">
                    {formatLayer(meta.layer)}
                  </span>
                </dd>
              </>
            )}
            <dt className="text-gray-500 dark:text-gray-400">Generated</dt>
            <dd className="text-gray-900 dark:text-gray-100">
              {formatDate(meta.generated)}
            </dd>
            <dt className="text-gray-500 dark:text-gray-400">Commit</dt>
            <dd className="font-mono text-gray-900 dark:text-gray-100">
              {meta.commit}
            </dd>
          </dl>
        </div>
      )}
    </div>
  )
}
```

**Step 2: Commit**

```bash
git add frontend/src/components/PageInfo.tsx
git commit -m "feat: add collapsible PageInfo component"
```

---

### Task 11: Integrate PageInfo into WikiContent

**Files:**
- Modify: `frontend/src/components/WikiContent.tsx`

**Step 1: Update WikiContent to parse frontmatter and show PageInfo**

```typescript
// frontend/src/components/WikiContent.tsx
// Add imports at top:
import { parseFrontmatter } from '../utils/frontmatter'
import { PageInfo } from './PageInfo'

// Update the component:
export function WikiContent({ page }: WikiContentProps) {
  // Parse frontmatter from content
  const { meta, content } = parseFrontmatter(page.content)

  return (
    <article className="prose prose-gray dark:prose-invert max-w-none">
      {meta && <PageInfo meta={meta} />}
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          // ... existing components unchanged
        }}
      >
        {content}
      </ReactMarkdown>
    </article>
  )
}
```

**Step 2: Run frontend tests**

Run: `cd frontend && npm run test`
Expected: PASS (all tests)

**Step 3: Run frontend build**

Run: `cd frontend && npm run build`
Expected: SUCCESS

**Step 4: Commit**

```bash
git add frontend/src/components/WikiContent.tsx
git commit -m "feat: integrate PageInfo into WikiContent"
```

---

### Task 12: Update WikiPage Type for Frontmatter

**Files:**
- Modify: `frontend/src/types/index.ts`

**Step 1: Add frontmatter-related types**

The `WikiPageMeta` type is already defined in `frontmatter.ts`. The `WikiPage` type in `types/index.ts` doesn't need changes since frontmatter is parsed from the content string client-side.

**Step 2: Verify types are consistent**

Run: `cd frontend && npm run build`
Expected: SUCCESS (no type errors)

**Step 3: Commit (if any changes)**

```bash
git add frontend/src/types/index.ts
git commit -m "docs: verify WikiPage type compatibility with frontmatter"
```

---

### Task 13: Run Full Test Suite

**Step 1: Run backend tests**

Run: `cd backend && source .venv/bin/activate && pytest`
Expected: All tests pass

**Step 2: Run frontend tests**

Run: `cd frontend && npm run test`
Expected: All tests pass

**Step 3: Run frontend lint**

Run: `cd frontend && npm run lint`
Expected: No errors

**Step 4: Final commit with any fixes**

```bash
git add -A
git commit -m "test: ensure all tests pass after stale content cleanup feature"
```

---

### Task 14: Manual Testing Checklist

**Step 1: Test frontmatter generation**

1. Start backend: `cd backend && uvicorn oya.main:app --reload`
2. Start frontend: `cd frontend && npm run dev`
3. Generate a wiki for a test repo
4. Check generated `.md` files have frontmatter:
   - `wiki/files/*.md` should have `source`, `type`, `layer`, `generated`, `commit`
   - `wiki/directories/*.md` should have `source`, `type`, `generated`, `commit` (no layer)
   - `wiki/overview.md` should have `type`, `generated`, `commit` (no source)

**Step 2: Test cleanup**

1. Delete a source file from the repo
2. Regenerate the wiki
3. Verify the orphaned wiki page was deleted
4. Verify any notes for that file were deleted

**Step 3: Test frontend display**

1. Open a wiki page in the browser
2. Click "Page Info" toggle
3. Verify metadata displays correctly
4. Verify markdown renders without frontmatter showing

**Step 4: Document any issues found**

Create issues or fix immediately as appropriate.
