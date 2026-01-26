"""Tests for cleanup module - stale content deletion during regeneration."""

from pathlib import Path

from oya.generation.cleanup import CleanupResult, delete_all_workflows


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
