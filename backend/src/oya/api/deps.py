"""FastAPI dependency injection functions."""

from functools import lru_cache
from typing import Optional

from fastapi import HTTPException, status

from oya.config import Settings, load_settings
from oya.db.connection import Database
from oya.db.migrations import run_migrations
from oya.db.repo_registry import RepoRegistry, RepoRecord
from oya.llm.client import LLMClient
from oya.repo.git_repo import GitRepo
from oya.repo.repo_paths import RepoPaths
from oya.vectorstore.issues import IssuesStore
from oya.vectorstore.store import VectorStore


# =============================================================================
# Active Repo Context
# =============================================================================


def get_active_repo() -> Optional[RepoRecord]:
    """Get the currently active repository record.

    Reads from persisted storage in the repo registry.

    Returns:
        RepoRecord if a repo is active, None otherwise.
    """
    settings = load_settings()
    registry = RepoRegistry(settings.repos_db_path)
    try:
        stored_id = registry.get_setting("active_repo_id")
        if stored_id is None:
            return None

        try:
            repo_id = int(stored_id)
        except ValueError:
            return None

        return registry.get(repo_id)
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


def get_db() -> Database:
    """Get database connection with migrations applied for the active repo.

    Raises:
        HTTPException: 400 if no repository is active.
    """
    repo = get_active_repo()
    if repo is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No repository is active. Please select a repository first.",
        )

    if repo.id not in _db_instances:
        settings = load_settings()
        paths = RepoPaths(settings.data_dir, repo.local_path)
        paths.meta_dir.mkdir(parents=True, exist_ok=True)
        db = Database(paths.db_path)
        run_migrations(db)
        _db_instances[repo.id] = db
    return _db_instances[repo.id]


def _reset_db_instance() -> None:
    """Reset database instances (for testing only)."""
    global _db_instances
    for db in _db_instances.values():
        db.close()
    _db_instances.clear()


def invalidate_db_cache_for_repo(repo_id: int) -> None:
    """Invalidate the cached database connection for a specific repo.

    This MUST be called after operations that replace the database file,
    such as promote_staging_to_production(), to ensure subsequent requests
    get a fresh connection to the new database file.

    Without this, cached connections will hold stale file descriptors
    pointing to the deleted database, causing "attempt to write a readonly
    database" errors.

    Args:
        repo_id: The ID of the repo whose DB cache should be invalidated.
    """
    if repo_id in _db_instances:
        _db_instances[repo_id].close()
        del _db_instances[repo_id]


def reconnect_db(repo_id: int, paths: RepoPaths) -> Database:
    """Invalidate the stale DB connection and return a fresh one.

    Use after any operation that replaces or destroys the .oyawiki directory
    (full regeneration wipe, staging promotion). Ensures the directory
    structure exists, runs migrations, and caches the new connection.

    Args:
        repo_id: The ID of the repo whose DB needs reconnecting.
        paths: RepoPaths for the repo.

    Returns:
        A fresh Database connection with migrations applied.
    """
    invalidate_db_cache_for_repo(repo_id)
    paths.meta_dir.mkdir(parents=True, exist_ok=True)
    db = Database(paths.db_path)
    run_migrations(db)
    _db_instances[repo_id] = db
    return db


def get_repo() -> GitRepo:
    """Get repository wrapper for the active repo's source directory.

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
    paths = RepoPaths(settings.data_dir, repo.local_path)
    return GitRepo(paths.source)


def get_vectorstore() -> VectorStore:
    """Get vector store instance for the active repo.

    Raises:
        HTTPException: 400 if no repository is active.
    """
    repo = get_active_repo()
    if repo is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No repository is active. Please select a repository first.",
        )

    if repo.id not in _vectorstore_instances:
        settings = load_settings()
        paths = RepoPaths(settings.data_dir, repo.local_path)
        paths.chroma_dir.parent.mkdir(parents=True, exist_ok=True)
        _vectorstore_instances[repo.id] = VectorStore(paths.chroma_dir)
    return _vectorstore_instances[repo.id]


def _reset_vectorstore_instance() -> None:
    """Reset vectorstore instances (for testing only)."""
    global _vectorstore_instances
    _vectorstore_instances.clear()


_llm_instance: LLMClient | None = None


def get_llm() -> LLMClient:
    """Get LLM client instance.

    The LLM client is repo-agnostic. Logging is enabled per-repo when available.
    """
    global _llm_instance
    if _llm_instance is None:
        settings = get_settings()

        # Try to get log path from active repo
        log_path = None
        repo = get_active_repo()
        if repo is not None:
            paths = RepoPaths(settings.data_dir, repo.local_path)
            log_path = paths.oya_logs / "llm-queries.jsonl"

        _llm_instance = LLMClient(
            provider=settings.llm_provider,
            model=settings.llm_model,
            api_key=settings.llm_api_key,
            endpoint=settings.llm_endpoint,
            log_path=log_path,
        )
    return _llm_instance


def _reset_llm_instance() -> None:
    """Reset LLM client instance (for testing only)."""
    global _llm_instance
    _llm_instance = None


def get_issues_store() -> IssuesStore:
    """Get or create the issues vector store instance for the active repo.

    Raises:
        HTTPException: 400 if no repository is active.
    """
    repo = get_active_repo()
    if repo is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No repository is active. Please select a repository first.",
        )

    if repo.id not in _issues_store_instances:
        settings = load_settings()
        paths = RepoPaths(settings.data_dir, repo.local_path)
        persist_path = paths.oyawiki / "vectorstore"
        persist_path.mkdir(parents=True, exist_ok=True)
        _issues_store_instances[repo.id] = IssuesStore(persist_path)
    return _issues_store_instances[repo.id]


def _reset_issues_store_instance() -> None:
    """Reset issues store instances (for testing only)."""
    global _issues_store_instances
    for store in _issues_store_instances.values():
        store.close()
    _issues_store_instances.clear()
