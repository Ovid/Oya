"""FastAPI dependency injection functions."""

from functools import lru_cache

from oya.config import Settings, load_settings
from oya.db.connection import Database
from oya.db.migrations import run_migrations
from oya.repo.git_repo import GitRepo


@lru_cache
def get_settings() -> Settings:
    """Get cached application settings."""
    return load_settings()


_db_instance: Database | None = None


def get_db() -> Database:
    """Get database connection with migrations applied."""
    global _db_instance
    if _db_instance is None:
        settings = get_settings()
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
