"""SSE streaming tests."""

import logging
import shutil
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from oya.main import app
from oya.api.deps import get_db, reconnect_db
from oya.db.connection import Database
from oya.db.migrations import run_migrations
from oya.generation.staging import prepare_staging_directory, promote_staging_to_production


@pytest.fixture
def workspace_with_job(setup_active_repo):
    """Create workspace with database and running job using active repo fixture."""
    db = get_db()
    db.execute(
        """
        INSERT INTO generations (id, type, status, started_at)
        VALUES ('stream-job-123', 'full', 'completed', datetime('now'))
        """
    )
    db.commit()

    return setup_active_repo


@pytest.fixture
async def client():
    """Create async test client."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client


async def test_sse_stream_endpoint_exists(client, workspace_with_job):
    """GET /api/jobs/{job_id}/stream returns SSE response."""
    response = await client.get("/api/jobs/stream-job-123/stream")

    # For completed jobs, we get a final event immediately
    assert response.status_code == 200
    assert "text/event-stream" in response.headers.get("content-type", "")


async def test_sse_stream_completed_job_sends_complete_event(client, workspace_with_job):
    """Streaming completed job sends complete event."""
    response = await client.get("/api/jobs/stream-job-123/stream")

    assert response.status_code == 200
    content = response.text
    assert "event: complete" in content or "completed" in content


async def test_sse_stream_nonexistent_job_returns_404(client, workspace_with_job):
    """GET /api/jobs/{nonexistent}/stream returns 404."""
    response = await client.get("/api/jobs/nonexistent/stream")

    assert response.status_code == 404


async def test_sse_stream_survives_mid_stream_reconnect(client, setup_active_repo):
    """SSE stream must survive reconnect_db firing mid-poll.

    This is the exact bug: SSE stream starts polling a running job,
    full regeneration calls reconnect_db in a background task (closing
    the old cached connection), and the generator's next poll must use
    the fresh connection instead of crashing with 'Cannot operate on
    a closed database'.

    The test uses asyncio concurrency: the reconnect task fires while
    the generator is sleeping between polls, then the generator wakes
    and must see the job as 'completed' in the NEW database.
    """
    import asyncio

    repo_id = setup_active_repo["repo_id"]
    paths = setup_active_repo["paths"]

    # Insert a running job — the stream will poll and yield progress events
    db = get_db()
    db.execute(
        """
        INSERT INTO generations (id, type, status, started_at)
        VALUES ('mid-stream-job', 'full', 'running', datetime('now'))
        """
    )
    db.commit()

    async def reconnect_mid_stream():
        """Simulate full regeneration wipe + reconnect while SSE sleeps."""
        await asyncio.sleep(0.1)  # Let the stream start first
        shutil.rmtree(paths.oyawiki)  # Wipe like real full regeneration
        new_db = reconnect_db(repo_id, paths)
        # Insert the job as completed in the NEW database
        new_db.execute(
            """
            INSERT INTO generations (id, type, status, started_at)
            VALUES ('mid-stream-job', 'full', 'completed', datetime('now'))
            """
        )
        new_db.commit()

    # Launch reconnect concurrently with the SSE request
    task = asyncio.create_task(reconnect_mid_stream())
    response = await client.get("/api/jobs/mid-stream-job/stream")
    await task

    assert response.status_code == 200
    assert "event: complete" in response.text


async def test_sse_stream_logs_exception_on_db_failure(client, setup_active_repo, caplog):
    """When get_db() raises during SSE polling, the exception is logged.

    The SSE stream catches DB errors and sends a clean error event to the
    client, but the actual exception must be logged server-side so the root
    cause is diagnosable (not just "Database connection lost").
    """
    db = get_db()
    db.execute(
        """
        INSERT INTO generations (id, type, status, started_at)
        VALUES ('log-test-job', 'full', 'running', datetime('now'))
        """
    )
    db.commit()

    call_count = 0

    def get_db_then_fail():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # First call: FastAPI dependency injection for initial job check
            return db
        raise RuntimeError("Simulated DB corruption")

    with (
        patch("oya.api.routers.jobs.get_db", side_effect=get_db_then_fail),
        caplog.at_level(logging.ERROR, logger="oya.api.routers.jobs"),
    ):
        response = await client.get("/api/jobs/log-test-job/stream")

    # Client gets a clean error event
    assert response.status_code == 200
    assert "event: error" in response.text
    assert "Database connection lost" in response.text

    # Server logs the actual exception details
    assert "SSE stream DB error for job log-test-job" in caplog.text
    assert "Simulated DB corruption" in caplog.text


async def test_sse_stream_sees_completed_after_staging_promotion(client, setup_active_repo):
    """SSE stream must see 'completed' after staging promotion replaces the DB.

    This is the stalled-progress-screen bug: generation completes, staging is
    promoted to production (replacing the DB file), and the SSE stream's next
    get_db() poll must see the job as 'completed' in the promoted DB.

    Without the fix (updating staging DB before promotion), the promoted DB
    has the stale 'running' status and the stream never terminates.
    """
    import asyncio

    repo_id = setup_active_repo["repo_id"]
    paths = setup_active_repo["paths"]

    # Insert a running job
    db = get_db()
    db.execute(
        """
        INSERT INTO generations (id, type, status, started_at, total_phases, current_phase)
        VALUES ('promo-stream-job', 'full', 'running', datetime('now'), 9, '0:starting')
        """
    )
    db.commit()

    async def promote_mid_stream():
        """Simulate generation completion + staging promotion while SSE polls."""
        await asyncio.sleep(0.1)  # Let the stream start

        # Copy production to staging (staging gets "running" snapshot)
        staging_path = paths.meta / ".oyawiki-building"
        prepare_staging_directory(staging_path, paths.oyawiki)

        staging_meta = staging_path / "meta"
        staging_db = Database(staging_meta / "oya.db")
        run_migrations(staging_db)

        # Update production DB to "completed"
        db.execute(
            """
            UPDATE generations
            SET status = 'completed', completed_at = datetime('now'), changes_made = 1
            WHERE id = 'promo-stream-job'
            """
        )
        db.commit()

        # THE FIX: also update staging DB
        staging_db.execute(
            """
            UPDATE generations
            SET status = 'completed', completed_at = datetime('now'), changes_made = 1
            WHERE id = 'promo-stream-job'
            """
        )
        staging_db.commit()
        staging_db.close()

        # Promote staging → production and reconnect
        promote_staging_to_production(staging_path, paths.oyawiki)
        reconnect_db(repo_id, paths)

    task = asyncio.create_task(promote_mid_stream())
    response = await client.get("/api/jobs/promo-stream-job/stream")
    await task

    assert response.status_code == 200
    assert "event: complete" in response.text
