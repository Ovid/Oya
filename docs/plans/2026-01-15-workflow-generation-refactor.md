# Workflow Generation Refactor Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Refactor workflow generation to align architecturally with Architecture/Overview phases - eliminate duplicate entry point discovery, implement domain-based grouping, trace related files via imports, and pass full context to the LLM.

**Architecture:** Replace `WorkflowDiscovery` with `WorkflowGrouper` that consumes `synthesis_map.entry_points`. Group entry points by domain using pattern heuristics (route prefix -> file path -> name prefix -> type). Trace related files via `file_imports` with depth-2 traversal. Update `WorkflowGenerator` to accept full context like Architecture/Overview phases.

**Tech Stack:** Python 3.11+, pytest, dataclasses

---

## Task 1: Create WorkflowGroup Dataclass

**Files:**
- Modify: `backend/src/oya/generation/workflows.py`
- Test: `backend/tests/test_workflow_generator.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_workflow_generator.py`:

```python
from oya.generation.workflows import WorkflowGroup
from oya.generation.summaries import EntryPointInfo


class TestWorkflowGroup:
    """Tests for WorkflowGroup dataclass."""

    def test_workflow_group_creation(self):
        """WorkflowGroup holds grouped entry points."""
        entry_points = [
            EntryPointInfo(name="get_users", entry_type="api_route", file="api/users.py", description="/users"),
            EntryPointInfo(name="create_user", entry_type="api_route", file="api/users.py", description="/users"),
        ]

        group = WorkflowGroup(
            name="Users API",
            slug="users-api",
            entry_points=entry_points,
            related_files=["api/users.py", "services/user_service.py"],
            primary_layer="api",
        )

        assert group.name == "Users API"
        assert group.slug == "users-api"
        assert len(group.entry_points) == 2
        assert "api/users.py" in group.related_files
        assert group.primary_layer == "api"
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/poecurt/projects/oya/.worktrees/workflow-refactor/backend && source .venv/bin/activate && pytest tests/test_workflow_generator.py::TestWorkflowGroup::test_workflow_group_creation -v`

Expected: FAIL with `ImportError: cannot import name 'WorkflowGroup'`

**Step 3: Write minimal implementation**

Add to `backend/src/oya/generation/workflows.py` after the existing imports and before `DiscoveredWorkflow`:

```python
from oya.generation.summaries import EntryPointInfo


@dataclass
class WorkflowGroup:
    """Represents a group of related entry points forming a workflow.

    Attributes:
        name: Human-readable name of the workflow group.
        slug: URL-friendly identifier.
        entry_points: List of EntryPointInfo objects in this group.
        related_files: List of file paths related to this workflow (traced via imports).
        primary_layer: Dominant architectural layer for this workflow.
    """

    name: str
    slug: str
    entry_points: list[EntryPointInfo] = field(default_factory=list)
    related_files: list[str] = field(default_factory=list)
    primary_layer: str = ""
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/poecurt/projects/oya/.worktrees/workflow-refactor/backend && source .venv/bin/activate && pytest tests/test_workflow_generator.py::TestWorkflowGroup::test_workflow_group_creation -v`

Expected: PASS

**Step 5: Commit**

```bash
cd /Users/poecurt/projects/oya/.worktrees/workflow-refactor && git add backend/src/oya/generation/workflows.py backend/tests/test_workflow_generator.py && git commit -m "feat(workflows): add WorkflowGroup dataclass"
```

---

## Task 2: Create WorkflowGrouper Class - Route-Based Grouping

**Files:**
- Modify: `backend/src/oya/generation/workflows.py`
- Test: `backend/tests/test_workflow_generator.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_workflow_generator.py`:

```python
from oya.generation.workflows import WorkflowGrouper


class TestWorkflowGrouper:
    """Tests for WorkflowGrouper."""

    def test_groups_by_route_prefix(self):
        """Groups API routes by common URL prefix."""
        grouper = WorkflowGrouper()

        entry_points = [
            EntryPointInfo(name="get_users", entry_type="api_route", file="api/users.py", description="/api/users"),
            EntryPointInfo(name="create_user", entry_type="api_route", file="api/users.py", description="/api/users"),
            EntryPointInfo(name="get_orders", entry_type="api_route", file="api/orders.py", description="/api/orders"),
            EntryPointInfo(name="list_orders", entry_type="api_route", file="api/orders.py", description="/api/orders/{id}"),
        ]

        groups = grouper.group(entry_points, file_imports={})

        # Should have 2 groups: users and orders
        assert len(groups) == 2

        users_group = next((g for g in groups if "users" in g.slug.lower()), None)
        orders_group = next((g for g in groups if "orders" in g.slug.lower()), None)

        assert users_group is not None
        assert orders_group is not None
        assert len(users_group.entry_points) == 2
        assert len(orders_group.entry_points) == 2
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/poecurt/projects/oya/.worktrees/workflow-refactor/backend && source .venv/bin/activate && pytest tests/test_workflow_generator.py::TestWorkflowGrouper::test_groups_by_route_prefix -v`

Expected: FAIL with `ImportError: cannot import name 'WorkflowGrouper'`

**Step 3: Write minimal implementation**

Add to `backend/src/oya/generation/workflows.py` after `WorkflowGroup`:

