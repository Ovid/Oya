# backend/tests/test_architecture_generator.py
"""Architecture page generator tests."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from oya.generation.architecture import ArchitectureGenerator


@pytest.fixture
def mock_llm_client():
    """Create mock LLM client."""
    client = AsyncMock()
    client.generate.return_value = """# Architecture

## System Design

The system follows a layered architecture.

```mermaid
graph TD
    A[Frontend] --> B[API]
    B --> C[Database]
```
"""
    return client


@pytest.fixture
def mock_repo():
    """Create mock repository."""
    repo = MagicMock()
    repo.path = Path("/workspace/my-project")
    return repo


@pytest.fixture
def generator(mock_llm_client, mock_repo):
    """Create architecture generator."""
    return ArchitectureGenerator(
        llm_client=mock_llm_client,
        repo=mock_repo,
    )


@pytest.mark.asyncio
async def test_generates_architecture_page(generator, mock_llm_client):
    """Generates architecture markdown from symbols."""
    result = await generator.generate(
        file_tree="src/\n  api/\n  db/",
        key_symbols=[
            {"file": "src/api/routes.py", "name": "app", "type": "variable"},
            {"file": "src/db/models.py", "name": "User", "type": "class"},
        ],
        dependencies=["fastapi", "sqlalchemy"],
    )

    assert "Architecture" in result.content
    mock_llm_client.generate.assert_called_once()


@pytest.mark.asyncio
async def test_includes_mermaid_diagrams(generator):
    """Generated architecture includes Mermaid diagrams."""
    result = await generator.generate(
        file_tree="src/",
        key_symbols=[],
        dependencies=[],
    )

    # The mock returns content with Mermaid
    assert "mermaid" in result.content.lower() or "graph" in result.content.lower()


@pytest.mark.asyncio
async def test_returns_architecture_metadata(generator):
    """Returns correct page metadata."""
    result = await generator.generate(
        file_tree="src/",
        key_symbols=[],
        dependencies=[],
    )

    assert result.page_type == "architecture"
    assert result.path == "architecture.md"
