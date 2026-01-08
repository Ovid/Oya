"""FastAPI application entry point."""

from fastapi import FastAPI

app = FastAPI(
    title="Oya",
    description="Local-first editable wiki generator for codebases",
    version="0.1.0",
)


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy"}
