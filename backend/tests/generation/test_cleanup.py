"""Tests for cleanup module - stale content deletion during regeneration."""

from pathlib import Path
from unittest.mock import MagicMock

from oya.generation.cleanup import (
    CleanupResult,
    cleanup_stale_content,
    delete_all_workflows,
    delete_orphaned_notes,
    delete_orphaned_pages,
)
from oya.notes.schemas import NoteScope


class TestCleanupResult:
    """Tests for CleanupResult dataclass."""

    def test_cleanup_result_defaults_to_zeros(self):
        """CleanupResult initializes all counts to zero by default."""
        result = CleanupResult()

        assert result.workflows_deleted == 0
        assert result.files_deleted == 0
        assert result.directories_deleted == 0
        assert result.notes_deleted == 0

    def test_cleanup_result_accepts_values(self):
        """CleanupResult can be initialized with specific values."""
        result = CleanupResult(
            workflows_deleted=5,
            files_deleted=10,
            directories_deleted=3,
            notes_deleted=2,
        )

        assert result.workflows_deleted == 5
        assert result.files_deleted == 10
        assert result.directories_deleted == 3
        assert result.notes_deleted == 2


class TestDeleteAllWorkflows:
    """Tests for delete_all_workflows function."""

    def test_delete_all_workflows_in_directory(self, tmp_path: Path):
        """Delete all .md files in the workflows directory."""
        workflows_dir = tmp_path / "workflows"
        workflows_dir.mkdir()

        # Create some workflow files
        (workflows_dir / "auth-flow.md").write_text("# Auth Flow")
        (workflows_dir / "checkout-process.md").write_text("# Checkout")
        (workflows_dir / "user-registration.md").write_text("# Registration")

        count = delete_all_workflows(workflows_dir)

        assert count == 3
        assert not (workflows_dir / "auth-flow.md").exists()
        assert not (workflows_dir / "checkout-process.md").exists()
        assert not (workflows_dir / "user-registration.md").exists()

    def test_delete_all_workflows_empty_directory(self, tmp_path: Path):
        """Return 0 when directory exists but is empty."""
        workflows_dir = tmp_path / "workflows"
        workflows_dir.mkdir()

        count = delete_all_workflows(workflows_dir)

        assert count == 0

    def test_delete_all_workflows_nonexistent_directory(self, tmp_path: Path):
        """Return 0 when directory does not exist."""
        workflows_dir = tmp_path / "workflows"
        # Do not create the directory

        count = delete_all_workflows(workflows_dir)

        assert count == 0

    def test_delete_all_workflows_only_deletes_md_files(self, tmp_path: Path):
        """Only delete .md files, leaving other files intact."""
        workflows_dir = tmp_path / "workflows"
        workflows_dir.mkdir()

        # Create workflow files and a non-md file
        (workflows_dir / "auth-flow.md").write_text("# Auth Flow")
        (workflows_dir / "config.json").write_text("{}")
        (workflows_dir / "readme.txt").write_text("readme")

        count = delete_all_workflows(workflows_dir)

        assert count == 1
        assert not (workflows_dir / "auth-flow.md").exists()
        assert (workflows_dir / "config.json").exists()
        assert (workflows_dir / "readme.txt").exists()


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

    def test_preserve_page_without_frontmatter(self, tmp_path):
        """Test that pages without frontmatter are preserved (backwards compatibility)."""
        wiki_files_dir = tmp_path / "wiki" / "files"
        wiki_files_dir.mkdir(parents=True)
        source_dir = tmp_path / "source"
        source_dir.mkdir()

        # Page without frontmatter - should be kept for backwards compatibility
        (wiki_files_dir / "old-page.md").write_text("# Old Page\n\nNo frontmatter here.")

        deleted = delete_orphaned_pages(wiki_files_dir, source_dir, is_file=True)

        assert len(deleted) == 0
        assert (wiki_files_dir / "old-page.md").exists()  # Should be preserved

    def test_preserve_page_with_frontmatter_but_no_source(self, tmp_path):
        """Test that pages with frontmatter but no source field are preserved."""
        wiki_files_dir = tmp_path / "wiki" / "files"
        wiki_files_dir.mkdir(parents=True)
        source_dir = tmp_path / "source"
        source_dir.mkdir()

        # Page with frontmatter but missing source field
        (wiki_files_dir / "partial-page.md").write_text("""---
type: file
generated: 2026-01-26T10:30:00Z
commit: abc123
---

# Partial Page
""")

        deleted = delete_orphaned_pages(wiki_files_dir, source_dir, is_file=True)

        assert len(deleted) == 0
        assert (wiki_files_dir / "partial-page.md").exists()  # Should be preserved

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

    def test_cleanup_stale_content_without_notes_service(self, tmp_path):
        """Test cleanup when notes_service is not provided."""
        wiki_path = tmp_path / "wiki"
        (wiki_path / "files").mkdir(parents=True)
        (wiki_path / "directories").mkdir(parents=True)
        (wiki_path / "workflows").mkdir(parents=True)

        source_path = tmp_path / "source"
        source_path.mkdir()

        result = cleanup_stale_content(
            wiki_path=wiki_path,
            source_path=source_path,
            notes_service=None,
        )

        assert result.workflows_deleted == 0
        assert result.files_deleted == 0
        assert result.directories_deleted == 0
        assert result.notes_deleted == 0

    def test_cleanup_stale_content_with_orphaned_notes(self, tmp_path):
        """Test cleanup deletes orphaned notes when notes_service provided."""
        wiki_path = tmp_path / "wiki"
        (wiki_path / "files").mkdir(parents=True)
        (wiki_path / "directories").mkdir(parents=True)
        (wiki_path / "workflows").mkdir(parents=True)

        source_path = tmp_path / "source"
        source_path.mkdir()
        (source_path / "exists.py").write_text("print('hello')")

        # Mock notes service with one orphaned note
        mock_notes_service = MagicMock()
        from oya.notes.schemas import NoteScope

        mock_notes_service.list.return_value = [
            MagicMock(scope=NoteScope.FILE, target="deleted.py"),
        ]

        result = cleanup_stale_content(
            wiki_path=wiki_path,
            source_path=source_path,
            notes_service=mock_notes_service,
        )

        assert result.notes_deleted == 1
        mock_notes_service.delete.assert_called_once_with(NoteScope.FILE, "deleted.py")
