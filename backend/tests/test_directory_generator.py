# backend/tests/test_directory_generator.py
"""Directory page generator tests."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from oya.generation.directory import DirectoryGenerator


@pytest.fixture
def mock_llm_client():
    """Create mock LLM client."""
    client = AsyncMock()
    client.generate.return_value = "# src/auth/\n\nAuthentication module."
    return client


@pytest.fixture
def mock_repo():
    """Create mock repository."""
    repo = MagicMock()
    repo.path = Path("/workspace/my-project")
    return repo


@pytest.fixture
def generator(mock_llm_client, mock_repo):
    """Create directory generator."""
    return DirectoryGenerator(
        llm_client=mock_llm_client,
        repo=mock_repo,
    )


@pytest.mark.asyncio
async def test_generates_directory_page(generator, mock_llm_client):
    """Generates directory markdown."""
    result = await generator.generate(
        directory_path="src/auth",
        file_list=["login.py", "session.py", "utils.py"],
        symbols=[
            {"file": "login.py", "name": "login", "type": "function"},
            {"file": "session.py", "name": "Session", "type": "class"},
        ],
        architecture_context="Handles user authentication.",
    )

    assert result.content
    mock_llm_client.generate.assert_called_once()


@pytest.mark.asyncio
async def test_returns_directory_metadata(generator):
    """Returns correct page metadata."""
    result = await generator.generate(
        directory_path="src/api",
        file_list=["routes.py"],
        symbols=[],
        architecture_context="",
    )

    assert result.page_type == "directory"
    assert "src-api" in result.path
    assert result.target == "src/api"


@pytest.mark.asyncio
async def test_handles_nested_directories(generator):
    """Handles deeply nested directory paths."""
    result = await generator.generate(
        directory_path="src/services/auth/providers",
        file_list=["oauth.py", "jwt.py"],
        symbols=[],
        architecture_context="",
    )

    assert result.target == "src/services/auth/providers"
    assert "providers" in result.path
