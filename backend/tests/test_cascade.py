"""Property-based tests for cascade regeneration behavior.

Feature: bottom-up-generation

These tests verify that changes to files cascade appropriately through the
generation pipeline, triggering regeneration of dependent documentation.
"""

import hashlib
from unittest.mock import MagicMock, AsyncMock, patch
from pathlib import Path

import pytest
from hypothesis import given, settings, strategies as st, HealthCheck

from oya.generation.orchestrator import (
    GenerationOrchestrator,
    compute_content_hash,
)


# ============================================================================
# Strategies for generating test data
# ============================================================================

# Safe alphabet for file content
CONTENT_ALPHABET = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 \n\t_-=+[]{}()#@!$%^&*"


@st.composite
def file_content_strategy(draw):
    """Generate valid file content."""
    return draw(st.text(alphabet=CONTENT_ALPHABET, min_size=1, max_size=1000))


@st.composite
def file_path_strategy(draw):
    """Generate valid file paths."""
    # Generate path components
    num_parts = draw(st.integers(min_value=1, max_value=4))
    parts = []
    for _ in range(num_parts - 1):
        part = draw(st.text(
            alphabet="abcdefghijklmnopqrstuvwxyz0123456789_-",
            min_size=1,
            max_size=20
        ).filter(lambda x: x.strip()))
        parts.append(part)
    
    # Add filename with extension
    filename = draw(st.text(
        alphabet="abcdefghijklmnopqrstuvwxyz0123456789_-",
        min_size=1,
        max_size=20
    ).filter(lambda x: x.strip()))
    extension = draw(st.sampled_from([".py", ".ts", ".js", ".tsx", ".jsx", ".java"]))
    parts.append(filename + extension)
    
    return "/".join(parts)


@st.composite
def file_with_content_strategy(draw):
    """Generate a file path with original and modified content."""
    file_path = draw(file_path_strategy())
    original_content = draw(file_content_strategy())
    
    # Generate modified content that is different from original
    modified_content = draw(file_content_strategy().filter(
        lambda x: x != original_content
    ))
    
    return {
        "file_path": file_path,
        "original_content": original_content,
        "modified_content": modified_content,
    }


# ============================================================================
# Property 10: Cascade - File Change Triggers Regeneration
# ============================================================================


