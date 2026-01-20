# Config Centralization Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Centralize all configuration into a single `config.ini` file with schema-based validation, eliminating scattered constants files and fixing hardcoded values throughout the codebase.

**Architecture:** Replace `backend/src/oya/constants/` with a schema-driven config loader in `config.py`. The schema defines types, defaults, ranges, and descriptions. Config loads from: env vars (secrets) → `config.ini` (project settings) → schema defaults.

**Tech Stack:** Python 3.11+, configparser, dataclasses, pytest

---

## Phase 1: Config Schema and Loader

### Task 1.1: Create ConfigError Exception

**Files:**
- Modify: `backend/src/oya/config.py`

**Step 1: Add ConfigError class after imports**

Add at line 14 (after `import os`):

```python
class ConfigError(Exception):
    """Raised when configuration validation fails."""
    pass
```

**Step 2: Commit**

```bash
cd /Users/poecurt/projects/oya/.worktrees/config-centralization
git add backend/src/oya/config.py
git commit -m "feat(config): add ConfigError exception class"
```

---

### Task 1.2: Define CONFIG_SCHEMA

**Files:**
- Modify: `backend/src/oya/config.py`

**Step 1: Add schema definition after ConfigError class**

```python
# Schema: section -> key -> (type, default, min, max, description)
# min/max are None for non-numeric types or unbounded values
CONFIG_SCHEMA: dict[str, dict[str, tuple[type, any, any, any, str]]] = {
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
```

**Step 2: Commit**

```bash
git add backend/src/oya/config.py
git commit -m "feat(config): define CONFIG_SCHEMA with types, defaults, and ranges"
```

---

### Task 1.3: Create Section Dataclasses

**Files:**
- Modify: `backend/src/oya/config.py`

**Step 1: Add section dataclasses after CONFIG_SCHEMA**

```python
@dataclass(frozen=True)
class GenerationConfig:
    """Generation settings."""
    temperature: float
    tokens_per_char: float
    context_limit: int
    chunk_tokens: int
    chunk_overlap_lines: int
    progress_report_interval: int
    parallel_limit: int


@dataclass(frozen=True)
class FilesConfig:
    """File processing settings."""
    max_file_size_kb: int
    binary_check_bytes: int
    minified_line_length: int
    parallel_limit_local: int
    parallel_limit_cloud: int


@dataclass(frozen=True)
class AskConfig:
    """Chat/Q&A system settings."""
    max_context_tokens: int
    max_result_tokens: int
    high_confidence_threshold: float
    medium_confidence_threshold: float
    strong_match_threshold: float
    min_strong_matches: int
    graph_expansion_hops: int
    graph_mermaid_token_budget: int
    cgrag_max_passes: int
    cgrag_session_ttl_minutes: int
    cgrag_session_max_nodes: int
    cgrag_targeted_top_k: int


@dataclass(frozen=True)
class SearchConfig:
    """Search settings."""
    result_limit: int
    snippet_max_length: int
    dedup_hash_length: int


@dataclass(frozen=True)
class LLMConfig:
    """LLM client settings."""
    max_tokens: int
    default_temperature: float
    json_temperature: float


@dataclass(frozen=True)
class PathsConfig:
    """Path configuration."""
    wiki_dir: str
    staging_dir: str
    logs_dir: str
    ignore_file: str
```

**Step 2: Commit**

```bash
git add backend/src/oya/config.py
git commit -m "feat(config): add frozen dataclasses for each config section"
```

---

### Task 1.4: Create Config Loader Function

**Files:**
- Modify: `backend/src/oya/config.py`

**Step 1: Add imports at top of file**

```python
from configparser import ConfigParser
```

**Step 2: Add _load_section helper and load_config function**

