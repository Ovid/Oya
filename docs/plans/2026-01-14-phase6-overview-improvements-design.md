# Phase 6 Overview Improvements Design

**Date:** 2026-01-14

**Problem:** The Overview page generation relies heavily on README content (which is often outdated) and lacks code-derived information that would help users understand the project.

**Solution:** Enrich SynthesisMap with entry points, tech stack, code metrics, and layer interactions—all derived from code analysis. Use this richer context to generate more accurate, useful overview pages.

---

## Architecture Overview

**Key principle:** Compute once in synthesis, reuse everywhere. All new data is added to `SynthesisMap` during Phase 4, then used by Phase 5 (Architecture) and Phase 6 (Overview).

**New SynthesisMap fields:**
1. `entry_points` - Discovered CLI commands, API routes, main functions
2. `tech_stack` - Categorized libraries by language
3. `metrics` - File counts and LOC by layer
4. `layer_interactions` - LLM-generated description of how layers communicate

**Data flow:**
```
Phase 3 (Files) → FileSummaries with external_deps, layer classifications
        ↓
Phase 4 (Synthesis) → Enhanced SynthesisMap with all new fields
        ↓
Phase 5/6 → Use enriched context for Architecture and Overview pages
```

---

## Data Model Changes

**Location:** `backend/src/oya/generation/summaries.py`

**New dataclasses:**

```python
@dataclass
class EntryPointInfo:
    name: str           # e.g., "main", "create_user"
    entry_type: str     # "cli_command", "api_route", "main_function"
    file: str           # Path to file containing entry point
    description: str    # Route path, CLI command name, etc.

@dataclass
class CodeMetrics:
    total_files: int
    files_by_layer: dict[str, int]      # layer name -> count
    lines_by_layer: dict[str, int]      # layer name -> LOC
    total_lines: int
```

**Updated SynthesisMap:**

```python
@dataclass
class SynthesisMap:
    # Existing fields
    layers: dict[str, LayerInfo]
    key_components: list[ComponentInfo]
    dependency_graph: dict[str, list[str]]
    project_summary: str

    # New fields
    entry_points: list[EntryPointInfo] = field(default_factory=list)
    tech_stack: dict[str, dict[str, list[str]]] = field(default_factory=dict)
    metrics: CodeMetrics | None = None
    layer_interactions: str = ""
```

---

## Technology Stack Detection

**Location:** Config file at `backend/src/oya/constants/techstack.yaml`

**Format:** Maps library names to language, category, and display name:

```yaml
libraries:
  # Python
  fastapi:
    language: python
    category: web_framework
    display: FastAPI
  sqlalchemy:
    language: python
    category: database
    display: SQLAlchemy

  # JavaScript/TypeScript
  express:
    language: javascript
    category: web_framework
    display: Express
  prisma:
    language: javascript
    category: database
    display: Prisma

  # Perl
  mojolicious:
    language: perl
    category: web_framework
    display: Mojolicious
  dancer:
    language: perl
    category: web_framework
    display: Dancer
  dbi:
    language: perl
    category: database
    display: DBI
  dbix-class:
    language: perl
    category: database
    display: DBIx::Class
  moose:
    language: perl
    category: object_system
    display: Moose
  test-more:
    language: perl
    category: testing
    display: Test::More

  # Go, Rust, Java, Ruby, etc...
```

**Aggregation function** in new module `backend/src/oya/generation/techstack.py`:

```python
def detect_tech_stack(file_summaries: list[FileSummary]) -> dict[str, dict[str, list[str]]]:
    """Aggregate external_deps into categorized tech stack by language.

    Returns: {
        "python": {"web_framework": ["FastAPI"], "database": ["SQLAlchemy"]},
        "javascript": {"testing": ["Jest", "Vitest"]}
    }
    """
```

The mapping covers common libraries across Python, JavaScript/TypeScript, Perl, Go, Rust, Java, Ruby, and other ecosystems. Unknown libraries are simply not categorized.

---

## Code Metrics Collection

**Location:** `backend/src/oya/generation/metrics.py`

```python
def compute_code_metrics(
    file_summaries: list[FileSummary],
    file_contents: dict[str, str],
) -> CodeMetrics:
    """Compute code metrics from analyzed files.

    Args:
        file_summaries: Summaries with layer classifications
        file_contents: Raw file contents for LOC counting

    Returns:
        CodeMetrics with file counts and LOC by layer
    """
    files_by_layer: dict[str, int] = defaultdict(int)
    lines_by_layer: dict[str, int] = defaultdict(int)

    for summary in file_summaries:
        layer = summary.layer
        files_by_layer[layer] += 1

        content = file_contents.get(summary.file_path, "")
        loc = len(content.splitlines())
        lines_by_layer[layer] += loc

    return CodeMetrics(
        total_files=len(file_summaries),
        files_by_layer=dict(files_by_layer),
        lines_by_layer=dict(lines_by_layer),
        total_lines=sum(lines_by_layer.values()),
    )
```

