"""Tests for database cache invalidation after staging promotion.

This tests the fix for the bug where cached database connections become stale
after wiki regeneration promotes staging to production, causing
"sqlite3.OperationalError: attempt to write a readonly database" errors.
"""

import pytest

from oya.api.deps import (
    get_db,
    _db_instances,
    invalidate_db_cache_for_repo,
)
from oya.db.connection import Database
from oya.db.migrations import run_migrations
from oya.generation.staging import promote_staging_to_production


class TestDbCacheInvalidationAfterPromotion:
    """Tests that database connections remain valid after staging promotion."""

    def test_db_write_works_after_promotion_with_cache_invalidation(self, setup_active_repo):
        """Tests the complete fix: cache invalidation after promotion allows writes.

        This test simulates the complete workflow:
        1. Get a database connection (gets cached in _db_instances)
        2. Replace the database file (simulating staging promotion)
        3. Invalidate the cache (the fix)
        4. Get database again and verify writes work
        """
        paths = setup_active_repo["paths"]
        repo_id = setup_active_repo["repo_id"]

        # Step 1: Get initial database connection (this gets cached)
        db = get_db()
        assert isinstance(db, Database)

        # Verify we can write to it
        db.execute("CREATE TABLE IF NOT EXISTS test_table (id INTEGER PRIMARY KEY)")
        db.commit()

        # Step 2: Simulate staging promotion by replacing the .oyawiki directory
        staging_path = paths.meta / ".oyawiki-building"
        production_path = paths.oyawiki

        # Create staging with a new database
        staging_path.mkdir(parents=True, exist_ok=True)
        staging_meta = staging_path / "meta"
        staging_meta.mkdir(parents=True, exist_ok=True)
        staging_db_path = staging_meta / "oya.db"
        staging_db = Database(staging_db_path)
        run_migrations(staging_db)
        staging_db.execute("CREATE TABLE IF NOT EXISTS staging_marker (id INTEGER PRIMARY KEY)")
        staging_db.commit()
        staging_db.close()

        # Promote staging to production (this replaces the database file)
        promote_staging_to_production(staging_path, production_path)

        # Step 3: THE FIX - invalidate the cached connection
        invalidate_db_cache_for_repo(repo_id)

        # Step 4: Get the database again - should get a fresh connection
        db_after = get_db()

        # Step 5: Verify we can write to the database
        # Without the fix (no invalidation): fails with "readonly database"
        # With the fix: works because we get a fresh connection
        db_after.execute("CREATE TABLE IF NOT EXISTS post_promotion_table (id INTEGER PRIMARY KEY)")
        db_after.commit()

        # Verify we're connected to the NEW database (has staging_marker table)
        cursor = db_after.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='staging_marker'"
        )
        result = cursor.fetchone()
        assert result is not None, "Should be connected to the new (promoted) database"

    def test_without_cache_invalidation_write_fails(self, setup_active_repo):
        """Demonstrates that WITHOUT cache invalidation, writes fail after promotion.

        This test proves the bug exists when we don't invalidate the cache.
        """
        paths = setup_active_repo["paths"]

        # Get initial database connection (this gets cached)
        db = get_db()
        db.execute("CREATE TABLE IF NOT EXISTS test_table (id INTEGER PRIMARY KEY)")
        db.commit()

        # Simulate staging promotion
        staging_path = paths.meta / ".oyawiki-building"
        production_path = paths.oyawiki

        staging_path.mkdir(parents=True, exist_ok=True)
        staging_meta = staging_path / "meta"
        staging_meta.mkdir(parents=True, exist_ok=True)
        staging_db_path = staging_meta / "oya.db"
        staging_db = Database(staging_db_path)
        run_migrations(staging_db)
        staging_db.close()

        # Promote staging to production
        promote_staging_to_production(staging_path, production_path)

        # DO NOT invalidate cache - this demonstrates the bug

        # Get database again - will get STALE cached connection
        db_after = get_db()

        # This SHOULD fail with readonly database error (proving the bug exists)
        import sqlite3

        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            db_after.execute("CREATE TABLE IF NOT EXISTS will_fail (id INTEGER PRIMARY KEY)")

    def test_invalidate_db_cache_for_repo_function_exists(self):
        """Test that we have a function to invalidate the DB cache for a specific repo."""
        from oya.api import deps

        # After the fix, there should be a function to invalidate cache for a repo
        assert hasattr(deps, "invalidate_db_cache_for_repo"), (
            "Should have invalidate_db_cache_for_repo function"
        )

    def test_invalidate_db_cache_removes_repo_from_cache(self, setup_active_repo):
        """Test that invalidate_db_cache_for_repo removes the repo's DB from cache."""
        from oya.api.deps import invalidate_db_cache_for_repo

        repo_id = setup_active_repo["repo_id"]

        # Get a database connection (gets cached)
        get_db()  # Result unused; we just need the caching side effect
        assert repo_id in _db_instances, "DB should be cached after get_db()"

        # Invalidate the cache for this repo
        invalidate_db_cache_for_repo(repo_id)

        # Cache should no longer contain this repo
        assert repo_id not in _db_instances, "DB should be removed from cache after invalidation"

    def test_get_db_after_invalidation_returns_fresh_connection(self, setup_active_repo):
        """Test that get_db returns a fresh connection after cache invalidation."""
        from oya.api.deps import invalidate_db_cache_for_repo

        repo_id = setup_active_repo["repo_id"]

        # Get initial connection
        db1 = get_db()
        db1_id = id(db1)

        # Invalidate cache
        invalidate_db_cache_for_repo(repo_id)

        # Get connection again - should be a NEW instance
        db2 = get_db()
        db2_id = id(db2)

        assert db1_id != db2_id, "Should get a fresh connection after invalidation"