```python
class WorkflowGrouper:
    """Groups entry points into workflow domains using pattern heuristics.

    Grouping strategy (priority order):
    1. Route path prefix - for HTTP endpoints
    2. File path - entry points in same file
    3. Function name prefix - common prefixes like export_, sync_
    4. Entry point type - fallback grouping by type
    """

    def group(
        self,
        entry_points: list[EntryPointInfo],
        file_imports: dict[str, list[str]],
    ) -> list[WorkflowGroup]:
        """Group entry points by domain and trace related files.

        Args:
            entry_points: List of EntryPointInfo from SynthesisMap.
            file_imports: Map of file paths to their imports.

        Returns:
            List of WorkflowGroup objects.
        """
        if not entry_points:
            return []

        groups: list[WorkflowGroup] = []
        ungrouped = list(entry_points)

        # 1. Route-based grouping for HTTP endpoints
        route_groups = self._group_by_route_prefix(ungrouped)
        groups.extend(route_groups)
        grouped_names = {ep.name for g in route_groups for ep in g.entry_points}
        ungrouped = [ep for ep in ungrouped if ep.name not in grouped_names]

        # TODO: Add more grouping strategies in subsequent tasks

        # For now, create individual groups for remaining
        for ep in ungrouped:
            groups.append(
                WorkflowGroup(
                    name=self._humanize_name(ep.name),
                    slug=self._slugify(ep.name),
                    entry_points=[ep],
                    related_files=[ep.file] if ep.file else [],
                    primary_layer="",
                )
            )

        return groups

    def _group_by_route_prefix(
        self, entry_points: list[EntryPointInfo]
    ) -> list[WorkflowGroup]:
        """Group API routes by common URL prefix.

        Extracts first 2 path segments after common bases (/api/, /v1/, etc).
        """
        # Filter to route entry points with descriptions (route paths)
        routes = [ep for ep in entry_points if ep.entry_type == "api_route" and ep.description]

        if not routes:
            return []

        # Extract route prefixes
        prefix_groups: dict[str, list[EntryPointInfo]] = {}
        for ep in routes:
            prefix = self._extract_route_prefix(ep.description)
            if prefix:
                if prefix not in prefix_groups:
                    prefix_groups[prefix] = []
                prefix_groups[prefix].append(ep)

        # Convert to WorkflowGroups
        groups = []
        for prefix, eps in prefix_groups.items():
            # Only create group if multiple entry points share the prefix
            if len(eps) >= 1:
                name = self._prefix_to_name(prefix)
                groups.append(
                    WorkflowGroup(
                        name=name,
                        slug=self._slugify(name),
                        entry_points=eps,
                        related_files=list({ep.file for ep in eps if ep.file}),
                        primary_layer="api",
                    )
                )

        return groups

    def _extract_route_prefix(self, route_path: str) -> str:
        """Extract grouping prefix from route path.

        /api/users -> users
        /api/v1/orders/{id} -> orders
        /users -> users
        """
        # Remove common API prefixes
        path = route_path.lstrip("/")
        for prefix in ["api/v1/", "api/v2/", "api/", "v1/", "v2/"]:
            if path.startswith(prefix):
                path = path[len(prefix):]
                break

        # Get first segment (the resource name)
        segments = path.split("/")
        if segments:
            # Remove path parameters like {id}
            first = segments[0]
            if not first.startswith("{"):
                return first.lower()

        return ""

    def _prefix_to_name(self, prefix: str) -> str:
        """Convert route prefix to human-readable name."""
        return f"{prefix.replace('_', ' ').replace('-', ' ').title()} API"

    def _humanize_name(self, name: str) -> str:
        """Convert a symbol name to a human-readable name."""
        human = name.replace("_", " ")
        human = re.sub(r"([a-z])([A-Z])", r"\1 \2", human)
        return human.title()

    def _slugify(self, name: str) -> str:
        """Convert a name to a URL-friendly slug."""
        slug = name.replace("_", "-").replace(" ", "-").lower()
        slug = re.sub(r"[^a-z0-9-]", "", slug)
        slug = re.sub(r"-+", "-", slug)
        return slug.strip("-")
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/poecurt/projects/oya/.worktrees/workflow-refactor/backend && source .venv/bin/activate && pytest tests/test_workflow_generator.py::TestWorkflowGrouper::test_groups_by_route_prefix -v`

Expected: PASS

**Step 5: Commit**

```bash
cd /Users/poecurt/projects/oya/.worktrees/workflow-refactor && git add backend/src/oya/generation/workflows.py backend/tests/test_workflow_generator.py && git commit -m "feat(workflows): add WorkflowGrouper with route-based grouping"
```

---

## Task 3: Add File-Based Grouping to WorkflowGrouper

**Files:**
- Modify: `backend/src/oya/generation/workflows.py`
- Test: `backend/tests/test_workflow_generator.py`

**Step 1: Write the failing test**

Add to `TestWorkflowGrouper` class:

```python
    def test_groups_by_file_path(self):
        """Groups non-route entry points by file."""
        grouper = WorkflowGrouper()

        entry_points = [
            EntryPointInfo(name="export_csv", entry_type="cli_command", file="commands/export.py", description="csv"),
            EntryPointInfo(name="export_json", entry_type="cli_command", file="commands/export.py", description="json"),
            EntryPointInfo(name="import_data", entry_type="cli_command", file="commands/import.py", description="data"),
        ]

        groups = grouper.group(entry_points, file_imports={})

        # Should have 2 groups: export.py and import.py
        assert len(groups) == 2

        export_group = next((g for g in groups if "export" in g.slug.lower()), None)
        assert export_group is not None
        assert len(export_group.entry_points) == 2
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/poecurt/projects/oya/.worktrees/workflow-refactor/backend && source .venv/bin/activate && pytest tests/test_workflow_generator.py::TestWorkflowGrouper::test_groups_by_file_path -v`

Expected: FAIL (creates 3 individual groups instead of 2 file-based groups)

**Step 3: Update implementation**

In `WorkflowGrouper.group()`, add file-based grouping after route-based:

```python
    def group(
        self,
        entry_points: list[EntryPointInfo],
        file_imports: dict[str, list[str]],
    ) -> list[WorkflowGroup]:
        """Group entry points by domain and trace related files."""
        if not entry_points:
            return []

        groups: list[WorkflowGroup] = []
        ungrouped = list(entry_points)

        # 1. Route-based grouping for HTTP endpoints
        route_groups = self._group_by_route_prefix(ungrouped)
        groups.extend(route_groups)
        grouped_names = {ep.name for g in route_groups for ep in g.entry_points}
        ungrouped = [ep for ep in ungrouped if ep.name not in grouped_names]

        # 2. File-based grouping for remaining
        file_groups = self._group_by_file(ungrouped)
        groups.extend(file_groups)
        grouped_names = {ep.name for g in file_groups for ep in g.entry_points}
        ungrouped = [ep for ep in ungrouped if ep.name not in grouped_names]

        # Create individual groups for any remaining
        for ep in ungrouped:
            groups.append(
                WorkflowGroup(
                    name=self._humanize_name(ep.name),
                    slug=self._slugify(ep.name),
                    entry_points=[ep],
                    related_files=[ep.file] if ep.file else [],
                    primary_layer="",
                )
            )

        return groups

    def _group_by_file(
        self, entry_points: list[EntryPointInfo]
    ) -> list[WorkflowGroup]:
        """Group entry points by their source file."""
        file_groups: dict[str, list[EntryPointInfo]] = {}

        for ep in entry_points:
            if ep.file:
                if ep.file not in file_groups:
                    file_groups[ep.file] = []
                file_groups[ep.file].append(ep)

        groups = []
        for file_path, eps in file_groups.items():
            # Only create group if multiple entry points in same file
            if len(eps) >= 2:
                name = self._file_to_name(file_path)
                groups.append(
                    WorkflowGroup(
                        name=name,
                        slug=self._slugify(name),
                        entry_points=eps,
                        related_files=[file_path],
                        primary_layer="",
                    )
                )

        return groups

    def _file_to_name(self, file_path: str) -> str:
        """Convert file path to human-readable workflow name."""
        # Get filename without extension
        from pathlib import Path
        name = Path(file_path).stem
        return self._humanize_name(name)
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/poecurt/projects/oya/.worktrees/workflow-refactor/backend && source .venv/bin/activate && pytest tests/test_workflow_generator.py::TestWorkflowGrouper::test_groups_by_file_path -v`

Expected: PASS

**Step 5: Commit**

```bash
cd /Users/poecurt/projects/oya/.worktrees/workflow-refactor && git add backend/src/oya/generation/workflows.py backend/tests/test_workflow_generator.py && git commit -m "feat(workflows): add file-based grouping to WorkflowGrouper"
```

---

## Task 4: Add Name Prefix Grouping to WorkflowGrouper

**Files:**
- Modify: `backend/src/oya/generation/workflows.py`
- Test: `backend/tests/test_workflow_generator.py`

**Step 1: Write the failing test**

Add to `TestWorkflowGrouper` class:

```python
    def test_groups_by_name_prefix(self):
        """Groups entry points by common function name prefix."""
        grouper = WorkflowGrouper()

        # These are in different files but share naming pattern
        entry_points = [
            EntryPointInfo(name="sync_users", entry_type="function", file="jobs/user_sync.py", description=""),
            EntryPointInfo(name="sync_orders", entry_type="function", file="jobs/order_sync.py", description=""),
            EntryPointInfo(name="sync_inventory", entry_type="function", file="jobs/inventory_sync.py", description=""),
            EntryPointInfo(name="cleanup_temp", entry_type="function", file="jobs/cleanup.py", description=""),
        ]

        groups = grouper.group(entry_points, file_imports={})

        # Should have sync group (3) and cleanup as individual
        sync_group = next((g for g in groups if "sync" in g.slug.lower()), None)
        assert sync_group is not None
        assert len(sync_group.entry_points) == 3
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/poecurt/projects/oya/.worktrees/workflow-refactor/backend && source .venv/bin/activate && pytest tests/test_workflow_generator.py::TestWorkflowGrouper::test_groups_by_name_prefix -v`

Expected: FAIL (creates 4 individual groups)

**Step 3: Update implementation**

Add to `WorkflowGrouper.group()` after file-based grouping:

```python
        # 3. Name-prefix grouping for remaining
        name_groups = self._group_by_name_prefix(ungrouped)
        groups.extend(name_groups)
        grouped_names = {ep.name for g in name_groups for ep in g.entry_points}
        ungrouped = [ep for ep in ungrouped if ep.name not in grouped_names]
```

Add the method:

```python
    def _group_by_name_prefix(
        self, entry_points: list[EntryPointInfo]
    ) -> list[WorkflowGroup]:
        """Group entry points by common function name prefix."""
        # Common prefixes that indicate related functionality
        COMMON_PREFIXES = [
            "sync_", "export_", "import_", "process_", "handle_",
            "create_", "update_", "delete_", "get_", "list_",
            "validate_", "send_", "fetch_", "load_", "save_",
        ]

        prefix_groups: dict[str, list[EntryPointInfo]] = {}

        for ep in entry_points:
            for prefix in COMMON_PREFIXES:
                if ep.name.startswith(prefix):
                    # Use prefix without underscore as group key
                    key = prefix.rstrip("_")
                    if key not in prefix_groups:
                        prefix_groups[key] = []
                    prefix_groups[key].append(ep)
                    break

        groups = []
        for prefix, eps in prefix_groups.items():
            # Only create group if multiple entry points share the prefix
            if len(eps) >= 2:
                name = f"{prefix.title()} Operations"
                groups.append(
                    WorkflowGroup(
                        name=name,
                        slug=self._slugify(name),
                        entry_points=eps,
                        related_files=list({ep.file for ep in eps if ep.file}),
                        primary_layer="",
                    )
                )

        return groups
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/poecurt/projects/oya/.worktrees/workflow-refactor/backend && source .venv/bin/activate && pytest tests/test_workflow_generator.py::TestWorkflowGrouper::test_groups_by_name_prefix -v`

Expected: PASS

**Step 5: Commit**

```bash
cd /Users/poecurt/projects/oya/.worktrees/workflow-refactor && git add backend/src/oya/generation/workflows.py backend/tests/test_workflow_generator.py && git commit -m "feat(workflows): add name-prefix grouping to WorkflowGrouper"
```

---

## Task 5: Add Type-Based Fallback Grouping

**Files:**
- Modify: `backend/src/oya/generation/workflows.py`
- Test: `backend/tests/test_workflow_generator.py`

**Step 1: Write the failing test**

Add to `TestWorkflowGrouper` class:

```python
    def test_groups_by_type_fallback(self):
        """Groups remaining entry points by type as fallback."""
        grouper = WorkflowGrouper()

        entry_points = [
            EntryPointInfo(name="init", entry_type="cli_command", file="cli/init.py", description="init"),
            EntryPointInfo(name="build", entry_type="cli_command", file="cli/build.py", description="build"),
            EntryPointInfo(name="main", entry_type="main_function", file="main.py", description=""),
        ]

        groups = grouper.group(entry_points, file_imports={})

        # CLI commands should be grouped together, main is separate
        cli_group = next((g for g in groups if "cli" in g.slug.lower()), None)
        assert cli_group is not None
        assert len(cli_group.entry_points) == 2
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/poecurt/projects/oya/.worktrees/workflow-refactor/backend && source .venv/bin/activate && pytest tests/test_workflow_generator.py::TestWorkflowGrouper::test_groups_by_type_fallback -v`

Expected: FAIL (creates 3 individual groups)

**Step 3: Update implementation**

Replace the individual group creation in `group()` with type-based fallback:

```python
        # 4. Type-based fallback for remaining
        type_groups = self._group_by_type(ungrouped)
        groups.extend(type_groups)
        grouped_names = {ep.name for g in type_groups for ep in g.entry_points}
        ungrouped = [ep for ep in ungrouped if ep.name not in grouped_names]

        # Create individual groups for any still remaining
        for ep in ungrouped:
            groups.append(
                WorkflowGroup(
                    name=self._humanize_name(ep.name),
                    slug=self._slugify(ep.name),
                    entry_points=[ep],
                    related_files=[ep.file] if ep.file else [],
                    primary_layer="",
                )
            )

        return groups
```

Add the method:

```python
    def _group_by_type(
        self, entry_points: list[EntryPointInfo]
    ) -> list[WorkflowGroup]:
        """Group entry points by their type as fallback."""
        TYPE_NAMES = {
            "cli_command": "CLI Commands",
            "api_route": "API Routes",
            "main_function": "Main Entry Points",
            "background_task": "Background Tasks",
        }

        type_groups: dict[str, list[EntryPointInfo]] = {}

        for ep in entry_points:
            entry_type = ep.entry_type
            if entry_type not in type_groups:
                type_groups[entry_type] = []
            type_groups[entry_type].append(ep)

        groups = []
        for entry_type, eps in type_groups.items():
            # Only create group if multiple entry points of same type
            if len(eps) >= 2:
                name = TYPE_NAMES.get(entry_type, f"{entry_type.title()} Workflows")
                groups.append(
                    WorkflowGroup(
                        name=name,
                        slug=self._slugify(name),
                        entry_points=eps,
                        related_files=list({ep.file for ep in eps if ep.file}),
                        primary_layer="",
                    )
                )

        return groups
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/poecurt/projects/oya/.worktrees/workflow-refactor/backend && source .venv/bin/activate && pytest tests/test_workflow_generator.py::TestWorkflowGrouper::test_groups_by_type_fallback -v`

Expected: PASS

**Step 5: Commit**

```bash
cd /Users/poecurt/projects/oya/.worktrees/workflow-refactor && git add backend/src/oya/generation/workflows.py backend/tests/test_workflow_generator.py && git commit -m "feat(workflows): add type-based fallback grouping"
```

---

## Task 6: Add Related Files Tracing via Imports

**Files:**
- Modify: `backend/src/oya/generation/workflows.py`
- Test: `backend/tests/test_workflow_generator.py`

**Step 1: Write the failing test**

Add to `TestWorkflowGrouper` class:

```python
    def test_traces_related_files_via_imports(self):
        """Traces related files through import graph."""
        grouper = WorkflowGrouper()

        entry_points = [
            EntryPointInfo(name="get_users", entry_type="api_route", file="api/users.py", description="/users"),
        ]

        file_imports = {
            "api/users.py": ["services/user_service.py", "external_lib"],
            "services/user_service.py": ["repositories/user_repo.py", "models/user.py"],
            "repositories/user_repo.py": ["db/connection.py"],
        }

        groups = grouper.group(entry_points, file_imports)

        assert len(groups) == 1
        related = groups[0].related_files

        # Should include entry point file + depth-1 + depth-2 (but not depth-3)
        assert "api/users.py" in related
        assert "services/user_service.py" in related
        assert "repositories/user_repo.py" in related
        assert "models/user.py" in related
        # Depth 3 should not be included
        assert "db/connection.py" not in related
        # External libs should not be included
        assert "external_lib" not in related
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/poecurt/projects/oya/.worktrees/workflow-refactor/backend && source .venv/bin/activate && pytest tests/test_workflow_generator.py::TestWorkflowGrouper::test_traces_related_files_via_imports -v`

Expected: FAIL (related_files only contains api/users.py)

**Step 3: Update implementation**

Add to `WorkflowGrouper.group()` after all grouping, before return:

```python
        # Trace related files for all groups
        for group in groups:
            group.related_files = self._find_related_files(
                group.entry_points, file_imports
            )

        return groups
```

Add the method:

```python
    def _find_related_files(
        self,
        entry_points: list[EntryPointInfo],
        file_imports: dict[str, list[str]],
        max_depth: int = 2,
    ) -> list[str]:
        """Trace imports from entry point files to find related code.

        Args:
            entry_points: Entry points in this workflow group.
            file_imports: Map of file -> list of imported files.
            max_depth: How deep to trace (2 = handler -> service -> repo).

        Returns:
            Deduplicated list of related file paths.
        """
        seed_files = {ep.file for ep in entry_points if ep.file}
        related = set(seed_files)
        frontier = set(seed_files)

        for _ in range(max_depth):
            next_frontier: set[str] = set()
            for file in frontier:
                imports = file_imports.get(file, [])
                # Filter to internal imports only (files that exist in our import map
                # or look like relative paths)
                internal = [
                    f for f in imports
                    if f in file_imports or "/" in f or f.endswith(".py")
                ]
                next_frontier.update(internal)
            new_files = next_frontier - related
            related.update(new_files)
            frontier = new_files

        return sorted(related)
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/poecurt/projects/oya/.worktrees/workflow-refactor/backend && source .venv/bin/activate && pytest tests/test_workflow_generator.py::TestWorkflowGrouper::test_traces_related_files_via_imports -v`

