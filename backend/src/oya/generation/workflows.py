# backend/src/oya/generation/workflows.py
"""Workflow discovery and generation."""

import re
from dataclasses import dataclass, field

from oya.generation.overview import GeneratedPage
from oya.generation.prompts import SYSTEM_PROMPT, get_workflow_prompt
from oya.generation.summaries import EntryPointInfo, SynthesisMap
from oya.parsing.models import ParsedSymbol, SymbolType


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


@dataclass
class DiscoveredWorkflow:
    """Represents a discovered workflow.

    Attributes:
        name: Human-readable name of the workflow.
        slug: URL-friendly identifier.
        entry_points: List of ParsedSymbol entry points.
        related_files: List of file paths related to the workflow.
    """

    name: str
    slug: str
    entry_points: list[ParsedSymbol] = field(default_factory=list)
    related_files: list[str] = field(default_factory=list)


class WorkflowDiscovery:
    """Discovers workflow entry points from parsed symbols.

    Entry points are functions or methods that serve as starting points
    for workflows - CLI commands, API routes, main functions, etc.
    """

    # Decorators that indicate entry points
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

    # Function names that indicate entry points
    ENTRY_POINT_NAMES: set[str] = {
        "main",
        "__main__",
        "run",
        "start",
        "serve",
        "execute",
    }

    def find_entry_points(self, symbols: list[ParsedSymbol]) -> list[ParsedSymbol]:
        """Find entry points from a list of symbols.

        Args:
            symbols: List of ParsedSymbol objects from parsing.

        Returns:
            List of symbols that are entry points.
        """
        entry_points = []

        for symbol in symbols:
            if self._is_entry_point(symbol):
                entry_points.append(symbol)

        return entry_points

    def _is_entry_point(self, symbol: ParsedSymbol) -> bool:
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
            if decorator in self.ENTRY_POINT_DECORATORS:
                return True
            # Also check partial matches (e.g., "app.get" in "@app.get('/users')")
            for entry_decorator in self.ENTRY_POINT_DECORATORS:
                if entry_decorator in decorator:
                    return True

        # Check function name
        if symbol.name in self.ENTRY_POINT_NAMES:
            return True

        return False

    def group_into_workflows(
        self,
        entry_points: list[ParsedSymbol],
        file_imports: dict[str, list[str]] | None = None,
    ) -> list[DiscoveredWorkflow]:
        """Group entry points into logical workflows.

        Args:
            entry_points: List of entry point ParsedSymbol objects.
            file_imports: Optional mapping of file paths to their imports.

        Returns:
            List of discovered workflows.
        """
        workflows = []

        for entry_point in entry_points:
            workflow = DiscoveredWorkflow(
                name=self._humanize_name(entry_point.name),
                slug=self._slugify(entry_point.name),
                entry_points=[entry_point],
                related_files=[entry_point.metadata.get("file", "")],
            )
            workflows.append(workflow)

        return workflows

    def _slugify(self, name: str) -> str:
        """Convert a name to a URL-friendly slug.

        Args:
            name: The name to slugify.

        Returns:
            URL-friendly slug.
        """
        # Replace underscores and spaces with hyphens
        slug = name.replace("_", "-").replace(" ", "-")
        # Convert to lowercase
        slug = slug.lower()
        # Remove non-alphanumeric characters except hyphens
        slug = re.sub(r"[^a-z0-9-]", "", slug)
        # Remove consecutive hyphens
        slug = re.sub(r"-+", "-", slug)
        # Strip leading/trailing hyphens
        slug = slug.strip("-")
        return slug

    def _humanize_name(self, name: str) -> str:
        """Convert a symbol name to a human-readable name.

        Args:
            name: The symbol name.

        Returns:
            Human-readable name.
        """
        # Replace underscores with spaces
        human = name.replace("_", " ")
        # Split on camelCase
        human = re.sub(r"([a-z])([A-Z])", r"\1 \2", human)
        # Capitalize each word
        human = human.title()
        return human


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

        content = await self.llm_client.generate(
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
        )

        word_count = len(content.split())

        return GeneratedPage(
            content=content,
            page_type="workflow",
            path=f"workflows/{workflow.slug}.md",
            word_count=word_count,
        )