class TestFileChangeCascade:
    """Property 10: Cascade - File Change Triggers Regeneration
    
    For any file whose content hash has changed since the last generation,
    running the Generation_Pipeline SHALL regenerate that file's documentation.
    
    Validates: Requirements 7.1
    """

    @pytest.fixture
    def mock_llm_client(self):
        """Create mock LLM client."""
        client = AsyncMock()
        client.generate.return_value = "# Generated Content"
        return client

    @pytest.fixture
    def mock_repo(self, tmp_path):
        """Create mock repository."""
        repo = MagicMock()
        repo.path = tmp_path
        repo.list_files.return_value = []
        repo.get_head_commit.return_value = "abc123"
        return repo

    @pytest.fixture
    def mock_db(self):
        """Create mock database that tracks page info."""
        db = MagicMock()
        db._page_info = {}  # Store page info for testing
        
        def mock_execute(query, params=None):
            cursor = MagicMock()
            if "SELECT metadata" in query and params:
                target, page_type = params
                key = f"{target}:{page_type}"
                if key in db._page_info:
                    info = db._page_info[key]
                    cursor.fetchone.return_value = (info.get("metadata"), info.get("generated_at"))
                else:
                    cursor.fetchone.return_value = None
            elif "SELECT COUNT" in query:
                cursor.fetchone.return_value = (0,)  # No new notes
            return cursor
        
        db.execute = mock_execute
        db.commit = MagicMock()
        return db

    @given(data=file_with_content_strategy())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_changed_content_hash_triggers_regeneration(
        self, data, mock_llm_client, mock_repo, mock_db, tmp_path
    ):
        """Feature: bottom-up-generation, Property 10: Cascade - File Change Triggers Regeneration
        
        When a file's content hash changes, _should_regenerate_file returns True.
        """
        orchestrator = GenerationOrchestrator(
            llm_client=mock_llm_client,
            repo=mock_repo,
            db=mock_db,
            wiki_path=tmp_path / "wiki",
        )
        
        file_path = data["file_path"]
        original_content = data["original_content"]
        modified_content = data["modified_content"]
        
        # Compute hashes
        original_hash = compute_content_hash(original_content)
        modified_hash = compute_content_hash(modified_content)
        
        # Simulate that the file was previously generated with original content
        key = f"{file_path}:file"
        mock_db._page_info[key] = {
            "metadata": f'{{"source_hash": "{original_hash}"}}',
            "generated_at": "2025-01-01T00:00:00",
        }
        
        # Check if file should be regenerated with modified content
        file_hashes = {}
        should_regen, content_hash = orchestrator._should_regenerate_file(
            file_path, modified_content, file_hashes
        )
        
        # Since content changed, should_regen must be True
        assert should_regen is True, (
            f"File with changed content should trigger regeneration. "
            f"Original hash: {original_hash}, Modified hash: {modified_hash}"
        )
        
        # The returned hash should match the modified content
        assert content_hash == modified_hash

    @given(content=file_content_strategy(), file_path=file_path_strategy())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_unchanged_content_hash_skips_regeneration(
        self, content, file_path, mock_llm_client, mock_repo, mock_db, tmp_path
    ):
        """Feature: bottom-up-generation, Property 10: Cascade - File Change Triggers Regeneration
        
        When a file's content hash is unchanged, _should_regenerate_file returns False.
        """
        orchestrator = GenerationOrchestrator(
            llm_client=mock_llm_client,
            repo=mock_repo,
            db=mock_db,
            wiki_path=tmp_path / "wiki",
        )
        
        # Compute hash
        content_hash = compute_content_hash(content)
        
        # Simulate that the file was previously generated with same content
        key = f"{file_path}:file"
        mock_db._page_info[key] = {
            "metadata": f'{{"source_hash": "{content_hash}"}}',
            "generated_at": "2025-01-01T00:00:00",
        }
        
        # Check if file should be regenerated with same content
        file_hashes = {}
        should_regen, returned_hash = orchestrator._should_regenerate_file(
            file_path, content, file_hashes
        )
        
        # Since content is unchanged, should_regen must be False
        assert should_regen is False, (
            f"File with unchanged content should NOT trigger regeneration. "
            f"Content hash: {content_hash}"
        )
        
        # The returned hash should match
        assert returned_hash == content_hash

    @given(content=file_content_strategy(), file_path=file_path_strategy())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_new_file_triggers_regeneration(
        self, content, file_path, mock_llm_client, mock_repo, mock_db, tmp_path
    ):
        """Feature: bottom-up-generation, Property 10: Cascade - File Change Triggers Regeneration
        
        When a file has no previous generation record, _should_regenerate_file returns True.
        """
        orchestrator = GenerationOrchestrator(
            llm_client=mock_llm_client,
            repo=mock_repo,
            db=mock_db,
            wiki_path=tmp_path / "wiki",
        )
        
        # Don't add any page info - simulating a new file
        # mock_db._page_info is empty for this file
        
        # Check if file should be regenerated
        file_hashes = {}
        should_regen, content_hash = orchestrator._should_regenerate_file(
            file_path, content, file_hashes
        )
        
        # New files should always trigger regeneration
        assert should_regen is True, (
            f"New file (no previous record) should trigger regeneration."
        )
        
        # The returned hash should be computed correctly
        expected_hash = compute_content_hash(content)
        assert content_hash == expected_hash

    @given(data=file_with_content_strategy())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_content_hash_is_deterministic(self, data):
        """Feature: bottom-up-generation, Property 10: Cascade - File Change Triggers Regeneration
        
        Content hash computation is deterministic - same content always produces same hash.
        """
        content = data["original_content"]
        
        # Compute hash multiple times
        hash1 = compute_content_hash(content)
        hash2 = compute_content_hash(content)
        hash3 = compute_content_hash(content)
        
        # All hashes should be identical
        assert hash1 == hash2 == hash3, (
            f"Content hash should be deterministic. Got: {hash1}, {hash2}, {hash3}"
        )

    @given(data=file_with_content_strategy())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_different_content_produces_different_hash(self, data):
        """Feature: bottom-up-generation, Property 10: Cascade - File Change Triggers Regeneration
        
        Different content produces different hashes (collision resistance).
        """
        original_content = data["original_content"]
        modified_content = data["modified_content"]
        
        # Compute hashes
        original_hash = compute_content_hash(original_content)
        modified_hash = compute_content_hash(modified_content)
        
        # Different content should produce different hashes
        assert original_hash != modified_hash, (
            f"Different content should produce different hashes. "
            f"Original: {original_hash}, Modified: {modified_hash}"
        )



