# backend/src/oya/generation/workflows.py
"""Workflow discovery and generation."""

import re
from dataclasses import dataclass, field
from pathlib import Path

from oya.generation.overview import GeneratedPage
from oya.generation.prompts import SYSTEM_PROMPT, get_workflow_prompt
from oya.generation.summaries import EntryPointInfo, SynthesisMap
from oya.parsing.models import ParsedSymbol, SymbolType

# Entry point detection constants
ENTRY_POINT_DECORATORS: set[str] = {
    # Click/Typer CLI
    "click.command",
    "click.group",
    "typer.command",
    # FastAPI/Flask/Starlette routes
    "app.route",
    "app.get",
    "app.post",
    "app.put",
    "app.delete",
    "app.patch",
    "router.route",
    "router.get",
    "router.post",
    "router.put",
    "router.delete",
    "router.patch",
    # Flask
    "flask.route",
    # Django
    "api_view",
    "action",
}

ENTRY_POINT_NAMES: set[str] = {
    "main",
    "__main__",
    "run",
    "start",
    "serve",
    "execute",
}


def _is_entry_point(symbol: ParsedSymbol) -> bool:
    """Check if a symbol is an entry point.

    Args:
        symbol: ParsedSymbol object.

    Returns:
        True if the symbol is an entry point.
    """
    # Check symbol type
    if symbol.symbol_type in (SymbolType.ROUTE, SymbolType.CLI_COMMAND):
        return True

    # Check decorators
    for decorator in symbol.decorators:
        if decorator in ENTRY_POINT_DECORATORS:
            return True
        # Also check partial matches (e.g., "app.get" in "@app.get('/users')")
        for entry_decorator in ENTRY_POINT_DECORATORS:
            if entry_decorator in decorator:
                return True

    # Check function name
    if symbol.name in ENTRY_POINT_NAMES:
        return True

    return False


def find_entry_points(symbols: list[ParsedSymbol]) -> list[ParsedSymbol]:
    """Find entry points from a list of symbols.

    Args:
        symbols: List of ParsedSymbol objects from parsing.

    Returns:
        List of symbols that are entry points.
    """
    return [s for s in symbols if _is_entry_point(s)]


def extract_entry_point_description(symbol: ParsedSymbol) -> str:
    """Extract description from an entry point symbol.

    For routes: extracts the path (e.g., "/users" from "@app.get('/users')").
    For CLI commands: extracts the command name.
    For main functions: returns empty string.

    Args:
        symbol: ParsedSymbol representing an entry point.

    Returns:
        Description string (route path, CLI command, or empty).
    """
    # Check decorators for route paths or CLI commands
    for decorator in symbol.decorators:
        # Route pattern: @app.get('/path') or @router.post("/path")
        route_match = re.search(r"\.(get|post|put|delete|patch)\(['\"]([^'\"]+)['\"]", decorator)
        if route_match:
            return route_match.group(2)

        # CLI command pattern: @click.command('name') or @typer.command("name")
        cli_match = re.search(r"\.command\(['\"]([^'\"]+)['\"]", decorator)
        if cli_match:
            return cli_match.group(1)

    return ""


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
        synthesis_map: SynthesisMap | None = None,
    ) -> list[WorkflowGroup]:
        """Group entry points by domain and trace related files.

        Args:
            entry_points: List of EntryPointInfo from SynthesisMap.
            file_imports: Map of file paths to their imports.
            synthesis_map: Optional SynthesisMap for determining primary layers.

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

        # 2. File-based grouping for remaining
        file_groups = self._group_by_file(ungrouped)
        groups.extend(file_groups)
        grouped_names = {ep.name for g in file_groups for ep in g.entry_points}
        ungrouped = [ep for ep in ungrouped if ep.name not in grouped_names]

        # 3. Name-prefix grouping for remaining
        name_groups = self._group_by_name_prefix(ungrouped)
        groups.extend(name_groups)
        grouped_names = {ep.name for g in name_groups for ep in g.entry_points}
        ungrouped = [ep for ep in ungrouped if ep.name not in grouped_names]

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

        # Trace related files and determine primary layer for all groups
        for group in groups:
            group.related_files = self._find_related_files(group.entry_points, file_imports)
            if synthesis_map:
                group.primary_layer = self._determine_primary_layer(
                    group.entry_points, synthesis_map
                )

        return groups

    def _group_by_route_prefix(self, entry_points: list[EntryPointInfo]) -> list[WorkflowGroup]:
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
                path = path[len(prefix) :]
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

    def _group_by_file(self, entry_points: list[EntryPointInfo]) -> list[WorkflowGroup]:
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

    def _group_by_name_prefix(self, entry_points: list[EntryPointInfo]) -> list[WorkflowGroup]:
        """Group entry points by common function name prefix."""
        # Common prefixes that indicate related functionality
        COMMON_PREFIXES = [
            "sync_",
            "export_",
            "import_",
            "process_",
            "handle_",
            "create_",
            "update_",
            "delete_",
            "get_",
            "list_",
            "validate_",
            "send_",
            "fetch_",
            "load_",
            "save_",
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

    def _group_by_type(self, entry_points: list[EntryPointInfo]) -> list[WorkflowGroup]:
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

    def _file_to_name(self, file_path: str) -> str:
        """Convert file path to human-readable workflow name."""
        # Get filename without extension
        name = Path(file_path).stem
        return self._humanize_name(name)

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
                    f for f in imports if f in file_imports or "/" in f or f.endswith(".py")
                ]
                next_frontier.update(internal)
            new_files = next_frontier - related
            related.update(new_files)
            frontier = new_files

        return sorted(related)

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


class WorkflowGenerator:
    """Generates workflow documentation pages.

    Creates detailed documentation for discovered workflows including
    entry points, related files, and step-by-step flow.
    """

    def __init__(self, llm_client, repo):
        """Initialize the workflow generator.

        Args:
            llm_client: LLM client for generation.
            repo: Repository wrapper for context.
        """
        self.llm_client = llm_client
        self.repo = repo

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

        # Format entry points for the prompt
        entry_points_list = [
            f"{ep.name} ({ep.entry_type}) - {ep.description or 'N/A'} in {ep.file}"
            for ep in workflow_group.entry_points
        ]

        prompt = get_workflow_prompt(
            repo_name=repo_name,
            workflow_name=workflow_group.name,
            entry_points=entry_points_list,
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
        """Build prompt context from available data.

        Args:
            workflow_group: The workflow group being documented.
            synthesis_map: Full synthesis context.
            symbols: All parsed symbols from the codebase.

        Returns:
            Dictionary with context for the prompt.
        """
        # Filter symbols to related files
        related_symbols = [
            s for s in symbols if s.metadata.get("file") in workflow_group.related_files
        ]

        # Format code context from symbols
        code_context = ""
        for symbol in related_symbols[:20]:  # Limit to avoid huge prompts
            file = symbol.metadata.get("file", "")
            code_context += f"- {symbol.name} ({symbol.symbol_type.value}) in {file}\n"

        return {
            "code_context": code_context or "No specific code context available.",
        }
