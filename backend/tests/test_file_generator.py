# backend/tests/test_file_generator.py
"""File page generator tests."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from oya.generation.file import FileGenerator
from oya.generation.summaries import FileSummary


@pytest.fixture
def mock_llm_client():
    """Create mock LLM client that returns content with valid YAML summary."""
    client = AsyncMock()
    client.generate.return_value = """---
file_summary:
  purpose: "Handles user authentication"
  layer: api
  key_abstractions: []
  internal_deps: []
  external_deps: []
---

# login.py

Handles user authentication.
"""
    return client


@pytest.fixture
def mock_llm_client_with_summary():
    """Create mock LLM client that returns content with YAML summary block."""
    client = AsyncMock()
    client.generate.return_value = """---
file_summary:
  purpose: "Handles user authentication and login flow"
  layer: api
  key_abstractions:
    - "login"
    - "authenticate_user"
  internal_deps:
    - "src/auth/utils.py"
  external_deps:
    - "flask"
---

# login.py

Handles user authentication.

## Functions

### login(user, password)
Authenticates a user with the given credentials.
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
    """Create file generator."""
    return FileGenerator(
        llm_client=mock_llm_client,
        repo=mock_repo,
    )


@pytest.mark.asyncio
async def test_generates_file_page(generator, mock_llm_client):
    """Generates file documentation markdown."""
    page, summary = await generator.generate(
        file_path="src/auth/login.py",
        content="def login(user, password): pass",
        symbols=[{"name": "login", "type": "function", "line": 1}],
        imports=["from flask import request"],
        architecture_summary="Authentication module.",
    )

    assert page.content
    mock_llm_client.generate.assert_called_once()


@pytest.mark.asyncio
async def test_returns_file_metadata(generator):
    """Returns correct page metadata."""
    page, summary = await generator.generate(
        file_path="src/main.py",
        content="print('hello')",
        symbols=[],
        imports=[],
        architecture_summary="",
    )

    assert page.page_type == "file"
    assert "src-main-py" in page.path
    assert page.target == "src/main.py"


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


# =============================================================================
# Task 9.1: Tests for FileGenerator summary extraction
# =============================================================================


@pytest.fixture
def generator_with_summary(mock_llm_client_with_summary, mock_repo):
    """Create file generator with LLM that returns summary."""
    return FileGenerator(
        llm_client=mock_llm_client_with_summary,
        repo=mock_repo,
    )


@pytest.mark.asyncio
async def test_generate_returns_tuple_with_file_summary(generator_with_summary):
    """Test that generate() returns a tuple of (GeneratedPage, FileSummary).
    
    Requirements: 1.1 - FileGenerator SHALL include a structured File_Summary block.
    """
    result = await generator_with_summary.generate(
        file_path="src/auth/login.py",
        content="def login(user, password): pass",
        symbols=[{"name": "login", "type": "function", "line": 1}],
        imports=["from flask import request"],
        architecture_summary="Authentication module.",
    )
    
    # Result should be a tuple of (GeneratedPage, FileSummary)
    assert isinstance(result, tuple)
    assert len(result) == 2
    
    page, summary = result
    
    # First element should be GeneratedPage
    assert page.page_type == "file"
    assert page.target == "src/auth/login.py"
    
    # Second element should be FileSummary
    assert isinstance(summary, FileSummary)


@pytest.mark.asyncio
async def test_generate_extracts_valid_file_summary(generator_with_summary):
    """Test that generate() extracts valid FileSummary from LLM output.
    
    Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6 - FileSummary fields.
    """
    page, summary = await generator_with_summary.generate(
        file_path="src/auth/login.py",
        content="def login(user, password): pass",
        symbols=[{"name": "login", "type": "function", "line": 1}],
        imports=["from flask import request"],
        architecture_summary="Authentication module.",
    )
    
    # FileSummary should have correct values from YAML block
    assert summary.file_path == "src/auth/login.py"
    assert summary.purpose == "Handles user authentication and login flow"
    assert summary.layer == "api"
    assert "login" in summary.key_abstractions
    assert "authenticate_user" in summary.key_abstractions
    assert "src/auth/utils.py" in summary.internal_deps
    assert "flask" in summary.external_deps


@pytest.mark.asyncio
async def test_generate_strips_yaml_from_page_content(generator_with_summary):
    """Test that YAML block is stripped from the page content.
    
    Requirements: 8.5 - Parser SHALL strip the summary block from user-facing markdown.
    """
    page, summary = await generator_with_summary.generate(
        file_path="src/auth/login.py",
        content="def login(user, password): pass",
        symbols=[{"name": "login", "type": "function", "line": 1}],
        imports=["from flask import request"],
        architecture_summary="Authentication module.",
    )
    
    # Page content should NOT contain YAML block
    assert "file_summary:" not in page.content
    assert "---\nfile_summary:" not in page.content
    
    # Page content should still have the markdown documentation
    assert "# login.py" in page.content
    assert "Handles user authentication" in page.content


@pytest.mark.asyncio
async def test_generate_returns_fallback_summary_on_missing_yaml(mock_repo):
    """Test that generate() returns fallback FileSummary when YAML is missing.
    
    Requirements: 1.7 - SHALL use fallback summary with purpose="Unknown", layer="utility".
    """
    # LLM client that returns content without YAML block
    mock_llm = AsyncMock()
    mock_llm.generate.return_value = "# file.py\n\nSome documentation without YAML."
    
    generator = FileGenerator(llm_client=mock_llm, repo=mock_repo)
    
    page, summary = await generator.generate(
        file_path="src/utils/helper.py",
        content="def helper(): pass",
        symbols=[],
        imports=[],
        architecture_summary="",
    )
    
    # Should return fallback summary
    assert summary.file_path == "src/utils/helper.py"
    assert summary.purpose == "Unknown"
    assert summary.layer == "utility"
    assert summary.key_abstractions == []
    assert summary.internal_deps == []
    assert summary.external_deps == []


