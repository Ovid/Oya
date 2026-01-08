# backend/tests/test_orchestrator.py
"""Generation orchestrator tests."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from oya.generation.orchestrator import (
    GenerationOrchestrator,
    GenerationPhase,
    GenerationProgress,
)
from oya.generation.overview import GeneratedPage


@pytest.fixture
def mock_llm_client():
    """Create mock LLM client."""
    client = AsyncMock()
    client.generate.return_value = "# Generated Content"
    return client


@pytest.fixture
def mock_repo():
    """Create mock repository."""
    repo = MagicMock()
    repo.path = Path("/workspace/my-project")
    repo.list_files.return_value = ["src/main.py", "README.md"]
    repo.get_head_commit.return_value = "abc123"
    return repo


@pytest.fixture
def mock_db():
    """Create mock database."""
    return MagicMock()


@pytest.fixture
def orchestrator(mock_llm_client, mock_repo, mock_db, tmp_path):
    """Create orchestrator."""
    return GenerationOrchestrator(
        llm_client=mock_llm_client,
        repo=mock_repo,
        db=mock_db,
        wiki_path=tmp_path / "wiki",
    )


def test_generation_phases_defined():
    """Generation phases are properly defined."""
    assert GenerationPhase.ANALYSIS.value == "analysis"
    assert GenerationPhase.OVERVIEW.value == "overview"
    assert GenerationPhase.ARCHITECTURE.value == "architecture"
    assert GenerationPhase.WORKFLOWS.value == "workflows"
    assert GenerationPhase.DIRECTORIES.value == "directories"
    assert GenerationPhase.FILES.value == "files"


@pytest.mark.asyncio
async def test_runs_full_generation(orchestrator):
    """Runs all generation phases."""
    progress_events = []

    async def progress_callback(progress: GenerationProgress):
        progress_events.append(progress)

    mock_overview_page = GeneratedPage(
        content="# Overview", page_type="overview", path="overview.md", word_count=1
    )
    mock_arch_page = GeneratedPage(
        content="# Architecture", page_type="architecture", path="architecture.md", word_count=1
    )

    with patch.object(orchestrator, "_run_analysis", new_callable=AsyncMock) as mock_analysis:
        mock_analysis.return_value = {"files": [], "symbols": [], "file_tree": "", "file_contents": {}}
        with patch.object(orchestrator, "_run_overview", new_callable=AsyncMock) as mock_overview:
            mock_overview.return_value = mock_overview_page
            with patch.object(orchestrator, "_run_architecture", new_callable=AsyncMock) as mock_arch:
                mock_arch.return_value = mock_arch_page
                with patch.object(orchestrator, "_run_workflows", new_callable=AsyncMock) as mock_workflows:
                    mock_workflows.return_value = []
                    with patch.object(orchestrator, "_run_directories", new_callable=AsyncMock) as mock_dirs:
                        mock_dirs.return_value = []
                        with patch.object(orchestrator, "_run_files", new_callable=AsyncMock) as mock_files:
                            mock_files.return_value = []
                            await orchestrator.run(progress_callback=progress_callback)

    # Should have progress events for each phase
    assert len(progress_events) >= 1


@pytest.mark.asyncio
async def test_emits_progress_events(orchestrator):
    """Emits progress events during generation."""
    progress_events = []

    async def progress_callback(progress: GenerationProgress):
        progress_events.append(progress)

    mock_overview_page = GeneratedPage(
        content="# Overview", page_type="overview", path="overview.md", word_count=1
    )
    mock_arch_page = GeneratedPage(
        content="# Architecture", page_type="architecture", path="architecture.md", word_count=1
    )

    with patch.object(orchestrator, "_run_analysis", new_callable=AsyncMock) as mock_analysis:
        mock_analysis.return_value = {"files": [], "symbols": [], "file_tree": "", "file_contents": {}}
        with patch.object(orchestrator, "_run_overview", new_callable=AsyncMock) as mock_overview:
            mock_overview.return_value = mock_overview_page
            with patch.object(orchestrator, "_run_architecture", new_callable=AsyncMock) as mock_arch:
                mock_arch.return_value = mock_arch_page
                with patch.object(orchestrator, "_run_workflows", new_callable=AsyncMock) as mock_workflows:
                    mock_workflows.return_value = []
                    with patch.object(orchestrator, "_run_directories", new_callable=AsyncMock) as mock_dirs:
                        mock_dirs.return_value = []
                        with patch.object(orchestrator, "_run_files", new_callable=AsyncMock) as mock_files:
                            mock_files.return_value = []
                            await orchestrator.run(progress_callback=progress_callback)

    # Check progress events have expected fields
    for event in progress_events:
        assert hasattr(event, "phase")
        assert hasattr(event, "message")


@pytest.mark.asyncio
async def test_saves_pages_to_wiki_path(orchestrator, mock_llm_client):
    """Saves generated pages to wiki directory."""
    with patch.object(orchestrator, "_run_analysis", new_callable=AsyncMock) as mock_analysis:
        mock_analysis.return_value = {"files": [], "symbols": [], "file_tree": "", "file_contents": {}}
        with patch.object(orchestrator, "_save_page", new_callable=AsyncMock) as mock_save:
            with patch.object(orchestrator, "_run_workflows", new_callable=AsyncMock):
                with patch.object(orchestrator, "_run_directories", new_callable=AsyncMock):
                    with patch.object(orchestrator, "_run_files", new_callable=AsyncMock):
                        await orchestrator.run()

            # Should have saved overview and architecture pages
            assert mock_save.call_count >= 2
