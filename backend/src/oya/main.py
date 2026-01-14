"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Configure global logging format with timestamps
LOG_FORMAT = "%(asctime)s %(levelname)-8s %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

logging.basicConfig(
    format=LOG_FORMAT,
    datefmt=DATE_FORMAT,
    level=logging.INFO,
)

from oya.api.routers import repos, wiki, jobs, search, qa, notes
from oya.config import load_settings
from oya.workspace import initialize_workspace

logger = logging.getLogger(__name__)


def _cleanup_stale_jobs(settings) -> None:
    """Mark any running/pending jobs as failed on startup.

    If the server is starting, any previously "running" jobs must have been
    interrupted by a server restart. Mark them as failed so the frontend
    doesn't try to resume them.
    """
    from oya.db.connection import Database

    try:
        if not settings.db_path.exists():
            return

        db = Database(settings.db_path)
        cursor = db.execute(
            """
            UPDATE generations
            SET status = 'failed',
                error_message = 'Interrupted by server restart',
                completed_at = datetime('now')
            WHERE status IN ('running', 'pending')
            """
        )
        if cursor.rowcount > 0:
            logger.info(f"Marked {cursor.rowcount} stale job(s) as failed")
        db.commit()
        db.close()
    except Exception as e:
        logger.warning(f"Failed to cleanup stale jobs: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Lifespan handler for startup and shutdown events.

    On startup:
    - Marks any stale running jobs as failed
    - Initializes the workspace directory structure

    On shutdown:
    - Cleanup if needed (currently none)
    """
    # Startup
    settings = load_settings()

    # Cleanup any jobs that were interrupted by a previous shutdown
    _cleanup_stale_jobs(settings)

    success = initialize_workspace(settings.workspace_path)
    if success:
        logger.info(f"Workspace initialized at {settings.workspace_path}")
    else:
        logger.warning(f"Failed to initialize workspace at {settings.workspace_path}")

    yield

    # Shutdown (cleanup if needed)


app = FastAPI(
    title="Ọya",
    description="Local-first editable wiki generator for codebases",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy"}


# Include routers
app.include_router(repos.router)
app.include_router(wiki.router)
app.include_router(jobs.router)
app.include_router(search.router)
app.include_router(qa.router)
app.include_router(notes.router)
