"""FastAPI application entry point."""

import logging
import os
import shutil
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Logging constants defined here (not in constants/) because logging.basicConfig()
# must run before any module imports that might create loggers.
LOG_FORMAT = "%(asctime)s %(levelname)-8s %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

logging.basicConfig(
    format=LOG_FORMAT,
    datefmt=DATE_FORMAT,
    level=logging.INFO,
)

# Unify uvicorn loggers with app format
for uvicorn_logger_name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
    uvicorn_logger = logging.getLogger(uvicorn_logger_name)
    uvicorn_logger.handlers.clear()
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
    uvicorn_logger.addHandler(handler)

from oya.api.routers import repos, wiki, jobs, search, qa, notes, repos_v2  # noqa: E402

logger = logging.getLogger(__name__)


def _check_git_available() -> bool:
    """Check if git is installed and available.

    Returns:
        True if git is available, False otherwise.
    """
    git_path = shutil.which("git")
    if git_path is None:
        logger.error("Git is not installed or not in PATH. Git is required for Oya to function.")
        return False
    logger.info(f"Git found at: {git_path}")
    return True


def _ensure_data_dir() -> Path:
    """Ensure the OYA_DATA_DIR exists and return its path.

    Creates the directory structure if it doesn't exist:
    - ~/.oya/ (or OYA_DATA_DIR)
    - ~/.oya/wikis/

    Returns:
        Path to the data directory.
    """
    data_dir_str = os.getenv("OYA_DATA_DIR")
    if data_dir_str:
        data_dir = Path(data_dir_str)
    else:
        data_dir = Path.home() / ".oya"

    # Create directory structure
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "wikis").mkdir(exist_ok=True)

    logger.info(f"Data directory: {data_dir}")
    return data_dir


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Lifespan handler for startup and shutdown events.

    On startup:
    - Checks that git is installed
    - Ensures OYA_DATA_DIR exists

    On shutdown:
    - Cleanup if needed (currently none)
    """
    # Startup

    # Check git is available (required for cloning repos)
    if not _check_git_available():
        logger.warning("Git not available - some features may not work")

    # Ensure data directory exists for multi-repo mode
    _ensure_data_dir()

    logger.info("Running in multi-repo mode")

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
app.include_router(repos_v2.router)