Expected: PASS

**Step 5: Commit**

```bash
cd /Users/poecurt/projects/oya/.worktrees/workflow-refactor && git add backend/src/oya/generation/workflows.py backend/tests/test_workflow_generator.py && git commit -m "feat(workflows): add related files tracing via imports"
```

---

## Task 7: Add Primary Layer Detection

**Files:**
- Modify: `backend/src/oya/generation/workflows.py`
- Test: `backend/tests/test_workflow_generator.py`

**Step 1: Write the failing test**

Add to `TestWorkflowGrouper` class:

```python
    def test_determines_primary_layer(self):
        """Determines primary layer from entry point files."""
        from oya.generation.summaries import SynthesisMap, LayerInfo

        grouper = WorkflowGrouper()

        entry_points = [
            EntryPointInfo(name="get_users", entry_type="api_route", file="api/users.py", description="/users"),
        ]

        synthesis_map = SynthesisMap(
            layers={
                "api": LayerInfo(name="api", purpose="HTTP endpoints", files=["api/users.py", "api/orders.py"]),
                "domain": LayerInfo(name="domain", purpose="Business logic", files=["services/user_service.py"]),
            }
        )

        groups = grouper.group(entry_points, file_imports={}, synthesis_map=synthesis_map)

        assert len(groups) == 1
        assert groups[0].primary_layer == "api"
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/poecurt/projects/oya/.worktrees/workflow-refactor/backend && source .venv/bin/activate && pytest tests/test_workflow_generator.py::TestWorkflowGrouper::test_determines_primary_layer -v`

Expected: FAIL (TypeError or primary_layer is empty)

**Step 3: Update implementation**

Update `WorkflowGrouper.group()` signature and add synthesis_map parameter:

```python
    def group(
        self,
        entry_points: list[EntryPointInfo],
        file_imports: dict[str, list[str]],
        synthesis_map: SynthesisMap | None = None,
    ) -> list[WorkflowGroup]:
```

Update the related files loop to also determine primary layer:

```python
        # Trace related files and determine primary layer for all groups
        for group in groups:
            group.related_files = self._find_related_files(
                group.entry_points, file_imports
            )
            if synthesis_map:
                group.primary_layer = self._determine_primary_layer(
                    group.entry_points, synthesis_map
                )

        return groups
```

Add the method:

```python
    def _determine_primary_layer(
        self,
        entry_points: list[EntryPointInfo],
        synthesis_map: SynthesisMap,
    ) -> str:
        """Determine the primary architectural layer for entry points.

        Returns the layer that contains the most entry point files.
        """
        layer_counts: dict[str, int] = {}

        for ep in entry_points:
            if not ep.file:
                continue
            for layer_name, layer_info in synthesis_map.layers.items():
                if ep.file in layer_info.files:
                    layer_counts[layer_name] = layer_counts.get(layer_name, 0) + 1
                    break

        if not layer_counts:
            return ""

        # Return layer with most entry points
        return max(layer_counts, key=lambda k: layer_counts[k])
```

Also add the import at the top of the file if not present:

```python
from oya.generation.summaries import EntryPointInfo, SynthesisMap
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/poecurt/projects/oya/.worktrees/workflow-refactor/backend && source .venv/bin/activate && pytest tests/test_workflow_generator.py::TestWorkflowGrouper::test_determines_primary_layer -v`

Expected: PASS

**Step 5: Commit**

```bash
cd /Users/poecurt/projects/oya/.worktrees/workflow-refactor && git add backend/src/oya/generation/workflows.py backend/tests/test_workflow_generator.py && git commit -m "feat(workflows): add primary layer detection from SynthesisMap"
```

---

## Task 8: Update WorkflowGenerator Signature

**Files:**
- Modify: `backend/src/oya/generation/workflows.py`
- Test: `backend/tests/test_workflow_generator.py`

**Step 1: Write the failing test**

Update `TestWorkflowGenerator` class - modify the existing test:

```python
class TestWorkflowGenerator:
    """Tests for workflow generation."""

    @pytest.fixture
    def generator(self, mock_llm_client, mock_repo):
        """Create workflow generator."""
        return WorkflowGenerator(
            llm_client=mock_llm_client,
            repo=mock_repo,
        )

    @pytest.mark.asyncio
    async def test_generates_workflow_page_with_full_context(self, generator, mock_llm_client):
        """Generates workflow markdown with full architectural context."""
        from oya.generation.summaries import SynthesisMap, LayerInfo, ComponentInfo

        workflow_group = WorkflowGroup(
            name="Users API",
            slug="users-api",
            entry_points=[
                EntryPointInfo(name="get_users", entry_type="api_route", file="api/users.py", description="/users"),
            ],
            related_files=["api/users.py", "services/user_service.py"],
            primary_layer="api",
        )

        synthesis_map = SynthesisMap(
            layers={"api": LayerInfo(name="api", purpose="HTTP endpoints", files=["api/users.py"])},
            key_components=[ComponentInfo(name="UserService", file="services/user_service.py", role="User operations", layer="domain")],
            project_summary="A user management system",
            layer_interactions="API calls domain services",
        )

        symbols = []
        file_imports = {}

        result = await generator.generate(
            workflow_group=workflow_group,
            synthesis_map=synthesis_map,
            symbols=symbols,
            file_imports=file_imports,
        )

        assert result.page_type == "workflow"
        assert result.path == "workflows/users-api.md"
        mock_llm_client.generate.assert_called_once()

        # Verify the prompt includes synthesis context
        call_args = mock_llm_client.generate.call_args
        prompt = call_args.kwargs.get("prompt", call_args.args[0] if call_args.args else "")
        assert "Users API" in prompt
        assert "api" in prompt.lower()  # Layer info
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/poecurt/projects/oya/.worktrees/workflow-refactor/backend && source .venv/bin/activate && pytest tests/test_workflow_generator.py::TestWorkflowGenerator::test_generates_workflow_page_with_full_context -v`

