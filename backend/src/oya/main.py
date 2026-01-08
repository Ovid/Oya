"""FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from oya.api.routers import repos, wiki, jobs, search

app = FastAPI(
    title="Oya",
    description="Local-first editable wiki generator for codebases",
    version="0.1.0",
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
