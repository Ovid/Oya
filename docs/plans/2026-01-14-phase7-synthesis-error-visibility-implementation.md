# Phase 7 SynthesisMap Integration and Error Visibility Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make Phase 7 (Workflows) use SynthesisMap for architectural context, and add error logging to surface silent failures in synthesis and summary parsing.

**Architecture:** Follow the same pattern as Phases 5-6 for SynthesisMap integration. Add targeted logging to existing silent exception handlers without changing control flow.

**Tech Stack:** Python 3.11, FastAPI, pytest, asyncio

---

## Task 1: Add Error Logging to Synthesis LLM Failures

**Files:**
- Modify: `backend/src/oya/generation/synthesis.py:1-22` (add logger import)
- Modify: `backend/src/oya/generation/synthesis.py:139-141` (add error logging)
- Test: `backend/tests/test_synthesis.py`

**Step 1: Add logger import to synthesis.py**

At the top of the file, after the existing imports (around line 21), add:

```python
import logging

logger = logging.getLogger(__name__)
```

**Step 2: Replace silent exception with logged error**

Change lines 139-141 from:

```python
        except Exception:
            # On LLM failure, return the basic layer grouping
            pass
```

To:

```python
        except Exception as e:
            logger.error(
                "LLM call failed during synthesis, falling back to basic layer grouping. "
                f"Error: {type(e).__name__}: {e}"
            )
```

**Step 3: Run existing tests to verify no regression**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_synthesis.py -v`
Expected: All tests pass (the change doesn't affect behavior, only adds logging)

**Step 4: Commit**

```bash
git add backend/src/oya/generation/synthesis.py
git commit -m "$(cat <<'EOF'
fix: log LLM failures in synthesis instead of silent pass

Previously, LLM errors during synthesis were silently swallowed,
making it difficult to diagnose why SynthesisMap was missing
key_components, dependency_graph, or project_summary.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Add Logging to Fallback Summary Methods

**Files:**
- Modify: `backend/src/oya/generation/summaries.py:400-412` (_fallback_file_summary)
- Modify: `backend/src/oya/generation/summaries.py:455-465` (_fallback_directory_summary)
- Test: `backend/tests/test_summaries.py`

**Step 1: Add logging to _fallback_file_summary**

Change the method at lines 400-412 from:

```python
    def _fallback_file_summary(self, file_path: str) -> FileSummary:
        """Create a fallback FileSummary with default values.

        Used when YAML parsing fails or no YAML block is found.
        """
        return FileSummary(
            file_path=file_path,
            purpose="Unknown",
            layer="utility",
            key_abstractions=[],
            internal_deps=[],
            external_deps=[],
        )
```

To:

```python
    def _fallback_file_summary(self, file_path: str) -> FileSummary:
        """Create a fallback FileSummary with default values.

        Used when YAML parsing fails or no YAML block is found.
        """
        logger.warning(
            f"YAML parsing failed for {file_path}, using fallback summary "
            "(purpose='Unknown', layer='utility')"
        )
        return FileSummary(
            file_path=file_path,
            purpose="Unknown",
            layer="utility",
            key_abstractions=[],
            internal_deps=[],
            external_deps=[],
        )
```

**Step 2: Add logging to _fallback_directory_summary**

Change the method at lines 455-465 from:

```python
    def _fallback_directory_summary(self, directory_path: str) -> DirectorySummary:
        """Create a fallback DirectorySummary with default values.

        Used when YAML parsing fails or no YAML block is found.
        """
        return DirectorySummary(
            directory_path=directory_path,
            purpose="Unknown",
            contains=[],
            role_in_system="",
        )
```

To:

```python
    def _fallback_directory_summary(self, directory_path: str) -> DirectorySummary:
        """Create a fallback DirectorySummary with default values.

        Used when YAML parsing fails or no YAML block is found.
        """
        logger.warning(
            f"YAML parsing failed for {directory_path}, using fallback summary "
            "(purpose='Unknown')"
        )
        return DirectorySummary(
            directory_path=directory_path,
            purpose="Unknown",
            contains=[],
            role_in_system="",
        )
```

