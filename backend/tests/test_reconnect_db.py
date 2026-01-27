"""Tests for reconnect_db: stale DB connection recovery.

Tests the reconnect_db function used after operations that destroy the
.oyawiki directory (full regeneration wipe, staging promotion), which
invalidates any cached DB connection pointing at the now-deleted oya.db file.
"""

import shutil
import sqlite3

import pytest

from oya.api.deps import (
    _db_instances,
    get_db,
    invalidate_db_cache_for_repo,
    reconnect_db,
)
from oya.db.connection import Database
from oya.db.migrations import run_migrations
from oya.generation.staging import promote_staging_to_production


class TestReconnectDb:
    """Unit tests for reconnect_db."""

    def test_returns_writable_database(self, setup_active_repo):
        """reconnect_db should return a Database that can be written to."""
        repo_id = setup_active_repo["repo_id"]
        paths = setup_active_repo["paths"]

        db = reconnect_db(repo_id, paths)

        db.execute("CREATE TABLE IF NOT EXISTS test_rw (id INTEGER PRIMARY KEY)")
        db.commit()

    def test_caches_new_connection(self, setup_active_repo):
        """reconnect_db should store the new connection in the instance cache."""
        repo_id = setup_active_repo["repo_id"]
        paths = setup_active_repo["paths"]

        db = reconnect_db(repo_id, paths)

        assert repo_id in _db_instances
        assert _db_instances[repo_id] is db

    def test_invalidates_old_connection(self, setup_active_repo):
        """reconnect_db should replace the previously cached connection."""
        repo_id = setup_active_repo["repo_id"]
        paths = setup_active_repo["paths"]

        old_db = get_db()
        old_id = id(old_db)

        new_db = reconnect_db(repo_id, paths)

        assert id(new_db) != old_id

    def test_recreates_directory_structure(self, setup_active_repo):
        """reconnect_db should create meta_dir if it doesn't exist."""
        repo_id = setup_active_repo["repo_id"]
        paths = setup_active_repo["paths"]

        # Wipe the entire .oyawiki directory
        if paths.oyawiki.exists():
            shutil.rmtree(paths.oyawiki)
        assert not paths.meta_dir.exists()

        db = reconnect_db(repo_id, paths)

        assert paths.meta_dir.exists()
        assert paths.db_path.exists()
        # Verify the returned db is writable
        db.execute("CREATE TABLE IF NOT EXISTS test_recreate (id INTEGER PRIMARY KEY)")
        db.commit()

    def test_runs_migrations(self, setup_active_repo):
        """reconnect_db should run migrations so the schema is ready."""
        repo_id = setup_active_repo["repo_id"]
        paths = setup_active_repo["paths"]

        # Wipe to force fresh DB
        if paths.oyawiki.exists():
            shutil.rmtree(paths.oyawiki)

        db = reconnect_db(repo_id, paths)

        # The generations table is created by migrations
        cursor = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='generations'"
        )
        assert cursor.fetchone() is not None


class TestInvalidateDoesNotCloseConnection:
    """Invalidation must NOT close old connections.

    Long-lived consumers (SSE streaming) hold references to the cached DB.
    If invalidate_db_cache_for_repo closes the old connection, those
    consumers crash with 'Cannot operate on a closed database'.
    """

    def test_old_connection_usable_after_invalidation(self, setup_active_repo):
        """Old DB connection should remain readable after cache invalidation."""
        repo_id = setup_active_repo["repo_id"]

        old_db = get_db()

        # Write data so we can read it back later
        old_db.execute(
            """
            INSERT INTO generations (id, type, status, started_at, total_phases)
            VALUES ('survive-test', 'full', 'running', datetime('now'), 9)
            """
        )
        old_db.commit()

        # Invalidate cache — old_db should NOT be closed
        invalidate_db_cache_for_repo(repo_id)

        # Old connection should still be usable (this is what the SSE stream does)
        cursor = old_db.execute("SELECT status FROM generations WHERE id = 'survive-test'")
        row = cursor.fetchone()
        assert row is not None
        assert row["status"] == "running"

    def test_old_connection_not_closed_during_reconnect(self, setup_active_repo):
        """reconnect_db should not close the old connection either."""
        repo_id = setup_active_repo["repo_id"]
        paths = setup_active_repo["paths"]

        old_db = get_db()
        old_db.execute(
            """
            INSERT INTO generations (id, type, status, started_at, total_phases)
            VALUES ('reconnect-survive', 'full', 'running', datetime('now'), 9)
            """
        )
        old_db.commit()

        # reconnect_db calls invalidate_db_cache_for_repo internally
        reconnect_db(repo_id, paths)

        # Old connection should still work
        cursor = old_db.execute("SELECT status FROM generations WHERE id = 'reconnect-survive'")
        row = cursor.fetchone()
        assert row is not None


