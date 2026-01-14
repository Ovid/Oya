# backend/tests/test_directory_generator.py
"""Directory page generator tests."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from oya.generation.directory import DirectoryGenerator
from oya.generation.summaries import FileSummary, DirectorySummary


@pytest.fixture
def mock_llm_client():
    """Create mock LLM client."""
    client = AsyncMock()
    client.generate.return_value = "# src/auth/\n\nAuthentication module."
    return client


@pytest.fixture
def mock_llm_client_with_yaml():
    """Create mock LLM client that returns YAML summary block."""
    client = AsyncMock()
    client.generate.return_value = """---
directory_summary:
  purpose: "Handles user authentication and session management"
  contains:
    - "login.py"
    - "session.py"
    - "utils.py"
  role_in_system: "Core authentication layer providing security for the application"
---

# src/auth/

Authentication module for the application.

## Overview

This directory contains all authentication-related functionality.
"""
    return client


@pytest.fixture
def sample_file_summaries():
    """Create sample FileSummaries for testing."""
    return [
        FileSummary(
            file_path="src/auth/login.py",
            purpose="Handles user login and credential validation",
            layer="api",
            key_abstractions=["login", "validate_credentials"],
            internal_deps=["src/auth/session.py"],
            external_deps=["bcrypt"],
        ),
        FileSummary(
            file_path="src/auth/session.py",
            purpose="Manages user sessions and tokens",
            layer="domain",
            key_abstractions=["Session", "create_token"],
            internal_deps=[],
            external_deps=["jwt"],
        ),
        FileSummary(
            file_path="src/auth/utils.py",
            purpose="Authentication utility functions",
            layer="utility",
            key_abstractions=["hash_password", "verify_password"],
            internal_deps=[],
            external_deps=["bcrypt"],
        ),
    ]


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


@pytest.fixture
def generator_with_yaml(mock_llm_client_with_yaml, mock_repo):
    """Create directory generator with YAML-returning LLM client."""
    return DirectoryGenerator(
        llm_client=mock_llm_client_with_yaml,
        repo=mock_repo,
    )


class TestDirectoryGeneratorWithFileSummaries:
    """Tests for DirectoryGenerator with FileSummary context.
    
    Requirements: 2.1, 2.6
    """

    @pytest.mark.asyncio
    async def test_generate_uses_file_summaries_and_returns_directory_summary(
        self, generator_with_yaml, mock_llm_client_with_yaml, sample_file_summaries
    ):
        """Test that generate() uses FileSummaries and returns valid DirectorySummary.
        
        Requirements: 2.1, 2.6
        """
        result = await generator_with_yaml.generate(
            directory_path="src/auth",
            file_list=["login.py", "session.py", "utils.py"],
            symbols=[
                {"file": "login.py", "name": "login", "type": "function"},
                {"file": "session.py", "name": "Session", "type": "class"},
            ],
            architecture_context="Handles user authentication.",
            file_summaries=sample_file_summaries,
        )

        # Should return a tuple of (GeneratedPage, DirectorySummary)
        assert isinstance(result, tuple)
        assert len(result) == 2
        
        page, summary = result
        
        # Page should have correct metadata
        assert page.page_type == "directory"
        assert page.target == "src/auth"
        assert page.content  # Should have content
        
        # Summary should be a valid DirectorySummary
        assert isinstance(summary, DirectorySummary)
        assert summary.directory_path == "src/auth"
        assert summary.purpose  # Should have a purpose
        assert isinstance(summary.contains, list)
        assert summary.role_in_system  # Should have role_in_system
        
        # LLM should have been called
        mock_llm_client_with_yaml.generate.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_includes_file_summaries_in_prompt(
        self, generator_with_yaml, mock_llm_client_with_yaml, sample_file_summaries
    ):
        """Test that FileSummaries are included in the LLM prompt as a navigation table.

        Requirements: 2.6
        """
        await generator_with_yaml.generate(
            directory_path="src/auth",
            file_list=["login.py", "session.py", "utils.py"],
            symbols=[],
            architecture_context="",
            file_summaries=sample_file_summaries,
        )

        # Get the prompt that was passed to the LLM
        call_args = mock_llm_client_with_yaml.generate.call_args
        prompt = call_args.kwargs.get("prompt") or call_args.args[0]

        # Prompt should contain file summary information as markdown table
        assert "login.py" in prompt
        assert "Handles user login" in prompt or "login" in prompt.lower()
        # Should include table format with links
        assert "| File | Purpose |" in prompt
        assert "../files/" in prompt  # File links should use relative paths

    @pytest.mark.asyncio
    async def test_generate_returns_fallback_summary_on_parse_failure(
        self, mock_llm_client, mock_repo
    ):
        """Test that generate() returns fallback DirectorySummary when YAML parsing fails.
        
        Requirements: 2.1, 2.5
        """
        # LLM returns content without valid YAML block
        mock_llm_client.generate.return_value = "# src/auth/\n\nAuthentication module."
        
        generator = DirectoryGenerator(
            llm_client=mock_llm_client,
            repo=mock_repo,
        )
        
        result = await generator.generate(
            directory_path="src/auth",
            file_list=["login.py"],
            symbols=[],
            architecture_context="",
            file_summaries=[],
        )

        # Should still return a tuple
        assert isinstance(result, tuple)
        assert len(result) == 2
        
        page, summary = result
        
        # Page should still be generated
        assert page.content
        
        # Summary should be fallback with default values
        assert isinstance(summary, DirectorySummary)
        assert summary.directory_path == "src/auth"
        assert summary.purpose == "Unknown"

    @pytest.mark.asyncio
    async def test_generate_works_with_empty_file_summaries(
        self, generator_with_yaml, sample_file_summaries
    ):
        """Test that generate() works when file_summaries is empty.
        
        Requirements: 2.1
        """
        result = await generator_with_yaml.generate(
            directory_path="src/empty",
            file_list=["file.py"],
            symbols=[],
            architecture_context="",
            file_summaries=[],  # Empty list
        )

        assert isinstance(result, tuple)
        page, summary = result
        assert page.content
        assert isinstance(summary, DirectorySummary)


@pytest.mark.asyncio
async def test_generates_directory_page(generator, mock_llm_client):
    """Generates directory markdown."""
    page, summary = await generator.generate(
        directory_path="src/auth",
        file_list=["login.py", "session.py", "utils.py"],
        symbols=[
            {"file": "login.py", "name": "login", "type": "function"},
            {"file": "session.py", "name": "Session", "type": "class"},
        ],
        architecture_context="Handles user authentication.",
    )

    assert page.content
    mock_llm_client.generate.assert_called_once()


@pytest.mark.asyncio
async def test_returns_directory_metadata(generator):
    """Returns correct page metadata."""
    page, summary = await generator.generate(
        directory_path="src/api",
        file_list=["routes.py"],
        symbols=[],
        architecture_context="",
    )

    assert page.page_type == "directory"
    assert "src-api" in page.path
    assert page.target == "src/api"


@pytest.mark.asyncio
async def test_handles_nested_directories(generator):
    """Handles deeply nested directory paths."""
    page, summary = await generator.generate(
        directory_path="src/services/auth/providers",
        file_list=["oauth.py", "jwt.py"],
        symbols=[],
        architecture_context="",
    )

    assert page.target == "src/services/auth/providers"
    assert "providers" in page.path
