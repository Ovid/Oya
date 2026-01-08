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
            {
                "file": "cli.py",
                "name": "main",
                "type": "function",
                "decorators": ["click.command"],
            },
            {
                "file": "cli.py",
                "name": "init_db",
                "type": "function",
                "decorators": ["click.command"],
            },
        ]

        entry_points = discovery.find_entry_points(symbols)

        assert len(entry_points) >= 2
        assert any(e["name"] == "main" for e in entry_points)

    def test_discovers_api_routes(self):
        """Finds API routes as workflow entry points."""
        discovery = WorkflowDiscovery()

        symbols = [
            {
                "file": "api/users.py",
                "name": "get_users",
                "type": "route",
                "metadata": {"method": "GET", "path": "/users"},
            },
            {
                "file": "api/users.py",
                "name": "create_user",
                "type": "route",
                "metadata": {"method": "POST", "path": "/users"},
            },
        ]

        entry_points = discovery.find_entry_points(symbols)

        assert len(entry_points) >= 2

    def test_discovers_main_functions(self):
        """Finds main functions as entry points."""
        discovery = WorkflowDiscovery()

        symbols = [
            {"file": "main.py", "name": "main", "type": "function"},
            {"file": "app.py", "name": "__main__", "type": "function"},
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
                {"file": "auth/login.py", "name": "login", "type": "route"}
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
