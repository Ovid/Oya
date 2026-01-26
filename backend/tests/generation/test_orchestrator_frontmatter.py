"""Tests for frontmatter integration in GenerationOrchestrator."""

from unittest.mock import MagicMock

import pytest

from oya.generation.orchestrator import GenerationOrchestrator
from oya.generation.overview import GeneratedPage


class TestSavePageWithFrontmatter:
    """Tests for _save_page_with_frontmatter method."""

    @pytest.fixture
    def orchestrator(self, tmp_path):
        """Create an orchestrator with mock dependencies."""
        mock_llm = MagicMock()
        mock_repo = MagicMock()
        mock_repo.get_head_commit.return_value = "abc123def456789012"
        mock_repo.path = tmp_path / "repo"
        mock_db = MagicMock()
        mock_db.execute = MagicMock()
        mock_db.commit = MagicMock()

        wiki_path = tmp_path / "wiki"
        wiki_path.mkdir()
        (wiki_path / "files").mkdir()

        return GenerationOrchestrator(
            llm_client=mock_llm,
            repo=mock_repo,
            db=mock_db,
            wiki_path=wiki_path,
        )

    @pytest.mark.asyncio
    async def test_save_page_with_frontmatter_includes_metadata(self, orchestrator, tmp_path):
        """Saved pages include frontmatter with source, type, commit, generated."""
        page = GeneratedPage(
            content="# Test File\n\nContent here.",
            page_type="file",
            path="files/test-py.md",
            word_count=4,
            target="test.py",
        )

        await orchestrator._save_page_with_frontmatter(page, layer="api")

        saved_path = orchestrator.wiki_path / "files" / "test-py.md"
        content = saved_path.read_text()

        assert content.startswith("---\n")
        assert "source: test.py" in content
        assert "type: file" in content
        assert "commit: abc123def456" in content
        assert "layer: api" in content
        assert "generated:" in content
        assert "# Test File" in content

    @pytest.mark.asyncio
    async def test_save_page_without_layer(self, orchestrator, tmp_path):
        """Pages without layer (directories, overview) omit layer field."""
        page = GeneratedPage(
            content="# Overview\n\nProject overview.",
            page_type="overview",
            path="overview.md",
            word_count=3,
            target=None,
        )

        await orchestrator._save_page_with_frontmatter(page, layer=None)

        saved_path = orchestrator.wiki_path / "overview.md"
        content = saved_path.read_text()

        assert content.startswith("---\n")
        assert "type: overview" in content
        assert "layer:" not in content
        assert "source:" not in content  # target is None

    @pytest.mark.asyncio
    async def test_save_page_records_to_database(self, orchestrator, tmp_path):
        """Verify page is recorded in database."""
        page = GeneratedPage(
            content="# Test",
            page_type="file",
            path="files/test.md",
            word_count=1,
            target="test.py",
        )

        await orchestrator._save_page_with_frontmatter(page, layer="api")

        orchestrator.db.execute.assert_called_once()
        orchestrator.db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_save_page_with_source_hash(self, orchestrator, tmp_path):
        """Verify source_hash is included in metadata when present."""
        page = GeneratedPage(
            content="# Test",
            page_type="file",
            path="files/test.md",
            word_count=1,
            target="test.py",
            source_hash="abcdef123456",
        )

        await orchestrator._save_page_with_frontmatter(page, layer="api")

        # Check that the execute call included the source_hash in metadata
        call_args = orchestrator.db.execute.call_args
        assert call_args is not None
        # The metadata JSON should contain source_hash
        metadata_json = call_args[0][1][4]  # 5th parameter is metadata
        assert "abcdef123456" in metadata_json

    @pytest.mark.asyncio
    async def test_save_page_creates_parent_directories(self, orchestrator, tmp_path):
        """Parent directories are created if they don't exist."""
        page = GeneratedPage(
            content="# Test",
            page_type="file",
            path="deep/nested/path/test.md",
            word_count=1,
            target="deep/nested/path/test.py",
        )

        await orchestrator._save_page_with_frontmatter(page, layer="domain")

        saved_path = orchestrator.wiki_path / "deep" / "nested" / "path" / "test.md"
        assert saved_path.exists()
        content = saved_path.read_text()
        assert content.startswith("---\n")
        assert "source: deep/nested/path/test.py" in content

    @pytest.mark.asyncio
    async def test_save_directory_page_with_frontmatter(self, orchestrator, tmp_path):
        """Directory pages include frontmatter with source path but no layer."""
        page = GeneratedPage(
            content="# Directory: src/api\n\nAPI routes.",
            page_type="directory",
            path="dirs/src-api.md",
            word_count=5,
            target="src/api",
        )

        await orchestrator._save_page_with_frontmatter(page, layer=None)

        saved_path = orchestrator.wiki_path / "dirs" / "src-api.md"
        content = saved_path.read_text()

        assert content.startswith("---\n")
        assert "source: src/api" in content
        assert "type: directory" in content
        assert "layer:" not in content
        assert "# Directory: src/api" in content

    @pytest.mark.asyncio
    async def test_save_workflow_page_with_frontmatter(self, orchestrator, tmp_path):
        """Workflow pages include frontmatter with appropriate type."""
        # Ensure the workflows directory exists
        (orchestrator.wiki_path / "workflows").mkdir(parents=True, exist_ok=True)

        page = GeneratedPage(
            content="# Authentication Workflow\n\nLogin flow.",
            page_type="workflow",
            path="workflows/authentication.md",
            word_count=5,
            target="auth",
        )

        await orchestrator._save_page_with_frontmatter(page, layer=None)

        saved_path = orchestrator.wiki_path / "workflows" / "authentication.md"
        content = saved_path.read_text()

        assert content.startswith("---\n")
        assert "type: workflow" in content
        assert "# Authentication Workflow" in content
