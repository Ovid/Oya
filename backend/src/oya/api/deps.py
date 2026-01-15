"""FastAPI dependency injection functions."""

import os
from functools import lru_cache
from pathlib import Path

from oya.config import Settings, load_settings
from oya.db.connection import Database
from oya.db.migrations import run_migrations
from oya.llm.client import LLMClient
from oya.repo.git_repo import GitRepo
from oya.vectorstore.store import VectorStore


def get_workspace_base_path() -> Path:
    """Get the allowed base path for workspaces.

    Returns the WORKSPACE_BASE_PATH environment variable if set,
    otherwise defaults to the user's home directory.

    Returns:
        Path: The resolved base path for workspace validation.
    """
    base = os.getenv("WORKSPACE_BASE_PATH")
    if base:
        return Path(base).resolve()
    return Path.home()


def validate_workspace_path(path: str, base_path: Path) -> tuple[bool, str, Path | None]:
    """Validate a workspace path is safe and within allowed bounds.

    Performs security checks including:
    - Path existence verification
    - Directory type verification
    - Base path containment (prevents path traversal attacks)
    - Symlink resolution (ensures symlink targets are also within bounds)

    Args:
        path: The requested workspace path string.
        base_path: The allowed base path that workspaces must be under.

    Returns:
        Tuple of (is_valid, error_message, resolved_path).
        - is_valid: True if path passes all validation checks
        - error_message: Empty string if valid, descriptive error otherwise
        - resolved_path: The canonical resolved path if valid, None otherwise
    """
    try:
        requested = Path(path).resolve()
    except (ValueError, OSError) as e:
        return False, f"Invalid path: {e}", None

    if not requested.exists():
        return False, "Path does not exist", None

    if not requested.is_dir():
        return False, "Path is not a directory", None

    # Security: ensure resolved path is under base_path
    # This handles symlinks and .. traversal since we use resolve()
    try:
        requested.relative_to(base_path)
    except ValueError:
        return False, "Path is outside allowed workspace area", None

    return True, "", requested


@lru_cache
def get_settings() -> Settings:
    """Get cached application settings."""
    return load_settings()


_db_instance: Database | None = None


def get_db() -> Database:
    """Get database connection with migrations applied."""
    global _db_instance
    settings = get_settings()

    # Check if cached connection is stale (db file was deleted)
    if _db_instance is not None and not settings.db_path.exists():
        _db_instance.close()
        _db_instance = None

    if _db_instance is None:
        _db_instance = Database(settings.db_path)
        run_migrations(_db_instance)
    return _db_instance


def _reset_db_instance() -> None:
    """Reset database instance (for testing only)."""
    global _db_instance
    if _db_instance is not None:
        _db_instance.close()
        _db_instance = None


def get_repo() -> GitRepo:
    """Get repository wrapper for workspace."""
    settings = get_settings()
    return GitRepo(settings.workspace_path)


_vectorstore_instance: VectorStore | None = None


def get_vectorstore() -> VectorStore:
    """Get vector store instance."""
    global _vectorstore_instance
    if _vectorstore_instance is None:
        settings = get_settings()
        _vectorstore_instance = VectorStore(settings.chroma_path)
    return _vectorstore_instance


def _reset_vectorstore_instance() -> None:
    """Reset vectorstore instance (for testing only)."""
    global _vectorstore_instance
    _vectorstore_instance = None


_llm_instance: LLMClient | None = None


def get_llm() -> LLMClient:
    """Get LLM client instance."""
    global _llm_instance
    if _llm_instance is None:
        settings = get_settings()
        _llm_instance = LLMClient(
            provider=settings.llm_provider,
            model=settings.llm_model,
            api_key=settings.llm_api_key,
            endpoint=settings.llm_endpoint,
            log_path=settings.llm_log_path,
        )
    return _llm_instance


def _reset_llm_instance() -> None:
    """Reset LLM client instance (for testing only)."""
    global _llm_instance
    _llm_instance = None
