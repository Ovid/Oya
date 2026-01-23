# backend/src/oya/config.py
"""Configuration system for Oya backend.

This module handles loading settings from environment variables and INI files,
providing sensible defaults, and computing derived paths for
the .oyawiki directory structure.
"""

from configparser import ConfigParser
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional
import os


# =============================================================================
# Task 1.1: ConfigError Exception
# =============================================================================


class ConfigError(Exception):
    """Raised when configuration validation fails."""

    pass


# =============================================================================
# Task 1.2: CONFIG_SCHEMA
# =============================================================================

# Schema: section -> key -> (type, default, min, max, description)
CONFIG_SCHEMA: dict[str, dict[str, tuple[type, Any, Any, Any, str]]] = {
    "generation": {
        "temperature": (float, 0.3, 0.0, 1.0, "LLM temperature for synthesis"),
        "tokens_per_char": (float, 0.25, 0.1, 1.0, "Token estimation multiplier"),
        "context_limit": (int, 100_000, 1000, None, "Max tokens sent to LLM"),
        "chunk_tokens": (int, 1000, 100, 10000, "Target chunk size for large files"),
        "chunk_overlap_lines": (int, 5, 0, 50, "Overlap between chunks"),
        "progress_report_interval": (int, 1, 1, 100, "Progress update frequency"),
        "parallel_limit": (int, 10, 1, 50, "Concurrent LLM calls"),
    },
    "files": {
        "max_file_size_kb": (int, 500, 1, 10000, "File size limit in KB"),
        "binary_check_bytes": (int, 1024, 64, 8192, "Bytes checked for binary detection"),
        "minified_line_length": (int, 500, 100, 5000, "Threshold for minified file detection"),
        "parallel_limit_local": (int, 2, 1, 10, "Parallel files for local LLM"),
        "parallel_limit_cloud": (int, 10, 1, 50, "Parallel files for cloud LLM"),
    },
    "ask": {  # Chat/Q&A system settings
        "max_context_tokens": (int, 6000, 500, 50000, "Total context budget"),
        "max_result_tokens": (int, 1500, 100, 10000, "Per-document token limit"),
        "high_confidence_threshold": (float, 0.3, 0.0, 1.0, "Threshold for high confidence"),
        "medium_confidence_threshold": (float, 0.6, 0.0, 1.0, "Threshold for medium confidence"),
        "strong_match_threshold": (float, 0.5, 0.0, 1.0, "Threshold for strong match"),
        "min_strong_matches": (int, 3, 1, 20, "Minimum strong matches for high confidence"),
        "graph_expansion_hops": (int, 2, 0, 5, "Graph traversal depth"),
        "graph_expansion_confidence_threshold": (
            float,
            0.5,
            0.0,
            1.0,
            "Confidence threshold for graph expansion",
        ),
        "graph_mermaid_token_budget": (int, 500, 100, 2000, "Token budget for mermaid diagrams"),
        "cgrag_max_passes": (int, 3, 1, 10, "Maximum CGRAG retrieval passes"),
        "cgrag_session_ttl_minutes": (int, 30, 5, 120, "CGRAG session timeout"),
        "cgrag_session_max_nodes": (int, 50, 10, 200, "Max nodes in CGRAG session"),
        "cgrag_targeted_top_k": (int, 3, 1, 20, "Top-k for targeted retrieval"),
    },
    "search": {
        "result_limit": (int, 10, 1, 100, "Default search results to return"),
        "snippet_max_length": (int, 200, 50, 1000, "Max snippet length in results"),
        "dedup_hash_length": (int, 500, 100, 2000, "Characters to hash for deduplication"),
    },
    "llm": {
        "max_tokens": (int, 8192, 256, 32768, "Max response tokens"),
        "default_temperature": (float, 0.7, 0.0, 2.0, "Default LLM temperature"),
        "json_temperature": (float, 0.3, 0.0, 1.0, "Temperature for structured output"),
    },
    "paths": {
        "wiki_dir": (str, ".oyawiki", None, None, "Wiki directory name"),
        "staging_dir": (str, ".oyawiki-building", None, None, "Staging directory name"),
        "logs_dir": (str, ".oya-logs", None, None, "Logs directory name"),
        "ignore_file": (str, ".oyaignore", None, None, "Ignore file name"),
    },
}


