# Phase 7 Workflow Generation Refactor Design

**Date:** 2026-01-15

**Problem:** Workflow generation is the least sophisticated high-level phase. While Architecture (Phase 5) and Overview (Phase 6) leverage the rich SynthesisMap, workflows use raw code snippets truncated to 2000 chars, re-discover entry points that synthesis already found, and create naive 1:1 mappings of entry points to workflow pages.

**Solution:** Refactor workflow generation to align architecturally with other high-level phases. Eliminate duplicate entry point discovery, implement domain-based grouping with pattern heuristics, trace related files via imports, and pass full context to the LLM.

---

## Architecture Overview

**Current flow:**
```
Orchestrator._run_workflows()
  -> WorkflowDiscovery.find_entry_points(symbols)  # Re-parses symbols
  -> WorkflowDiscovery.group_into_workflows()      # 1:1 mapping
  -> WorkflowGenerator.generate(workflow, code_context, synthesis_map)
```

**New flow:**
```
Orchestrator._run_workflows()
  -> WorkflowGrouper.group(synthesis_map.entry_points, file_imports)
  -> WorkflowGenerator.generate(
      workflow_group,
      synthesis_map,
      file_tree,
      symbols,
      file_imports
    )
```

**Key principle:** Use data already computed in synthesis. SynthesisMap has `entry_points` since Phase 6 improvements—workflows should consume that, not re-discover.

---

## Data Model Changes

**Location:** `backend/src/oya/generation/workflows.py`

**Delete:**
- `DiscoveredWorkflow` dataclass
- `WorkflowDiscovery` class

**New dataclass:**

```python
@dataclass
class WorkflowGroup:
    name: str                           # Human-readable: "Users API"
    slug: str                           # URL-friendly: "users-api"
    entry_points: list[EntryPointInfo]  # Multiple entry points per group
    related_files: list[str]            # Files traced via imports
    primary_layer: str                  # Dominant layer classification
```

**New class:**

```python
class WorkflowGrouper:
    """Groups entry points into workflow domains using pattern heuristics."""

    def group(
        self,
        entry_points: list[EntryPointInfo],
        file_imports: dict[str, list[str]]
    ) -> list[WorkflowGroup]:
        """Group entry points by domain and trace related files."""
```

---

## Domain Grouping Strategy

**Pattern-based heuristics (priority order):**

1. **Route path prefix** - For HTTP endpoints:
   - `/api/users/create`, `/api/users/delete` -> "Users API"
   - `/api/orders/{id}`, `/api/orders/list` -> "Orders API"
   - Extract first 2 path segments after common base (`/api/`, `/v1/`)

2. **File path grouping** - Entry points in same file:
   - `routers/users.py` has 5 endpoints -> one workflow group
   - `commands/import.py` has 3 CLI commands -> one workflow group

3. **Function name prefix** - For non-route entry points:
   - `export_csv`, `export_json`, `export_pdf` -> "Export"
   - `sync_users`, `sync_orders` -> "Sync"

4. **Entry point type fallback** - Group by type:
   - All CLI commands without clear domain -> "CLI Commands"
   - All background tasks -> "Background Jobs"

**Algorithm:**

```python
def group(self, entry_points: list[EntryPointInfo], file_imports: dict[str, list[str]]) -> list[WorkflowGroup]:
    groups: list[WorkflowGroup] = []
    ungrouped = list(entry_points)

    # 1. Route-based grouping for HTTP endpoints
    route_groups = self._group_by_route_prefix(ungrouped)
    groups.extend(route_groups)
    ungrouped = [ep for ep in ungrouped if not self._in_any_group(ep, route_groups)]

    # 2. File-based grouping for remaining
    file_groups = self._group_by_file(ungrouped)
    groups.extend(file_groups)
    ungrouped = [ep for ep in ungrouped if not self._in_any_group(ep, file_groups)]

    # 3. Name-prefix grouping for remaining
    name_groups = self._group_by_name_prefix(ungrouped)
    groups.extend(name_groups)
    ungrouped = [ep for ep in ungrouped if not self._in_any_group(ep, name_groups)]

    # 4. Type-based fallback for stragglers
    type_groups = self._group_by_type(ungrouped)
    groups.extend(type_groups)

    # 5. Trace related files for each group
    for group in groups:
        group.related_files = self._find_related_files(group.entry_points, file_imports)
        group.primary_layer = self._determine_primary_layer(group)

    return groups
```

**No artificial limit.** Generate as many workflow groups as the heuristics produce.

---

## Related Files Discovery

**Import-based tracing with depth limit:**

```python
def _find_related_files(
    self,
    entry_points: list[EntryPointInfo],
    file_imports: dict[str, list[str]],
    max_depth: int = 2
) -> list[str]:
    """Trace imports from entry point files to find related code.

    Args:
        entry_points: Entry points in this workflow group
        file_imports: Map of file -> list of imported files
        max_depth: How deep to trace (2 = handler -> service -> repo)

    Returns:
        Deduplicated list of related file paths
    """
    seed_files = {ep.file for ep in entry_points}
    related = set(seed_files)
    frontier = set(seed_files)

    for _ in range(max_depth):
        next_frontier = set()
        for file in frontier:
            imports = file_imports.get(file, [])
            # Filter to internal imports only (within project)
            internal = [f for f in imports if not self._is_external(f)]
            next_frontier.update(internal)
        related.update(next_frontier)
        frontier = next_frontier - related  # Only traverse new files

    return sorted(related)
```

**Why depth 2:** Captures typical call chains (handler -> service -> repo/model) without pulling in the entire codebase.

---

## Code Context Building

**Replace truncated raw code with structured data:**

