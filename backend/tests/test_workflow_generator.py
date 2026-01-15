# backend/tests/test_workflow_generator.py
"""Workflow discovery and generator tests."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from oya.generation.workflows import (
    WorkflowDiscovery,
    WorkflowGenerator,
    WorkflowGroup,
    WorkflowGrouper,
)
from oya.generation.summaries import EntryPointInfo, SynthesisMap, LayerInfo, ComponentInfo
from oya.parsing.models import ParsedSymbol, SymbolType


@pytest.fixture
def mock_llm_client():
    """Create mock LLM client."""
    client = AsyncMock()
    client.generate.return_value = "# User Authentication\n\nHandles login flow."
    return client


@pytest.fixture
def mock_repo():
    """Create mock repository."""
    repo = MagicMock()
    repo.path = Path("/workspace/my-project")
    return repo


class TestWorkflowDiscovery:
    """Tests for workflow discovery."""

    def test_discovers_cli_entry_points(self):
        """Finds CLI commands as workflow entry points."""
        discovery = WorkflowDiscovery()

        symbols = [
            ParsedSymbol(
                name="main",
                symbol_type=SymbolType.FUNCTION,
                start_line=1,
                end_line=10,
                decorators=["click.command"],
                metadata={"file": "cli.py"},
            ),
            ParsedSymbol(
                name="init_db",
                symbol_type=SymbolType.FUNCTION,
                start_line=12,
                end_line=20,
                decorators=["click.command"],
                metadata={"file": "cli.py"},
            ),
        ]

        entry_points = discovery.find_entry_points(symbols)

        assert len(entry_points) >= 2
        assert any(e.name == "main" for e in entry_points)

    def test_discovers_api_routes(self):
        """Finds API routes as workflow entry points."""
        discovery = WorkflowDiscovery()

        symbols = [
            ParsedSymbol(
                name="get_users",
                symbol_type=SymbolType.ROUTE,
                start_line=1,
                end_line=10,
                metadata={"file": "api/users.py", "method": "GET", "path": "/users"},
            ),
            ParsedSymbol(
                name="create_user",
                symbol_type=SymbolType.ROUTE,
                start_line=12,
                end_line=20,
                metadata={"file": "api/users.py", "method": "POST", "path": "/users"},
            ),
        ]

        entry_points = discovery.find_entry_points(symbols)

        assert len(entry_points) >= 2

    def test_discovers_main_functions(self):
        """Finds main functions as entry points."""
        discovery = WorkflowDiscovery()

        symbols = [
            ParsedSymbol(
                name="main",
                symbol_type=SymbolType.FUNCTION,
                start_line=1,
                end_line=10,
                metadata={"file": "main.py"},
            ),
            ParsedSymbol(
                name="__main__",
                symbol_type=SymbolType.FUNCTION,
                start_line=1,
                end_line=10,
                metadata={"file": "app.py"},
            ),
        ]

        entry_points = discovery.find_entry_points(symbols)

        assert len(entry_points) >= 1


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
        workflow_group = WorkflowGroup(
            name="Users API",
            slug="users-api",
            entry_points=[
                EntryPointInfo(
                    name="get_users",
                    entry_type="api_route",
                    file="api/users.py",
                    description="/users",
                ),
            ],
            related_files=["api/users.py", "services/user_service.py"],
            primary_layer="api",
        )

        synthesis_map = SynthesisMap(
            layers={
                "api": LayerInfo(
                    name="api", purpose="HTTP endpoints", files=["api/users.py"]
                )
            },
            key_components=[
                ComponentInfo(
                    name="UserService",
                    file="services/user_service.py",
                    role="User operations",
                    layer="domain",
                )
            ],
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

    @pytest.mark.asyncio
    async def test_generates_workflow_page_with_symbols(self, generator, mock_llm_client):
        """Generates workflow with code context from symbols."""
        workflow_group = WorkflowGroup(
            name="User Authentication",
            slug="user-authentication",
            entry_points=[
                EntryPointInfo(
                    name="login",
                    entry_type="api_route",
                    file="auth/login.py",
                    description="/login",
                ),
            ],
            related_files=["auth/login.py", "auth/session.py"],
            primary_layer="api",
        )

        synthesis_map = SynthesisMap(
            layers={"api": LayerInfo(name="api", purpose="HTTP endpoints", files=[])},
            project_summary="Auth system",
        )

        symbols = [
            ParsedSymbol(
                name="login_user",
                symbol_type=SymbolType.FUNCTION,
                start_line=1,
                end_line=10,
                metadata={"file": "auth/login.py"},
            ),
            ParsedSymbol(
                name="create_session",
                symbol_type=SymbolType.FUNCTION,
                start_line=12,
                end_line=20,
                metadata={"file": "auth/session.py"},
            ),
        ]

        result = await generator.generate(
            workflow_group=workflow_group,
            synthesis_map=synthesis_map,
            symbols=symbols,
            file_imports={},
        )

        assert result.page_type == "workflow"
        assert "user-authentication" in result.path
        mock_llm_client.generate.assert_called_once()

        # Verify symbols are included in the prompt
        call_args = mock_llm_client.generate.call_args
        prompt = call_args.kwargs.get("prompt", call_args.args[0] if call_args.args else "")
        assert "login_user" in prompt
        assert "create_session" in prompt

    @pytest.mark.asyncio
    async def test_returns_workflow_metadata(self, generator):
        """Returns correct page metadata."""
        workflow_group = WorkflowGroup(
            name="Test Workflow",
            slug="test-workflow",
            entry_points=[],
            related_files=[],
            primary_layer="",
        )

        synthesis_map = SynthesisMap()

        result = await generator.generate(
            workflow_group=workflow_group,
            synthesis_map=synthesis_map,
            symbols=[],
            file_imports={},
        )

        assert result.page_type == "workflow"
        assert result.path == "workflows/test-workflow.md"


class TestExtractEntryPointDescription:
    """Tests for entry point description extraction."""

    def test_extracts_route_path_from_decorator(self):
        """Test extraction of route path from route decorator."""
        from oya.generation.workflows import extract_entry_point_description

        symbol = ParsedSymbol(
            name="get_users",
            symbol_type=SymbolType.ROUTE,
            start_line=10,
            end_line=20,
            decorators=["@router.get('/users')"],
            metadata={"file": "api/users.py"},
        )

        result = extract_entry_point_description(symbol)

        assert result == "/users"

    def test_extracts_cli_command_from_decorator(self):
        """Test extraction of CLI command name from decorator."""
        from oya.generation.workflows import extract_entry_point_description

        symbol = ParsedSymbol(
            name="init_cmd",
            symbol_type=SymbolType.CLI_COMMAND,
            start_line=10,
            end_line=20,
            decorators=["@click.command('init')"],
            metadata={"file": "cli/commands.py"},
        )

        result = extract_entry_point_description(symbol)

        assert result == "init"

    def test_returns_empty_for_main_function(self):
        """Test that main functions return empty description."""
        from oya.generation.workflows import extract_entry_point_description

        symbol = ParsedSymbol(
            name="main",
            symbol_type=SymbolType.FUNCTION,
            start_line=10,
            end_line=20,
            decorators=[],
            metadata={"file": "main.py"},
        )

        result = extract_entry_point_description(symbol)

        assert result == ""

    def test_handles_complex_route_decorator(self):
        """Test extraction from complex route decorators."""
        from oya.generation.workflows import extract_entry_point_description

        symbol = ParsedSymbol(
            name="create_user",
            symbol_type=SymbolType.ROUTE,
            start_line=10,
            end_line=20,
            decorators=["@app.post('/api/v1/users', status_code=201)"],
            metadata={"file": "api/users.py"},
        )

        result = extract_entry_point_description(symbol)

        assert result == "/api/v1/users"


class TestWorkflowGroup:
    """Tests for WorkflowGroup dataclass."""

    def test_workflow_group_creation(self):
        """WorkflowGroup holds grouped entry points."""
        entry_points = [
            EntryPointInfo(
                name="get_users", entry_type="api_route", file="api/users.py", description="/users"
            ),
            EntryPointInfo(
                name="create_user",
                entry_type="api_route",
                file="api/users.py",
                description="/users",
            ),
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


class TestWorkflowGrouper:
    """Tests for WorkflowGrouper."""

    def test_groups_by_route_prefix(self):
        """Groups API routes by common URL prefix."""
        grouper = WorkflowGrouper()

        entry_points = [
            EntryPointInfo(
                name="get_users",
                entry_type="api_route",
                file="api/users.py",
                description="/api/users",
            ),
            EntryPointInfo(
                name="create_user",
                entry_type="api_route",
                file="api/users.py",
                description="/api/users",
            ),
            EntryPointInfo(
                name="get_orders",
                entry_type="api_route",
                file="api/orders.py",
                description="/api/orders",
            ),
            EntryPointInfo(
                name="list_orders",
                entry_type="api_route",
                file="api/orders.py",
                description="/api/orders/{id}",
            ),
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