```python
def _load_section(
    section_name: str,
    parser: ConfigParser,
    schema: dict[str, tuple[type, any, any, any, str]],
) -> dict[str, any]:
    """Load a config section with validation.

    Priority: environment variable > config file > schema default.
    Environment variables use format: OYA_{SECTION}_{KEY} (uppercase).
    """
    result = {}
    for key, (typ, default, min_val, max_val, _desc) in schema.items():
        # Check environment variable first (OYA_SECTION_KEY format)
        env_key = f"OYA_{section_name.upper()}_{key.upper()}"
        env_val = os.getenv(env_key)

        if env_val is not None:
            raw_value = env_val
            source = f"environment variable {env_key}"
        elif parser.has_option(section_name, key):
            raw_value = parser.get(section_name, key)
            source = f"config.ini [{section_name}].{key}"
        else:
            result[key] = default
            continue

        # Parse and validate
        try:
            if typ == bool:
                value = raw_value.lower() in ("true", "1", "yes", "on")
            elif typ == int:
                value = int(raw_value)
            elif typ == float:
                value = float(raw_value)
            else:
                value = raw_value
        except ValueError as e:
            raise ConfigError(
                f"Invalid value for {section_name}.{key}: expected {typ.__name__}, "
                f"got '{raw_value}' from {source}"
            ) from e

        # Range validation for numeric types
        if typ in (int, float):
            if min_val is not None and value < min_val:
                raise ConfigError(
                    f"Value for {section_name}.{key} is {value}, "
                    f"but minimum is {min_val} (from {source})"
                )
            if max_val is not None and value > max_val:
                raise ConfigError(
                    f"Value for {section_name}.{key} is {value}, "
                    f"but maximum is {max_val} (from {source})"
                )

        result[key] = value

    return result


def load_config(workspace_path: Path) -> "Config":
    """Load configuration from config.ini with schema validation.

    Args:
        workspace_path: Path to the workspace root containing config.ini.

    Returns:
        Config object with all settings loaded and validated.

    Raises:
        ConfigError: If any setting has an invalid type or out-of-range value.
    """
    parser = ConfigParser()
    config_file = workspace_path / "config.ini"
    if config_file.exists():
        parser.read(config_file)

    return Config(
        workspace_path=workspace_path,
        generation=GenerationConfig(**_load_section("generation", parser, CONFIG_SCHEMA["generation"])),
        files=FilesConfig(**_load_section("files", parser, CONFIG_SCHEMA["files"])),
        ask=AskConfig(**_load_section("ask", parser, CONFIG_SCHEMA["ask"])),
        search=SearchConfig(**_load_section("search", parser, CONFIG_SCHEMA["search"])),
        llm=LLMConfig(**_load_section("llm", parser, CONFIG_SCHEMA["llm"])),
        paths=PathsConfig(**_load_section("paths", parser, CONFIG_SCHEMA["paths"])),
    )
```

**Step 3: Commit**

```bash
git add backend/src/oya/config.py
git commit -m "feat(config): add load_config function with schema validation"
```

---

### Task 1.5: Create Config Dataclass with Computed Properties

**Files:**
- Modify: `backend/src/oya/config.py`

**Step 1: Add Config dataclass (this replaces the Settings class purpose for new code)**

```python
@dataclass(frozen=True)
class Config:
    """Complete application configuration.

    Contains all config sections plus computed path properties.
    """
    workspace_path: Path
    generation: GenerationConfig
    files: FilesConfig
    ask: AskConfig
    search: SearchConfig
    llm: LLMConfig
    paths: PathsConfig

    # Runtime settings (from environment, not config.ini)
    workspace_display_path: Optional[str] = None
    active_provider: str = "ollama"
    active_model: str = "llama2"
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    google_api_key: Optional[str] = None
    ollama_endpoint: str = "http://localhost:11434"

    @property
    def display_path(self) -> str:
        """Path to display to users."""
        return self.workspace_display_path or str(self.workspace_path)

    @property
    def oyawiki_path(self) -> Path:
        """Path to wiki directory."""
        return self.workspace_path / self.paths.wiki_dir

    @property
    def staging_path(self) -> Path:
        """Path to staging directory."""
        return self.workspace_path / self.paths.staging_dir

    @property
    def wiki_path(self) -> Path:
        """Path to wiki content subdirectory."""
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
        """Path to LLM query log file."""
        return self.workspace_path / self.paths.logs_dir / "llm-queries.jsonl"

    @property
    def ignore_path(self) -> Path:
        """Path to ignore file."""
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
        """Endpoint for LLM provider."""
        if self.active_provider == "ollama":
            return self.ollama_endpoint
        return None
```

**Step 2: Commit**

```bash
git add backend/src/oya/config.py
git commit -m "feat(config): add Config dataclass with computed path properties"
```

---

### Task 1.6: Update load_settings to Use New Config System

**Files:**
- Modify: `backend/src/oya/config.py`

**Step 1: Modify load_settings to delegate to load_config**

Replace the current `load_settings` function body to use the new config system while maintaining backward compatibility:

