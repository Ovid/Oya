# Configuration Centralization Design

**Date:** 2026-01-20
**Branch:** ovid/fix-config-usage
**Status:** Approved

## Problem Statement

1. **Tests hard-code expected values** - Tests like `assert settings.parallel_file_limit == 2` break when config values change. Tests should verify types and ranges, not specific values.

2. **Config values aren't used consistently** - `git grep '.oyawiki'` reveals 50+ places where paths are hardcoded instead of using the settings object.

3. **No central config file** - Settings are scattered across `constants/` files and environment variables with no single source of truth.

## Design

### Configuration Architecture

```
workspace/
├── .env                    # Secrets only (API keys) - gitignored
├── config.ini              # Project-specific settings - committed
├── config.ini.example      # Template with all options documented
├── .oyaignore              # File exclusions - committed
└── .oyawiki/               # Generated content - deletable
```

**Key principle:** `config.ini` lives in the workspace root (not `.oyawiki/`) so that `.oyawiki/` remains deletable at will.

### Layered Loading (priority high→low)

1. Environment variables (`.env` or shell) - for secrets and CI overrides
2. `config.ini` in workspace root - project-specific tuning
3. Built-in defaults in the schema - always available fallback

### What Goes Where

| Location | Contents | Committed? |
|----------|----------|------------|
| `.env` | `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`, `ACTIVE_PROVIDER`, `ACTIVE_MODEL`, `OLLAMA_ENDPOINT` | No |
| `config.ini` | All tuning parameters (temperatures, thresholds, limits, paths) | Yes |
| Schema/code | Default values, type definitions, valid ranges | Yes |

**Key Principle:** Deleting `config.ini` should never break Oya - it falls back to sensible defaults. Deleting `.env` means no LLM access until keys are provided.

---

## config.ini Structure

```ini
[generation]
temperature = 0.3
tokens_per_char = 0.25
context_limit = 100000
chunk_tokens = 1000
chunk_overlap_lines = 5
progress_report_interval = 1

[files]
max_file_size_kb = 500
binary_check_bytes = 1024
minified_line_length = 500
parallel_limit_local = 2
parallel_limit_cloud = 10

# Settings for the chat/Q&A system
[ask]
max_context_tokens = 6000
max_result_tokens = 1500
high_confidence_threshold = 0.3
medium_confidence_threshold = 0.6
strong_match_threshold = 0.5
min_strong_matches = 3
graph_expansion_hops = 2
graph_mermaid_token_budget = 500
cgrag_max_passes = 3
cgrag_session_ttl_minutes = 30
cgrag_session_max_nodes = 50

[search]
result_limit = 10
snippet_max_length = 200
dedup_hash_length = 500

[llm]
max_tokens = 8192
default_temperature = 0.7
json_temperature = 0.3

[paths]
wiki_dir = .oyawiki
staging_dir = .oyawiki-building
logs_dir = .oya-logs
ignore_file = .oyaignore
```

**Notes:**
- `config.ini.example` will include comments explaining each setting and valid ranges
- The `[paths]` section allows customization (e.g., someone might want `.docs/` instead of `.oyawiki/`)
- Issue detection keywords remain in code - that's logic, not configuration

---

## Config Schema and Loader

### Eliminating constants/ files

The current structure:
```
backend/src/oya/constants/
├── __init__.py
├── files.py
├── generation.py
├── issues.py
├── llm.py
├── qa.py
└── search.py
```

Will be replaced by a single schema definition in `backend/src/oya/config.py`:

```python
from configparser import ConfigParser
from dataclasses import dataclass
from pathlib import Path
from typing import Any

CONFIG_SCHEMA: dict[str, dict[str, tuple[type, Any, str]]] = {
    # section -> {key -> (type, default, description)}
    "generation": {
        "temperature": (float, 0.3, "LLM temperature for synthesis (0.0-1.0)"),
        "context_limit": (int, 100_000, "Max tokens sent to LLM"),
        # ... etc
    },
    "ask": {
        "max_context_tokens": (int, 6000, "Total context budget for chat"),
        # ... etc
    },
}

def load_config(workspace: Path) -> "Config":
    """Load config with layered precedence: env > config.ini > defaults."""
    parser = ConfigParser()
    config_file = workspace / "config.ini"
    if config_file.exists():
        parser.read(config_file)

    # Build Config object using schema defaults + file overrides
    # Validate types and ranges during loading
    ...
```

**Validation happens at load time** - invalid types or out-of-range values raise clear errors with the setting name and expected range.

**Migration:** All imports like `from oya.constants import MAX_CONTEXT_TOKENS` will change to `settings.ask.max_context_tokens` (accessing the loaded config object).

---

## Testing Strategy

Tests verify *behavior* (types valid, ranges sensible, loading works, errors clear) not *specific values*.

