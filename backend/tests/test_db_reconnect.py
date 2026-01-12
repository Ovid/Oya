"""Tests for database reconnection when .oyawiki is deleted."""

import pytest
from pathlib import Path

from oya.api.deps import get_db, _reset_db_instance, get_settings
from oya.db.connection import Database


class TestDatabaseReconnect:
    """Test database reconnection after .oyawiki deletion."""

    def test_get_db_recreates_connection_when_file_deleted(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """get_db should recreate connection if database file was deleted."""
        # Setup: create a workspace with .oyawiki structure
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        oyawiki = workspace / ".oyawiki"
        oyawiki.mkdir()
        meta = oyawiki / "meta"
        meta.mkdir()

        # Configure settings to use this workspace
        monkeypatch.setenv("WORKSPACE_PATH", str(workspace))
        
        # Clear any cached settings/db
        get_settings.cache_clear()
        _reset_db_instance()

        # First call creates the database
        db1 = get_db()
        db_path = workspace / ".oyawiki" / "meta" / "oya.db"
        assert db_path.exists(), "Database file should be created"

        # Simulate user deleting .oyawiki directory
        import shutil
        shutil.rmtree(oyawiki)
        assert not db_path.exists(), "Database file should be deleted"

        # Recreate the directory structure (as initialize_workspace would)
        oyawiki.mkdir()
        meta.mkdir()

        # Second call should detect missing file and recreate connection
        db2 = get_db()
        
        # The database file should exist again
        assert db_path.exists(), "Database file should be recreated"
        
        # Should be able to execute queries without error
        db2.execute("SELECT 1")
        
        # Cleanup
        _reset_db_instance()
        get_settings.cache_clear()
