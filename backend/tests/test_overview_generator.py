# backend/tests/test_overview_generator.py
"""Overview page generator tests."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from oya.generation.overview import OverviewGenerator
from oya.generation.summaries import (
    SynthesisMap,
    LayerInfo,
    ComponentInfo,
)


@pytest.fixture
def mock_llm_client():
    """Create mock LLM client."""
    client = AsyncMock()
    client.generate.return_value = "# Overview\n\nThis is the generated overview."
    return client


@pytest.fixture
def mock_repo():
    """Create mock repository."""
    repo = MagicMock()
    repo.path = Path("/workspace/my-project")
    return repo


@pytest.fixture
def generator(mock_llm_client, mock_repo):
    """Create overview generator."""
    return OverviewGenerator(
        llm_client=mock_llm_client,
        repo=mock_repo,
    )


@pytest.mark.asyncio
async def test_generates_overview_page(generator, mock_llm_client):
    """Generates overview markdown from repo context."""
    result = await generator.generate(
        readme_content="# My Project\n\nA cool project.",
        file_tree="src/\n  main.py",
        package_info={"name": "my-project"},
    )

    assert "Overview" in result.content
    mock_llm_client.generate.assert_called_once()


@pytest.mark.asyncio
async def test_handles_missing_readme(generator):
    """Generates overview even without README."""
    result = await generator.generate(
        readme_content=None,
        file_tree="src/\n  main.py",
        package_info={},
    )

    assert result.content  # Should still generate something


@pytest.mark.asyncio
async def test_returns_page_metadata(generator):
    """Returns metadata with the generated page."""
    result = await generator.generate(
        readme_content="# Test",
        file_tree="src/",
        package_info={},
    )

    assert result.page_type == "overview"
    assert result.path == "overview.md"
    assert result.word_count > 0


# =============================================================================
# Tests for SynthesisMap-based generation (Requirements 6.1, 6.5)
# =============================================================================


@pytest.fixture
def sample_synthesis_map():
    """Create a sample SynthesisMap for testing."""
    return SynthesisMap(
        layers={
            "api": LayerInfo(
                name="api",
                purpose="REST API endpoints and request handling",
                directories=["src/api"],
                files=["src/api/routes.py", "src/api/handlers.py"],
            ),
            "domain": LayerInfo(
                name="domain",
                purpose="Core business logic and domain models",
                directories=["src/domain"],
                files=["src/domain/models.py", "src/domain/services.py"],
            ),
            "infrastructure": LayerInfo(
                name="infrastructure",
                purpose="Database and external service integrations",
                directories=["src/db"],
                files=["src/db/connection.py", "src/db/repositories.py"],
            ),
        },
        key_components=[
            ComponentInfo(
                name="UserService",
                file="src/domain/services.py",
                role="Handles user-related business logic",
                layer="domain",
            ),
            ComponentInfo(
                name="DatabaseConnection",
                file="src/db/connection.py",
                role="Manages database connections",
                layer="infrastructure",
            ),
        ],
        dependency_graph={
            "api": ["domain"],
            "domain": ["infrastructure"],
        },
        project_summary="A sample project demonstrating layered architecture with API, domain, and infrastructure layers.",
    )


@pytest.mark.asyncio
async def test_generates_overview_with_synthesis_map_no_readme(
    generator, mock_llm_client, sample_synthesis_map
):
    """Test generation succeeds with SynthesisMap, no README.

    Requirements: 6.1, 6.5
    - Overview generator receives SynthesisMap as input
    - Generation succeeds without README when SynthesisMap is provided
    """
    result = await generator.generate(
        readme_content=None,  # No README
        file_tree="src/\n  api/\n  domain/\n  db/",
        package_info={"name": "my-project"},
        synthesis_map=sample_synthesis_map,
    )

    # Verify generation succeeded
    assert result is not None
    assert result.content is not None
    assert len(result.content) > 0
    assert result.page_type == "overview"
    assert result.path == "overview.md"

    # Verify LLM was called
    mock_llm_client.generate.assert_called_once()


@pytest.mark.asyncio
async def test_synthesis_map_project_summary_used_when_no_readme(
    generator, mock_llm_client, sample_synthesis_map
):
    """Test that project_summary from SynthesisMap is used when README is absent.

    Requirements: 6.2
    - Overview generator derives project summary from SynthesisMap when README is absent
    """
    await generator.generate(
        readme_content=None,
        file_tree="src/",
        package_info={},
        synthesis_map=sample_synthesis_map,
    )

    # Get the prompt that was passed to the LLM
    call_args = mock_llm_client.generate.call_args
    prompt = call_args.kwargs.get("prompt") or call_args.args[0]

    # Verify project summary from SynthesisMap is in the prompt
    assert "layered architecture" in prompt.lower()


@pytest.mark.asyncio
async def test_synthesis_map_layers_included_in_overview_prompt(
    generator, mock_llm_client, sample_synthesis_map
):
    """Test that layer information from SynthesisMap is included in the prompt.

    Requirements: 6.3
    - Overview generator uses layer groupings to describe project structure
    """
    await generator.generate(
        readme_content=None,
        file_tree="src/",
        package_info={},
        synthesis_map=sample_synthesis_map,
    )

    # Get the prompt that was passed to the LLM
    call_args = mock_llm_client.generate.call_args
    prompt = call_args.kwargs.get("prompt") or call_args.args[0]

    # Verify layer information is in the prompt
    assert "api" in prompt.lower()
    assert "domain" in prompt.lower()
    assert "infrastructure" in prompt.lower()


@pytest.mark.asyncio
async def test_readme_used_as_supplementary_with_synthesis_map(
    generator, mock_llm_client, sample_synthesis_map
):
    """Test that README is used as supplementary context alongside SynthesisMap.

    Requirements: 6.4
    - When README content exists, it is used as supplementary context alongside SynthesisMap
    """
    readme_content = "# My Project\n\nThis is a great project with custom features."

    await generator.generate(
        readme_content=readme_content,
        file_tree="src/",
        package_info={},
        synthesis_map=sample_synthesis_map,
    )

    # Get the prompt that was passed to the LLM
    call_args = mock_llm_client.generate.call_args
    prompt = call_args.kwargs.get("prompt") or call_args.args[0]

    # Verify both README and SynthesisMap info are in the prompt
    assert "My Project" in prompt or "great project" in prompt
    assert "layered architecture" in prompt.lower() or "api" in prompt.lower()


@pytest.mark.asyncio
async def test_backward_compatible_without_synthesis_map(generator, mock_llm_client):
    """Test that generator still works without synthesis_map for backward compatibility."""
    result = await generator.generate(
        readme_content="# Test Project",
        file_tree="src/",
        package_info={"name": "test"},
    )

    assert result is not None
    assert result.page_type == "overview"
    mock_llm_client.generate.assert_called_once()
