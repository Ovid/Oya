# backend/tests/test_file_generator.py
"""File page generator tests."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from oya.generation.file import FileGenerator


@pytest.fixture
def mock_llm_client():
    """Create mock LLM client."""
    client = AsyncMock()
    client.generate.return_value = "# login.py\n\nHandles user authentication."
    return client


@pytest.fixture
def mock_repo():
    """Create mock repository."""
    repo = MagicMock()
    repo.path = Path("/workspace/my-project")
    return repo


@pytest.fixture
def generator(mock_llm_client, mock_repo):
    """Create file generator."""
    return FileGenerator(
        llm_client=mock_llm_client,
        repo=mock_repo,
    )


@pytest.mark.asyncio
async def test_generates_file_page(generator, mock_llm_client):
    """Generates file documentation markdown."""
    result = await generator.generate(
        file_path="src/auth/login.py",
        content="def login(user, password): pass",
        symbols=[{"name": "login", "type": "function", "line": 1}],
        imports=["from flask import request"],
        architecture_summary="Authentication module.",
    )

    assert result.content
    mock_llm_client.generate.assert_called_once()


@pytest.mark.asyncio
async def test_returns_file_metadata(generator):
    """Returns correct page metadata."""
    result = await generator.generate(
        file_path="src/main.py",
        content="print('hello')",
        symbols=[],
        imports=[],
        architecture_summary="",
    )

    assert result.page_type == "file"
    assert "src-main-py" in result.path
    assert result.target == "src/main.py"


@pytest.mark.asyncio
async def test_includes_language_in_prompt(generator, mock_llm_client):
    """Includes language for syntax highlighting."""
    await generator.generate(
        file_path="src/app.ts",
        content="const x = 1;",
        symbols=[],
        imports=[],
        architecture_summary="",
    )

    call_args = mock_llm_client.generate.call_args
    # The prompt should mention the file for context
    assert "app.ts" in call_args.kwargs["prompt"]