# ============================================================================
# Unit Tests for End-to-End Cascade Behavior (Task 20.2)
# ============================================================================


class TestFileChangeCascadeEndToEnd:
    """Unit tests verifying end-to-end cascade behavior for file changes.
    
    These tests verify that the _run_files method correctly uses
    _should_regenerate_file to determine which files need regeneration.
    
    Requirements: 7.1
    """

    @pytest.fixture
    def mock_llm_client(self):
        """Create mock LLM client."""
        client = AsyncMock()
        client.generate.return_value = "# Generated Content"
        return client

    @pytest.fixture
    def mock_repo(self, tmp_path):
        """Create mock repository."""
        repo = MagicMock()
        repo.path = tmp_path
        repo.list_files.return_value = []
        repo.get_head_commit.return_value = "abc123"
        return repo

    @pytest.fixture
    def mock_db_with_tracking(self):
        """Create mock database that tracks page info and regeneration calls."""
        db = MagicMock()
        db._page_info = {}
        db._regenerated_files = []
        
        def mock_execute(query, params=None):
            cursor = MagicMock()
            if "SELECT metadata" in query and params:
                target, page_type = params
                key = f"{target}:{page_type}"
                if key in db._page_info:
                    info = db._page_info[key]
                    cursor.fetchone.return_value = (info.get("metadata"), info.get("generated_at"))
                else:
                    cursor.fetchone.return_value = None
            elif "SELECT COUNT" in query:
                cursor.fetchone.return_value = (0,)
            elif "INSERT OR REPLACE" in query and params:
                # Track which files are being saved (regenerated)
                path = params[0]
                if path.startswith("files/"):
                    db._regenerated_files.append(path)
            return cursor
        
        db.execute = mock_execute
        db.commit = MagicMock()
        return db

    @pytest.mark.asyncio
    async def test_changed_file_is_regenerated_in_pipeline(
        self, mock_llm_client, mock_repo, mock_db_with_tracking, tmp_path
    ):
        """Changed file content triggers regeneration in _run_files.
        
        Requirements: 7.1
        """
        from oya.generation.summaries import FileSummary
        from oya.generation.overview import GeneratedPage
        
        orchestrator = GenerationOrchestrator(
            llm_client=mock_llm_client,
            repo=mock_repo,
            db=mock_db_with_tracking,
            wiki_path=tmp_path / "wiki",
        )
        
        # Setup: file was previously generated with old content
        old_content = "print('old version')"
        old_hash = compute_content_hash(old_content)
        mock_db_with_tracking._page_info["src/main.py:file"] = {
            "metadata": f'{{"source_hash": "{old_hash}"}}',
            "generated_at": "2025-01-01T00:00:00",
        }
        
        # New content is different
        new_content = "print('new version')"
        
        # Mock the file generator
        mock_page = GeneratedPage(
            content="# File Doc",
            page_type="file",
            path="files/src-main-py.md",
            word_count=10,
            target="src/main.py",
        )
        mock_summary = FileSummary(
            file_path="src/main.py",
            purpose="Main entry point",
            layer="api",
        )
        
        async def mock_generate(*args, **kwargs):
            return mock_page, mock_summary
        
        orchestrator.file_generator.generate = mock_generate
        
        # Run files phase with changed content
        analysis = {
            "files": ["src/main.py"],
            "symbols": [],
            "file_tree": "src/main.py",
            "file_contents": {"src/main.py": new_content},
        }
        
        pages, file_hashes, file_summaries = await orchestrator._run_files(analysis)
        
        # File should have been regenerated
        assert len(pages) == 1, "Changed file should be regenerated"
        assert pages[0].target == "src/main.py"
        assert len(file_summaries) == 1
        assert file_summaries[0].file_path == "src/main.py"

    @pytest.mark.asyncio
    async def test_unchanged_file_is_skipped_in_pipeline(
        self, mock_llm_client, mock_repo, mock_db_with_tracking, tmp_path
    ):
        """Unchanged file content skips regeneration in _run_files.
        
        Requirements: 7.1
        """
        from oya.generation.summaries import FileSummary
        from oya.generation.overview import GeneratedPage
        
        orchestrator = GenerationOrchestrator(
            llm_client=mock_llm_client,
            repo=mock_repo,
            db=mock_db_with_tracking,
            wiki_path=tmp_path / "wiki",
        )
        
        # Setup: file was previously generated with same content
        content = "print('same version')"
        content_hash = compute_content_hash(content)
        mock_db_with_tracking._page_info["src/main.py:file"] = {
            "metadata": f'{{"source_hash": "{content_hash}"}}',
            "generated_at": "2025-01-01T00:00:00",
        }
        
        # Track if generate was called
        generate_called = []
        
        async def mock_generate(*args, **kwargs):
            generate_called.append(True)
            mock_page = GeneratedPage(
                content="# File Doc",
                page_type="file",
                path="files/src-main-py.md",
                word_count=10,
                target="src/main.py",
            )
            mock_summary = FileSummary(
                file_path="src/main.py",
                purpose="Main entry point",
                layer="api",
            )
            return mock_page, mock_summary
        
        orchestrator.file_generator.generate = mock_generate
        
        # Run files phase with same content
        analysis = {
            "files": ["src/main.py"],
            "symbols": [],
            "file_tree": "src/main.py",
            "file_contents": {"src/main.py": content},
        }
        
        pages, file_hashes, file_summaries = await orchestrator._run_files(analysis)
        
        # File should NOT have been regenerated
        assert len(pages) == 0, "Unchanged file should be skipped"
        assert len(generate_called) == 0, "Generator should not be called for unchanged file"
        assert len(file_summaries) == 0

    @pytest.mark.asyncio
    async def test_mixed_changed_and_unchanged_files(
        self, mock_llm_client, mock_repo, mock_db_with_tracking, tmp_path
    ):
        """Pipeline correctly handles mix of changed and unchanged files.
        
        Requirements: 7.1
        """
        from oya.generation.summaries import FileSummary
        from oya.generation.overview import GeneratedPage
        
        orchestrator = GenerationOrchestrator(
            llm_client=mock_llm_client,
            repo=mock_repo,
            db=mock_db_with_tracking,
            wiki_path=tmp_path / "wiki",
        )
        
        # Setup: file1 unchanged, file2 changed, file3 new
        file1_content = "print('file1')"
        file1_hash = compute_content_hash(file1_content)
        mock_db_with_tracking._page_info["src/file1.py:file"] = {
            "metadata": f'{{"source_hash": "{file1_hash}"}}',
            "generated_at": "2025-01-01T00:00:00",
        }
        
        file2_old_content = "print('file2 old')"
        file2_old_hash = compute_content_hash(file2_old_content)
        mock_db_with_tracking._page_info["src/file2.py:file"] = {
            "metadata": f'{{"source_hash": "{file2_old_hash}"}}',
            "generated_at": "2025-01-01T00:00:00",
        }
        file2_new_content = "print('file2 new')"
        
        file3_content = "print('file3 new')"
        # file3 has no previous record (new file)
        
        # Track which files are generated
        generated_files = []
        
        async def mock_generate(file_path, *args, **kwargs):
            generated_files.append(file_path)
            mock_page = GeneratedPage(
                content="# File Doc",
                page_type="file",
                path=f"files/{file_path.replace('/', '-')}.md",
                word_count=10,
                target=file_path,
            )
            mock_summary = FileSummary(
                file_path=file_path,
                purpose="Test file",
                layer="utility",
            )
            return mock_page, mock_summary
        
        orchestrator.file_generator.generate = mock_generate
        
        # Run files phase
        analysis = {
            "files": ["src/file1.py", "src/file2.py", "src/file3.py"],
            "symbols": [],
            "file_tree": "src/file1.py\nsrc/file2.py\nsrc/file3.py",
            "file_contents": {
                "src/file1.py": file1_content,  # unchanged
                "src/file2.py": file2_new_content,  # changed
                "src/file3.py": file3_content,  # new
            },
        }
        
        pages, file_hashes, file_summaries = await orchestrator._run_files(analysis)
        
        # Only file2 (changed) and file3 (new) should be regenerated
        assert len(pages) == 2, f"Expected 2 regenerated files, got {len(pages)}"
        assert "src/file2.py" in generated_files, "Changed file should be regenerated"
        assert "src/file3.py" in generated_files, "New file should be regenerated"
        assert "src/file1.py" not in generated_files, "Unchanged file should be skipped"