**Step 3: Run existing tests to verify no regression**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_summaries.py -v`
Expected: All tests pass

**Step 4: Commit**

```bash
git add backend/src/oya/generation/summaries.py
git commit -m "$(cat <<'EOF'
fix: log when fallback summaries are used due to YAML parse failures

Makes it visible when LLM output was unparseable, helping diagnose
why generated documentation may have low-quality summaries.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Unify Uvicorn Logging Format

**Files:**
- Modify: `backend/src/oya/main.py:15-19` (add uvicorn logger config after basicConfig)

**Step 1: Add uvicorn logger configuration**

After line 19 (`level=logging.INFO,` closing the basicConfig), add:

```python
# Unify uvicorn loggers with app format
for uvicorn_logger_name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
    uvicorn_logger = logging.getLogger(uvicorn_logger_name)
    uvicorn_logger.handlers.clear()
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
    uvicorn_logger.addHandler(handler)
```

**Step 2: Test manually by running the server**

Run: `cd backend && source .venv/bin/activate && WORKSPACE_PATH=/tmp uvicorn oya.main:app --host 0.0.0.0 --port 8000`
Expected: All log lines have timestamps in format `YYYY-MM-DD HH:MM:SS`

**Step 3: Commit**

```bash
git add backend/src/oya/main.py
git commit -m "$(cat <<'EOF'
fix: unify uvicorn logging format with app timestamps

All logs now use consistent format: YYYY-MM-DD HH:MM:SS LEVEL message

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Add WORKFLOW_SYNTHESIS_TEMPLATE to prompts.py

**Files:**
- Modify: `backend/src/oya/generation/prompts.py:242-265` (add new template after WORKFLOW_TEMPLATE)

**Step 1: Add the new template**

After line 265 (end of WORKFLOW_TEMPLATE), add:

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

**Step 2: Run linter to check syntax**

Run: `cd backend && source .venv/bin/activate && ruff check src/oya/generation/prompts.py`
Expected: No errors

**Step 3: Commit**

```bash
git add backend/src/oya/generation/prompts.py
git commit -m "$(cat <<'EOF'
feat: add WORKFLOW_SYNTHESIS_TEMPLATE for SynthesisMap-aware workflows

New template includes system layers, key components, and dependency
graph sections to provide architectural context to workflow docs.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Add get_workflow_synthesis_prompt Function

**Files:**
- Modify: `backend/src/oya/generation/prompts.py:812-844` (modify get_workflow_prompt to support synthesis_map)

**Step 1: Update get_workflow_prompt to accept optional synthesis_map**

Replace the function at lines 812-844 with:

```python
def get_workflow_prompt(
    repo_name: str,
    workflow_name: str,
    entry_points: list[str],
    related_files: list[str],
    code_context: str,
    synthesis_map: Any | None = None,
) -> str:
    """Generate a prompt for creating a workflow page.

    Args:
        repo_name: Name of the repository.
        workflow_name: Name of the workflow being documented.
        entry_points: List of entry point descriptions.
        related_files: List of related file paths.
        code_context: Relevant code snippets or context.
        synthesis_map: Optional SynthesisMap for architectural context.

    Returns:
        The rendered prompt string.
    """
    entry_points_str = (
        "\n".join(f"- {ep}" for ep in entry_points) if entry_points else "No entry points defined."
    )
    related_files_str = (
        "\n".join(f"- {f}" for f in related_files) if related_files else "No related files."
    )

    # Use synthesis template if synthesis_map is provided
    if synthesis_map is not None:
        return WORKFLOW_SYNTHESIS_TEMPLATE.render(
            repo_name=repo_name,
            workflow_name=workflow_name,
            entry_points=entry_points_str,
            related_files=related_files_str,
            layers=_format_synthesis_layers(synthesis_map),
            key_components=_format_synthesis_key_components(synthesis_map),
            dependency_graph=_format_synthesis_dependency_graph(synthesis_map),
            code_context=code_context or "No code context provided.",
        )

    # Legacy template without synthesis
    return WORKFLOW_TEMPLATE.render(
        repo_name=repo_name,
        workflow_name=workflow_name,
        entry_points=entry_points_str,
        related_files=related_files_str,
        code_context=code_context or "No code context provided.",
    )
```

