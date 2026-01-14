# backend/tests/test_architecture_generator.py
"""Architecture page generator tests."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from oya.generation.architecture import ArchitectureGenerator
from oya.generation.summaries import (
    SynthesisMap,
    LayerInfo,
    ComponentInfo,
)


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
        project_summary="A sample project demonstrating layered architecture.",
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


# =============================================================================
# Tests for SynthesisMap-based generation (Requirements 5.1, 5.5)
# =============================================================================


@pytest.mark.asyncio
async def test_generates_architecture_with_synthesis_map(
    generator, mock_llm_client, sample_synthesis_map
):
    """Test generation succeeds with SynthesisMap, no README.

    Requirements: 5.1, 5.5
    - Architecture generator receives SynthesisMap as input
    - Generation succeeds without README when SynthesisMap is provided
    """
    result = await generator.generate(
        file_tree="src/\n  api/\n  domain/\n  db/",
        synthesis_map=sample_synthesis_map,
        dependencies=["fastapi", "sqlalchemy"],
    )

    # Verify generation succeeded
    assert result is not None
    assert result.content is not None
    assert len(result.content) > 0
    assert result.page_type == "architecture"
    assert result.path == "architecture.md"

    # Verify LLM was called
    mock_llm_client.generate.assert_called_once()


@pytest.mark.asyncio
async def test_synthesis_map_layers_included_in_prompt(
    generator, mock_llm_client, sample_synthesis_map
):
    """Test that layer information from SynthesisMap is included in the prompt.

    Requirements: 5.2
    - Architecture generator uses layer groupings from SynthesisMap
    """
    await generator.generate(
        file_tree="src/",
        synthesis_map=sample_synthesis_map,
        dependencies=[],
    )

    # Get the prompt that was passed to the LLM
    call_args = mock_llm_client.generate.call_args
    prompt = call_args.kwargs.get("prompt") or call_args.args[0]

    # Verify layer information is in the prompt
    assert "api" in prompt.lower()
    assert "domain" in prompt.lower()
    assert "infrastructure" in prompt.lower()


@pytest.mark.asyncio
async def test_synthesis_map_key_components_included_in_prompt(
    generator, mock_llm_client, sample_synthesis_map
):
    """Test that key components from SynthesisMap are included in the prompt.

    Requirements: 5.4
    - Architecture generator references key_components from SynthesisMap
    """
    await generator.generate(
        file_tree="src/",
        synthesis_map=sample_synthesis_map,
        dependencies=[],
    )

    # Get the prompt that was passed to the LLM
    call_args = mock_llm_client.generate.call_args
    prompt = call_args.kwargs.get("prompt") or call_args.args[0]

    # Verify key components are in the prompt
    assert "UserService" in prompt
    assert "DatabaseConnection" in prompt


@pytest.mark.asyncio
async def test_synthesis_map_dependency_graph_included_in_prompt(
    generator, mock_llm_client, sample_synthesis_map
):
    """Test that dependency graph from SynthesisMap is included in the prompt.

    Requirements: 5.3
    - Architecture generator uses dependency_graph from SynthesisMap
    """
    await generator.generate(
        file_tree="src/",
        synthesis_map=sample_synthesis_map,
        dependencies=[],
    )

    # Get the prompt that was passed to the LLM
    call_args = mock_llm_client.generate.call_args
    prompt = call_args.kwargs.get("prompt") or call_args.args[0]

    # Verify dependency graph information is in the prompt
    # The prompt should mention layer dependencies
    assert "depend" in prompt.lower() or "graph" in prompt.lower()


@pytest.mark.asyncio
async def test_backward_compatible_with_key_symbols(generator, mock_llm_client):
    """Test that generator still works with key_symbols when no synthesis_map provided.

    This ensures backward compatibility with existing code.
    """
    result = await generator.generate(
        file_tree="src/",
        key_symbols=[
            {"file": "src/main.py", "name": "main", "type": "function"},
        ],
        dependencies=["fastapi"],
    )

    assert result is not None
    assert result.page_type == "architecture"
    mock_llm_client.generate.assert_called_once()


# =============================================================================
# Tests for Python-generated Mermaid diagrams (Task 8)
# =============================================================================


@pytest.mark.asyncio
async def test_architecture_includes_generated_diagrams(tmp_path):
    """Architecture page includes Python-generated diagrams."""
    from unittest.mock import AsyncMock, MagicMock

    from oya.generation.architecture import ArchitectureGenerator
    from oya.generation.summaries import SynthesisMap, LayerInfo, ComponentInfo

    repo = MagicMock()
    repo.path = tmp_path

    mock_client = AsyncMock()
    # Mock LLM to return prose content without diagrams
    mock_client.generate.return_value = "# Architecture\n\nThis is the architecture."

    generator = ArchitectureGenerator(mock_client, repo)

    synthesis_map = SynthesisMap(
        layers={
            "api": LayerInfo(name="api", purpose="HTTP endpoints", directories=[], files=[]),
        },
        key_components=[
            ComponentInfo(name="Router", file="routes.py", role="Routing", layer="api"),
        ],
        dependency_graph={},
    )

    page = await generator.generate(
        file_tree="src/\n  api/",
        synthesis_map=synthesis_map,
        file_imports={"routes.py": []},
        symbols=[],
    )

    # Should include mermaid code blocks
    assert "```mermaid" in page.content
    assert "flowchart" in page.content.lower()
