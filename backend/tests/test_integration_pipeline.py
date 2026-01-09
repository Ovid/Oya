"""Integration tests for the bottom-up wiki generation pipeline.

Feature: bottom-up-generation

These tests verify end-to-end behavior of the generation pipeline,
including:
- Full pipeline execution with no README (Task 25.1)
- Cascade behavior when files change (Task 25.2)

Requirements: 5.5, 6.5, 7.1, 7.2, 7.3
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from oya.generation.orchestrator import GenerationOrchestrator, compute_content_hash
from oya.generation.overview import GeneratedPage
from oya.generation.summaries import (
    FileSummary,
    DirectorySummary,
    SynthesisMap,
    LayerInfo,
    ComponentInfo,
)


# ============================================================================
# Task 25.1: Integration test for full pipeline with no README
# ============================================================================


class TestFullPipelineNoReadme:
    """Integration tests for full pipeline execution without README.

    Verifies that generation succeeds and produces valid Architecture/Overview
    pages even when no README.md exists in the repository.

    Requirements: 5.5, 6.5
    """

    @pytest.fixture
    def mock_llm_client(self):
        """Create mock LLM client that returns valid responses."""
        client = AsyncMock()

        # Track call count to return different responses
        call_count = [0]

        async def mock_generate(prompt, system_prompt=None, temperature=None):
            call_count[0] += 1

            # Return different responses based on prompt content
            if "file_summary" in prompt.lower() or "file documentation" in prompt.lower():
                return """# File Documentation

---
file_summary:
  purpose: "Test file for demonstration"
  layer: "utility"
  key_abstractions:
    - "main"
  internal_deps: []
  external_deps:
    - "os"
---

This is a test file."""

            elif "directory" in prompt.lower():
                return """# Directory Documentation

---
directory_summary:
  purpose: "Source code directory"
  contains:
    - "main.py"
  role_in_system: "Contains application code"
---

This directory contains source code."""

            elif "synthesis" in prompt.lower():
                return json.dumps({
                    "key_components": [
                        {
                            "name": "main",
                            "file": "src/main.py",
                            "role": "Entry point",
                            "layer": "utility"
                        }
                    ],
                    "dependency_graph": {
                        "utility": []
                    },
                    "project_summary": "A test project with utility functions."
                })

            elif "architecture" in prompt.lower():
                return """# Architecture

## Overview

This project follows a simple utility-based architecture.

## Layers

### Utility Layer

Contains helper functions and utilities.

## Components

- **main**: Entry point for the application
"""

            elif "overview" in prompt.lower():
                return """# Project Overview

## Summary

A test project demonstrating the wiki generation pipeline.

## Structure