**Step 2: Run linter**

Run: `cd backend && source .venv/bin/activate && ruff check src/oya/generation/prompts.py`
Expected: No errors

**Step 3: Commit**

```bash
git add backend/src/oya/generation/prompts.py
git commit -m "$(cat <<'EOF'
feat: update get_workflow_prompt to support synthesis_map parameter

When synthesis_map is provided, uses WORKFLOW_SYNTHESIS_TEMPLATE
with architectural context. Falls back to legacy template otherwise.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Update WorkflowGenerator to Accept synthesis_map

**Files:**
- Modify: `backend/src/oya/generation/workflows.py:1-10` (add SynthesisMap import)
- Modify: `backend/src/oya/generation/workflows.py:200-230` (update generate method)

**Step 1: Add SynthesisMap import**

Change line 8 from:

```python
from oya.generation.prompts import SYSTEM_PROMPT, get_workflow_prompt
```

To:

```python
from oya.generation.prompts import SYSTEM_PROMPT, get_workflow_prompt
from oya.generation.summaries import SynthesisMap
```

**Step 2: Update generate method signature and implementation**

Change lines 200-230 from:

```python
    async def generate(
        self,
        workflow: DiscoveredWorkflow,
        code_context: str,
    ) -> GeneratedPage:
        """Generate a workflow documentation page.

        Args:
            workflow: The discovered workflow to document.
            code_context: Relevant code snippets or context.

        Returns:
            GeneratedPage with workflow content.
        """
        repo_name = self.repo.path.name

        # Format entry points for the prompt
        entry_points_list = []
        for ep in workflow.entry_points:
            ep_file = ep.metadata.get("file", "")
            ep_name = ep.name
            ep_type = ep.symbol_type.value
            entry_points_list.append(f"{ep_name} ({ep_type}) in {ep_file}")

        prompt = get_workflow_prompt(
            repo_name=repo_name,
            workflow_name=workflow.name,
            entry_points=entry_points_list,
            related_files=workflow.related_files,
            code_context=code_context,
        )
```

To:

```python
    async def generate(
        self,
        workflow: DiscoveredWorkflow,
        code_context: str,
        synthesis_map: SynthesisMap | None = None,
    ) -> GeneratedPage:
        """Generate a workflow documentation page.

        Args:
            workflow: The discovered workflow to document.
            code_context: Relevant code snippets or context.
            synthesis_map: Optional SynthesisMap for architectural context.

        Returns:
            GeneratedPage with workflow content.
        """
        repo_name = self.repo.path.name

        # Format entry points for the prompt
        entry_points_list = []
        for ep in workflow.entry_points:
            ep_file = ep.metadata.get("file", "")
            ep_name = ep.name
            ep_type = ep.symbol_type.value
            entry_points_list.append(f"{ep_name} ({ep_type}) in {ep_file}")

        prompt = get_workflow_prompt(
            repo_name=repo_name,
            workflow_name=workflow.name,
            entry_points=entry_points_list,
            related_files=workflow.related_files,
            code_context=code_context,
            synthesis_map=synthesis_map,
        )
```

**Step 3: Run tests**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_workflows.py -v`
Expected: All tests pass

**Step 4: Commit**

