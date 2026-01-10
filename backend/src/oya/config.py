# backend/src/oya/config.py
"""Configuration system for Oya backend.

This module handles loading settings from environment variables,
providing sensible defaults, and computing derived paths for
the .oyawiki directory structure.
"""

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Optional
import os


@dataclass(frozen=True)
class Settings:
    """Application settings loaded from environment.

    Attributes:
        workspace_path: Root path to the mounted repository/workspace
        workspace_display_path: Human-readable path to display (for Docker environments)
        active_provider: LLM provider to use (openai, anthropic, google, ollama)
        active_model: Model identifier for the active provider
        openai_api_key: OpenAI API key (optional)
        anthropic_api_key: Anthropic API key (optional)
        google_api_key: Google AI API key (optional)
        ollama_endpoint: Ollama server endpoint
        max_file_size_kb: Maximum file size to process in KB
        parallel_file_limit: Maximum files to process in parallel
        chunk_size: Chunk size for text processing
    """

    workspace_path: Path
    workspace_display_path: Optional[str] = None
    active_provider: str = "ollama"
    active_model: str = "llama2"
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    google_api_key: Optional[str] = None
    ollama_endpoint: str = "http://localhost:11434"
    max_file_size_kb: int = 1024
    parallel_file_limit: int = 10
    chunk_size: int = 4096

    @property
    def display_path(self) -> str:
        """Path to display to users (uses workspace_display_path if set, otherwise workspace_path)."""
        return self.workspace_display_path or str(self.workspace_path)

    @property
    def oyawiki_path(self) -> Path:
        """Path to .oyawiki directory."""
        return self.workspace_path / ".oyawiki"

    @property
    def wiki_path(self) -> Path:
        """Path to wiki subdirectory."""
        return self.oyawiki_path / "wiki"

    @property
    def notes_path(self) -> Path:
        """Path to notes subdirectory."""
        return self.oyawiki_path / "notes"

    @property
    def db_path(self) -> Path:
        """Path to SQLite database file."""
        return self.oyawiki_path / "meta" / "oya.db"

    @property
    def index_path(self) -> Path:
        """Path to search index directory."""
        return self.oyawiki_path / "meta" / "index"

    @property
    def cache_path(self) -> Path:
        """Path to cache directory."""
        return self.oyawiki_path / "meta" / "cache"

    @property
    def chroma_path(self) -> Path:
        """Path to ChromaDB vector store directory."""
        return self.oyawiki_path / "meta" / "chroma"

    @property
    def llm_provider(self) -> str:
        """LLM provider name."""
        return self.active_provider

    @property
    def llm_model(self) -> str:
        """LLM model name."""
        return self.active_model

    @property
    def llm_api_key(self) -> Optional[str]:
        """API key for the active LLM provider."""
        provider_keys = {
            "openai": self.openai_api_key,
            "anthropic": self.anthropic_api_key,
            "google": self.google_api_key,
        }
        return provider_keys.get(self.active_provider)

    @property
    def llm_endpoint(self) -> Optional[str]:
        """Endpoint for LLM provider (mainly for Ollama)."""
        if self.active_provider == "ollama":
            return self.ollama_endpoint
        return None


def _detect_provider_from_keys() -> tuple[str, str]:
    """Auto-detect provider from available API keys.

    Returns:
        Tuple of (provider, model) based on available keys.
        Falls back to ollama if no keys are found.
    """
    if os.getenv("OPENAI_API_KEY"):
        return ("openai", "gpt-4o")
    if os.getenv("ANTHROPIC_API_KEY"):
        return ("anthropic", "claude-3-5-sonnet-20241022")
    if os.getenv("GOOGLE_API_KEY"):
        return ("google", "gemini-1.5-pro")
    return ("ollama", "llama2")


@lru_cache(maxsize=1)
def load_settings() -> Settings:
    """Load settings from environment variables.

    Settings are cached for the lifetime of the application.
    Use load_settings.cache_clear() to reload settings.

    Returns:
        Settings object populated from environment variables.

    Raises:
        ValueError: If WORKSPACE_PATH is not set.
    """
    workspace_path_str = os.getenv("WORKSPACE_PATH")
    if not workspace_path_str:
        raise ValueError("WORKSPACE_PATH environment variable must be set")

    workspace_path = Path(workspace_path_str)

    # Get provider and model, auto-detecting if not explicitly set
    active_provider = os.getenv("ACTIVE_PROVIDER")
    active_model = os.getenv("ACTIVE_MODEL")

    if not active_provider:
        detected_provider, detected_model = _detect_provider_from_keys()
        active_provider = detected_provider
        if not active_model:
            active_model = detected_model
    elif not active_model:
        # Provider set but model not - use default for that provider
        provider_defaults = {
            "openai": "gpt-4o",
            "anthropic": "claude-3-5-sonnet-20241022",
            "google": "gemini-1.5-pro",
            "ollama": "llama2",
        }
        active_model = provider_defaults.get(active_provider, "llama2")

    # Determine parallel limit based on provider
    # Local models (Ollama) can't handle many concurrent requests efficiently
    # Cloud APIs (OpenAI, Anthropic, Google) handle concurrency well
    parallel_limit_env = os.getenv("PARALLEL_FILE_LIMIT")
    if parallel_limit_env:
        parallel_file_limit = int(parallel_limit_env)
    elif active_provider == "ollama":
        parallel_file_limit = 2  # Safe default for local models
    else:
        parallel_file_limit = 10  # Cloud APIs handle concurrency well

    return Settings(
        workspace_path=workspace_path,
        workspace_display_path=os.getenv("WORKSPACE_DISPLAY_PATH"),
        active_provider=active_provider,
        active_model=active_model,
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
        google_api_key=os.getenv("GOOGLE_API_KEY"),
        ollama_endpoint=os.getenv("OLLAMA_ENDPOINT", "http://localhost:11434"),
        max_file_size_kb=int(os.getenv("MAX_FILE_SIZE_KB", "1024")),
        parallel_file_limit=parallel_file_limit,
        chunk_size=int(os.getenv("CHUNK_SIZE", "4096")),
    )