# =============================================================================
# Task 4: Tests for retry semantics on YAML parsing failures
# =============================================================================


@pytest.mark.asyncio
async def test_generate_retries_on_yaml_failure(mock_repo, caplog):
    """Test that generate() retries once when YAML parsing fails."""
    import logging

    # First call returns bad YAML, second call returns good YAML
    mock_llm = AsyncMock()
    mock_llm.generate.side_effect = [
        "# file.py\n\nNo YAML block here.",  # First attempt fails
        """---
file_summary:
  purpose: "Test file after retry"
  layer: utility
  key_abstractions: []
  internal_deps: []
  external_deps: []
---

# file.py

Documentation after retry.
""",  # Second attempt succeeds
    ]

    generator = FileGenerator(llm_client=mock_llm, repo=mock_repo)

    with caplog.at_level(logging.WARNING):
        page, summary = await generator.generate(
            file_path="src/test.py",
            content="# test",
            symbols=[],
            imports=[],
            architecture_summary="",
        )

    # Should have called LLM twice (original + retry)
    assert mock_llm.generate.call_count == 2

    # Should have logged a warning about retry
    assert "YAML parsing failed" in caplog.text
    assert "retrying" in caplog.text

    # Should have the successful result
    assert summary.purpose == "Test file after retry"


@pytest.mark.asyncio
async def test_generate_logs_error_after_retry_fails(mock_repo, caplog):
    """Test that generate() logs error when retry also fails."""
    import logging

    # Both calls return bad YAML
    mock_llm = AsyncMock()
    mock_llm.generate.return_value = "# file.py\n\nNo YAML block here."

    generator = FileGenerator(llm_client=mock_llm, repo=mock_repo)

    with caplog.at_level(logging.WARNING):
        page, summary = await generator.generate(
            file_path="src/test.py",
            content="# test",
            symbols=[],
            imports=[],
            architecture_summary="",
        )

    # Should have called LLM twice
    assert mock_llm.generate.call_count == 2

    # Should have logged warning then error
    assert "YAML parsing failed" in caplog.text
    assert "retrying" in caplog.text
    assert "after retry" in caplog.text

    # Should return fallback summary
    assert summary.purpose == "Unknown"
    assert summary.layer == "utility"


# =============================================================================
# Task 6: Tests for Mermaid diagram integration
# =============================================================================


@pytest.mark.asyncio
async def test_generate_includes_class_diagram_when_classes_present(mock_repo):
    """Test that class diagram is included when file has classes."""
    from oya.parsing.models import ParsedSymbol, SymbolType

    mock_llm = AsyncMock()
    mock_llm.generate.return_value = """---
file_summary:
  purpose: "Service class"
  layer: domain
  key_abstractions:
    - "UserService"
  internal_deps: []
  external_deps: []
---

# user_service.py

User service implementation.
"""

    generator = FileGenerator(llm_client=mock_llm, repo=mock_repo)

    # Provide symbols with a class
    symbols = [
        ParsedSymbol(
            name="UserService",
            symbol_type=SymbolType.CLASS,
            start_line=1,
            end_line=10,
        ),
        ParsedSymbol(
            name="get_user",
            symbol_type=SymbolType.METHOD,
            start_line=5,
            end_line=8,
            parent="UserService",
        ),
    ]

    page, summary = await generator.generate(
        file_path="src/service.py",
        content="class UserService:\n    def get_user(self): pass",
        symbols=[{"name": "UserService", "type": "class", "line": 1}],
        imports=[],
        architecture_summary="",
        parsed_symbols=symbols,
    )

    # Should include class diagram
    assert "## Diagrams" in page.content
    assert "classDiagram" in page.content
    assert "UserService" in page.content


@pytest.mark.asyncio
async def test_generate_includes_dependency_diagram_when_imports_present(mock_repo):
    """Test that dependency diagram is included when file has imports."""
    mock_llm = AsyncMock()
    mock_llm.generate.return_value = """---
file_summary:
  purpose: "Routes file"
  layer: api
  key_abstractions: []
  internal_deps:
    - "src/service.py"
  external_deps: []
---

# routes.py

API routes.
"""

    generator = FileGenerator(llm_client=mock_llm, repo=mock_repo)

    file_imports = {
        "src/routes.py": ["src/service.py"],
        "src/service.py": [],
    }

    page, summary = await generator.generate(
        file_path="src/routes.py",
        content="from src.service import Service",
        symbols=[],
        imports=["from src.service import Service"],
        architecture_summary="",
        file_imports=file_imports,
    )

    # Should include dependency diagram
    assert "## Diagrams" in page.content
    assert "flowchart" in page.content


@pytest.mark.asyncio
async def test_generate_omits_diagrams_when_no_classes_or_deps(mock_repo):
    """Test that diagrams section is omitted when not applicable."""
    mock_llm = AsyncMock()
    mock_llm.generate.return_value = """---
file_summary:
  purpose: "Simple utility"
  layer: utility
  key_abstractions: []
  internal_deps: []
  external_deps: []
---

# utils.py

Simple utilities.
"""

    generator = FileGenerator(llm_client=mock_llm, repo=mock_repo)

    page, summary = await generator.generate(
        file_path="src/utils.py",
        content="def helper(): pass",
        symbols=[],
        imports=[],
        architecture_summary="",
    )

    # Should NOT include diagrams section
    assert "## Diagrams" not in page.content