Expected: FAIL (TypeError - unexpected keyword arguments)

**Step 3: Update implementation**

Update `WorkflowGenerator.generate()`:

```python
    async def generate(
        self,
        workflow_group: WorkflowGroup,
        synthesis_map: SynthesisMap,
        symbols: list[ParsedSymbol],
        file_imports: dict[str, list[str]],
    ) -> GeneratedPage:
        """Generate a workflow documentation page with full architectural context.

        Args:
            workflow_group: The workflow group to document.
            synthesis_map: Full synthesis context (layers, components, etc.)
            symbols: Parsed symbols for code context.
            file_imports: Import relationships for dependency info.

        Returns:
            GeneratedPage with workflow content.
        """
        repo_name = self.repo.path.name

        # Build context for the prompt
        context = self._build_context(workflow_group, synthesis_map, symbols)

        prompt = get_workflow_prompt(
            repo_name=repo_name,
            workflow_name=workflow_group.name,
            entry_points=[
                f"{ep.name} ({ep.entry_type}) - {ep.description or 'N/A'} in {ep.file}"
                for ep in workflow_group.entry_points
            ],
            related_files=workflow_group.related_files,
            code_context=context.get("code_context", ""),
            synthesis_map=synthesis_map,
        )

        content = await self.llm_client.generate(
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
        )

        word_count = len(content.split())

        return GeneratedPage(
            content=content,
            page_type="workflow",
            path=f"workflows/{workflow_group.slug}.md",
            word_count=word_count,
        )

    def _build_context(
        self,
        workflow_group: WorkflowGroup,
        synthesis_map: SynthesisMap,
        symbols: list[ParsedSymbol],
    ) -> dict:
        """Build prompt context from available data."""
        # Filter symbols to related files
        related_symbols = [
            s for s in symbols
            if s.metadata.get("file") in workflow_group.related_files
        ]

        # Format code context from symbols
        code_context = ""
        for symbol in related_symbols[:20]:  # Limit to avoid huge prompts
            file = symbol.metadata.get("file", "")
            code_context += f"- {symbol.name} ({symbol.symbol_type.value}) in {file}\n"

        return {
            "code_context": code_context or "No specific code context available.",
        }
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/poecurt/projects/oya/.worktrees/workflow-refactor/backend && source .venv/bin/activate && pytest tests/test_workflow_generator.py::TestWorkflowGenerator::test_generates_workflow_page_with_full_context -v`

Expected: PASS

**Step 5: Commit**

```bash
cd /Users/poecurt/projects/oya/.worktrees/workflow-refactor && git add backend/src/oya/generation/workflows.py backend/tests/test_workflow_generator.py && git commit -m "feat(workflows): update WorkflowGenerator to accept full context"
```

---

## Task 9: Update Prompt Template

**Files:**
- Modify: `backend/src/oya/generation/prompts.py`
- Test: `backend/tests/test_workflow_generator.py`

**Step 1: Write the failing test**

Add a new test to verify the prompt includes all context:

```python
class TestWorkflowPrompt:
    """Tests for workflow prompt generation."""

    def test_workflow_prompt_includes_synthesis_context(self):
        """Verifies prompt includes project summary and layer interactions."""
        from oya.generation.prompts import get_workflow_prompt
        from oya.generation.summaries import SynthesisMap, LayerInfo

        synthesis_map = SynthesisMap(
            layers={"api": LayerInfo(name="api", purpose="HTTP endpoints", files=[])},
            project_summary="A user management system for enterprises",
            layer_interactions="API layer calls domain services which access repositories",
        )

        prompt = get_workflow_prompt(
            repo_name="myproject",
            workflow_name="Users API",
            entry_points=["get_users (api_route) in api/users.py"],
            related_files=["api/users.py"],
            code_context="def get_users(): pass",
            synthesis_map=synthesis_map,
        )

        assert "user management system" in prompt.lower()
        assert "layer" in prompt.lower()
        assert "Users API" in prompt
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/poecurt/projects/oya/.worktrees/workflow-refactor/backend && source .venv/bin/activate && pytest tests/test_workflow_generator.py::TestWorkflowPrompt::test_workflow_prompt_includes_synthesis_context -v`

Expected: FAIL (project_summary not in prompt)

**Step 3: Update implementation**

Update `WORKFLOW_SYNTHESIS_TEMPLATE` in `backend/src/oya/generation/prompts.py`:

```python
WORKFLOW_SYNTHESIS_TEMPLATE = PromptTemplate(
    """Generate a workflow documentation page for the "{workflow_name}" workflow in "{repo_name}".

## Project Context
{project_summary}

## Entry Points
{entry_points}

## Related Files
{related_files}

## System Layers
{layers}

## Layer Interactions
{layer_interactions}

## Key Components
{key_components}

## Layer Dependencies
{dependency_graph}

## Code Context
{code_context}

---

Create workflow documentation that includes:
1. **Overview**: What this workflow accomplishes and its role in the system (2-3 sentences)
2. **Entry Points**: How the workflow is triggered (routes, CLI commands, etc.)
3. **Execution Flow**: Step-by-step walkthrough showing how data moves through layers
4. **Key Components Involved**: Which components participate and their roles
5. **Error Handling**: How errors are handled at each layer
6. **Data Flow**: What data moves through the system and how it transforms

Format the output as clean Markdown suitable for a wiki page."""
)
```

Update `get_workflow_prompt()` to include the new fields:

```python
def get_workflow_prompt(
    repo_name: str,
    workflow_name: str,
    entry_points: list[str],
    related_files: list[str],
    code_context: str,
    synthesis_map: Any | None = None,
) -> str:
    """Generate a prompt for creating a workflow page."""
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
            project_summary=synthesis_map.project_summary or "No project summary available.",
            layers=_format_synthesis_layers(synthesis_map),
            layer_interactions=synthesis_map.layer_interactions or "No layer interaction info available.",
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

**Step 4: Run test to verify it passes**

Run: `cd /Users/poecurt/projects/oya/.worktrees/workflow-refactor/backend && source .venv/bin/activate && pytest tests/test_workflow_generator.py::TestWorkflowPrompt::test_workflow_prompt_includes_synthesis_context -v`

Expected: PASS

**Step 5: Commit**

```bash
cd /Users/poecurt/projects/oya/.worktrees/workflow-refactor && git add backend/src/oya/generation/prompts.py backend/tests/test_workflow_generator.py && git commit -m "feat(prompts): update workflow template with full synthesis context"
```

---

## Task 10: Update Orchestrator to Use New Classes

**Files:**
- Modify: `backend/src/oya/generation/orchestrator.py`
- Test: `backend/tests/test_orchestrator.py` (or integration test)

**Step 1: Write the failing test**

Add to test file (create if needed):

```python
# In backend/tests/test_orchestrator_workflows.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

from oya.generation.orchestrator import WikiOrchestrator
from oya.generation.summaries import SynthesisMap, LayerInfo, EntryPointInfo


class TestOrchestratorWorkflows:
    """Tests for orchestrator workflow generation."""

    @pytest.fixture
    def mock_orchestrator(self, tmp_path):
        """Create orchestrator with mocked dependencies."""
        wiki_path = tmp_path / ".oyawiki"
        wiki_path.mkdir()

        mock_llm = AsyncMock()
        mock_llm.generate.return_value = "# Workflow\n\nGenerated content."

        mock_repo = MagicMock()
        mock_repo.path = tmp_path

        orchestrator = WikiOrchestrator(
            repo=mock_repo,
            llm_client=mock_llm,
            wiki_path=wiki_path,
        )

        return orchestrator

    @pytest.mark.asyncio
    async def test_run_workflows_uses_synthesis_entry_points(self, mock_orchestrator):
        """Verifies _run_workflows uses entry points from SynthesisMap."""
        synthesis_map = SynthesisMap(
            layers={"api": LayerInfo(name="api", purpose="HTTP", files=["api/users.py"])},
            entry_points=[
                EntryPointInfo(name="get_users", entry_type="api_route", file="api/users.py", description="/users"),
                EntryPointInfo(name="create_user", entry_type="api_route", file="api/users.py", description="/users"),
            ],
        )

        analysis = {
            "symbols": [],  # Should NOT be used for entry point discovery
            "file_contents": {"api/users.py": "def get_users(): pass"},
            "file_imports": {},
        }

        pages = await mock_orchestrator._run_workflows(
            analysis=analysis,
            progress_callback=None,
            synthesis_map=synthesis_map,
        )

        # Should generate workflow pages from synthesis_map.entry_points
        assert len(pages) >= 1
        # Entry points should be grouped (both are /users routes)
        assert any("users" in p.path.lower() for p in pages)
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/poecurt/projects/oya/.worktrees/workflow-refactor/backend && source .venv/bin/activate && pytest tests/test_orchestrator_workflows.py::TestOrchestratorWorkflows::test_run_workflows_uses_synthesis_entry_points -v`

Expected: FAIL (still uses WorkflowDiscovery instead of SynthesisMap entry points)

**Step 3: Update implementation**

Update `_run_workflows` in `backend/src/oya/generation/orchestrator.py`:

```python
    async def _run_workflows(
        self,
        analysis: dict,
        progress_callback: ProgressCallback | None = None,
        synthesis_map: SynthesisMap | None = None,
    ) -> list[GeneratedPage]:
        """Run workflow generation phase.

        Uses entry points from SynthesisMap (computed during synthesis phase)
        and groups them by domain using pattern heuristics.

        Args:
            analysis: Analysis results.
            progress_callback: Optional async callback for progress updates.
            synthesis_map: SynthesisMap containing entry points and context.

        Returns:
            List of generated workflow pages.
        """
        pages = []

        # Use entry points from synthesis_map (already discovered during synthesis)
        if not synthesis_map or not synthesis_map.entry_points:
            logger.info("No entry points in synthesis map, skipping workflow generation")
            return pages

        # Group entry points by domain
        grouper = WorkflowGrouper()
        workflow_groups = grouper.group(
            entry_points=synthesis_map.entry_points,
            file_imports=analysis.get("file_imports", {}),
            synthesis_map=synthesis_map,
        )

        total_workflows = len(workflow_groups)

        # Emit initial progress
        await self._emit_progress(
            progress_callback,
            GenerationProgress(
                phase=GenerationPhase.WORKFLOWS,
                step=0,
                total_steps=total_workflows,
                message=f"Generating workflow pages (0/{total_workflows})...",
            ),
        )

        # Generate page for each workflow group
        for idx, workflow_group in enumerate(workflow_groups):
            page = await self.workflow_generator.generate(
                workflow_group=workflow_group,
                synthesis_map=synthesis_map,
                symbols=analysis.get("symbols", []),
                file_imports=analysis.get("file_imports", {}),
            )
            pages.append(page)

            # Emit progress after each workflow
            await self._emit_progress(
                progress_callback,
                GenerationProgress(
                    phase=GenerationPhase.WORKFLOWS,
                    step=idx + 1,
                    total_steps=total_workflows,
                    message=f"Generated {idx + 1}/{total_workflows} workflows...",
                ),
            )

        return pages
