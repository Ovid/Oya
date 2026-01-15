# backend/tests/test_orchestrator_workflows.py
"""Tests for orchestrator workflow generation."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from oya.generation.orchestrator import GenerationOrchestrator
from oya.generation.summaries import SynthesisMap, LayerInfo, EntryPointInfo


class TestOrchestratorWorkflows:
    """Tests for orchestrator workflow generation."""

    @pytest.fixture
    def mock_llm_client(self):
        """Create mock LLM client."""
        client = AsyncMock()
        client.generate.return_value = "# Workflow\n\nGenerated content."
        return client

    @pytest.fixture
    def mock_orchestrator(self, mock_llm_client, tmp_path):
        """Create orchestrator with mocked dependencies."""
        wiki_path = tmp_path / ".oyawiki"
        wiki_path.mkdir()

        mock_repo = MagicMock()
        mock_repo.path = tmp_path

        mock_db = MagicMock()

        orchestrator = GenerationOrchestrator(
            repo=mock_repo,
            llm_client=mock_llm_client,
            wiki_path=wiki_path,
            db=mock_db,
        )

        return orchestrator

    @pytest.mark.asyncio
    async def test_run_workflows_uses_synthesis_entry_points(self, mock_orchestrator):
        """Verifies _run_workflows uses entry points from SynthesisMap."""
        synthesis_map = SynthesisMap(
            layers={"api": LayerInfo(name="api", purpose="HTTP", files=["api/users.py"])},
            entry_points=[
                EntryPointInfo(
                    name="get_users",
                    entry_type="api_route",
                    file="api/users.py",
                    description="/users",
                ),
                EntryPointInfo(
                    name="create_user",
                    entry_type="api_route",
                    file="api/users.py",
                    description="/users",
                ),
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

    @pytest.mark.asyncio
    async def test_run_workflows_returns_empty_when_no_entry_points(self, mock_orchestrator):
        """Verifies _run_workflows returns empty list when no entry points."""
        synthesis_map = SynthesisMap(
            layers={"api": LayerInfo(name="api", purpose="HTTP", files=[])},
            entry_points=[],  # No entry points
        )

        analysis = {
            "symbols": [],
            "file_contents": {},
            "file_imports": {},
        }

        pages = await mock_orchestrator._run_workflows(
            analysis=analysis,
            progress_callback=None,
            synthesis_map=synthesis_map,
        )

        assert pages == []

    @pytest.mark.asyncio
    async def test_run_workflows_returns_empty_when_no_synthesis_map(self, mock_orchestrator):
        """Verifies _run_workflows returns empty list when synthesis_map is None."""
        analysis = {
            "symbols": [],
            "file_contents": {},
            "file_imports": {},
        }

        pages = await mock_orchestrator._run_workflows(
            analysis=analysis,
            progress_callback=None,
            synthesis_map=None,
        )

        assert pages == []

    @pytest.mark.asyncio
    async def test_workflow_generation_end_to_end(self, mock_orchestrator):
        """Full integration test for workflow generation."""
        synthesis_map = SynthesisMap(
            layers={
                "api": LayerInfo(
                    name="api", purpose="HTTP endpoints", files=["api/users.py", "api/orders.py"]
                ),
                "domain": LayerInfo(
                    name="domain", purpose="Business logic", files=["services/user_service.py"]
                ),
            },
            key_components=[],
            entry_points=[
                # Users API group
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
                # Orders API group
                EntryPointInfo(
                    name="get_orders",
                    entry_type="api_route",
                    file="api/orders.py",
                    description="/api/orders",
                ),
                # CLI commands
                EntryPointInfo(
                    name="init",
                    entry_type="cli_command",
                    file="cli/main.py",
                    description="init",
                ),
                EntryPointInfo(
                    name="build",
                    entry_type="cli_command",
                    file="cli/main.py",
                    description="build",
                ),
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

        # Should have multiple groups: users-api, orders-api, cli
        assert len(pages) >= 2

        # Check page paths are correctly slugified
        paths = [p.path for p in pages]
        assert all(p.startswith("workflows/") for p in paths)
        assert all(p.endswith(".md") for p in paths)

        # Verify different groups were created
        path_names = [p.path.lower() for p in pages]
        assert any("users" in p for p in path_names), "Should have users workflow"
        assert any("orders" in p or "cli" in p for p in path_names), "Should have orders or cli workflow"