# =============================================================================
# Task 1.3: Section Dataclasses
# =============================================================================


@dataclass(frozen=True)
class GenerationConfig:
    """Generation-related configuration."""

    temperature: float
    tokens_per_char: float
    context_limit: int
    chunk_tokens: int
    chunk_overlap_lines: int
    progress_report_interval: int
    parallel_limit: int


@dataclass(frozen=True)
class FilesConfig:
    """File processing configuration."""

    max_file_size_kb: int
    binary_check_bytes: int
    minified_line_length: int
    parallel_limit_local: int
    parallel_limit_cloud: int


@dataclass(frozen=True)
class AskConfig:
    """Q&A/Chat system configuration."""

    max_context_tokens: int
    max_result_tokens: int
    high_confidence_threshold: float
    medium_confidence_threshold: float
    strong_match_threshold: float
    min_strong_matches: int
    graph_expansion_hops: int
    graph_expansion_confidence_threshold: float
    graph_mermaid_token_budget: int
    cgrag_max_passes: int
    cgrag_session_ttl_minutes: int
    cgrag_session_max_nodes: int
    cgrag_targeted_top_k: int


@dataclass(frozen=True)
class SearchConfig:
    """Search configuration."""

    result_limit: int
    snippet_max_length: int
    dedup_hash_length: int


@dataclass(frozen=True)
class LLMConfig:
    """LLM client configuration."""

    max_tokens: int
    default_temperature: float
    json_temperature: float


@dataclass(frozen=True)
class PathsConfig:
    """Path names configuration."""

    wiki_dir: str
    staging_dir: str
    logs_dir: str
    ignore_file: str


# =============================================================================
# Task 1.4: Config Loader Function
# =============================================================================


def _load_section(
    parser: ConfigParser, section: str, schema: dict[str, tuple[type, Any, Any, Any, str]]
) -> dict[str, Any]:
    """Load and validate a configuration section.

    Args:
        parser: ConfigParser instance with loaded config
        section: Section name to load
        schema: Schema definition for the section

    Returns:
        Dictionary of validated configuration values

    Raises:
        ConfigError: If validation fails
    """
    result = {}

    for key, (typ, default, min_val, max_val, _) in schema.items():
        # Get value from parser or use default
        if parser.has_option(section, key):
            raw_value = parser.get(section, key)
            value: bool | int | float | str
            try:
                if typ is bool:
                    value = raw_value.lower() in ("true", "1", "yes", "on")
                elif typ is int:
                    value = int(raw_value)
                elif typ is float:
                    value = float(raw_value)
                else:
                    value = raw_value
            except ValueError as e:
                raise ConfigError(
                    f"Invalid value for [{section}].{key}: {raw_value!r} (expected {typ.__name__})"
                ) from e
        else:
            value = default

        # Validate range for numeric types
        if typ in (int, float) and value is not None:
            if min_val is not None and value < min_val:
                raise ConfigError(
                    f"Value for [{section}].{key} is {value}, but minimum is {min_val}"
                )
            if max_val is not None and value > max_val:
                raise ConfigError(
                    f"Value for [{section}].{key} is {value}, but maximum is {max_val}"
                )

        result[key] = value

    return result