```python
@lru_cache(maxsize=1)
def load_settings() -> Config:
    """Load settings from environment variables and config.ini.

    Settings are cached for the lifetime of the application.
    Use load_settings.cache_clear() to reload settings.

    Returns:
        Config object populated from environment and config.ini.

    Raises:
        ValueError: If WORKSPACE_PATH is not set.
        ConfigError: If any config value is invalid.
    """
    workspace_path_str = os.getenv("WORKSPACE_PATH")
    if not workspace_path_str:
        raise ValueError("WORKSPACE_PATH environment variable must be set")

    workspace_path = Path(workspace_path_str)

    # Load config.ini settings
    config = load_config(workspace_path)

    # Get provider and model from environment, auto-detecting if not set
    active_provider = os.getenv("ACTIVE_PROVIDER")
    active_model = os.getenv("ACTIVE_MODEL")

    if not active_provider:
        detected_provider, detected_model = _detect_provider_from_keys()
        active_provider = detected_provider
        if not active_model:
            active_model = detected_model
    elif not active_model:
        provider_defaults = {
            "openai": "gpt-4o",
            "anthropic": "claude-3-5-sonnet-20241022",
            "google": "gemini-1.5-pro",
            "ollama": "llama2",
        }
        active_model = provider_defaults.get(active_provider, "llama2")

    # Return new Config object with runtime settings merged in
    return Config(
        workspace_path=workspace_path,
        generation=config.generation,
        files=config.files,
        ask=config.ask,
        search=config.search,
        llm=config.llm,
        paths=config.paths,
        workspace_display_path=os.getenv("WORKSPACE_DISPLAY_PATH"),
        active_provider=active_provider,
        active_model=active_model,
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
        google_api_key=os.getenv("GOOGLE_API_KEY"),
        ollama_endpoint=os.getenv("OLLAMA_ENDPOINT", "http://localhost:11434"),
    )
```

