"""Tests for database reconnection when meta directory is deleted."""

import shutil


from oya.api.deps import get_db, _reset_db_instance


class TestDatabaseReconnect:
    """Test database reconnection after meta directory deletion."""

    def test_get_db_recreates_connection_when_file_deleted(self, setup_active_repo) -> None:
        """get_db should recreate connection if database file was deleted."""
        paths = setup_active_repo["paths"]
        meta_dir = paths.meta_dir

        # First call creates the database
        get_db()
        db_path = paths.db_path
        assert db_path.exists(), "Database file should be created"

        # Simulate user deleting meta directory
        _reset_db_instance()  # Close existing connection before deleting
        shutil.rmtree(meta_dir)
        assert not db_path.exists(), "Database file should be deleted"

        # Recreate the directory structure
        meta_dir.mkdir(parents=True)

        # Second call should detect missing file and recreate connection
        db2 = get_db()

        # The database file should exist again
        assert db_path.exists(), "Database file should be recreated"

        # Should be able to execute queries without error
        db2.execute("SELECT 1")

        # Cleanup
        _reset_db_instance()
