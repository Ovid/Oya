# backend/tests/test_workflow_generator.py
"""Workflow discovery and generator tests."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from oya.generation.workflows import (
    WorkflowDiscovery,
    WorkflowGenerator,
    DiscoveredWorkflow,
)
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
