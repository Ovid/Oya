# backend/tests/test_config.py
"""Configuration tests."""

import tempfile
from pathlib import Path

import pytest

from oya.config import Settings, load_settings


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


def test_settings_from_environment(temp_workspace: Path, monkeypatch):
    """Settings load from environment variables."""
    monkeypatch.setenv("WORKSPACE_PATH", str(temp_workspace))
    monkeypatch.setenv("ACTIVE_PROVIDER", "openai")
    monkeypatch.setenv("ACTIVE_MODEL", "gpt-4o")

    settings = load_settings()

    assert settings.workspace_path == temp_workspace
    assert settings.active_provider == "openai"
    assert settings.active_model == "gpt-4o"


def test_settings_defaults(temp_workspace: Path, monkeypatch):
    """Settings have sensible defaults."""
    monkeypatch.setenv("WORKSPACE_PATH", str(temp_workspace))
    monkeypatch.delenv("ACTIVE_PROVIDER", raising=False)
    monkeypatch.delenv("ACTIVE_MODEL", raising=False)
    # Clear API keys so auto-detection falls back to ollama
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    settings = load_settings()

    assert settings.active_provider == "ollama"  # Default fallback
    assert settings.active_model == "llama2"


def test_oyawiki_paths(temp_workspace: Path, monkeypatch):
    """Oyawiki subdirectory paths are computed correctly."""
    monkeypatch.setenv("WORKSPACE_PATH", str(temp_workspace))

    settings = load_settings()

    assert settings.oyawiki_path == temp_workspace / ".oyawiki"
    assert settings.wiki_path == temp_workspace / ".oyawiki" / "wiki"
    assert settings.notes_path == temp_workspace / ".oyawiki" / "notes"
    assert settings.db_path == temp_workspace / ".oyawiki" / "meta" / "oya.db"
    assert settings.index_path == temp_workspace / ".oyawiki" / "meta" / "index"
    assert settings.cache_path == temp_workspace / ".oyawiki" / "meta" / "cache"


def test_parallel_limit_defaults_for_ollama(temp_workspace: Path, monkeypatch):
    """Ollama provider gets conservative parallel limit (2) by default."""
    monkeypatch.setenv("WORKSPACE_PATH", str(temp_workspace))
    monkeypatch.setenv("ACTIVE_PROVIDER", "ollama")
    monkeypatch.delenv("PARALLEL_FILE_LIMIT", raising=False)

    settings = load_settings()

    assert settings.parallel_file_limit == 2


def test_parallel_limit_defaults_for_cloud_providers(temp_workspace: Path, monkeypatch):
    """Cloud providers get higher parallel limit (10) by default."""
    monkeypatch.setenv("WORKSPACE_PATH", str(temp_workspace))
    monkeypatch.delenv("PARALLEL_FILE_LIMIT", raising=False)

    for provider in ["openai", "anthropic", "google"]:
        load_settings.cache_clear()
        monkeypatch.setenv("ACTIVE_PROVIDER", provider)

        settings = load_settings()

        assert settings.parallel_file_limit == 10, f"Expected 10 for {provider}"


def test_parallel_limit_explicit_override(temp_workspace: Path, monkeypatch):
    """Explicit PARALLEL_FILE_LIMIT overrides provider-based default."""
    monkeypatch.setenv("WORKSPACE_PATH", str(temp_workspace))
    monkeypatch.setenv("ACTIVE_PROVIDER", "ollama")
    monkeypatch.setenv("PARALLEL_FILE_LIMIT", "5")

    settings = load_settings()

    assert settings.parallel_file_limit == 5
