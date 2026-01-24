"""FastAPI dependency injection functions."""

import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

from fastapi import HTTPException, status

from oya.config import Settings, load_settings
from oya.db.connection import Database
from oya.db.migrations import run_migrations
from oya.db.repo_registry import RepoRegistry, RepoRecord
from oya.llm.client import LLMClient
from oya.repo.git_repo import GitRepo
from oya.repo.repo_paths import RepoPaths
from oya.state import get_app_state
from oya.vectorstore.issues import IssuesStore
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


# =============================================================================
# Active Repo Context
# =============================================================================


def get_active_repo() -> Optional[RepoRecord]:
    """Get the currently active repository record.

    Returns:
        RepoRecord if a repo is active, None otherwise.
    """
    app_state = get_app_state()
    if app_state.active_repo_id is None:
        return None

    settings = load_settings()
    registry = RepoRegistry(settings.repos_db_path)
    try:
        return registry.get(app_state.active_repo_id)
    finally:
        registry.close()


def get_active_repo_paths() -> RepoPaths:
    """Get paths for the currently active repository.

    Returns:
        RepoPaths for the active repo.

    Raises:
        HTTPException: 400 if no repository is active.
    """
    repo = get_active_repo()
    if repo is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No repository is active. Please select a repository first.",
        )

    settings = load_settings()
    return RepoPaths(settings.data_dir, repo.local_path)


def require_active_repo() -> RepoRecord:
    """Get the active repository, raising an error if none is active.

    This is a FastAPI dependency for endpoints that require an active repo.

    Returns:
        RepoRecord for the active repo.

    Raises:
        HTTPException: 400 if no repository is active.
    """
    repo = get_active_repo()
    if repo is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No repository is active. Please select a repository first.",
        )
    return repo


@lru_cache
def get_settings() -> Settings:
    """Get cached application settings."""
    return load_settings()


# Per-repo instance caches (keyed by repo_id)
_db_instances: dict[int, Database] = {}
_vectorstore_instances: dict[int, VectorStore] = {}
_issues_store_instances: dict[int, IssuesStore] = {}

# Legacy single-instance for backward compatibility (when no active repo)
_legacy_db_instance: Database | None = None


def get_db() -> Database:
    """Get database connection with migrations applied.

    If a repo is active, returns the database for that repo.
    Falls back to legacy WORKSPACE_PATH-based database if no repo is active.
    """
    global _legacy_db_instance

    # Try active repo first
    repo = get_active_repo()
    if repo is not None:
        if repo.id not in _db_instances:
            settings = load_settings()
            paths = RepoPaths(settings.data_dir, repo.local_path)
            paths.meta_dir.mkdir(parents=True, exist_ok=True)
            db = Database(paths.db_path)
            run_migrations(db)
            _db_instances[repo.id] = db
        return _db_instances[repo.id]

    # Fall back to legacy behavior for backward compatibility
    settings = get_settings()

    # Check if cached connection is stale (db file was deleted)
    if _legacy_db_instance is not None and not settings.db_path.exists():
        _legacy_db_instance.close()
        _legacy_db_instance = None

    if _legacy_db_instance is None:
        _legacy_db_instance = Database(settings.db_path)
        run_migrations(_legacy_db_instance)
    return _legacy_db_instance


def _reset_db_instance() -> None:
    """Reset database instances (for testing only)."""
    global _legacy_db_instance, _db_instances
    if _legacy_db_instance is not None:
        _legacy_db_instance.close()
        _legacy_db_instance = None
    for db in _db_instances.values():
        db.close()
    _db_instances.clear()


def get_repo() -> GitRepo:
    """Get repository wrapper for active repo or workspace.

    If a repo is active, returns GitRepo for that repo's source directory.
    Falls back to legacy WORKSPACE_PATH if no repo is active.
    """
    repo = get_active_repo()
    if repo is not None:
        settings = load_settings()
        paths = RepoPaths(settings.data_dir, repo.local_path)
        return GitRepo(paths.source)

    # Legacy fallback
    settings = get_settings()
    return GitRepo(settings.workspace_path)


def get_vectorstore() -> VectorStore:
    """Get vector store instance for active repo.

    If a repo is active, returns the vectorstore for that repo.
    Falls back to legacy WORKSPACE_PATH-based vectorstore if no repo is active.
    """
    repo = get_active_repo()
    if repo is not None:
        if repo.id not in _vectorstore_instances:
            settings = load_settings()
            paths = RepoPaths(settings.data_dir, repo.local_path)
            paths.chroma_dir.parent.mkdir(parents=True, exist_ok=True)
            _vectorstore_instances[repo.id] = VectorStore(paths.chroma_dir)
        return _vectorstore_instances[repo.id]

    # Legacy fallback
    settings = get_settings()
    return VectorStore(settings.chroma_path)


def _reset_vectorstore_instance() -> None:
    """Reset vectorstore instances (for testing only)."""
    global _vectorstore_instances
    _vectorstore_instances.clear()


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


_legacy_issues_store: IssuesStore | None = None


def get_issues_store() -> IssuesStore:
    """Get or create the issues vector store instance.

    If a repo is active, returns the issues store for that repo.
    Falls back to legacy WORKSPACE_PATH-based store if no repo is active.
    """
    global _legacy_issues_store

    repo = get_active_repo()
    if repo is not None:
        if repo.id not in _issues_store_instances:
            settings = load_settings()
            paths = RepoPaths(settings.data_dir, repo.local_path)
            persist_path = paths.oyawiki / "vectorstore"
            persist_path.mkdir(parents=True, exist_ok=True)
            _issues_store_instances[repo.id] = IssuesStore(persist_path)
        return _issues_store_instances[repo.id]

    # Legacy fallback
    settings = get_settings()
    if _legacy_issues_store is None:
        persist_path = settings.oyawiki_path / "vectorstore"
        _legacy_issues_store = IssuesStore(persist_path)
    return _legacy_issues_store


def _reset_issues_store_instance() -> None:
    """Reset issues store instances (for testing only)."""
    global _legacy_issues_store, _issues_store_instances
    if _legacy_issues_store is not None:
        _legacy_issues_store.close()
        _legacy_issues_store = None
    for store in _issues_store_instances.values():
        store.close()
    _issues_store_instances.clear()