class TestReconnectDbAfterFullWipe:
    """Integration tests simulating the full regeneration wipe scenario."""

    def test_db_writable_after_oyawiki_wipe(self, setup_active_repo):
        """After wiping .oyawiki, reconnect_db should provide a writable DB.

        This is the exact scenario that caused the original
        "attempt to write a readonly database" error.
        """
        repo_id = setup_active_repo["repo_id"]
        paths = setup_active_repo["paths"]

        # Get initial connection and write a job record
        db = get_db()
        db.execute(
            """
            INSERT INTO generations (id, type, status, started_at, total_phases)
            VALUES ('test-job', 'full', 'pending', datetime('now'), 9)
            """
        )
        db.commit()

        # Wipe production (simulating full regeneration)
        production_path = paths.oyawiki
        shutil.rmtree(production_path)

        # Reconnect
        db = reconnect_db(repo_id, paths)

        # Should be able to write (this is what failed before the fix)
        db.execute(
            """
            INSERT INTO generations (id, type, status, started_at, total_phases)
            VALUES ('test-job-2', 'full', 'running', datetime('now'), 9)
            """
        )
        db.commit()

    def test_closure_sees_reconnected_db(self, setup_active_repo):
        """A closure capturing db should see the new connection after reassignment.

        This tests the exact pattern used by progress_callback in _run_generation:
        a closure captures 'db' by name, db gets reassigned via reconnect_db,
        and the closure should use the new connection.
        """
        repo_id = setup_active_repo["repo_id"]
        paths = setup_active_repo["paths"]

        db = get_db()

        # Simulate the progress_callback closure pattern
        writes = []

        def progress_callback():
            db.execute(
                """
                INSERT INTO generations (id, type, status, started_at, total_phases)
                VALUES (?, 'full', 'running', datetime('now'), 9)
                """,
                (f"job-{len(writes)}",),
            )
            db.commit()
            writes.append(True)

        # First call works fine
        progress_callback()
        assert len(writes) == 1

        # Wipe production
        shutil.rmtree(paths.oyawiki)

        # Reassign db (simulating what _run_generation does)
        db = reconnect_db(repo_id, paths)

        # Closure should use the NEW db (Python late-binding)
        progress_callback()
        assert len(writes) == 2

    def test_without_reconnect_write_fails_after_wipe(self, setup_active_repo):
        """Proves the bug: without reconnect_db, writes fail after wipe."""
        paths = setup_active_repo["paths"]

        db = get_db()
        db.execute(
            """
            INSERT INTO generations (id, type, status, started_at, total_phases)
            VALUES ('test-job', 'full', 'pending', datetime('now'), 9)
            """
        )
        db.commit()

        # Wipe production WITHOUT reconnecting
        shutil.rmtree(paths.oyawiki)

        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            db.execute("UPDATE generations SET status = 'running' WHERE id = 'test-job'")