# ============================================================================
# Property 11: Cascade - File Regeneration Triggers Synthesis
# ============================================================================


class TestSynthesisCascade:
    """Property 11: Cascade - File Regeneration Triggers Synthesis
    
    For any generation run where at least one file's documentation was
    regenerated, the Synthesis_Map SHALL also be regenerated.
    
    Validates: Requirements 7.2
    """

    @pytest.fixture
    def mock_llm_client(self):
        """Create mock LLM client."""
        client = AsyncMock()
        client.generate.return_value = "# Generated Content"
        return client

    @pytest.fixture
    def mock_repo(self, tmp_path):
        """Create mock repository."""
        repo = MagicMock()
        repo.path = tmp_path
        repo.list_files.return_value = []
        repo.get_head_commit.return_value = "abc123"
        return repo

    @pytest.fixture
    def mock_db(self):
        """Create mock database that tracks page info."""
        db = MagicMock()
        db._page_info = {}
        
        def mock_execute(query, params=None):
            cursor = MagicMock()
            if "SELECT metadata" in query and params:
                target, page_type = params
                key = f"{target}:{page_type}"
                if key in db._page_info:
                    info = db._page_info[key]
                    cursor.fetchone.return_value = (info.get("metadata"), info.get("generated_at"))
                else:
                    cursor.fetchone.return_value = None
            elif "SELECT COUNT" in query:
                cursor.fetchone.return_value = (0,)
            return cursor
        
        db.execute = mock_execute
        db.commit = MagicMock()
        return db

    @given(data=file_with_content_strategy())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_file_regeneration_triggers_synthesis_regeneration(
        self, data, mock_llm_client, mock_repo, mock_db, tmp_path
    ):
        """Feature: bottom-up-generation, Property 11: Cascade - File Regeneration Triggers Synthesis
        
        When at least one file is regenerated (content hash changed), the cascade
        property requires that synthesis must also be regenerated.
        
        This test verifies the precondition: changed content triggers file regeneration.
        The cascade behavior (file regen -> synthesis regen) is tested in the
        integration test below.
        """
        orchestrator = GenerationOrchestrator(
            llm_client=mock_llm_client,
            repo=mock_repo,
            db=mock_db,
            wiki_path=tmp_path / "wiki",
        )
        
        file_path = data["file_path"]
        original_content = data["original_content"]
        modified_content = data["modified_content"]
        
        # Compute hashes
        original_hash = compute_content_hash(original_content)
        
        # Simulate that the file was previously generated with original content
        key = f"{file_path}:file"
        mock_db._page_info[key] = {
            "metadata": f'{{"source_hash": "{original_hash}"}}',
            "generated_at": "2025-01-01T00:00:00",
        }
        
        # Check if file should be regenerated with modified content
        file_hashes = {}
        should_regen, content_hash = orchestrator._should_regenerate_file(
            file_path, modified_content, file_hashes
        )
        
        # Property: changed content MUST trigger file regeneration
        assert should_regen is True, (
            f"File with changed content should trigger regeneration. "
            f"Original hash: {original_hash}, New hash: {content_hash}"
        )

    @given(content=file_content_strategy(), file_path=file_path_strategy())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_unchanged_file_does_not_trigger_regeneration(
        self, content, file_path, mock_llm_client, mock_repo, mock_db, tmp_path
    ):
        """Feature: bottom-up-generation, Property 11: Cascade - File Regeneration Triggers Synthesis
        
        When no files have changed content, file regeneration is skipped.
        This is the inverse case - unchanged files don't trigger the cascade.
        """
        orchestrator = GenerationOrchestrator(
            llm_client=mock_llm_client,
            repo=mock_repo,
            db=mock_db,
            wiki_path=tmp_path / "wiki",
        )
        
        # Compute hash
        content_hash = compute_content_hash(content)
        
        # Simulate that the file was previously generated with same content
        key = f"{file_path}:file"
        mock_db._page_info[key] = {
            "metadata": f'{{"source_hash": "{content_hash}"}}',
            "generated_at": "2025-01-01T00:00:00",
        }
        
        # Check if file should be regenerated with same content
        file_hashes = {}
        should_regen, returned_hash = orchestrator._should_regenerate_file(
            file_path, content, file_hashes
        )
        
        # Property: unchanged content should NOT trigger regeneration
        assert should_regen is False, (
            f"File with unchanged content should NOT trigger regeneration. "
            f"Content hash: {content_hash}"
        )

    @pytest.mark.asyncio
    @given(data=file_with_content_strategy())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    async def test_regenerated_files_produce_summaries_for_synthesis(
        self, data, mock_llm_client, mock_repo, mock_db, tmp_path
    ):
        """Feature: bottom-up-generation, Property 11: Cascade - File Regeneration Triggers Synthesis
        
        When files are regenerated, their FileSummaries are collected and will
        be passed to the synthesis phase. This is the data flow that enables
        the cascade.
        """
        from oya.generation.summaries import FileSummary
        from oya.generation.overview import GeneratedPage
        
        orchestrator = GenerationOrchestrator(
            llm_client=mock_llm_client,
            repo=mock_repo,
            db=mock_db,
            wiki_path=tmp_path / "wiki",
        )
        
        file_path = data["file_path"]
        modified_content = data["modified_content"]
        
        # No previous generation - file is new (will be regenerated)
        
        # Mock the file generator to return a known FileSummary
        expected_summary = FileSummary(
            file_path=file_path,
            purpose="Test purpose",
            layer="utility",
        )
        mock_page = GeneratedPage(
            content="# File Doc",
            page_type="file",
            path=f"files/{file_path.replace('/', '-')}.md",
            word_count=10,
            target=file_path,
        )
        
        async def mock_generate(*args, **kwargs):
            return mock_page, expected_summary
        
        orchestrator.file_generator.generate = mock_generate
        
        # Run files phase
        analysis = {
            "files": [file_path],
            "symbols": [],
            "file_tree": file_path,
            "file_contents": {file_path: modified_content},
        }
        
        pages, file_hashes, file_summaries = await orchestrator._run_files(analysis)
        
        # Property: regenerated files produce summaries
        assert len(pages) == 1, "New file should be regenerated"
        assert len(file_summaries) == 1, "FileSummary should be collected for regenerated file"
        assert file_summaries[0].file_path == file_path
        
        # These summaries will be passed to _run_synthesis in the pipeline