**Step 2: Remove the old Settings class (it's now replaced by Config)**

Delete the entire `Settings` class definition (lines 16-125 approximately).

**Step 3: Run tests to verify nothing broke**

```bash
cd /Users/poecurt/projects/oya/.worktrees/config-centralization/backend
source .venv/bin/activate
pytest tests/test_config.py -v
```

Expected: Some tests may fail due to API changes. We'll fix these in Phase 3.

**Step 4: Commit**

```bash
git add backend/src/oya/config.py
git commit -m "feat(config): integrate new Config system into load_settings"
```

---

## Phase 2: Create config.ini.example

### Task 2.1: Create Documented config.ini.example

**Files:**
- Create: `config.ini.example`

**Step 1: Write the example file**

```ini
# Oya Configuration File
# =====================
# Copy this file to config.ini and customize as needed.
# All values shown are defaults - delete lines to use defaults.
# Environment variables override config.ini values.
# Env var format: OYA_{SECTION}_{KEY} (e.g., OYA_GENERATION_TEMPERATURE)

[generation]
# LLM temperature for documentation synthesis (0.0-1.0)
# Lower = more deterministic, higher = more creative
temperature = 0.3

# Token estimation multiplier (chars * this = estimated tokens)
tokens_per_char = 0.25

# Maximum tokens to send to LLM in one request
context_limit = 100000

# Target size in tokens when splitting large files
chunk_tokens = 1000

# Lines of overlap between chunks to preserve context
chunk_overlap_lines = 5

# How often to emit progress updates (1 = every file)
progress_report_interval = 1

# Concurrent LLM calls during generation
parallel_limit = 10

[files]
# Skip files larger than this (KB)
max_file_size_kb = 500

# Bytes to read when detecting binary files
binary_check_bytes = 1024

# Average line length above this = minified/generated file
minified_line_length = 500

# Parallel file limit for local LLM (Ollama)
parallel_limit_local = 2

# Parallel file limit for cloud LLM (OpenAI, Anthropic, Google)
parallel_limit_cloud = 10

# Settings for the chat/Q&A system
[ask]
# Total context budget for building prompts (tokens)
max_context_tokens = 6000

# Maximum tokens from any single document
max_result_tokens = 1500

# Vector distance threshold for "high" confidence (0.0-1.0, lower = stricter)
high_confidence_threshold = 0.3

# Vector distance threshold for "medium" confidence
medium_confidence_threshold = 0.6

# Threshold for counting a match as "strong"
strong_match_threshold = 0.5

# Minimum strong matches needed for high confidence
min_strong_matches = 3

# Graph traversal depth for context expansion
graph_expansion_hops = 2

# Token budget for mermaid diagram generation
graph_mermaid_token_budget = 500

# Maximum retrieval passes in CGRAG mode
cgrag_max_passes = 3

# Session timeout for CGRAG (minutes)
cgrag_session_ttl_minutes = 30

# Maximum nodes tracked in CGRAG session
cgrag_session_max_nodes = 50

# Top-k for targeted retrieval in CGRAG
cgrag_targeted_top_k = 3

[search]
# Default number of results to return
result_limit = 10

# Maximum characters in result snippets
snippet_max_length = 200

# Characters to hash for deduplication
dedup_hash_length = 500

[llm]
# Maximum tokens in LLM response
max_tokens = 8192

# Default temperature for general LLM calls
default_temperature = 0.7

# Temperature for structured/JSON output (lower = more consistent)
json_temperature = 0.3

[paths]
# Directory for generated wiki content
wiki_dir = .oyawiki

# Staging directory during generation (deleted on completion)
staging_dir = .oyawiki-building

# Directory for LLM query logs
logs_dir = .oya-logs

# File specifying patterns to exclude from generation
ignore_file = .oyaignore
```

**Step 2: Commit**

```bash
git add config.ini.example
git commit -m "docs: add config.ini.example with all settings documented"
```

---

## Phase 3: Rewrite Tests

### Task 3.1: Write Type and Range Validation Tests

**Files:**
- Modify: `backend/tests/test_config.py`

**Step 1: Replace entire test file with new tests**

```python
# backend/tests/test_config.py
"""Configuration tests.

Tests verify behavior (types, ranges, loading) not specific values.
"""

import tempfile
from pathlib import Path

import pytest

from oya.config import (
    CONFIG_SCHEMA,
    Config,
    ConfigError,
    load_config,
    load_settings,
)


@pytest.fixture
def temp_workspace():
    """Create temporary workspace directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir) / "workspace"
        workspace.mkdir()
        yield workspace


@pytest.fixture(autouse=True)
def clear_settings_cache():
    """Clear the load_settings cache before each test."""
    load_settings.cache_clear()
    yield
    load_settings.cache_clear()


def write_config(workspace: Path, content: str) -> None:
    """Write a config.ini file to the workspace."""
    (workspace / "config.ini").write_text(content)


# =============================================================================
# Type Validation Tests
# =============================================================================

def test_all_settings_have_correct_types(temp_workspace: Path):
    """Every setting matches its declared type from schema."""
    config = load_config(temp_workspace)

    for section_name, keys in CONFIG_SCHEMA.items():
        section = getattr(config, section_name)
        for key, (expected_type, *_) in keys.items():
            value = getattr(section, key)
            assert isinstance(value, expected_type), (
                f"{section_name}.{key}: expected {expected_type.__name__}, "
                f"got {type(value).__name__}"
            )


def test_invalid_type_raises_clear_error(temp_workspace: Path):
    """Non-numeric value for int setting gives helpful message."""
    write_config(temp_workspace, "[generation]\ncontext_limit = not_a_number")

    with pytest.raises(ConfigError) as exc_info:
        load_config(temp_workspace)

    assert "generation.context_limit" in str(exc_info.value)
    assert "int" in str(exc_info.value)


def test_invalid_float_raises_clear_error(temp_workspace: Path):
    """Non-numeric value for float setting gives helpful message."""
    write_config(temp_workspace, "[generation]\ntemperature = very_hot")

    with pytest.raises(ConfigError) as exc_info:
        load_config(temp_workspace)

    assert "generation.temperature" in str(exc_info.value)
    assert "float" in str(exc_info.value)


# =============================================================================
# Range Validation Tests
# =============================================================================

def test_numeric_settings_in_valid_ranges(temp_workspace: Path):
    """Default values are within their declared ranges."""
    config = load_config(temp_workspace)

    # Temperatures between 0 and their max
    assert 0.0 <= config.generation.temperature <= 1.0
    assert 0.0 <= config.llm.default_temperature <= 2.0
    assert 0.0 <= config.llm.json_temperature <= 1.0

    # Positive limits
    assert config.files.max_file_size_kb > 0
    assert config.search.result_limit > 0
    assert config.llm.max_tokens > 0

    # Confidence thresholds are ordered correctly
    assert config.ask.high_confidence_threshold < config.ask.medium_confidence_threshold


def test_value_below_minimum_raises_error(temp_workspace: Path):
    """Value below declared minimum raises ConfigError."""
    write_config(temp_workspace, "[generation]\ntemperature = -0.5")

    with pytest.raises(ConfigError) as exc_info:
        load_config(temp_workspace)

    assert "generation.temperature" in str(exc_info.value)
    assert "minimum" in str(exc_info.value)


def test_value_above_maximum_raises_error(temp_workspace: Path):
    """Value above declared maximum raises ConfigError."""
    write_config(temp_workspace, "[generation]\ntemperature = 5.0")

    with pytest.raises(ConfigError) as exc_info:
        load_config(temp_workspace)

    assert "generation.temperature" in str(exc_info.value)
    assert "maximum" in str(exc_info.value)


# =============================================================================
# Loading Behavior Tests
# =============================================================================

def test_missing_config_uses_defaults(temp_workspace: Path):
    """No config.ini file? All defaults load successfully."""
    config = load_config(temp_workspace)

    assert config is not None
    assert config.workspace_path == temp_workspace
    # All sections should exist with default values
    assert config.generation is not None
    assert config.files is not None
    assert config.ask is not None
    assert config.search is not None
    assert config.llm is not None
    assert config.paths is not None


def test_partial_config_merges_with_defaults(temp_workspace: Path):
    """Config with only [generation] still has [ask] defaults."""
    write_config(temp_workspace, "[generation]\ntemperature = 0.5")

    config = load_config(temp_workspace)

    assert config.generation.temperature == 0.5
    # Other sections should have defaults
    assert config.ask.max_context_tokens > 0
    assert config.files.max_file_size_kb > 0


def test_env_overrides_config_file(temp_workspace: Path, monkeypatch):
    """Environment variables take precedence over config.ini."""
    write_config(temp_workspace, "[files]\nmax_file_size_kb = 100")
    monkeypatch.setenv("OYA_FILES_MAX_FILE_SIZE_KB", "200")

    config = load_config(temp_workspace)

    assert config.files.max_file_size_kb == 200


def test_empty_config_file_uses_defaults(temp_workspace: Path):
    """Empty config.ini file loads all defaults."""
    write_config(temp_workspace, "")

    config = load_config(temp_workspace)

    assert config is not None


# =============================================================================
# Path Property Tests
# =============================================================================

def test_computed_paths_use_config_values(temp_workspace: Path):
    """Computed path properties use paths section values."""
    write_config(temp_workspace, "[paths]\nwiki_dir = .custom-wiki")

    config = load_config(temp_workspace)

    assert config.oyawiki_path == temp_workspace / ".custom-wiki"
    assert config.wiki_path == temp_workspace / ".custom-wiki" / "wiki"


def test_default_paths_are_correct(temp_workspace: Path):
    """Default path values produce expected paths."""
    config = load_config(temp_workspace)

    assert config.paths.wiki_dir == ".oyawiki"
    assert config.paths.staging_dir == ".oyawiki-building"
    assert config.paths.logs_dir == ".oya-logs"
    assert config.paths.ignore_file == ".oyaignore"


# =============================================================================
# Integration Tests (load_settings)
# =============================================================================

def test_load_settings_from_environment(temp_workspace: Path, monkeypatch):
    """load_settings integrates config.ini with env vars."""
    monkeypatch.setenv("WORKSPACE_PATH", str(temp_workspace))
    monkeypatch.setenv("ACTIVE_PROVIDER", "openai")
    monkeypatch.setenv("ACTIVE_MODEL", "gpt-4o")

    settings = load_settings()

    assert settings.workspace_path == temp_workspace
    assert settings.active_provider == "openai"
    assert settings.active_model == "gpt-4o"


def test_load_settings_auto_detects_provider(temp_workspace: Path, monkeypatch):
    """Provider auto-detection from API keys works."""
    monkeypatch.setenv("WORKSPACE_PATH", str(temp_workspace))
    monkeypatch.delenv("ACTIVE_PROVIDER", raising=False)
    monkeypatch.delenv("ACTIVE_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    settings = load_settings()

    # Falls back to ollama when no API keys present
    assert settings.active_provider == "ollama"


def test_load_settings_requires_workspace_path(monkeypatch):
    """load_settings raises ValueError without WORKSPACE_PATH."""
    monkeypatch.delenv("WORKSPACE_PATH", raising=False)

    with pytest.raises(ValueError, match="WORKSPACE_PATH"):
        load_settings()
```

**Step 2: Run tests to verify they pass**

```bash
pytest tests/test_config.py -v
```

Expected: All tests pass (or we'll iterate on the implementation).

**Step 3: Commit**

```bash
git add backend/tests/test_config.py
git commit -m "test(config): rewrite tests for type/range/behavior validation"
```

---

## Phase 4: Fix Hardcoded References

### Task 4.1: Fix file_filter.py Hardcoded Values

**Files:**
- Modify: `backend/src/oya/repo/file_filter.py`

**Step 1: Read the file to understand current structure**

The file has hardcoded `.oyaignore` at line 103 and uses hardcoded path patterns.

**Step 2: Update imports and use settings**

At top of file, add:
```python
from oya.config import load_settings
```

**Step 3: Replace hardcoded `.oyaignore` with settings**

Find line 103:
```python
oyaignore = repo_path / ".oyaignore"
```

Replace with:
```python
settings = load_settings()
oyaignore = settings.ignore_path
```

**Step 4: Update default max_file_size_kb parameter**

Find function signature with `max_file_size_kb: int = 500`.
Change to:
```python
max_file_size_kb: int | None = None
```

Then in the function body, at the start:
```python
if max_file_size_kb is None:
    settings = load_settings()
    max_file_size_kb = settings.files.max_file_size_kb
```

**Step 5: Run tests**

```bash
pytest tests/test_file_filter.py -v
```

**Step 6: Commit**

```bash
git add backend/src/oya/repo/file_filter.py
git commit -m "refactor(file_filter): use settings for paths and size limits"
```

---

### Task 4.2: Fix repos.py Hardcoded Paths

**Files:**
- Modify: `backend/src/oya/api/routers/repos.py`

**Step 1: Audit all hardcoded paths in the file**

Lines with hardcoded paths:
- Line 107: `meta_path = workspace_path / ".oyawiki" / "meta"`
- Line 115: `wiki_path=workspace_path / ".oyawiki" / "wiki"`
- Line 261: `oyaignore_path = workspace_path / ".oyaignore"`

**Step 2: Replace with settings properties**

Each instance should use `settings.oyawiki_path`, `settings.wiki_path`, `settings.ignore_path`, etc.

**Step 3: Run tests**

```bash
pytest tests/test_repos_api.py -v
```

**Step 4: Commit**

```bash
git add backend/src/oya/api/routers/repos.py
git commit -m "refactor(repos): use settings for all paths"
```

---

### Task 4.3: Fix deps.py Hardcoded Paths

**Files:**
- Modify: `backend/src/oya/api/deps.py`

**Step 1: Find and fix line 160**

```python
persist_path = settings.workspace_path / ".oyawiki" / "vectorstore"
```

Replace with:
```python
persist_path = settings.oyawiki_path / "vectorstore"
```

**Step 2: Run tests**

```bash
pytest -v
```

**Step 3: Commit**

```bash
git add backend/src/oya/api/deps.py
git commit -m "refactor(deps): use settings.oyawiki_path"
```

---

### Task 4.4: Fix qa.py Hardcoded Paths

**Files:**
- Modify: `backend/src/oya/api/routers/qa.py`

**Step 1: Find and fix line 32**

```python
graph_dir = workspace / ".oyawiki" / "graph"
```

Replace with:
```python
graph_dir = settings.oyawiki_path / "graph"
```

**Step 2: Run tests**

```bash
pytest tests/test_qa_api.py -v
```

**Step 3: Commit**

```bash
git add backend/src/oya/api/routers/qa.py
git commit -m "refactor(qa): use settings.oyawiki_path"
```

---

### Task 4.5: Fix staging.py Hardcoded Paths

**Files:**
- Modify: `backend/src/oya/generation/staging.py`

**Step 1: Find and fix line 66**

```python
staging_path = workspace_path / ".oyawiki-building"
```

Replace with:
```python
from oya.config import load_settings
settings = load_settings()
staging_path = settings.staging_path
```

**Step 2: Run tests**

```bash
pytest -v
```

**Step 3: Commit**

```bash
git add backend/src/oya/generation/staging.py
git commit -m "refactor(staging): use settings.staging_path"
```

---

### Task 4.6: Fix workspace.py Hardcoded Paths

**Files:**
- Modify: `backend/src/oya/workspace.py`

**Step 1: Find and fix line 42**

```python
oyawiki_path = workspace_path / ".oyawiki"
```

This should use settings:
```python
from oya.config import load_settings
settings = load_settings()
oyawiki_path = settings.oyawiki_path
```

**Step 2: Run tests**

```bash
pytest -v
```

**Step 3: Commit**

```bash
git add backend/src/oya/workspace.py
git commit -m "refactor(workspace): use settings.oyawiki_path"
```

---

### Task 4.7: Fix All Remaining Hardcoded Paths

**Files:**
- Multiple files identified in audit

**Step 1: Use grep to find any remaining hardcoded paths**

```bash
git grep '\.oyawiki' -- '*.py' | grep -v test | grep -v '__pycache__'
git grep '\.oyaignore' -- '*.py' | grep -v test | grep -v '__pycache__'
git grep '\.oya-logs' -- '*.py' | grep -v test | grep -v '__pycache__'
```

**Step 2: Fix each remaining instance to use settings**

**Step 3: Run full test suite**

```bash
pytest -v
```

**Step 4: Commit**

```bash
git add -A
git commit -m "refactor: replace all remaining hardcoded paths with settings"
```

---

## Phase 5: Delete Constants and Update Imports

### Task 5.1: Update All Imports from constants to config

**Files:**
- All files that import from `oya.constants`

**Step 1: Find all imports**

```bash
git grep 'from oya.constants import' -- '*.py'
git grep 'from oya.constants.' -- '*.py'
```

**Step 2: Update each file**

Replace imports like:
```python
from oya.constants import MAX_CONTEXT_TOKENS, SYNTHESIS_TEMPERATURE
```

With accessing via settings:
```python
from oya.config import load_settings
# Then use settings.ask.max_context_tokens, settings.generation.temperature
```

**Step 3: Run tests**

```bash
pytest -v
```

**Step 4: Commit**

```bash
git add -A
git commit -m "refactor: update all imports from constants to config"
```

---

### Task 5.2: Delete Constants Directory

**Files:**
- Delete: `backend/src/oya/constants/` (entire directory)

**Step 1: Remove the directory**

```bash
rm -rf backend/src/oya/constants/
```

**Step 2: Run tests to ensure nothing breaks**

```bash
pytest -v
```

**Step 3: Commit**

```bash
git add -A
git commit -m "refactor: remove constants directory (now in config schema)"
```

---

## Phase 6: Documentation

### Task 6.1: Create CONTRIBUTING.md

**Files:**
- Create: `CONTRIBUTING.md`

**Step 1: Write the file**

```markdown
# Contributing to Oya

Thank you for your interest in contributing to Oya! This document provides guidelines for contributing to the project.

## Code of Conduct

Please read and follow our [Code of Conduct](CODE_OF_CONDUCT.md). We are committed to providing a welcoming and inclusive environment.

## Development Setup

### Backend (Python)

```bash
cd backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Frontend (TypeScript/React)

```bash
cd frontend
npm install
```

### Running Tests

```bash
# Backend
cd backend && pytest

# Frontend
cd frontend && npm test
```

## Configuration Rules

**Never hardcode configurable values.** All tunable parameters must come from `config.ini` via the settings object.

### Do:
```python
from oya.config import load_settings
settings = load_settings()
max_size = settings.files.max_file_size_kb
```

### Don't:
```python
max_size = 500  # Hardcoded!
path = workspace / ".oyawiki"  # Hardcoded path!
```

### Adding New Config Values

1. Add to `CONFIG_SCHEMA` in `backend/src/oya/config.py`
2. Add to the appropriate section dataclass
3. Document in `config.ini.example`
4. Write tests verifying type and range

## Code Style

### Backend (Python)
- Python 3.11+
- Format with `ruff format`
- Lint with `ruff check`
- Line length: 100 characters
- Type hints required for public APIs

### Frontend (TypeScript)
- TypeScript strict mode
- ESLint for linting
- Tailwind CSS for styling

## Pull Request Process

1. Create a feature branch from `main`
2. Write tests for new functionality
3. Ensure all tests pass: `pytest` and `npm test`
4. Update documentation if needed
5. Submit PR with clear description of changes

## Testing Guidelines

- Write tests before implementation (TDD preferred)
- Tests should verify behavior, not implementation details
- Config tests verify types and ranges, not specific values
- Use property-based testing (hypothesis) for complex logic

## Questions?

Open an issue for questions about contributing.
```

**Step 2: Commit**

```bash
git add CONTRIBUTING.md
git commit -m "docs: add CONTRIBUTING.md with development guidelines"
```

---

### Task 6.2: Create CODE_OF_CONDUCT.md

**Files:**
- Create: `CODE_OF_CONDUCT.md`

**Step 1: Write the file**

```markdown
# Code of Conduct

## Our Commitment

We are committed to providing a welcoming, inclusive, and harassment-free environment for everyone, regardless of age, body size, visible or invisible disability, ethnicity, sex characteristics, gender identity and expression, level of experience, education, socio-economic status, nationality, personal appearance, race, caste, color, religion, or sexual identity and orientation.

## Our Standards

### Expected Behavior

- Using welcoming and inclusive language
- Being respectful of differing viewpoints and experiences
- Gracefully accepting constructive criticism
- Focusing on what is best for the community
- Showing empathy towards other community members

### Unacceptable Behavior

The following behaviors are **strictly prohibited**:

- **Bigotry of any kind** - including racism, sexism, homophobia, transphobia, ableism, or discrimination based on religion, nationality, or any other characteristic
- **Harassment** - public or private, including offensive comments, deliberate intimidation, stalking, or unwelcome attention
- **Offensive language** - slurs, derogatory terms, or language intended to demean or exclude
- **Personal attacks** - including insults, trolling, or inflammatory comments
- **Sexual harassment** - unwelcome sexual attention, imagery, or advances
- **Doxxing** - publishing private information without consent
- **Advocating for or encouraging** any of the above behaviors

## Enforcement

### Zero Tolerance Policy

**We have zero tolerance for bigotry, discrimination, or harassment.**

Violations will result in **immediate and permanent removal** from the project, including:
- Ban from all project spaces (issues, PRs, discussions)
- Removal of any contributed code at maintainer discretion
- Report to relevant platforms (GitHub, etc.)

### Reporting

Report violations to the project maintainers. All reports will be reviewed promptly and kept confidential.

When reporting, please include:
- Your contact information
- Names/usernames of those involved
- Description of what happened
- Any supporting evidence (screenshots, links)

### Scope

This Code of Conduct applies to all project spaces, including:
- GitHub repository (issues, PRs, discussions, code review)
- Project communication channels
- Events or meetups related to the project
- Representation of the project in public spaces

## Attribution

This Code of Conduct is adapted from the [Contributor Covenant](https://www.contributor-covenant.org), version 2.1, with additional enforcement provisions.
```

**Step 2: Commit**

```bash
git add CODE_OF_CONDUCT.md
git commit -m "docs: add CODE_OF_CONDUCT.md with zero tolerance policy"
```

---

### Task 6.3: Update CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

**Step 1: Add configuration section after "Key Patterns"**

Add this section:

```markdown
### Configuration Rules

**All tunable values must come from `config.ini` via the settings object.** Never hardcode paths like `.oyawiki` or numeric thresholds.

```python
# Correct - use settings
from oya.config import load_settings
settings = load_settings()
wiki_path = settings.wiki_path
max_size = settings.files.max_file_size_kb

# Wrong - hardcoded values
wiki_path = workspace / ".oyawiki" / "wiki"  # Never do this!
max_size = 500  # Never do this!
```

**Adding new config values:**
1. Add to `CONFIG_SCHEMA` in `backend/src/oya/config.py` with type, default, min, max, description
2. Add field to the appropriate section dataclass (GenerationConfig, FilesConfig, etc.)
3. Document in `config.ini.example` with comment explaining the setting
4. Write tests verifying type and range validation
```

**Step 2: Update the "Configuration Constants" section to reflect new structure**

Replace the old constants section with:

```markdown
### Configuration

All configuration is centralized in `backend/src/oya/config.py`:
- `CONFIG_SCHEMA` defines all settings with types, defaults, ranges, and descriptions
- Section dataclasses (`GenerationConfig`, `FilesConfig`, `AskConfig`, etc.) provide typed access
- `load_settings()` loads from environment variables and `config.ini`
- `config.ini.example` documents all available settings

**Frontend:** `frontend/src/config/` contains TypeScript config (layout, timing, storage keys).
```

**Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md with configuration rules"
```

---

## Phase 7: Final Verification

### Task 7.1: Run Full Test Suite

**Step 1: Run backend tests**

```bash
cd /Users/poecurt/projects/oya/.worktrees/config-centralization/backend
source .venv/bin/activate
pytest -v
```

Expected: All tests pass.

**Step 2: Run frontend tests**

```bash
cd /Users/poecurt/projects/oya/.worktrees/config-centralization/frontend
npm test
```

Expected: All tests pass.

**Step 3: Run linters**

```bash
cd /Users/poecurt/projects/oya/.worktrees/config-centralization/backend
ruff check .
ruff format --check .
```

**Step 4: Verify no hardcoded paths remain**

```bash
git grep '\.oyawiki' -- '*.py' | grep -v test | grep -v config.py | grep -v '__pycache__'
```

Expected: No results (all should use settings).

---

### Task 7.2: Final Commit and Summary

**Step 1: If any fixes needed, commit them**

```bash
git add -A
git commit -m "fix: address final issues from verification"
```

**Step 2: Create summary commit if needed**

Review git log to ensure all changes are properly committed and organized.

---

## Summary of Changes

| File | Change |
|------|--------|
| `backend/src/oya/config.py` | New schema, section dataclasses, load_config function |
| `backend/src/oya/constants/` | Deleted entirely |
| `backend/tests/test_config.py` | Rewritten for behavior testing |
| `config.ini.example` | New documented template |
| `CONTRIBUTING.md` | New contributor guidelines |
| `CODE_OF_CONDUCT.md` | New code of conduct |
| `CLAUDE.md` | Updated with config rules |
| Multiple source files | Updated to use settings instead of hardcoded values |