Simple, deterministic, uses data we already collect.

---

## Entry Point Integration

**Reuse existing WorkflowDiscovery** from `workflows.py`:

```python
from oya.generation.workflows import WorkflowDiscovery

# During synthesis phase
discovery = WorkflowDiscovery()
entry_points = discovery.find_entry_points(all_symbols)

# Convert to EntryPointInfo for SynthesisMap
entry_point_infos = [
    EntryPointInfo(
        name=ep.name,
        entry_type=ep.symbol_type.value,
        file=ep.metadata.get("file", ""),
        description=_extract_description(ep),
    )
    for ep in entry_points
]

synthesis_map.entry_points = entry_point_infos
```

**Helper for descriptions:**

```python
def _extract_description(symbol: ParsedSymbol) -> str:
    """Extract route path or CLI command from decorators/metadata."""
    # For routes: "@app.get('/users')" -> "/users"
    # For CLI: "@click.command('init')" -> "init"
    # For main: "" (no special description)
```

---

## Synthesis LLM Prompt Changes

**Location:** `backend/src/oya/generation/prompts.py`

Extend `SYNTHESIS_TEMPLATE` to request `layer_interactions`:

```python
SYNTHESIS_TEMPLATE = PromptTemplate(
    """Synthesize the following file and directory summaries...

## File Summaries
{file_summaries}

## Directory Summaries
{directory_summaries}

---

Produce a JSON response with this structure:

```json
{{
  "key_components": [...],
  "dependency_graph": {{...}},
  "project_summary": "...",
  "layer_interactions": "A 2-4 sentence description of how the architectural layers communicate. Describe the flow of data and control between layers."
}}
```

Guidelines:
...existing guidelines...

4. **layer_interactions**: Describe how code flows between layers. Focus on patterns used (dependency injection, direct calls, events) and direction of dependencies. Be concrete but concise.
"""
)
```

No extra LLM call—piggybacks on existing synthesis request.

---

## Overview Prompt Changes

**Location:** `backend/src/oya/generation/prompts.py`

Updated `OVERVIEW_SYNTHESIS_TEMPLATE` with:
- New SynthesisMap fields as context
- Pre-generated architecture diagram (from existing generators)
- README deprioritized as "supplementary - may be outdated"
- Structured output template with standard sections

```python
OVERVIEW_SYNTHESIS_TEMPLATE = PromptTemplate(
    """Generate a comprehensive overview page for the repository "{repo_name}".

## Project Summary (from code analysis)
{project_summary}

## Entry Points
{entry_points}

## Technology Stack
{tech_stack}

## Code Metrics
{metrics}

## System Layers
{layers}

## Layer Interactions
{layer_interactions}

## Key Components
{key_components}

## Architecture Diagram (pre-generated)
{architecture_diagram}

## README Content (supplementary - may be outdated)
{readme_content}

## Project Structure
```
{file_tree}
```

## Package Information
{package_info}

---

Generate the overview using this EXACT structure:

# {repo_name}

## Overview
[2-3 paragraph summary from code analysis. README may be outdated—only use if it adds unique context.]

## Technology Stack
[Table or bullet list of detected technologies by category]

## Getting Started
[Based on discovered entry points—CLI commands, API startup, main functions.]

## Architecture
[Brief layer description with metrics for scale]

{architecture_diagram}

## Key Components
[Important classes/functions and their roles]

## Optional sections (include only if relevant):
- **Configuration**: Notable config patterns
- **Testing**: Test structure highlights
- **API Reference**: Clear API surface from entry points

Format as clean Markdown."""
)
```

**Helper functions** to format new fields (similar to existing `_format_synthesis_layers`):
- `_format_entry_points()`
- `_format_tech_stack()`
- `_format_metrics()`

---

## Summary

| Component | Changes |
|-----------|---------|
| `summaries.py` | Add `EntryPointInfo`, `CodeMetrics` dataclasses; extend `SynthesisMap` |
| `techstack.yaml` | New config file with library→category mappings |
| `techstack.py` | New module for tech stack aggregation |
| `metrics.py` | New module for code metrics computation |
| `orchestrator.py` | Integrate entry point discovery and metrics into synthesis phase |
| `prompts.py` | Extend `SYNTHESIS_TEMPLATE` for layer_interactions; update `OVERVIEW_SYNTHESIS_TEMPLATE` |
| `overview.py` | Pass new SynthesisMap fields to prompt |

**Key design principles:**
- Code-derived data is source of truth; README is supplementary context
- Compute once in synthesis, reuse in Architecture and Overview
- Diagrams are pre-generated by existing generators, not LLM
- Tech stack mapping is config-driven and extensible
