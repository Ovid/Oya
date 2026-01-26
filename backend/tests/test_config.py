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
    _load_config,
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


def write_config(workspace: Path, content: str) -> Path:
    """Write a config.ini file to the workspace and return the path."""
    config_path = workspace / "config.ini"
    config_path.write_text(content)
    return config_path


# =============================================================================
# Type Validation Tests
# =============================================================================


def test_all_settings_have_correct_types(temp_workspace: Path):
    """Every setting matches its declared type from schema."""
    config = _load_config(None)  # Load with defaults only

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
    config_path = write_config(temp_workspace, "[generation]\ncontext_limit = not_a_number")

    with pytest.raises(ConfigError) as exc_info:
        _load_config(config_path)

    assert "generation" in str(exc_info.value)
    assert "context_limit" in str(exc_info.value)
    assert "int" in str(exc_info.value)


def test_invalid_float_raises_clear_error(temp_workspace: Path):
    """Non-numeric value for float setting gives helpful message."""
    config_path = write_config(temp_workspace, "[generation]\ntemperature = very_hot")

    with pytest.raises(ConfigError) as exc_info:
        _load_config(config_path)

    assert "generation" in str(exc_info.value)
    assert "temperature" in str(exc_info.value)
    assert "float" in str(exc_info.value)


# =============================================================================
# Range Validation Tests
# =============================================================================


def test_numeric_settings_in_valid_ranges(temp_workspace: Path):
    """Default values are within their declared ranges."""
    config = _load_config(None)  # Load with defaults only

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
    config_path = write_config(temp_workspace, "[generation]\ntemperature = -0.5")

    with pytest.raises(ConfigError) as exc_info:
        _load_config(config_path)

    assert "generation" in str(exc_info.value)
    assert "temperature" in str(exc_info.value)
    assert "minimum" in str(exc_info.value)


def test_value_above_maximum_raises_error(temp_workspace: Path):
    """Value above declared maximum raises ConfigError."""
    config_path = write_config(temp_workspace, "[generation]\ntemperature = 5.0")

    with pytest.raises(ConfigError) as exc_info:
        _load_config(config_path)

    assert "generation" in str(exc_info.value)
    assert "temperature" in str(exc_info.value)
    assert "maximum" in str(exc_info.value)


# =============================================================================
# Loading Behavior Tests
# =============================================================================


def test_missing_config_uses_defaults(temp_workspace: Path):
    """No config.ini file? All defaults load successfully."""
    config = _load_config(None)  # No config file

    assert config is not None
    # All sections should exist with default values
    assert config.generation is not None
    assert config.files is not None
    assert config.ask is not None
    assert config.search is not None
    assert config.llm is not None
    assert config.paths is not None


def test_partial_config_merges_with_defaults(temp_workspace: Path):
    """Config with only [generation] still has [ask] defaults."""
    config_path = write_config(temp_workspace, "[generation]\ntemperature = 0.5")

    config = _load_config(config_path)

    assert config.generation.temperature == 0.5
    # Other sections should have defaults
    assert config.ask.max_context_tokens > 0
    assert config.files.max_file_size_kb > 0


def test_empty_config_file_uses_defaults(temp_workspace: Path):
    """Empty config.ini file loads all defaults."""
    config_path = write_config(temp_workspace, "")

    config = _load_config(config_path)

    assert config is not None


# =============================================================================
# Path Property Tests
# =============================================================================


def test_computed_paths_use_config_values(temp_workspace: Path):
    """Computed path properties use paths section values."""
    config_path = write_config(temp_workspace, "[paths]\nwiki_dir = .custom-wiki")

    config = _load_config(config_path)
    # Manually set workspace_path since _load_config uses a placeholder
    # We need to create a new Config with proper workspace_path
    config_with_workspace = Config(
        workspace_path=temp_workspace,
        generation=config.generation,
        files=config.files,
        ask=config.ask,
        search=config.search,
        llm=config.llm,
        paths=config.paths,
    )

    assert config_with_workspace.oyawiki_path == temp_workspace / ".custom-wiki"
    assert config_with_workspace.wiki_path == temp_workspace / ".custom-wiki" / "wiki"


