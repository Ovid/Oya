"""Tests for staging directory generation approach.

Generation builds in .oyawiki-building and only moves to .oyawiki on success.
"""

from pathlib import Path


class TestStagingDirectory:
    """Tests for staging directory behavior."""

    def test_promote_staging_moves_directory(self, tmp_path: Path):
        """promote_staging_to_production moves staging to production."""
        from oya.generation.staging import promote_staging_to_production

        staging = tmp_path / ".oyawiki-building"
        production = tmp_path / ".oyawiki"

        # Create staging with content
        staging.mkdir()
        (staging / "wiki").mkdir()
        (staging / "wiki" / "overview.md").write_text("# Overview")
        (staging / "meta").mkdir()
        (staging / "meta" / "synthesis.json").write_text("{}")

        # Promote
        promote_staging_to_production(staging, production)

        # Staging should be gone, production should have content
        assert not staging.exists()
        assert production.exists()
        assert (production / "wiki" / "overview.md").read_text() == "# Overview"
        assert (production / "meta" / "synthesis.json").read_text() == "{}"

    def test_promote_staging_replaces_existing_production(self, tmp_path: Path):
        """promote_staging_to_production replaces existing production directory."""
        from oya.generation.staging import promote_staging_to_production

        staging = tmp_path / ".oyawiki-building"
        production = tmp_path / ".oyawiki"

        # Create existing production with old content
        production.mkdir()
        (production / "wiki").mkdir()
        (production / "wiki" / "old.md").write_text("old content")

        # Create staging with new content
        staging.mkdir()
        (staging / "wiki").mkdir()
        (staging / "wiki" / "new.md").write_text("new content")

        # Promote
        promote_staging_to_production(staging, production)

        # Production should have new content only
        assert not staging.exists()
        assert not (production / "wiki" / "old.md").exists()
        assert (production / "wiki" / "new.md").read_text() == "new content"

    def test_prepare_staging_clears_existing(self, tmp_path: Path):
        """prepare_staging_directory clears any existing staging directory."""
        from oya.generation.staging import prepare_staging_directory

        staging = tmp_path / ".oyawiki-building"
        production = tmp_path / ".oyawiki"

        # Create existing staging with old content (simulating incomplete build)
        staging.mkdir()
        (staging / "old_file.txt").write_text("old")

        # Prepare staging (no production exists)
        prepare_staging_directory(staging, production)

        # Staging should exist but be empty (old content wiped)
        assert staging.exists()
        assert not (staging / "old_file.txt").exists()

    def test_prepare_staging_copies_production_for_incremental(self, tmp_path: Path):
        """prepare_staging_directory copies production for incremental regeneration."""
        from oya.generation.staging import prepare_staging_directory

        staging = tmp_path / ".oyawiki-building"
        production = tmp_path / ".oyawiki"

        # Create production with existing wiki content
        production.mkdir()
        (production / "wiki").mkdir()
        (production / "wiki" / "overview.md").write_text("# Existing Overview")

        # Prepare staging
        prepare_staging_directory(staging, production)

        # Staging should have copy of production content
        assert staging.exists()
        assert (staging / "wiki" / "overview.md").read_text() == "# Existing Overview"
        # Production should still exist (not moved)
        assert production.exists()
        assert (production / "wiki" / "overview.md").exists()

    def test_prepare_staging_wipes_incomplete_before_copying_production(self, tmp_path: Path):
        """prepare_staging_directory wipes incomplete staging before copying production."""
        from oya.generation.staging import prepare_staging_directory

        staging = tmp_path / ".oyawiki-building"
        production = tmp_path / ".oyawiki"

        # Create incomplete staging with corrupted content
        staging.mkdir()
        (staging / "corrupted.txt").write_text("bad data")

        # Create production with good content
        production.mkdir()
        (production / "wiki").mkdir()
        (production / "wiki" / "overview.md").write_text("# Good Overview")

        # Prepare staging
        prepare_staging_directory(staging, production)

        # Staging should have production content, not corrupted content
        assert not (staging / "corrupted.txt").exists()
        assert (staging / "wiki" / "overview.md").read_text() == "# Good Overview"

    def test_has_incomplete_build_detects_staging(self, tmp_path: Path):
        """has_incomplete_build returns True when staging directory exists."""
        from oya.generation.staging import has_incomplete_build

        staging = tmp_path / ".oyawiki-building"

        # No staging = no incomplete build
        assert not has_incomplete_build(tmp_path)

        # Create staging
        staging.mkdir()
        assert has_incomplete_build(tmp_path)

    def test_has_incomplete_build_false_when_no_staging(self, tmp_path: Path):
        """has_incomplete_build returns False when no staging directory."""
        from oya.generation.staging import has_incomplete_build

        # Only production exists
        production = tmp_path / ".oyawiki"
        production.mkdir()

        assert not has_incomplete_build(tmp_path)


class TestGenerationStatusAPI:
    """Tests for the generation status API endpoint."""

    def test_get_generation_status_returns_none_when_no_staging(self, tmp_path: Path):
        """API returns null when no staging directory exists."""
        from fastapi.testclient import TestClient
        from oya.main import app
        import os

        # Set up workspace path without staging
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        oyawiki = workspace / ".oyawiki"
        oyawiki.mkdir()

        os.environ["WORKSPACE_PATH"] = str(workspace)

        # Clear caches
        from oya.config import load_settings
        from oya.api.deps import get_settings

        load_settings.cache_clear()
        get_settings.cache_clear()

        client = TestClient(app)
        response = client.get("/api/repos/generation-status")

        assert response.status_code == 200
        assert response.json() is None

    def test_get_generation_status_returns_incomplete_when_staging_exists(self, tmp_path: Path):
        """API returns incomplete status when staging directory exists."""
        from fastapi.testclient import TestClient
        from oya.main import app
        import os

        # Set up workspace path with staging directory
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        staging = workspace / ".oyawiki-building"
        staging.mkdir()

        os.environ["WORKSPACE_PATH"] = str(workspace)

        # Clear caches
        from oya.config import load_settings
        from oya.api.deps import get_settings

        load_settings.cache_clear()
        get_settings.cache_clear()

        client = TestClient(app)
        response = client.get("/api/repos/generation-status")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "incomplete"
        assert "message" in data