class TestPromotedDbHasCompletedJobStatus:
    """After staging promotion, the promoted DB must have the completed job status.

    Bug: The generation pipeline writes job status "completed" to the production
    DB (db), then promotes staging → production. The staging DB is a copy from
    BEFORE generation started, so it has the job with status "running". After
    promotion, get_db() returns a connection to the promoted (staging) DB which
    has the stale "running" status. The SSE stream polls forever, and the UI
    shows a stalled progress screen.

    Fix: Before closing staging_db, copy the final job status into the staging
    DB so the promoted DB has the correct "completed" state.
    """

    def test_without_staging_update_promoted_db_has_stale_status(self, setup_active_repo):
        """Proves the bug: without updating staging DB, promoted DB has stale status.

        The generation pipeline writes "completed" only to the production DB.
        The staging DB (copied before generation) still has "running". After
        promotion, get_db() sees the stale "running" status.
        """
        repo_id = setup_active_repo["repo_id"]
        paths = setup_active_repo["paths"]

        db = get_db()
        db.execute(
            """
            INSERT INTO generations (id, type, status, started_at, total_phases, current_phase)
            VALUES ('stale-job', 'full', 'running', datetime('now'), 9, '0:starting')
            """
        )
        db.commit()

        # Copy production to staging (staging gets "running" snapshot)
        staging_path = paths.meta / ".oyawiki-building"
        from oya.generation.staging import prepare_staging_directory

        prepare_staging_directory(staging_path, paths.oyawiki)
        staging_meta = staging_path / "meta"
        staging_db = Database(staging_meta / "oya.db")
        run_migrations(staging_db)

        # Update production only — staging still has "running"
        db.execute("UPDATE generations SET status = 'completed' WHERE id = 'stale-job'")
        db.commit()

        # Promote WITHOUT updating staging DB first (the bug)
        staging_db.close()
        promote_staging_to_production(staging_path, paths.oyawiki)
        reconnect_db(repo_id, paths)

        fresh_db = get_db()
        cursor = fresh_db.execute("SELECT status FROM generations WHERE id = 'stale-job'")
        row = cursor.fetchone()
        assert row is not None
        # This proves the bug: promoted DB has stale "running" status
        assert row["status"] == "running"

    def test_with_staging_update_promoted_db_has_completed_status(self, setup_active_repo):
        """Fix: updating staging DB before promotion gives correct status.

        When the staging DB is updated with the final job status before closing
        and promoting, the promoted DB has "completed" and the SSE stream
        terminates correctly.
        """
        repo_id = setup_active_repo["repo_id"]
        paths = setup_active_repo["paths"]

        db = get_db()
        db.execute(
            """
            INSERT INTO generations (id, type, status, started_at, total_phases, current_phase)
            VALUES ('fixed-job', 'full', 'running', datetime('now'), 9, '0:starting')
            """
        )
        db.commit()

        # Copy production to staging (staging gets "running" snapshot)
        staging_path = paths.meta / ".oyawiki-building"
        from oya.generation.staging import prepare_staging_directory

        prepare_staging_directory(staging_path, paths.oyawiki)
        staging_meta = staging_path / "meta"
        staging_db = Database(staging_meta / "oya.db")
        run_migrations(staging_db)

        # Update production DB to "completed"
        db.execute(
            """
            UPDATE generations
            SET status = 'completed', completed_at = datetime('now'), changes_made = 1
            WHERE id = 'fixed-job'
            """
        )
        db.commit()

        # THE FIX: also update staging DB before closing
        staging_db.execute(
            """
            UPDATE generations
            SET status = 'completed', completed_at = datetime('now'), changes_made = 1
            WHERE id = 'fixed-job'
            """
        )
        staging_db.commit()

        # Close and promote
        staging_db.close()
        promote_staging_to_production(staging_path, paths.oyawiki)
        reconnect_db(repo_id, paths)

        # Promoted DB must show "completed"
        fresh_db = get_db()
        cursor = fresh_db.execute("SELECT status FROM generations WHERE id = 'fixed-job'")
        row = cursor.fetchone()
        assert row is not None, "Job 'fixed-job' not found in promoted DB"
        assert row["status"] == "completed", (
            f"Expected 'completed' but got '{row['status']}' — "
            "staging DB has stale job status after promotion"
        )


class TestReconnectDbAfterPromotion:
    """Integration tests simulating the staging-to-production promotion scenario."""

    def test_db_writable_after_promotion(self, setup_active_repo):
        """After staging promotion, reconnect_db provides a writable DB."""
        repo_id = setup_active_repo["repo_id"]
        paths = setup_active_repo["paths"]

        # Get initial connection
        get_db()

        # Create staging with a new database
        staging_path = paths.meta / ".oyawiki-building"
        staging_path.mkdir(parents=True, exist_ok=True)
        staging_meta = staging_path / "meta"
        staging_meta.mkdir(parents=True, exist_ok=True)
        staging_db = Database(staging_meta / "oya.db")
        run_migrations(staging_db)
        staging_db.execute("CREATE TABLE IF NOT EXISTS staging_marker (id INTEGER PRIMARY KEY)")
        staging_db.commit()
        staging_db.close()

        # Promote (replaces .oyawiki)
        promote_staging_to_production(staging_path, paths.oyawiki)

        # Reconnect
        db = reconnect_db(repo_id, paths)

        # Should be writable
        db.execute("CREATE TABLE IF NOT EXISTS post_promotion (id INTEGER PRIMARY KEY)")
        db.commit()

        # Should be connected to the NEW (promoted) database
        cursor = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='staging_marker'"
        )
        assert cursor.fetchone() is not None