def _load_config(config_path: Optional[Path] = None) -> "Config":
    """Load configuration from an INI file (internal use only).

    This is an internal function called by load_settings(). It returns a Config
    with a placeholder workspace_path that load_settings() will replace with
    the actual workspace path from WORKSPACE_PATH environment variable.

    Args:
        config_path: Path to config file. If None, uses defaults from schema.

    Returns:
        Config object with all sections populated (workspace_path is placeholder)

    Raises:
        ConfigError: If validation fails
    """
    parser = ConfigParser()

    if config_path and config_path.exists():
        parser.read(config_path)

    # Load each section
    generation_values = _load_section(parser, "generation", CONFIG_SCHEMA["generation"])
    files_values = _load_section(parser, "files", CONFIG_SCHEMA["files"])
    ask_values = _load_section(parser, "ask", CONFIG_SCHEMA["ask"])
    search_values = _load_section(parser, "search", CONFIG_SCHEMA["search"])
    llm_values = _load_section(parser, "llm", CONFIG_SCHEMA["llm"])
    paths_values = _load_section(parser, "paths", CONFIG_SCHEMA["paths"])

    # Create section dataclasses
    generation = GenerationConfig(**generation_values)
    files = FilesConfig(**files_values)
    ask = AskConfig(**ask_values)
    search = SearchConfig(**search_values)
    llm = LLMConfig(**llm_values)
    paths = PathsConfig(**paths_values)

    # Create Config with placeholder workspace_path (will be set by load_settings)
    return Config(
        workspace_path=Path("."),  # Placeholder, will be overwritten
        generation=generation,
        files=files,
        ask=ask,
        search=search,
        llm=llm,
        paths=paths,
    )


# =============================================================================
# Task 1.5: Config Dataclass with Computed Properties
# =============================================================================


@dataclass(frozen=True)
class Config:
    """Complete application configuration.

    This replaces the old Settings class while maintaining backward compatibility
    with existing code that accesses settings properties.
    """

    # Core settings
    workspace_path: Path
    data_dir: Path = None  # type: ignore[assignment]  # Set in __post_init__ if None
    workspace_display_path: Optional[str] = None
    active_provider: str = "ollama"
    active_model: str = "llama2"
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    google_api_key: Optional[str] = None
    ollama_endpoint: str = "http://localhost:11434"

    # Legacy fields for backward compatibility
    max_file_size_kb: int = 500
    parallel_file_limit: int = 10
    chunk_size: int = 4096

    # Section configs - defaults set in __post_init__, type: ignore needed because
    # frozen dataclass doesn't allow proper initialization pattern
    generation: GenerationConfig = None  # type: ignore[assignment]
    files: FilesConfig = None  # type: ignore[assignment]
    ask: AskConfig = None  # type: ignore[assignment]
    search: SearchConfig = None  # type: ignore[assignment]
    llm: LLMConfig = None  # type: ignore[assignment]
    paths: PathsConfig = None  # type: ignore[assignment]

    def __post_init__(self):
        """Initialize section configs with defaults if not provided."""
        # Since frozen=True, we need to use object.__setattr__
        if self.data_dir is None:
            object.__setattr__(self, "data_dir", Path.home() / ".oya")
        if self.generation is None:
            generation_values = {
                key: default for key, (_, default, _, _, _) in CONFIG_SCHEMA["generation"].items()
            }
            object.__setattr__(self, "generation", GenerationConfig(**generation_values))
        if self.files is None:
            files_values = {
                key: default for key, (_, default, _, _, _) in CONFIG_SCHEMA["files"].items()
            }
            object.__setattr__(self, "files", FilesConfig(**files_values))
        if self.ask is None:
            ask_values = {
                key: default for key, (_, default, _, _, _) in CONFIG_SCHEMA["ask"].items()
            }
            object.__setattr__(self, "ask", AskConfig(**ask_values))
        if self.search is None:
            search_values = {
                key: default for key, (_, default, _, _, _) in CONFIG_SCHEMA["search"].items()
            }
            object.__setattr__(self, "search", SearchConfig(**search_values))
        if self.llm is None:
            llm_values = {
                key: default for key, (_, default, _, _, _) in CONFIG_SCHEMA["llm"].items()
            }
            object.__setattr__(self, "llm", LLMConfig(**llm_values))
        if self.paths is None:
            paths_values = {
                key: default for key, (_, default, _, _, _) in CONFIG_SCHEMA["paths"].items()
            }
            object.__setattr__(self, "paths", PathsConfig(**paths_values))

    @property
    def repos_db_path(self) -> Path:
        """Path to the multi-repo SQLite database."""
        return self.data_dir / "repos.db"

    @property
    def wikis_dir(self) -> Path:
        """Path to the directory containing all wiki data."""
        return self.data_dir / "wikis"

    @property
    def display_path(self) -> str:
        """Path to display to users (uses workspace_display_path if set)."""
        return self.workspace_display_path or str(self.workspace_path)

    @property
    def oyawiki_path(self) -> Path:
        """Path to .oyawiki directory."""
        return self.workspace_path / self.paths.wiki_dir

    @property
    def staging_path(self) -> Path:
        """Path to .oyawiki-building staging directory."""
        return self.workspace_path / self.paths.staging_dir

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
    def llm_log_path(self) -> Path:
        """Path to LLM query log file.

        Stored outside .oyawiki so logs aren't affected by staging/promotion.
        """
        return self.workspace_path / self.paths.logs_dir / "llm-queries.jsonl"

    @property
    def ignore_path(self) -> Path:
        """Path to .oyaignore file."""
        return self.workspace_path / self.paths.ignore_file

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