```bash
git add backend/src/oya/generation/workflows.py
git commit -m "$(cat <<'EOF'
feat: add synthesis_map parameter to WorkflowGenerator.generate()

WorkflowGenerator now accepts optional SynthesisMap and passes it
to get_workflow_prompt for architectural context in workflow docs.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Update Orchestrator to Pass synthesis_map to Workflows

**Files:**
- Modify: `backend/src/oya/generation/orchestrator.py:574` (update call site)
- Modify: `backend/src/oya/generation/orchestrator.py:829-833` (update method signature)
- Modify: `backend/src/oya/generation/orchestrator.py:875-878` (update generate call)

**Step 1: Update _run_workflows method signature**

Change lines 829-833 from:

```python
    async def _run_workflows(
        self,
        analysis: dict,
        progress_callback: ProgressCallback | None = None,
    ) -> list[GeneratedPage]:
```

To:

```python
    async def _run_workflows(
        self,
        analysis: dict,
        progress_callback: ProgressCallback | None = None,
        synthesis_map: SynthesisMap | None = None,
    ) -> list[GeneratedPage]:
```

**Step 2: Update the docstring**

Update the docstring (lines 834-842) to include synthesis_map:

```python
        """Run workflow generation phase.

        Args:
            analysis: Analysis results.
            progress_callback: Optional async callback for progress updates.
            synthesis_map: Optional SynthesisMap for architectural context.

        Returns:
            List of generated workflow pages.
        """
```

**Step 3: Update the generate call inside _run_workflows**

Change lines 875-878 from:

```python
            page = await self.workflow_generator.generate(
                workflow=workflow,
                code_context=code_context,
            )
```

To:

```python
            page = await self.workflow_generator.generate(
                workflow=workflow,
                code_context=code_context,
                synthesis_map=synthesis_map,
            )
```

**Step 4: Update the call site**

Change line 574 from:

```python
            workflow_pages = await self._run_workflows(analysis, progress_callback)
```

To:

```python
            workflow_pages = await self._run_workflows(
                analysis, progress_callback, synthesis_map=synthesis_map
            )
```

**Step 5: Run all tests to verify integration**

Run: `cd backend && source .venv/bin/activate && pytest -v`
Expected: All 460 tests pass

**Step 6: Commit**

```bash
git add backend/src/oya/generation/orchestrator.py
git commit -m "$(cat <<'EOF'
feat: pass synthesis_map to workflow generation phase

Phase 7 (Workflows) now receives SynthesisMap like Phases 5-6,
enabling workflow documentation with full architectural context.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: Final Integration Test

**Step 1: Run full test suite**

Run: `cd backend && source .venv/bin/activate && pytest -v`
Expected: All tests pass

**Step 2: Run linter on all modified files**

Run: `cd backend && source .venv/bin/activate && ruff check src/oya/generation/ src/oya/main.py`
Expected: No errors

**Step 3: Create final summary commit (if any uncommitted changes)**

If there are any uncommitted changes from minor fixes:

```bash
git status
# If clean, skip this step
# If changes exist:
git add -A
git commit -m "$(cat <<'EOF'
chore: minor fixes from integration testing

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

## Summary

After completing all tasks, you will have:

1. **Error visibility**: LLM failures in synthesis and YAML parsing failures in summaries now log warnings/errors
2. **Unified logging**: All logs (including Uvicorn) use consistent timestamp format
3. **Phase 7 SynthesisMap integration**: Workflows now receive architectural context like Phases 5-6

Files modified:
- `backend/src/oya/generation/synthesis.py` - Added logger, error logging
- `backend/src/oya/generation/summaries.py` - Added fallback logging
- `backend/src/oya/main.py` - Unified uvicorn logging
- `backend/src/oya/generation/prompts.py` - Added WORKFLOW_SYNTHESIS_TEMPLATE, updated get_workflow_prompt
- `backend/src/oya/generation/workflows.py` - Added synthesis_map to generate()
- `backend/src/oya/generation/orchestrator.py` - Pass synthesis_map to _run_workflows()