```python
# test_config.py

def test_all_settings_have_correct_types(loaded_config):
    """Every setting matches its declared type."""
    for section, keys in CONFIG_SCHEMA.items():
        for key, (expected_type, _, _) in keys.items():
            value = getattr(getattr(loaded_config, section), key)
            assert isinstance(value, expected_type), f"{section}.{key}"

def test_numeric_settings_in_valid_ranges(loaded_config):
    """Temperatures 0-1, limits positive, thresholds sensible."""
    assert 0.0 <= loaded_config.generation.temperature <= 1.0
    assert loaded_config.files.max_file_size_kb > 0
    assert loaded_config.ask.high_confidence_threshold < loaded_config.ask.medium_confidence_threshold

def test_invalid_type_raises_clear_error(temp_workspace):
    """Non-numeric value for int setting gives helpful message."""
    write_config(temp_workspace, "[generation]\ncontext_limit = not_a_number")
    with pytest.raises(ConfigError, match="generation.context_limit"):
        load_config(temp_workspace)

def test_missing_config_uses_defaults(temp_workspace):
    """No config.ini file? All defaults load successfully."""
    config = load_config(temp_workspace)
    assert config is not None  # Loads without error

def test_partial_config_merges_with_defaults(temp_workspace):
    """Config with only [generation] still has [ask] defaults."""
    write_config(temp_workspace, "[generation]\ntemperature = 0.5")
    config = load_config(temp_workspace)
    assert config.ask.max_context_tokens > 0  # Default loaded

def test_env_overrides_config_file(temp_workspace, monkeypatch):
    """Environment variables take precedence."""
    write_config(temp_workspace, "[files]\nmax_file_size_kb = 100")
    monkeypatch.setenv("OYA_FILES_MAX_FILE_SIZE_KB", "200")
    config = load_config(temp_workspace)
    assert config.files.max_file_size_kb == 200
```

---

## Code Migration

### Fixing hardcoded values throughout the codebase

Full audit required using:
- `git grep '\.oyawiki'` - all wiki path references
- `git grep '\.oyaignore'` - all ignore file references
- `git grep '\.oya-logs'` - all log path references
- Review of numeric literals that match config values

**Migration pattern:**

```python
# BEFORE (scattered throughout codebase)
wiki_path = repo_path / ".oyawiki" / "wiki"
staging = repo_path / ".oyawiki-building"
oyaignore = repo_path / ".oyaignore"

# AFTER (using loaded config)
wiki_path = settings.paths.wiki_path
staging = settings.paths.staging_path
oyaignore = settings.paths.ignore_path
```

**Settings access pattern:**

```python
# In modules that need config
from oya.config import get_settings

def some_function():
    settings = get_settings()  # Cached, same instance
    if file_size > settings.files.max_file_size_kb * 1024:
        ...
```

**Computed properties** remain on the Settings object for convenience:
- `settings.paths.wiki_path` → `workspace / wiki_dir / "wiki"`
- `settings.paths.db_path` → `workspace / wiki_dir / "meta" / "oya.db"`

---

## Documentation

### CONTRIBUTING.md

Will cover:
- Development setup (backend venv, frontend npm)
- Running tests
- Code style (ruff, eslint, TypeScript strict)
- **Configuration rules:** "Never hardcode values that belong in config.ini. Use `settings.*` for all tunable parameters."
- PR process
- Where to ask questions

### CODE_OF_CONDUCT.md

Based on Contributor Covenant with strong enforcement:
- Zero tolerance for bigotry, discrimination, harassment
- Inclusive language requirements
- Clear examples of unacceptable behavior
- Enforcement: immediate removal from project for violations
- Reporting mechanism

### CLAUDE.md update

Add section reinforcing:

> "All tunable values must come from `config.ini` via the settings object. Never hardcode paths like `.oyawiki` or numeric thresholds. If you need a configurable value, add it to the schema in `config.py`."

---

## File Changes Summary

### New files to create
- `config.ini.example` - documented template with all settings
- `CONTRIBUTING.md` - development guide with config rules
- `CODE_OF_CONDUCT.md` - zero-tolerance policy

### Files to modify
- `backend/src/oya/config.py` - add schema, new loader, validation
- `backend/tests/test_config.py` - rewrite for type/range/behavior testing
- `CLAUDE.md` - add config enforcement section
- All files with hardcoded paths/values (full audit during implementation)

### Files to delete
- `backend/src/oya/constants/generation.py`
- `backend/src/oya/constants/files.py`
- `backend/src/oya/constants/qa.py`
- `backend/src/oya/constants/llm.py`
- `backend/src/oya/constants/search.py`
- `backend/src/oya/constants/__init__.py`
- `backend/src/oya/constants/issues.py`

---

## Implementation Order

1. Create schema in `config.py` with all defaults
2. Create `config.ini.example`
3. Update tests to new approach
4. Audit and fix all hardcoded references
5. Delete old constants files
6. Update imports throughout codebase
7. Create CONTRIBUTING.md and CODE_OF_CONDUCT.md
8. Update CLAUDE.md