def test_default_paths_are_correct(temp_workspace: Path):
    """Default path values produce expected paths."""
    config = _load_config(None)

    assert config.paths.wiki_dir == ".oyawiki"
    assert config.paths.staging_dir == ".oyawiki-building"
    assert config.paths.logs_dir == ".oya-logs"
    assert config.paths.ignore_file == ".oyaignore"


# =============================================================================
# Integration Tests (load_settings)
# =============================================================================


def test_load_settings_from_environment(monkeypatch):
    """load_settings integrates with env vars."""
    monkeypatch.setenv("ACTIVE_PROVIDER", "openai")
    monkeypatch.setenv("ACTIVE_MODEL", "gpt-4o")

    settings = load_settings()

    # workspace_path is always None
    assert settings.workspace_path is None
    assert settings.active_provider == "openai"
    assert settings.active_model == "gpt-4o"


def test_load_settings_auto_detects_provider(monkeypatch):
    """Provider auto-detection from API keys works."""
    monkeypatch.delenv("ACTIVE_PROVIDER", raising=False)
    monkeypatch.delenv("ACTIVE_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    settings = load_settings()

    # Falls back to ollama when no API keys present
    assert settings.active_provider == "ollama"


def test_load_settings_workspace_path_always_none(monkeypatch):
    """load_settings always returns workspace_path=None."""
    load_settings.cache_clear()

    settings = load_settings()

    # workspace_path is always None - use active repo context from deps.py
    assert settings.workspace_path is None
    # Other settings should still work
    assert settings.active_provider in ("ollama", "openai", "anthropic", "google")
    assert settings.data_dir is not None


# =============================================================================
# OYA_DATA_DIR Configuration Tests
# =============================================================================


def test_oya_data_dir_default(monkeypatch):
    """OYA_DATA_DIR defaults to ~/.oya when not set."""
    monkeypatch.delenv("OYA_DATA_DIR", raising=False)
    load_settings.cache_clear()
    settings = load_settings()
    expected = Path.home() / ".oya"
    assert settings.data_dir == expected


def test_oya_data_dir_from_env(monkeypatch, temp_workspace):
    """OYA_DATA_DIR can be set via environment variable."""
    custom_dir = temp_workspace / "custom-oya"
    monkeypatch.setenv("OYA_DATA_DIR", str(custom_dir))
    load_settings.cache_clear()
    settings = load_settings()
    assert settings.data_dir == custom_dir


def test_repos_db_path(monkeypatch, temp_workspace):
    """repos.db path is under data_dir."""
    custom_dir = temp_workspace / "oya"
    monkeypatch.setenv("OYA_DATA_DIR", str(custom_dir))
    load_settings.cache_clear()
    settings = load_settings()
    assert settings.repos_db_path == custom_dir / "repos.db"


def test_wikis_dir_path(monkeypatch, temp_workspace):
    """wikis directory path is under data_dir."""
    custom_dir = temp_workspace / "oya"
    monkeypatch.setenv("OYA_DATA_DIR", str(custom_dir))
    load_settings.cache_clear()
    settings = load_settings()
    assert settings.wikis_dir == custom_dir / "wikis"


# =============================================================================
# CGRAG Classification Config Tests
# =============================================================================


def test_cgrag_classification_config():
    """Should have classification config settings."""
    from oya.config import load_settings

    load_settings.cache_clear()

    settings = load_settings()

    assert hasattr(settings.ask, "classification_model")
    assert settings.ask.classification_model == "haiku"
    assert hasattr(settings.ask, "use_mode_routing")
    assert settings.ask.use_mode_routing is True
    assert hasattr(settings.ask, "use_code_index")
    assert settings.ask.use_code_index is True
    assert hasattr(settings.ask, "use_source_fetching")
    assert settings.ask.use_source_fetching is True
