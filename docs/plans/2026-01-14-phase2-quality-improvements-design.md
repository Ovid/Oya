# Phase 2 Quality Improvements Design

## Overview

This design addresses quality issues in Phase 2 (File Documentation) of the Oya generation pipeline. The changes focus on ensuring documentation is always generated, maintaining consistent structure, improving error handling, and adding visual diagrams.

## Problems Addressed

| Problem | Impact |
|---------|--------|
| Empty wiki pages when LLM sees "internal" comments | Missing documentation for important files |
| Inconsistent wiki page structure | Hard to scan across files |
| Silent YAML parsing failures | Bad fallback data propagates to synthesis |
| Silent layer coercion | Hidden prompt issues |
| Missing log timestamps | Hard to diagnose issues |
| Text-only documentation | Missing visual understanding of structure |

## Design

### 1. Prompt Changes (`prompts.py`)

**Audience Clarity**

Add explicit audience statement near the top of `FILE_TEMPLATE`:

```
AUDIENCE: You are writing for developers who will maintain, debug, and
extend this code - NOT for end users of an API. Even files marked as
"internal" or "no user-serviceable parts" need thorough documentation
for the development team.

REQUIREMENT: You MUST always produce documentation. Every file has value
to developers - explain what it does, why it exists, and how it works.
Never skip documentation because a file seems "internal" or "trivial".
```

**Required Template Structure**

Specify mandatory sections in order:

```
Your documentation MUST include these sections in order:
1. **Purpose** - What this file does and why it exists
2. **Public API** - Exported classes, functions, constants (if any)
3. **Internal Details** - Implementation specifics developers need to know
4. **Dependencies** - What this file imports and why
5. **Usage Examples** - How to use the components in this file

You MAY add additional sections after these if there's important
information that doesn't fit (e.g., "Concurrency Notes", "Migration
History", "Known Limitations").
```

### 2. Retry Semantics (`file.py`)

**Location:** `FileGenerator.generate()` method

**Logic:**

```python
async def generate(self, ...):
    # First attempt
    generated_content = await self.llm_client.generate(prompt=prompt, ...)
    clean_content, file_summary = self._parser.parse_file_summary(generated_content, file_path)

    # Check if parsing produced fallback (indicates failure)
    if file_summary.purpose == "Unknown":
        logger.warning(f"YAML parsing failed for {file_path}, retrying...")

        # Retry once with same prompt
        generated_content = await self.llm_client.generate(prompt=prompt, ...)
        clean_content, file_summary = self._parser.parse_file_summary(generated_content, file_path)

        if file_summary.purpose == "Unknown":
            logger.error(f"YAML parsing failed after retry for {file_path}")

    # Continue with page creation...
```

### 3. Layer Validation Logging (`summaries.py`)

**Location:** `SummaryParser.parse_file_summary()` method, around line 384

**Change:**

```python
# Before (silent coercion)
if layer not in VALID_LAYERS:
    layer = "utility"

# After (logged coercion)
if layer not in VALID_LAYERS:
    logger.warning(
        f"Invalid layer '{layer}' for {file_path}, defaulting to 'utility'. "
        f"Valid layers: {', '.join(sorted(VALID_LAYERS))}"
    )
    layer = "utility"
```

### 4. Global Logging Configuration (`main.py`)

**Add logging configuration at module level:**

```python
import logging

LOG_FORMAT = "%(asctime)s %(levelname)-8s %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

logging.basicConfig(
    format=LOG_FORMAT,
    datefmt=DATE_FORMAT,
    level=logging.INFO,
)
```

**Configure uvicorn** to use the same format for HTTP request logs.

**Expected output:**
```
2026-01-14 10:23:45 INFO     172.66.0.243:57481 - "GET /api/wiki/tree HTTP/1.1" 200 OK
2026-01-14 10:23:45 WARNING  YAML parsing failed for src/utils/helpers.py, retrying...
2026-01-14 10:23:48 ERROR    YAML parsing failed after retry for src/utils/helpers.py
```

### 5. Mermaid Diagrams for Files

**Class Diagrams**

Include when the file defines 1 or more classes. Uses existing `ClassDiagramGenerator`.

```python
# Filter symbols to just this file
file_symbols = [s for s in all_symbols if s.file == file_path]
class_diagram = ClassDiagramGenerator().generate(file_symbols)
```

**Dependency Diagrams**

Include when the file has imports. Requires new method on `DependencyGraphGenerator`.

**New method in `mermaid.py`:**

```python
def generate_for_file(self, file_path: str, all_imports: dict[str, list[str]]) -> str:
    """Generate a dependency diagram focused on a single file.

    Shows:
    - What this file imports (outgoing)
    - What files import this file (incoming)

    Args:
        file_path: The file to focus on
        all_imports: Dict mapping all file paths to their imports

    Returns:
        Mermaid diagram string, or empty string if no dependencies
    """
```

**Integration in `FileGenerator.generate()`:**

After LLM content generation, append diagrams:

```python
# Generate diagrams (Python, not LLM)
diagrams_md = ""

if file_symbols:  # Has classes
    class_diagram = ClassDiagramGenerator().generate(file_symbols)
    if class_diagram:
        diagrams_md += f"\n\n### Class Structure\n\n```mermaid\n{class_diagram}\n```"

dep_diagram = DependencyGraphGenerator().generate_for_file(file_path, file_imports)
if dep_diagram:
    diagrams_md += f"\n\n### Dependencies\n\n```mermaid\n{dep_diagram}\n```"

if diagrams_md:
    clean_content += f"\n\n## Diagrams{diagrams_md}"
```

## Files Changed

| File | Changes |
|------|---------|
| `backend/src/oya/generation/prompts.py` | Audience statement, required sections template |
| `backend/src/oya/generation/file.py` | Retry logic, diagram integration |
| `backend/src/oya/generation/summaries.py` | Layer validation warning |
| `backend/src/oya/generation/mermaid.py` | New `generate_for_file()` method |
| `backend/src/oya/main.py` | Global logging configuration |

## Testing

- Unit tests for retry logic (mock LLM to return bad YAML, verify retry)
- Unit tests for `generate_for_file()` method
- Integration test: file with "no user-serviceable parts" comment still gets documented
- Manual verification of log output format

## Not In Scope

The following issues from `docs/notes/phase-2-files.md` are explicitly not addressed:

- File filtering false positives (weakness #1)
- Semantic validation of LLM output (weakness #3)
- Layer classification flexibility (weakness #4)
- Static parallel limit (weakness #5)
- Incremental regeneration edge cases (weakness #6)