1. **From SynthesisMap (already available):**
   - `layers` - Layer classification for each file/component
   - `key_components` - Important classes/functions with roles
   - `dependency_graph` - How layers interact
   - `project_summary` - Overall codebase understanding
   - `layer_interactions` - How data flows between layers

2. **Workflow-specific context:**
   - Entry point details (name, type, route path, file location)
   - Related files with layer classifications
   - Relevant symbols filtered to related files

3. **Targeted code snippets:**
   - Extract specific symbols from related files (not truncated raw files)
   - Include function signatures and docstrings
   - For small files (< 100 lines), include full content

---

## Prompt Template Updates

**Location:** `backend/src/oya/generation/prompts.py`

**Updated `WORKFLOW_SYNTHESIS_TEMPLATE`:**

```python
WORKFLOW_SYNTHESIS_TEMPLATE = PromptTemplate(
    """Generate documentation for the "{workflow_name}" workflow.

## Project Context
{project_summary}

## Architecture Layers
{layers}

## Layer Interactions
{layer_interactions}

---

## Workflow: {workflow_name}

### Entry Points
{entry_points}

### Related Components
{related_components}

### Layer Flow
{layer_flow}

### Code Context
{code_context}

---

Generate workflow documentation with this structure:

## Overview
[What this workflow accomplishes - 2-3 sentences]

## Entry Points
[How the workflow is triggered - routes, CLI commands, etc.]

## Execution Flow
[Step-by-step through the layers, referencing specific components]

## Key Components
[Important functions/classes involved with brief descriptions]

## Error Handling
[How failures are managed at each layer]

## Data Flow
[What data moves through the system and how it transforms]

Format as clean Markdown with code references where helpful."""
)
```

---

## Orchestrator Changes

**Location:** `backend/src/oya/generation/orchestrator.py`

**Updated `_run_workflows()`:**

```python
async def _run_workflows(self, analysis: dict, synthesis_map: SynthesisMap) -> None:
    """Generate workflow documentation pages.

    Uses entry points from SynthesisMap (computed during synthesis phase)
    and groups them by domain using pattern heuristics.
    """
    if not synthesis_map.entry_points:
        logger.info("No entry points found, skipping workflow generation")
        return

    grouper = WorkflowGrouper()
    workflow_groups = grouper.group(
        entry_points=synthesis_map.entry_points,
        file_imports=analysis.get("file_imports", {})
    )

    logger.info(f"Generating {len(workflow_groups)} workflow pages")

    for group in workflow_groups:
        self._report_progress(f"Generating workflow: {group.name}")

        page = await self.workflow_generator.generate(
            workflow_group=group,
            synthesis_map=synthesis_map,
            file_tree=analysis["file_tree"],
            symbols=analysis.get("symbols", []),
            file_imports=analysis.get("file_imports", {})
        )

        await self._write_wiki_page(f"workflows/{group.slug}.md", page)
```

---

## WorkflowGenerator Updates

**Location:** `backend/src/oya/generation/workflows.py`

**Updated `generate()` signature:**

```python
class WorkflowGenerator:
    async def generate(
        self,
        workflow_group: WorkflowGroup,
        synthesis_map: SynthesisMap,
        file_tree: str,
        symbols: list[ParsedSymbol],
        file_imports: dict[str, list[str]]
    ) -> str:
        """Generate documentation for a workflow group.

        Args:
            workflow_group: Grouped entry points with related files
            synthesis_map: Full synthesis context (layers, components, etc.)
            file_tree: Project structure visualization
            symbols: Parsed symbols for code context
            file_imports: Import relationships for dependency info

        Returns:
            Markdown documentation for the workflow
        """
```

**Context building:**

```python
def _build_context(
    self,
    workflow_group: WorkflowGroup,
    synthesis_map: SynthesisMap,
    symbols: list[ParsedSymbol]
) -> dict:
    """Build prompt context from available data."""

    # Filter symbols to related files
    related_symbols = [
        s for s in symbols
        if s.metadata.get("file") in workflow_group.related_files
    ]

    # Determine layer flow from related files
    layer_flow = self._trace_layer_flow(
        workflow_group.related_files,
        synthesis_map.layers
    )

    # Find relevant key components
    related_components = [
        c for c in synthesis_map.key_components
        if c.file in workflow_group.related_files
    ]

    return {
        "workflow_name": workflow_group.name,
        "project_summary": synthesis_map.project_summary,
        "layers": self._format_layers(synthesis_map.layers),
        "layer_interactions": synthesis_map.layer_interactions,
        "entry_points": self._format_entry_points(workflow_group.entry_points),
        "related_components": self._format_components(related_components),
        "layer_flow": layer_flow,
        "code_context": self._format_symbols(related_symbols),
    }
```

---

## Summary

| Component | Changes |
|-----------|---------|
| `workflows.py` | Delete `WorkflowDiscovery`, `DiscoveredWorkflow`. Add `WorkflowGrouper`, `WorkflowGroup`. Update `WorkflowGenerator.generate()` signature and implementation. |
| `orchestrator.py` | Update `_run_workflows()` to use `synthesis_map.entry_points`, pass full context to generator. Remove 10-workflow limit. |
| `prompts.py` | Update `WORKFLOW_SYNTHESIS_TEMPLATE` with rich context variables and structured output format. |

**Deleted code:**
- `WorkflowDiscovery` class (duplicate of synthesis entry point discovery)
- 2000-char truncation logic
- Hard-coded limit of 10 workflows

**Key design principles:**
- Use data already computed in synthesis (no re-discovery)
- Domain-based grouping works for any codebase (generic patterns)
- Related files traced via imports (depth 2)
- Full architectural context like Architecture/Overview phases
- No artificial limits on workflow count
