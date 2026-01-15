# backend/tests/test_workflow_generator.py
"""Workflow discovery and generator tests."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from oya.generation.workflows import (
    WorkflowDiscovery,
    WorkflowGenerator,
    WorkflowGroup,
    DiscoveredWorkflow,
)
from oya.generation.summaries import EntryPointInfo
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
    async def test_generates_workflow_page(self, generator, mock_llm_client):
        """Generates workflow markdown."""
        workflow = DiscoveredWorkflow(
            name="User Authentication",
            slug="user-authentication",
            entry_points=[
                ParsedSymbol(
                    name="login",
                    symbol_type=SymbolType.ROUTE,
                    start_line=1,
                    end_line=10,
                    metadata={"file": "auth/login.py"},
                )
            ],
            related_files=["auth/login.py", "auth/session.py"],
        )

        result = await generator.generate(
            workflow=workflow,
            code_context="def login(): pass",
        )

        assert "Authentication" in result.content
        mock_llm_client.generate.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_workflow_metadata(self, generator):
        """Returns correct page metadata."""
        workflow = DiscoveredWorkflow(
            name="Test Workflow",
            slug="test-workflow",
            entry_points=[],
            related_files=[],
        )

        result = await generator.generate(
            workflow=workflow,
            code_context="",
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