# =============================================================================
# Task 1.6: Update load_settings to Use New Config System
# =============================================================================


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
def load_settings() -> Config:
    """Load settings from environment variables and config file.

    Settings are cached for the lifetime of the application.
    Use load_settings.cache_clear() to reload settings.

    Returns:
        Config object populated from environment variables and config file.

    Raises:
        ValueError: If WORKSPACE_PATH is not set.
    """
    workspace_path_str = os.getenv("WORKSPACE_PATH")
    if not workspace_path_str:
        raise ValueError("WORKSPACE_PATH environment variable must be set")

    workspace_path = Path(workspace_path_str)

    # Load config from file if it exists (stored in workspace root, not .oyawiki)
    config_file = workspace_path / "config.ini"
    try:
        config_exists = config_file.exists()
    except PermissionError:
        config_exists = False
    base_config = _load_config(config_file if config_exists else None)

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
        parallel_file_limit = base_config.files.parallel_limit_local
    else:
        parallel_file_limit = base_config.files.parallel_limit_cloud

    # Get max_file_size_kb from env or config
    max_file_size_kb = int(os.getenv("MAX_FILE_SIZE_KB", str(base_config.files.max_file_size_kb)))

    # Get OYA_DATA_DIR from env, defaulting to ~/.oya
    data_dir_str = os.getenv("OYA_DATA_DIR")
    data_dir = Path(data_dir_str) if data_dir_str else Path.home() / ".oya"

    return Config(
        workspace_path=workspace_path,
        data_dir=data_dir,
        workspace_display_path=os.getenv("WORKSPACE_DISPLAY_PATH"),
        active_provider=active_provider,
        active_model=active_model,
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
        google_api_key=os.getenv("GOOGLE_API_KEY"),
        ollama_endpoint=os.getenv("OLLAMA_ENDPOINT", "http://localhost:11434"),
        max_file_size_kb=max_file_size_kb,
        parallel_file_limit=parallel_file_limit,
        chunk_size=int(os.getenv("CHUNK_SIZE", "4096")),
        generation=base_config.generation,
        files=base_config.files,
        ask=base_config.ask,
        search=base_config.search,
        llm=base_config.llm,
        paths=base_config.paths,
    )


# =============================================================================
# Backward Compatibility
# =============================================================================

# Alias for legacy code that imports Settings instead of Config
Settings = Config