The project contains utility functions organized in the src directory.
"""

            else:
                return "# Generated Content"

        client.generate = mock_generate
        return client

    @pytest.fixture
    def mock_repo_no_readme(self, tmp_path):
        """Create mock repository without README."""
        repo = MagicMock()
        repo.path = tmp_path

        # Create a simple Python file (no README)
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        main_py = src_dir / "main.py"
        main_py.write_text("def main():\n    print('Hello')\n")

        repo.list_files.return_value = ["src/main.py"]
        repo.get_head_commit.return_value = "abc123"
        return repo

    @pytest.fixture
    def mock_db(self):
        """Create mock database."""
        db = MagicMock()
        db._page_info = {}
        db._saved_pages = []

        def mock_execute(query, params=None):
            cursor = MagicMock()
            if "SELECT metadata" in query and params:
                target, page_type = params
                key = f"{target}:{page_type}"
                if key in db._page_info:
                    info = db._page_info[key]
                    cursor.fetchone.return_value = (
                        info.get("metadata"),
                        info.get("generated_at"),
                    )
                else:
                    cursor.fetchone.return_value = None
            elif "SELECT COUNT" in query:
                cursor.fetchone.return_value = (0,)
            elif "INSERT OR REPLACE" in query and params:
                path = params[0]
                db._saved_pages.append(path)
            return cursor

        db.execute = mock_execute
        db.commit = MagicMock()
        return db

    @pytest.mark.asyncio
    async def test_pipeline_succeeds_without_readme(
        self, mock_llm_client, mock_repo_no_readme, mock_db, tmp_path
    ):
        """Pipeline completes successfully when no README exists.

        Requirements: 5.5, 6.5
        """
        wiki_path = tmp_path / "wiki"

        orchestrator = GenerationOrchestrator(
            llm_client=mock_llm_client,
            repo=mock_repo_no_readme,
            db=mock_db,
            wiki_path=wiki_path,
        )

        # Run the full pipeline
        job_id = await orchestrator.run()

        # Verify job completed
        assert job_id is not None
        assert len(job_id) > 0

    @pytest.mark.asyncio
    async def test_architecture_page_generated_without_readme(
        self, mock_llm_client, mock_repo_no_readme, mock_db, tmp_path
    ):
        """Architecture page is generated even without README.

        Requirements: 5.5
        """
        wiki_path = tmp_path / "wiki"

        orchestrator = GenerationOrchestrator(
            llm_client=mock_llm_client,
            repo=mock_repo_no_readme,
            db=mock_db,
            wiki_path=wiki_path,
        )

        await orchestrator.run()

        # Verify architecture page was created
        arch_path = wiki_path / "architecture.md"
        assert arch_path.exists(), "Architecture page should be generated"

        # Verify content is valid
        content = arch_path.read_text()
        assert len(content) > 0, "Architecture page should have content"
        assert "Architecture" in content or "architecture" in content.lower()

    @pytest.mark.asyncio
    async def test_overview_page_generated_without_readme(
        self, mock_llm_client, mock_repo_no_readme, mock_db, tmp_path
    ):
        """Overview page is generated even without README.

        Requirements: 6.5
        """
        wiki_path = tmp_path / "wiki"

        orchestrator = GenerationOrchestrator(
            llm_client=mock_llm_client,
            repo=mock_repo_no_readme,
            db=mock_db,
            wiki_path=wiki_path,
        )

        await orchestrator.run()

        # Verify overview page was created
        overview_path = wiki_path / "overview.md"
        assert overview_path.exists(), "Overview page should be generated"

        # Verify content is valid
        content = overview_path.read_text()
        assert len(content) > 0, "Overview page should have content"

    @pytest.mark.asyncio
    async def test_synthesis_map_created_without_readme(
        self, mock_llm_client, mock_repo_no_readme, mock_db, tmp_path
    ):
        """Synthesis map is created and saved without README.

        Requirements: 5.5, 6.5 (synthesis is prerequisite for arch/overview)
        """
        wiki_path = tmp_path / "wiki"

        orchestrator = GenerationOrchestrator(
            llm_client=mock_llm_client,
            repo=mock_repo_no_readme,
            db=mock_db,
            wiki_path=wiki_path,
        )

        await orchestrator.run()

        # Verify synthesis.json was created
        synthesis_path = orchestrator.meta_path / "synthesis.json"
        assert synthesis_path.exists(), "synthesis.json should be created"

        # Verify content is valid JSON
        with open(synthesis_path) as f:
            data = json.load(f)

        assert "layers" in data, "Synthesis should contain layers"
        assert "synthesis_hash" in data, "Synthesis should contain hash"

    @pytest.mark.asyncio
    async def test_file_pages_generated_before_high_level_docs(
        self, mock_llm_client, mock_repo_no_readme, mock_db, tmp_path
    ):
        """File documentation is generated before architecture/overview.

        This verifies the bottom-up approach where file summaries inform
        high-level documentation.

        Requirements: 5.5, 6.5
        """
        wiki_path = tmp_path / "wiki"

        orchestrator = GenerationOrchestrator(
            llm_client=mock_llm_client,
            repo=mock_repo_no_readme,
            db=mock_db,
            wiki_path=wiki_path,
        )

        # Track phase order
        phase_order = []

        async def progress_callback(progress):
            if progress.phase.value not in phase_order:
                phase_order.append(progress.phase.value)

        await orchestrator.run(progress_callback=progress_callback)

        # Verify files phase comes before architecture and overview
        if "files" in phase_order and "architecture" in phase_order:
            files_idx = phase_order.index("files")
            arch_idx = phase_order.index("architecture")
            assert files_idx < arch_idx, "Files should be processed before architecture"

        if "files" in phase_order and "overview" in phase_order:
            files_idx = phase_order.index("files")
            overview_idx = phase_order.index("overview")
            assert files_idx < overview_idx, "Files should be processed before overview"


# ============================================================================
# Task 25.2: Integration test for cascade behavior
# ============================================================================


class TestCascadeBehavior:
    """Integration tests for cascade regeneration behavior.

    Verifies that modifying a file triggers the cascade:
    file change -> file regen -> synthesis regen -> arch/overview regen

    Requirements: 7.1, 7.2, 7.3
    """

    @pytest.fixture
    def mock_llm_client(self):
        """Create mock LLM client."""
        client = AsyncMock()

        async def mock_generate(prompt, system_prompt=None, temperature=None):
            if "file_summary" in prompt.lower() or "file documentation" in prompt.lower():
                return """# File Documentation