```

Update imports at top of file:

```python
from oya.generation.workflows import (
    WorkflowGrouper,
    WorkflowGenerator,
    extract_entry_point_description,
)
```

Remove the `WorkflowDiscovery` import and `self.workflow_discovery` initialization from `__init__`.

**Step 4: Run test to verify it passes**

Run: `cd /Users/poecurt/projects/oya/.worktrees/workflow-refactor/backend && source .venv/bin/activate && pytest tests/test_orchestrator_workflows.py::TestOrchestratorWorkflows::test_run_workflows_uses_synthesis_entry_points -v`

Expected: PASS

**Step 5: Commit**

```bash
cd /Users/poecurt/projects/oya/.worktrees/workflow-refactor && git add backend/src/oya/generation/orchestrator.py backend/tests/test_orchestrator_workflows.py && git commit -m "feat(orchestrator): update _run_workflows to use WorkflowGrouper"
```

---

## Task 11: Clean Up - Remove WorkflowDiscovery

**Files:**
- Modify: `backend/src/oya/generation/workflows.py`
- Modify: `backend/src/oya/generation/orchestrator.py`
- Modify: `backend/tests/test_workflow_generator.py`

**Step 1: Verify existing tests still pass**

Run: `cd /Users/poecurt/projects/oya/.worktrees/workflow-refactor/backend && source .venv/bin/activate && pytest tests/test_workflow_generator.py -v`

Check which tests use `WorkflowDiscovery` and will need updating.

**Step 2: Update tests that use WorkflowDiscovery**

The old `TestWorkflowDiscovery` tests should be removed or converted to test entry point logic in synthesis. For now, remove the class since entry point discovery happens in synthesis:

```python
# Remove or comment out TestWorkflowDiscovery class
# Entry point discovery is now tested as part of synthesis phase
```

**Step 3: Remove WorkflowDiscovery from workflows.py**

Delete the following from `backend/src/oya/generation/workflows.py`:
- `DiscoveredWorkflow` dataclass
- `WorkflowDiscovery` class

Keep:
- `extract_entry_point_description` function (still used by synthesis)
- `WorkflowGroup` dataclass (new)
- `WorkflowGrouper` class (new)
- `WorkflowGenerator` class (updated)

**Step 4: Update orchestrator imports**

Ensure `backend/src/oya/generation/orchestrator.py` only imports what's needed:

```python
from oya.generation.workflows import (
    WorkflowGrouper,
    WorkflowGenerator,
    extract_entry_point_description,
)
```

Remove any reference to `WorkflowDiscovery` or `DiscoveredWorkflow`.

**Step 5: Run all tests**

Run: `cd /Users/poecurt/projects/oya/.worktrees/workflow-refactor/backend && source .venv/bin/activate && pytest -v`

Expected: All tests PASS

**Step 6: Commit**

```bash
cd /Users/poecurt/projects/oya/.worktrees/workflow-refactor && git add backend/src/oya/generation/workflows.py backend/src/oya/generation/orchestrator.py backend/tests/test_workflow_generator.py && git commit -m "refactor(workflows): remove deprecated WorkflowDiscovery class"
```

---

## Task 12: Final Integration Test

**Files:**
- Test: `backend/tests/test_orchestrator_workflows.py`

**Step 1: Write integration test**

Add comprehensive integration test:

```python
    @pytest.mark.asyncio
    async def test_workflow_generation_end_to_end(self, mock_orchestrator):
        """Full integration test for workflow generation."""
        synthesis_map = SynthesisMap(
            layers={
                "api": LayerInfo(name="api", purpose="HTTP endpoints", files=["api/users.py", "api/orders.py"]),
                "domain": LayerInfo(name="domain", purpose="Business logic", files=["services/user_service.py"]),
            },
            key_components=[],
            entry_points=[
                # Users API group
                EntryPointInfo(name="get_users", entry_type="api_route", file="api/users.py", description="/api/users"),
                EntryPointInfo(name="create_user", entry_type="api_route", file="api/users.py", description="/api/users"),
                # Orders API group
                EntryPointInfo(name="get_orders", entry_type="api_route", file="api/orders.py", description="/api/orders"),
                # CLI commands
                EntryPointInfo(name="init", entry_type="cli_command", file="cli/main.py", description="init"),
                EntryPointInfo(name="build", entry_type="cli_command", file="cli/main.py", description="build"),
            ],
            project_summary="E-commerce platform",
            layer_interactions="API calls domain services",
        )

        analysis = {
            "symbols": [],
            "file_contents": {
                "api/users.py": "def get_users(): pass",
                "api/orders.py": "def get_orders(): pass",
                "cli/main.py": "def init(): pass",
            },
            "file_imports": {
                "api/users.py": ["services/user_service.py"],
            },
        }

        pages = await mock_orchestrator._run_workflows(
            analysis=analysis,
            progress_callback=None,
            synthesis_map=synthesis_map,
        )

        # Should have 3 groups: users-api, orders-api, cli (or main.py)
        assert len(pages) >= 2

        # Check page paths are correctly slugified
        paths = [p.path for p in pages]
        assert all(p.startswith("workflows/") for p in paths)
        assert all(p.endswith(".md") for p in paths)
```

**Step 2: Run the test**

Run: `cd /Users/poecurt/projects/oya/.worktrees/workflow-refactor/backend && source .venv/bin/activate && pytest tests/test_orchestrator_workflows.py -v`

Expected: All tests PASS

**Step 3: Run full test suite**

Run: `cd /Users/poecurt/projects/oya/.worktrees/workflow-refactor/backend && source .venv/bin/activate && pytest`

Expected: All 500+ tests PASS

**Step 4: Commit**

```bash
cd /Users/poecurt/projects/oya/.worktrees/workflow-refactor && git add backend/tests/test_orchestrator_workflows.py && git commit -m "test(workflows): add end-to-end integration test"
```

---

## Summary

| Task | Description | Files |
|------|-------------|-------|
| 1 | Create WorkflowGroup dataclass | workflows.py, test_workflow_generator.py |
| 2 | WorkflowGrouper with route-based grouping | workflows.py, test_workflow_generator.py |
| 3 | Add file-based grouping | workflows.py, test_workflow_generator.py |
| 4 | Add name-prefix grouping | workflows.py, test_workflow_generator.py |
| 5 | Add type-based fallback | workflows.py, test_workflow_generator.py |
| 6 | Add related files tracing | workflows.py, test_workflow_generator.py |
| 7 | Add primary layer detection | workflows.py, test_workflow_generator.py |
| 8 | Update WorkflowGenerator signature | workflows.py, test_workflow_generator.py |
| 9 | Update prompt template | prompts.py, test_workflow_generator.py |
| 10 | Update orchestrator | orchestrator.py, test_orchestrator_workflows.py |
| 11 | Clean up deprecated code | workflows.py, orchestrator.py, tests |
| 12 | Integration test | test_orchestrator_workflows.py |

**Total commits:** 12
**Estimated test coverage:** All new code tested via TDD
