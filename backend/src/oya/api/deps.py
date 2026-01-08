"""FastAPI dependency injection functions."""

from functools import lru_cache

from oya.config import Settings, load_settings
from oya.db.connection import Database
from oya.db.migrations import run_migrations
from oya.llm.client import LLMClient
from oya.repo.git_repo import GitRepo
from oya.vectorstore.store import VectorStore


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
        )
    return _llm_instance


def _reset_llm_instance() -> None:
    """Reset LLM client instance (for testing only)."""
    global _llm_instance
    _llm_instance = None