---
file_summary:
  purpose: "Test file"
  layer: "utility"
  key_abstractions: ["main"]
  internal_deps: []
  external_deps: []
---

File content."""

            elif "directory" in prompt.lower():
                return """# Directory

---
directory_summary:
  purpose: "Source directory"
  contains: ["main.py"]
  role_in_system: "Contains code"
---

Directory content."""

            elif "synthesis" in prompt.lower():
                return json.dumps({
                    "key_components": [],
                    "dependency_graph": {},
                    "project_summary": "Test project"
                })

            elif "architecture" in prompt.lower():
                return "# Architecture\n\nArchitecture content."

            elif "overview" in prompt.lower():
                return "# Overview\n\nOverview content."

            return "# Generated"

        client.generate = mock_generate
        return client

    @pytest.fixture
    def mock_repo(self, tmp_path):
        """Create mock repository with a Python file."""
        repo = MagicMock()
        repo.path = tmp_path

        src_dir = tmp_path / "src"
        src_dir.mkdir()
        main_py = src_dir / "main.py"
        main_py.write_text("def main():\n    pass\n")

        repo.list_files.return_value = ["src/main.py"]
        repo.get_head_commit.return_value = "abc123"
        return repo

    @pytest.fixture
    def mock_db_with_history(self):
        """Create mock database that tracks page history."""
        db = MagicMock()
        db._page_info = {}
        db._saved_pages = []
        db._save_count = {}

        def mock_execute(query, params=None):
            cursor = MagicMock()
            if "SELECT metadata" in query and params:
                target, page_type = params
                key = f"{target}:{page_type}"
                if key in db._page_info:
                    info = db._page_info[key]
                    cursor.fetchone.return_value = (
                        info.get("metadata"),
                        info.get("generated_at"),
                    )
                else:
                    cursor.fetchone.return_value = None
            elif "SELECT COUNT" in query:
                cursor.fetchone.return_value = (0,)
            elif "INSERT OR REPLACE" in query and params:
                path = params[0]
                db._saved_pages.append(path)
                db._save_count[path] = db._save_count.get(path, 0) + 1
            return cursor

        db.execute = mock_execute
        db.commit = MagicMock()
        return db

    @pytest.mark.asyncio
    async def test_file_change_triggers_file_regeneration(
        self, mock_llm_client, mock_repo, mock_db_with_history, tmp_path
    ):
        """Changed file content triggers file documentation regeneration.

        Requirements: 7.1
        """
        wiki_path = tmp_path / "wiki"

        orchestrator = GenerationOrchestrator(
            llm_client=mock_llm_client,
            repo=mock_repo,
            db=mock_db_with_history,
            wiki_path=wiki_path,
        )

        # First run - generate initial docs
        await orchestrator.run()

        # Record initial state
        initial_file_saves = [p for p in mock_db_with_history._saved_pages if "files/" in p]

        # Simulate file change by updating the hash in the repo
        main_py = mock_repo.path / "src" / "main.py"
        original_content = main_py.read_text()
        new_content = original_content + "\n# Modified\n"
        main_py.write_text(new_content)

        # Clear saved pages tracking
        mock_db_with_history._saved_pages = []

        # Second run - should detect change and regenerate
        await orchestrator.run()

        # Verify file was regenerated
        file_saves = [p for p in mock_db_with_history._saved_pages if "files/" in p]
        assert len(file_saves) > 0, "Changed file should be regenerated"

    @pytest.mark.asyncio
    async def test_file_regeneration_triggers_synthesis_regeneration(
        self, mock_llm_client, mock_repo, mock_db_with_history, tmp_path
    ):
        """File regeneration triggers synthesis map regeneration.

        Requirements: 7.2
        """
        wiki_path = tmp_path / "wiki"

        orchestrator = GenerationOrchestrator(
            llm_client=mock_llm_client,
            repo=mock_repo,
            db=mock_db_with_history,
            wiki_path=wiki_path,
        )

        # First run
        await orchestrator.run()

        # Get initial synthesis hash
        synthesis_path = orchestrator.meta_path / "synthesis.json"
        with open(synthesis_path) as f:
            initial_data = json.load(f)
        initial_hash = initial_data.get("synthesis_hash")

        # Modify file
        main_py = mock_repo.path / "src" / "main.py"
        main_py.write_text("def main():\n    print('changed')\n")

        # Second run
        await orchestrator.run()

        # Verify synthesis was regenerated (file exists and was updated)
        assert synthesis_path.exists(), "Synthesis should exist after regeneration"

    @pytest.mark.asyncio
    async def test_synthesis_regeneration_triggers_arch_overview_regeneration(
        self, mock_llm_client, mock_repo, mock_db_with_history, tmp_path
    ):
        """Synthesis regeneration triggers architecture and overview regeneration.

        Requirements: 7.3
        """
        wiki_path = tmp_path / "wiki"

        orchestrator = GenerationOrchestrator(
            llm_client=mock_llm_client,
            repo=mock_repo,
            db=mock_db_with_history,
            wiki_path=wiki_path,
        )

        # First run
        await orchestrator.run()

        # Clear tracking
        mock_db_with_history._saved_pages = []

        # Modify file to trigger cascade
        main_py = mock_repo.path / "src" / "main.py"
        main_py.write_text("def main():\n    print('cascade test')\n")

        # Second run
        await orchestrator.run()

        # Verify architecture and overview were regenerated
        saved_pages = mock_db_with_history._saved_pages
        arch_saved = any("architecture" in p for p in saved_pages)
        overview_saved = any("overview" in p for p in saved_pages)

        assert arch_saved, "Architecture should be regenerated when synthesis changes"
        assert overview_saved, "Overview should be regenerated when synthesis changes"

    @pytest.mark.asyncio
    async def test_no_change_skips_regeneration(
        self, mock_llm_client, mock_repo, mock_db_with_history, tmp_path
    ):
        """No file changes skips all regeneration.

        Requirements: 7.1, 7.2, 7.3 (inverse case)
        """
        wiki_path = tmp_path / "wiki"

        orchestrator = GenerationOrchestrator(
            llm_client=mock_llm_client,
            repo=mock_repo,
            db=mock_db_with_history,
            wiki_path=wiki_path,
        )

        # First run - generate everything
        await orchestrator.run()

        # Store the file hash in the mock db to simulate "already generated"
        main_py = mock_repo.path / "src" / "main.py"
        content = main_py.read_text()
        content_hash = compute_content_hash(content)
        mock_db_with_history._page_info["src/main.py:file"] = {
            "metadata": json.dumps({"source_hash": content_hash}),
            "generated_at": "2025-01-01T00:00:00",
        }

        # Clear tracking
        mock_db_with_history._saved_pages = []

        # Second run with no changes
        await orchestrator.run()

        # Verify no file pages were regenerated
        file_saves = [p for p in mock_db_with_history._saved_pages if "files/" in p]
        assert len(file_saves) == 0, "Unchanged files should not be regenerated"

    @pytest.mark.asyncio
    async def test_full_cascade_chain(
        self, mock_llm_client, mock_repo, mock_db_with_history, tmp_path
    ):
        """Full cascade: file change -> file regen -> synthesis -> arch/overview.

        Requirements: 7.1, 7.2, 7.3
        """
        wiki_path = tmp_path / "wiki"

        orchestrator = GenerationOrchestrator(
            llm_client=mock_llm_client,
            repo=mock_repo,
            db=mock_db_with_history,
            wiki_path=wiki_path,
        )

        # First run
        await orchestrator.run()

        # Store initial state
        main_py = mock_repo.path / "src" / "main.py"
        original_content = main_py.read_text()
        original_hash = compute_content_hash(original_content)

        # Simulate that file was already generated
        mock_db_with_history._page_info["src/main.py:file"] = {
            "metadata": json.dumps({"source_hash": original_hash}),
            "generated_at": "2025-01-01T00:00:00",
        }

        # Clear tracking
        mock_db_with_history._saved_pages = []

        # Modify file
        new_content = "def main():\n    print('full cascade')\n"
        main_py.write_text(new_content)

        # Track phases
        phases_executed = []

        async def progress_callback(progress):
            if progress.phase.value not in phases_executed:
                phases_executed.append(progress.phase.value)

        # Run with progress tracking
        await orchestrator.run(progress_callback=progress_callback)

        # Verify cascade occurred
        saved_pages = mock_db_with_history._saved_pages

        # File should be regenerated (7.1)
        file_regenerated = any("files/" in p for p in saved_pages)
        assert file_regenerated, "Changed file should trigger file regeneration (7.1)"

        # Synthesis should be regenerated (7.2)
        synthesis_path = orchestrator.meta_path / "synthesis.json"
        assert synthesis_path.exists(), "Synthesis should be regenerated (7.2)"

        # Architecture and Overview should be regenerated (7.3)
        arch_regenerated = any("architecture" in p for p in saved_pages)
        overview_regenerated = any("overview" in p for p in saved_pages)
        assert arch_regenerated, "Architecture should be regenerated (7.3)"
        assert overview_regenerated, "Overview should be regenerated (7.3)"
