# backend/tests/test_overview_generator.py
"""Overview page generator tests."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from oya.generation.overview import OverviewGenerator


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
