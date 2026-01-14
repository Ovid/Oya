# Phase 7 SynthesisMap Integration and Error Visibility

**Date:** 2026-01-14
**Status:** Approved

## Overview

This design addresses two high-impact issues in the Oya wiki generation pipeline:

1. **Phase 7 (Workflows) lacks architectural context** - Unlike Phases 5 (Architecture) and 6 (Overview), Phase 7 doesn't use SynthesisMap, resulting in workflow documentation that lacks layer awareness and component relationships.

2. **Silent failures hide data quality issues** - LLM failures in synthesis and YAML parsing failures in summaries are silently swallowed, making it difficult to diagnose why generated documentation is incomplete or low-quality.

Additionally, we'll unify logging configuration so all logs (including Uvicorn's) use consistent timestamp formatting.

## Design

### 1. Phase 7 SynthesisMap Integration

#### 1.1 Orchestrator Changes

**File:** `backend/src/oya/generation/orchestrator.py`

Add `synthesis_map` parameter to `_run_workflows()`:

```python
async def _run_workflows(
    self,
    analysis: dict,
    progress_callback: ProgressCallback | None = None,
    synthesis_map: SynthesisMap | None = None,  # NEW
) -> list[GeneratedPage]:
```

Update call site to pass synthesis_map:

```python
workflow_pages = await self._run_workflows(
    analysis, progress_callback, synthesis_map=synthesis_map
)
```

Pass synthesis_map to WorkflowGenerator.generate() inside the method.

#### 1.2 WorkflowGenerator Changes

**File:** `backend/src/oya/generation/workflows.py`

Add `synthesis_map` parameter to `generate()`:

```python
async def generate(
    self,
    workflow: DiscoveredWorkflow,
    code_context: str,
    synthesis_map: SynthesisMap | None = None,  # NEW
) -> GeneratedPage:
```

Add import at top of file:

```python
from oya.generation.summaries import SynthesisMap
```

Call the appropriate prompt function based on whether synthesis_map is provided.

#### 1.3 New Prompt Template

**File:** `backend/src/oya/generation/prompts.py`

Add `WORKFLOW_SYNTHESIS_TEMPLATE`:

```python
WORKFLOW_SYNTHESIS_TEMPLATE = PromptTemplate(
    """Generate a workflow documentation page for the "{workflow_name}" workflow in "{repo_name}".

## Entry Points
{entry_points}

## Related Files
{related_files}

## System Layers
{layers}

## Key Components
{key_components}

## Layer Dependencies
{dependency_graph}

## Code Context
{code_context}

---

Create workflow documentation that includes:
1. **Workflow Overview**: What this workflow accomplishes and its role in the system
2. **Trigger/Entry Point**: How the workflow is initiated
3. **Step-by-Step Flow**: Walkthrough showing how data moves through layers
4. **Key Components Involved**: Which key components participate and their roles
5. **Error Handling**: How errors are handled at each layer
6. **Related Workflows**: Connections to other workflows

Format the output as clean Markdown suitable for a wiki page."""
)
```

Add `get_workflow_synthesis_prompt()` function that formats the template using existing helpers:
- `_format_synthesis_layers()`
- `_format_synthesis_key_components()`
- `_format_synthesis_dependency_graph()`

Update `get_workflow_prompt()` to select template based on synthesis_map presence.

### 2. Error Visibility

#### 2.1 Synthesis LLM Failures

**File:** `backend/src/oya/generation/synthesis.py`

Change silent exception handling in `_process_batch()`:

```python
# Before
except Exception:
    # On LLM failure, return the basic layer grouping
    pass

# After
except Exception as e:
    logger.error(
        "LLM call failed during synthesis, falling back to basic layer grouping. "
        f"Error: {type(e).__name__}: {e}"
    )
```

Add similar logging in `_parse_llm_response()` for JSON parse failures.

#### 2.2 Summary Fallback Logging

**File:** `backend/src/oya/generation/summaries.py`

Add logging to `_fallback_file_summary()`:

```python
def _fallback_file_summary(self, file_path: str) -> FileSummary:
    logger.warning(
        f"YAML parsing failed for {file_path}, using fallback summary "
        "(purpose='Unknown', layer='utility')"
    )
    return FileSummary(...)
```

Add similar logging to `_fallback_directory_summary()`.

### 3. Logging Configuration Cleanup

**File:** `backend/src/oya/main.py`

Add after `logging.basicConfig()`:

```python
# Unify uvicorn loggers with app format
for uvicorn_logger_name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
    uvicorn_logger = logging.getLogger(uvicorn_logger_name)
    uvicorn_logger.handlers.clear()
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
    uvicorn_logger.addHandler(handler)
```

## Files Changed

| File | Changes |
|------|---------|
| `orchestrator.py` | Add synthesis_map param to _run_workflows(), update call site |
| `workflows.py` | Add synthesis_map param to generate(), add SynthesisMap import |
| `prompts.py` | Add WORKFLOW_SYNTHESIS_TEMPLATE, add get_workflow_synthesis_prompt() |
| `synthesis.py` | Add error logging for LLM failures and JSON parse failures |
| `summaries.py` | Add warning logging for fallback summary usage |
| `main.py` | Configure uvicorn loggers to use app format |

## Out of Scope

- Database error tracking (storing errors for UI display)
- Error aggregation system (summary at end of generation)
- Fallback quality improvements (smarter defaults when parsing fails)
- FileSummary integration for workflows (using structured summaries instead of raw code)

These can be addressed in follow-up work.

## Testing

- Run generation on a test repository and verify workflow pages include layer/component context
- Intentionally trigger LLM failures (e.g., invalid API key) and verify errors appear in logs
- Verify all logs now have consistent timestamp formatting
