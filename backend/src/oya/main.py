"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from oya.api.routers import repos, wiki, jobs, search, qa, notes
from oya.config import load_settings
from oya.workspace import initialize_workspace

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Lifespan handler for startup and shutdown events.
    
    On startup:
    - Initializes the workspace directory structure
    
    On shutdown:
    - Cleanup if needed (currently none)
    """
    # Startup
    settings = load_settings()
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
