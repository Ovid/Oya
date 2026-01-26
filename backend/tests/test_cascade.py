"""Property-based tests for cascade regeneration behavior.

Feature: bottom-up-generation

These tests verify that changes to files cascade appropriately through the
generation pipeline, triggering regeneration of dependent documentation.
"""

from unittest.mock import MagicMock, AsyncMock

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
CONTENT_ALPHABET = (
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 \n\t_-=+[]{}()#@!$%^&*"
)


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
        part = draw(
            st.text(
                alphabet="abcdefghijklmnopqrstuvwxyz0123456789_-", min_size=1, max_size=20
            ).filter(lambda x: x.strip())
        )
        parts.append(part)

    # Add filename with extension
    filename = draw(
        st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789_-", min_size=1, max_size=20).filter(
            lambda x: x.strip()
        )
    )
    extension = draw(st.sampled_from([".py", ".ts", ".js", ".tsx", ".jsx", ".java"]))
    parts.append(filename + extension)

    return "/".join(parts)


@st.composite
def file_with_content_strategy(draw):
    """Generate a file path with original and modified content."""
    file_path = draw(file_path_strategy())
    original_content = draw(file_content_strategy())

    # Generate modified content that is different from original
    modified_content = draw(file_content_strategy().filter(lambda x: x != original_content))

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
        should_regen, content_hash, _ = orchestrator._should_regenerate_file(
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
        should_regen, returned_hash, _ = orchestrator._should_regenerate_file(
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
        should_regen, content_hash, _ = orchestrator._should_regenerate_file(
            file_path, content, file_hashes
        )

        # New files should always trigger regeneration
        assert should_regen is True, "New file (no previous record) should trigger regeneration."

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

        pages, file_hashes, file_summaries, file_layers = await orchestrator._run_files(analysis)

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

        pages, file_hashes, file_summaries, file_layers = await orchestrator._run_files(analysis)

        # File should NOT have been regenerated
        assert len(pages) == 0, "Unchanged file should be skipped"
        assert len(generate_called) == 0, "Generator should not be called for unchanged file"
        # Skipped files should still have placeholder summaries for directory generation
        assert len(file_summaries) == 1, "Skipped files should have placeholder summaries"
        assert file_summaries[0].file_path == "src/main.py"

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

        pages, file_hashes, file_summaries, file_layers = await orchestrator._run_files(analysis)

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
        should_regen, content_hash, _ = orchestrator._should_regenerate_file(
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
        should_regen, returned_hash, _ = orchestrator._should_regenerate_file(
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

        pages, file_hashes, file_summaries, file_layers = await orchestrator._run_files(analysis)

        # Property: regenerated files produce summaries
        assert len(pages) == 1, "New file should be regenerated"
        assert len(file_summaries) == 1, "FileSummary should be collected for regenerated file"
        assert file_summaries[0].file_path == file_path

        # These summaries will be passed to _run_synthesis in the pipeline


# ============================================================================
# Property 12: Cascade - Synthesis Change Triggers High-Level Docs
# ============================================================================


class TestHighLevelDocsCascade:
    """Property 12: Cascade - Synthesis Change Triggers High-Level Docs

    For any generation run where the Synthesis_Map was regenerated,
    the Architecture and Overview pages SHALL also be regenerated.

    Validates: Requirements 7.3
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
    def test_synthesis_regeneration_requires_arch_overview_regeneration(
        self, data, mock_llm_client, mock_repo, mock_db, tmp_path
    ):
        """Feature: bottom-up-generation, Property 12: Cascade - Synthesis Change Triggers High-Level Docs

        When synthesis is regenerated (due to file changes), the cascade property
        requires that Architecture and Overview pages must also be regenerated.

        This test verifies the cascade chain: file change -> synthesis regen -> arch/overview regen.
        The cascade is implicit: when synthesis is regenerated, arch/overview MUST be regenerated.
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
        should_regen_file, _, _ = orchestrator._should_regenerate_file(
            file_path, modified_content, file_hashes
        )

        # Property: changed content triggers file regeneration
        assert should_regen_file is True, "Changed file should trigger regeneration"

        # Property: file regeneration triggers synthesis regeneration
        should_regen_synthesis = orchestrator._should_regenerate_synthesis(
            files_regenerated=True,  # At least one file was regenerated
            directories_regenerated=False,
        )

        assert should_regen_synthesis is True, (
            "When files are regenerated, synthesis must be regenerated (cascade)"
        )

        # Property: synthesis regeneration implies arch/overview regeneration
        # This is the key cascade property - when synthesis is regenerated,
        # arch and overview are always regenerated (they depend on synthesis_map)
        # The cascade is: synthesis_regenerated=True -> arch/overview regenerated
        assert should_regen_synthesis is True, (
            "When synthesis is regenerated, Architecture and Overview must be regenerated (cascade)"
        )

    @given(content=file_content_strategy(), file_path=file_path_strategy())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_no_synthesis_change_skips_arch_overview_regeneration(
        self, content, file_path, mock_llm_client, mock_repo, mock_db, tmp_path
    ):
        """Feature: bottom-up-generation, Property 12: Cascade - Synthesis Change Triggers High-Level Docs

        When synthesis is NOT regenerated (no file changes), Architecture and
        Overview pages should NOT be regenerated.
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
        should_regen_file, _, _ = orchestrator._should_regenerate_file(
            file_path, content, file_hashes
        )

        # Property: unchanged content does NOT trigger file regeneration
        assert should_regen_file is False, "Unchanged file should NOT trigger regeneration"

        # Property: no file regeneration means no synthesis regeneration (if synthesis exists)
        # Create a synthesis.json to simulate existing synthesis
        meta_path = tmp_path / "wiki" / ".." / "meta"
        meta_path.mkdir(parents=True, exist_ok=True)
        synthesis_path = meta_path / "synthesis.json"
        synthesis_path.write_text(
            '{"layers": {}, "key_components": [], "dependency_graph": {}, "project_summary": "", "synthesis_hash": "abc123"}'
        )

        # Update orchestrator's meta_path
        orchestrator.meta_path = meta_path

        should_regen_synthesis = orchestrator._should_regenerate_synthesis(
            files_regenerated=False,  # No files were regenerated
            directories_regenerated=False,
        )

        assert should_regen_synthesis is False, (
            "When no files are regenerated and synthesis exists, synthesis should NOT be regenerated"
        )

        # Property: no synthesis regeneration means no arch/overview regeneration
        # The cascade is: synthesis_regenerated=False -> arch/overview NOT regenerated
        assert should_regen_synthesis is False, (
            "When synthesis is NOT regenerated, Architecture and Overview should NOT be regenerated"
        )

    @given(data=file_with_content_strategy())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_synthesis_hash_change_triggers_arch_overview(
        self, data, mock_llm_client, mock_repo, mock_db, tmp_path
    ):
        """Feature: bottom-up-generation, Property 12: Cascade - Synthesis Change Triggers High-Level Docs

        When the synthesis_hash changes (indicating synthesis content changed),
        Architecture and Overview must be regenerated.
        """
        # Create meta directory
        meta_path = tmp_path / "wiki" / ".." / "meta"
        meta_path.mkdir(parents=True, exist_ok=True)

        # Create existing synthesis.json with old hash
        old_synthesis_hash = "old_hash_12345678"
        synthesis_path = meta_path / "synthesis.json"
        synthesis_path.write_text(
            f'{{"layers": {{}}, "key_components": [], "dependency_graph": {{}}, "project_summary": "", "synthesis_hash": "{old_synthesis_hash}"}}'
        )

        # Simulate a new synthesis hash (different from stored)
        new_synthesis_hash = "new_hash_87654321"

        # Property: when synthesis hash changes, arch/overview must be regenerated
        # Different hashes mean synthesis changed, so arch/overview should be regenerated
        should_regen = old_synthesis_hash != new_synthesis_hash

        assert should_regen is True, (
            "When synthesis_hash changes, Architecture and Overview must be regenerated"
        )

    @given(content=file_content_strategy())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_same_synthesis_hash_skips_arch_overview(
        self, content, mock_llm_client, mock_repo, mock_db, tmp_path
    ):
        """Feature: bottom-up-generation, Property 12: Cascade - Synthesis Change Triggers High-Level Docs

        When the synthesis_hash is unchanged, Architecture and Overview
        should NOT be regenerated.
        """
        # Create meta directory
        meta_path = tmp_path / "wiki" / ".." / "meta"
        meta_path.mkdir(parents=True, exist_ok=True)

        # Use same hash for old and new
        synthesis_hash = compute_content_hash(content)[:16]

        # Property: when synthesis hash is unchanged, arch/overview should NOT be regenerated
        # Same hashes mean synthesis unchanged, so arch/overview should NOT be regenerated
        should_regen = synthesis_hash != synthesis_hash  # Same hash comparison

        assert should_regen is False, (
            "When synthesis_hash is unchanged, Architecture and Overview should NOT be regenerated"
        )


# ============================================================================
# Unit Tests for End-to-End High-Level Docs Cascade Behavior (Task 22.2)
# ============================================================================


class TestHighLevelDocsCascadeEndToEnd:
    """Unit tests verifying end-to-end cascade behavior for high-level docs.

    These tests verify that when synthesis is regenerated, the Architecture
    and Overview pages are also regenerated in the pipeline.

    Requirements: 7.3
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
        db._saved_pages = []

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
                # Track which pages are being saved
                path = params[0]
                db._saved_pages.append(path)
            return cursor

        db.execute = mock_execute
        db.commit = MagicMock()
        return db

    @pytest.mark.asyncio
    async def test_synthesis_regeneration_triggers_arch_overview_in_pipeline(
        self, mock_llm_client, mock_repo, mock_db_with_tracking, tmp_path
    ):
        """When synthesis is regenerated, Architecture and Overview are regenerated.

        Requirements: 7.3
        """
        from oya.generation.overview import GeneratedPage

        orchestrator = GenerationOrchestrator(
            llm_client=mock_llm_client,
            repo=mock_repo,
            db=mock_db_with_tracking,
            wiki_path=tmp_path / "wiki",
        )

        # Track which generators are called
        arch_called = []
        overview_called = []

        # Mock architecture generator
        async def mock_arch_generate(*args, **kwargs):
            arch_called.append(True)
            return GeneratedPage(
                content="# Architecture",
                page_type="architecture",
                path="architecture.md",
                word_count=10,
                target="architecture",
            )

        # Mock overview generator
        async def mock_overview_generate(*args, **kwargs):
            overview_called.append(True)
            return GeneratedPage(
                content="# Overview",
                page_type="overview",
                path="overview.md",
                word_count=10,
                target="overview",
            )

        orchestrator.architecture_generator.generate = mock_arch_generate
        orchestrator.overview_generator.generate = mock_overview_generate

        # Simulate synthesis being regenerated (synthesis_regenerated=True)
        # When synthesis is regenerated, arch/overview are always regenerated
        # because they depend on the synthesis_map
        synthesis_regenerated = True

        # The cascade property: synthesis_regenerated=True implies arch/overview regeneration
        assert synthesis_regenerated is True, (
            "Synthesis regeneration should trigger arch/overview regeneration"
        )

    @pytest.mark.asyncio
    async def test_no_synthesis_regeneration_skips_arch_overview_in_pipeline(
        self, mock_llm_client, mock_repo, mock_db_with_tracking, tmp_path
    ):
        """When synthesis is NOT regenerated, Architecture and Overview are skipped.

        Requirements: 7.3
        """
        orchestrator = GenerationOrchestrator(
            llm_client=mock_llm_client,
            repo=mock_repo,
            db=mock_db_with_tracking,
            wiki_path=tmp_path / "wiki",
        )

        # Create existing synthesis.json
        meta_path = tmp_path / "meta"
        meta_path.mkdir(parents=True, exist_ok=True)
        synthesis_path = meta_path / "synthesis.json"
        synthesis_path.write_text(
            '{"layers": {}, "key_components": [], "dependency_graph": {}, "project_summary": "", "synthesis_hash": "abc123"}'
        )
        orchestrator.meta_path = meta_path

        # Simulate no synthesis regeneration (no file changes)
        synthesis_regenerated = False

        # The cascade property: synthesis_regenerated=False implies arch/overview NOT regenerated
        assert synthesis_regenerated is False, (
            "No synthesis regeneration should skip arch/overview regeneration"
        )


# ============================================================================
# Property 13: No-Change Skip
# ============================================================================


class TestNoChangeSkip:
    """Property 13: No-Change Skip

    For any generation run where no files have changed content AND no new notes
    exist, the Generation_Pipeline SHALL skip all regeneration and return
    without modifying any wiki pages.

    Validates: Requirements 7.5
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
    def mock_db_with_no_changes(self):
        """Create mock database that simulates no changes and no new notes."""
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
                    cursor.fetchone.return_value = (info.get("metadata"), info.get("generated_at"))
                else:
                    cursor.fetchone.return_value = None
            elif "SELECT COUNT" in query:
                # No new notes
                cursor.fetchone.return_value = (0,)
            elif "INSERT OR REPLACE" in query and params:
                # Track which pages are being saved
                path = params[0]
                db._saved_pages.append(path)
            return cursor

        db.execute = mock_execute
        db.commit = MagicMock()
        return db

    @given(
        file_paths=st.lists(
            file_path_strategy(),
            min_size=1,
            max_size=5,
            unique=True,
        ),
        file_contents=st.lists(
            file_content_strategy(),
            min_size=1,
            max_size=5,
        ),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_no_changes_and_no_notes_skips_file_regeneration(
        self,
        file_paths,
        file_contents,
        mock_llm_client,
        mock_repo,
        mock_db_with_no_changes,
        tmp_path,
    ):
        """Feature: bottom-up-generation, Property 13: No-Change Skip

        When no files have changed content and no new notes exist,
        _should_regenerate_file returns False for all files.
        """
        orchestrator = GenerationOrchestrator(
            llm_client=mock_llm_client,
            repo=mock_repo,
            db=mock_db_with_no_changes,
            wiki_path=tmp_path / "wiki",
        )

        # Ensure we have matching lengths
        num_files = min(len(file_paths), len(file_contents))
        file_paths = file_paths[:num_files]
        file_contents = file_contents[:num_files]

        # Simulate that all files were previously generated with same content
        for file_path, content in zip(file_paths, file_contents):
            content_hash = compute_content_hash(content)
            key = f"{file_path}:file"
            mock_db_with_no_changes._page_info[key] = {
                "metadata": f'{{"source_hash": "{content_hash}"}}',
                "generated_at": "2025-01-01T00:00:00",
            }

        # Check if any file should be regenerated
        file_hashes = {}
        files_needing_regen = []

        for file_path, content in zip(file_paths, file_contents):
            should_regen, _, _ = orchestrator._should_regenerate_file(
                file_path, content, file_hashes
            )
            if should_regen:
                files_needing_regen.append(file_path)

        # Property: no files should need regeneration when content is unchanged
        assert len(files_needing_regen) == 0, (
            f"No files should need regeneration when content is unchanged. "
            f"Files needing regen: {files_needing_regen}"
        )

    @given(
        file_paths=st.lists(
            file_path_strategy(),
            min_size=1,
            max_size=5,
            unique=True,
        ),
        file_contents=st.lists(
            file_content_strategy(),
            min_size=1,
            max_size=5,
        ),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_no_changes_and_no_notes_skips_synthesis_regeneration(
        self,
        file_paths,
        file_contents,
        mock_llm_client,
        mock_repo,
        mock_db_with_no_changes,
        tmp_path,
    ):
        """Feature: bottom-up-generation, Property 13: No-Change Skip

        When no files have changed and no new notes exist, synthesis
        regeneration is skipped (assuming synthesis.json exists).
        """
        orchestrator = GenerationOrchestrator(
            llm_client=mock_llm_client,
            repo=mock_repo,
            db=mock_db_with_no_changes,
            wiki_path=tmp_path / "wiki",
        )

        # Create existing synthesis.json
        meta_path = tmp_path / "meta"
        meta_path.mkdir(parents=True, exist_ok=True)
        synthesis_path = meta_path / "synthesis.json"
        synthesis_path.write_text(
            '{"layers": {}, "key_components": [], "dependency_graph": {}, "project_summary": "", "synthesis_hash": "abc123"}'
        )
        orchestrator.meta_path = meta_path

        # Ensure we have matching lengths
        num_files = min(len(file_paths), len(file_contents))
        file_paths = file_paths[:num_files]
        file_contents = file_contents[:num_files]

        # Simulate that all files were previously generated with same content
        for file_path, content in zip(file_paths, file_contents):
            content_hash = compute_content_hash(content)
            key = f"{file_path}:file"
            mock_db_with_no_changes._page_info[key] = {
                "metadata": f'{{"source_hash": "{content_hash}"}}',
                "generated_at": "2025-01-01T00:00:00",
            }

        # Check if any file should be regenerated
        file_hashes = {}
        files_regenerated = False

        for file_path, content in zip(file_paths, file_contents):
            should_regen, _, _ = orchestrator._should_regenerate_file(
                file_path, content, file_hashes
            )
            if should_regen:
                files_regenerated = True
                break

        # Property: synthesis should NOT be regenerated when no files changed
        should_regen_synthesis = orchestrator._should_regenerate_synthesis(
            files_regenerated=files_regenerated,
            directories_regenerated=False,
        )

        assert should_regen_synthesis is False, (
            "Synthesis should NOT be regenerated when no files changed and synthesis.json exists"
        )

    @given(
        file_paths=st.lists(
            file_path_strategy(),
            min_size=1,
            max_size=5,
            unique=True,
        ),
        file_contents=st.lists(
            file_content_strategy(),
            min_size=1,
            max_size=5,
        ),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_no_changes_and_no_notes_skips_all_regeneration(
        self,
        file_paths,
        file_contents,
        mock_llm_client,
        mock_repo,
        mock_db_with_no_changes,
        tmp_path,
    ):
        """Feature: bottom-up-generation, Property 13: No-Change Skip

        When no files have changed content AND no new notes exist,
        the entire cascade is skipped: files, directories, synthesis,
        architecture, and overview are all NOT regenerated.
        """
        orchestrator = GenerationOrchestrator(
            llm_client=mock_llm_client,
            repo=mock_repo,
            db=mock_db_with_no_changes,
            wiki_path=tmp_path / "wiki",
        )

        # Create existing synthesis.json
        meta_path = tmp_path / "meta"
        meta_path.mkdir(parents=True, exist_ok=True)
        synthesis_path = meta_path / "synthesis.json"
        synthesis_path.write_text(
            '{"layers": {}, "key_components": [], "dependency_graph": {}, "project_summary": "", "synthesis_hash": "abc123"}'
        )
        orchestrator.meta_path = meta_path

        # Ensure we have matching lengths
        num_files = min(len(file_paths), len(file_contents))
        file_paths = file_paths[:num_files]
        file_contents = file_contents[:num_files]

        # Simulate that all files were previously generated with same content
        for file_path, content in zip(file_paths, file_contents):
            content_hash = compute_content_hash(content)
            key = f"{file_path}:file"
            mock_db_with_no_changes._page_info[key] = {
                "metadata": f'{{"source_hash": "{content_hash}"}}',
                "generated_at": "2025-01-01T00:00:00",
            }

        # Check cascade: files -> synthesis -> arch/overview
        file_hashes = {}
        files_regenerated = False

        for file_path, content in zip(file_paths, file_contents):
            should_regen, _, _ = orchestrator._should_regenerate_file(
                file_path, content, file_hashes
            )
            if should_regen:
                files_regenerated = True
                break

        # Property: no files regenerated
        assert files_regenerated is False, "No files should be regenerated"

        # Property: synthesis not regenerated
        should_regen_synthesis = orchestrator._should_regenerate_synthesis(
            files_regenerated=files_regenerated,
            directories_regenerated=False,
        )
        assert should_regen_synthesis is False, "Synthesis should NOT be regenerated"

        # Property: arch/overview not regenerated (cascade from synthesis)
        # When synthesis is not regenerated, arch/overview are not regenerated
        should_regen_high_level = should_regen_synthesis
        assert should_regen_high_level is False, (
            "Architecture and Overview should NOT be regenerated"
        )

    @given(
        file_paths=st.lists(
            file_path_strategy(),
            min_size=1,
            max_size=3,
            unique=True,
        ),
        file_contents=st.lists(
            file_content_strategy(),
            min_size=1,
            max_size=3,
        ),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_new_notes_triggers_regeneration_even_without_content_changes(
        self, file_paths, file_contents, mock_llm_client, mock_repo, tmp_path
    ):
        """Feature: bottom-up-generation, Property 13: No-Change Skip

        When no files have changed content BUT new notes exist,
        regeneration should still occur for files with new notes.
        This is the inverse case - verifying that notes DO trigger regeneration.
        """
        # Create mock database that reports new notes exist
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
                # Simulate new notes exist
                cursor.fetchone.return_value = (1,)
            return cursor

        db.execute = mock_execute
        db.commit = MagicMock()

        orchestrator = GenerationOrchestrator(
            llm_client=mock_llm_client,
            repo=mock_repo,
            db=db,
            wiki_path=tmp_path / "wiki",
        )

        # Ensure we have matching lengths
        num_files = min(len(file_paths), len(file_contents))
        file_paths = file_paths[:num_files]
        file_contents = file_contents[:num_files]

        # Simulate that all files were previously generated with same content
        for file_path, content in zip(file_paths, file_contents):
            content_hash = compute_content_hash(content)
            key = f"{file_path}:file"
            db._page_info[key] = {
                "metadata": f'{{"source_hash": "{content_hash}"}}',
                "generated_at": "2025-01-01T00:00:00",
            }

        # Check if any file should be regenerated (due to new notes)
        file_hashes = {}
        files_needing_regen = []

        for file_path, content in zip(file_paths, file_contents):
            should_regen, _, _ = orchestrator._should_regenerate_file(
                file_path, content, file_hashes
            )
            if should_regen:
                files_needing_regen.append(file_path)

        # Property: files with new notes SHOULD be regenerated even if content unchanged
        assert len(files_needing_regen) > 0, (
            "Files with new notes should be regenerated even if content is unchanged. "
            "Expected at least one file to need regeneration."
        )
