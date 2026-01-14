# backend/tests/test_orchestrator.py
"""Generation orchestrator tests."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from oya.generation.orchestrator import (
    GenerationOrchestrator,
    GenerationPhase,
    GenerationProgress,
)
from oya.generation.overview import GeneratedPage
from oya.generation.summaries import (
    FileSummary,
    DirectorySummary,
    SynthesisMap,
    LayerInfo,
    ComponentInfo,
)


@pytest.fixture
def mock_llm_client():
    """Create mock LLM client."""
    client = AsyncMock()
    client.generate.return_value = "# Generated Content"
    return client


@pytest.fixture
def mock_repo():
    """Create mock repository."""
    repo = MagicMock()
    repo.path = Path("/workspace/my-project")
    repo.list_files.return_value = ["src/main.py", "README.md"]
    repo.get_head_commit.return_value = "abc123"
    return repo


@pytest.fixture
def mock_db():
    """Create mock database."""
    return MagicMock()


@pytest.fixture
def orchestrator(mock_llm_client, mock_repo, mock_db, tmp_path):
    """Create orchestrator."""
    return GenerationOrchestrator(
        llm_client=mock_llm_client,
        repo=mock_repo,
        db=mock_db,
        wiki_path=tmp_path / "wiki",
    )


def test_generation_phases_defined():
    """Generation phases are properly defined."""
    assert GenerationPhase.ANALYSIS.value == "analysis"
    assert GenerationPhase.OVERVIEW.value == "overview"
    assert GenerationPhase.ARCHITECTURE.value == "architecture"
    assert GenerationPhase.WORKFLOWS.value == "workflows"
    assert GenerationPhase.DIRECTORIES.value == "directories"
    assert GenerationPhase.FILES.value == "files"


@pytest.mark.asyncio
async def test_runs_full_generation(orchestrator):
    """Runs all generation phases."""
    progress_events = []

    async def progress_callback(progress: GenerationProgress):
        progress_events.append(progress)

    mock_overview_page = GeneratedPage(
        content="# Overview", page_type="overview", path="overview.md", word_count=1
    )
    mock_arch_page = GeneratedPage(
        content="# Architecture", page_type="architecture", path="architecture.md", word_count=1
    )

    with patch.object(orchestrator, "_run_analysis", new_callable=AsyncMock) as mock_analysis:
        mock_analysis.return_value = {"files": [], "symbols": [], "file_tree": "", "file_contents": {}}
        with patch.object(orchestrator, "_run_overview", new_callable=AsyncMock) as mock_overview:
            mock_overview.return_value = mock_overview_page
            with patch.object(orchestrator, "_run_architecture", new_callable=AsyncMock) as mock_arch:
                mock_arch.return_value = mock_arch_page
                with patch.object(orchestrator, "_run_workflows", new_callable=AsyncMock) as mock_workflows:
                    mock_workflows.return_value = []
                    with patch.object(orchestrator, "_run_directories", new_callable=AsyncMock) as mock_dirs:
                        mock_dirs.return_value = ([], [])  # Updated: (pages, directory_summaries)
                        with patch.object(orchestrator, "_run_files", new_callable=AsyncMock) as mock_files:
                            mock_files.return_value = ([], {}, [])  # Updated: (pages, file_hashes, file_summaries)
                            with patch.object(orchestrator, "_run_synthesis", new_callable=AsyncMock) as mock_synthesis:
                                mock_synthesis.return_value = SynthesisMap()
                                await orchestrator.run(progress_callback=progress_callback)

    # Should have progress events for each phase
    assert len(progress_events) >= 1


@pytest.mark.asyncio
async def test_emits_progress_events(orchestrator):
    """Emits progress events during generation."""
    progress_events = []

    async def progress_callback(progress: GenerationProgress):
        progress_events.append(progress)

    mock_overview_page = GeneratedPage(
        content="# Overview", page_type="overview", path="overview.md", word_count=1
    )
    mock_arch_page = GeneratedPage(
        content="# Architecture", page_type="architecture", path="architecture.md", word_count=1
    )

    with patch.object(orchestrator, "_run_analysis", new_callable=AsyncMock) as mock_analysis:
        mock_analysis.return_value = {"files": [], "symbols": [], "file_tree": "", "file_contents": {}}
        with patch.object(orchestrator, "_run_overview", new_callable=AsyncMock) as mock_overview:
            mock_overview.return_value = mock_overview_page
            with patch.object(orchestrator, "_run_architecture", new_callable=AsyncMock) as mock_arch:
                mock_arch.return_value = mock_arch_page
                with patch.object(orchestrator, "_run_workflows", new_callable=AsyncMock) as mock_workflows:
                    mock_workflows.return_value = []
                    with patch.object(orchestrator, "_run_directories", new_callable=AsyncMock) as mock_dirs:
                        mock_dirs.return_value = ([], [])  # Updated: (pages, directory_summaries)
                        with patch.object(orchestrator, "_run_files", new_callable=AsyncMock) as mock_files:
                            mock_files.return_value = ([], {}, [])  # Updated: (pages, file_hashes, file_summaries)
                            with patch.object(orchestrator, "_run_synthesis", new_callable=AsyncMock) as mock_synthesis:
                                mock_synthesis.return_value = SynthesisMap()
                                await orchestrator.run(progress_callback=progress_callback)

    # Check progress events have expected fields
    for event in progress_events:
        assert hasattr(event, "phase")
        assert hasattr(event, "message")


@pytest.mark.asyncio
async def test_saves_pages_to_wiki_path(orchestrator, mock_llm_client):
    """Saves generated pages to wiki directory."""
    with patch.object(orchestrator, "_run_analysis", new_callable=AsyncMock) as mock_analysis:
        mock_analysis.return_value = {"files": [], "symbols": [], "file_tree": "", "file_contents": {}}
        with patch.object(orchestrator, "_save_page", new_callable=AsyncMock) as mock_save:
            with patch.object(orchestrator, "_run_workflows", new_callable=AsyncMock):
                with patch.object(orchestrator, "_run_directories", new_callable=AsyncMock) as mock_dirs:
                    mock_dirs.return_value = ([], [])  # Updated: (pages, directory_summaries)
                    with patch.object(orchestrator, "_run_files", new_callable=AsyncMock) as mock_files:
                        mock_files.return_value = ([], {}, [])  # Updated: (pages, file_hashes, file_summaries)
                        with patch.object(orchestrator, "_run_synthesis", new_callable=AsyncMock) as mock_synthesis:
                            mock_synthesis.return_value = SynthesisMap()
                            await orchestrator.run()

            # Should have saved overview and architecture pages
            assert mock_save.call_count >= 2



# ============================================================================
# Task 18: GenerationOrchestrator Pipeline Refactor Tests (TDD)
# ============================================================================


class TestPipelinePhaseOrder:
    """Tests for pipeline phase execution order (Task 18.1).

    Requirements: 4.1 - THE Generation_Pipeline SHALL execute phases in this order:
    Analysis, Files, Directories, Synthesis, Architecture, Overview, Workflows.
    """

    @pytest.fixture
    def orchestrator_with_mocks(self, mock_llm_client, mock_repo, mock_db, tmp_path):
        """Create orchestrator with all phase methods mocked to track call order."""
        orch = GenerationOrchestrator(
            llm_client=mock_llm_client,
            repo=mock_repo,
            db=mock_db,
            wiki_path=tmp_path / "wiki",
        )
        return orch

    @pytest.mark.asyncio
    async def test_phases_execute_in_correct_order(self, orchestrator_with_mocks):
        """Phases execute in order: Analysis → Files → Directories → Synthesis → Architecture → Overview → Workflows.

        Requirements: 4.1
        """
        call_order = []

        # Mock all phase methods to track call order
        async def mock_analysis(progress_callback=None):
            call_order.append("analysis")
            return {"files": [], "symbols": [], "file_tree": "", "file_contents": {}}

        async def mock_files(analysis, progress_callback=None):
            call_order.append("files")
            return [], {}, []  # pages, file_hashes, file_summaries

        async def mock_directories(analysis, file_hashes, progress_callback=None, file_summaries=None):
            call_order.append("directories")
            return [], []  # pages, directory_summaries

        async def mock_synthesis(file_summaries, directory_summaries):
            call_order.append("synthesis")
            return SynthesisMap()

        async def mock_architecture(analysis, synthesis_map=None):
            call_order.append("architecture")
            return GeneratedPage(
                content="# Architecture",
                page_type="architecture",
                path="architecture.md",
                word_count=1,
            )

        async def mock_overview(analysis, synthesis_map=None):
            call_order.append("overview")
            return GeneratedPage(
                content="# Overview",
                page_type="overview",
                path="overview.md",
                word_count=1,
            )

        async def mock_workflows(analysis, progress_callback=None):
            call_order.append("workflows")
            return []

        with patch.object(orchestrator_with_mocks, "_run_analysis", mock_analysis):
            with patch.object(orchestrator_with_mocks, "_run_files", mock_files):
                with patch.object(orchestrator_with_mocks, "_run_directories", mock_directories):
                    with patch.object(orchestrator_with_mocks, "_run_synthesis", mock_synthesis):
                        with patch.object(orchestrator_with_mocks, "_run_architecture", mock_architecture):
                            with patch.object(orchestrator_with_mocks, "_run_overview", mock_overview):
                                with patch.object(orchestrator_with_mocks, "_run_workflows", mock_workflows):
                                    with patch.object(orchestrator_with_mocks, "_save_page", AsyncMock()):
                                        await orchestrator_with_mocks.run()

        # Verify the correct order
        expected_order = [
            "analysis",
            "files",
            "directories",
            "synthesis",
            "architecture",
            "overview",
            "workflows",
        ]
        assert call_order == expected_order, f"Expected {expected_order}, got {call_order}"

    def test_synthesis_phase_exists_in_enum(self):
        """SYNTHESIS phase is defined in GenerationPhase enum.

        Requirements: 4.1
        """
        assert hasattr(GenerationPhase, "SYNTHESIS")
        assert GenerationPhase.SYNTHESIS.value == "synthesis"


class TestFileSummariesPassedToSynthesis:
    """Tests for File_Summaries being passed to Synthesis (Task 18.2).

    Requirements: 4.2 - WHEN the Files phase completes, THE Generation_Pipeline
    SHALL pass all File_Summaries to the Synthesis phase.
    """

    @pytest.fixture
    def orchestrator_with_mocks(self, mock_llm_client, mock_repo, mock_db, tmp_path):
        """Create orchestrator for testing."""
        return GenerationOrchestrator(
            llm_client=mock_llm_client,
            repo=mock_repo,
            db=mock_db,
            wiki_path=tmp_path / "wiki",
        )

    @pytest.mark.asyncio
    async def test_run_files_returns_file_summaries(self, orchestrator_with_mocks):
        """_run_files returns FileSummaries along with pages and hashes.

        Requirements: 4.2
        """
        # Create mock file summary
        mock_file_summary = FileSummary(
            file_path="src/main.py",
            purpose="Main entry point",
            layer="api",
            key_abstractions=["main"],
            internal_deps=[],
            external_deps=["fastapi"],
        )

        # Mock the file generator to return a page and summary
        mock_page = GeneratedPage(
            content="# File",
            page_type="file",
            path="files/src-main-py.md",
            word_count=1,
            target="src/main.py",
        )

        async def mock_generate(*args, **kwargs):
            return mock_page, mock_file_summary

        orchestrator_with_mocks.file_generator.generate = mock_generate

        analysis = {
            "files": ["src/main.py"],
            "symbols": [],
            "file_tree": "src/main.py",
            "file_contents": {"src/main.py": "print('hello')"},
        }

        # Call _run_files and check it returns file_summaries
        result = await orchestrator_with_mocks._run_files(analysis)

        # Should return tuple of (pages, file_hashes, file_summaries)
        assert len(result) == 3, f"Expected 3 return values, got {len(result)}"
        pages, file_hashes, file_summaries = result
        assert isinstance(file_summaries, list)
        assert len(file_summaries) == 1
        assert file_summaries[0].file_path == "src/main.py"

    @pytest.mark.asyncio
    async def test_file_summaries_reach_synthesis(self, orchestrator_with_mocks):
        """File_Summaries from _run_files reach _run_synthesis.

        Requirements: 4.2
        """
        captured_file_summaries = []

        mock_file_summary = FileSummary(
            file_path="src/main.py",
            purpose="Main entry point",
            layer="api",
        )

        async def mock_analysis(progress_callback=None):
            return {"files": [], "symbols": [], "file_tree": "", "file_contents": {}}

        async def mock_files(analysis, progress_callback=None):
            return [], {}, [mock_file_summary]

        async def mock_directories(analysis, file_hashes, progress_callback=None, file_summaries=None):
            return [], []

        async def mock_synthesis(file_summaries, directory_summaries):
            captured_file_summaries.extend(file_summaries)
            return SynthesisMap()

        async def mock_architecture(analysis, synthesis_map=None):
            return GeneratedPage(content="", page_type="architecture", path="architecture.md", word_count=0)

        async def mock_overview(analysis, synthesis_map=None):
            return GeneratedPage(content="", page_type="overview", path="overview.md", word_count=0)

        async def mock_workflows(analysis, progress_callback=None):
            return []

        with patch.object(orchestrator_with_mocks, "_run_analysis", mock_analysis):
            with patch.object(orchestrator_with_mocks, "_run_files", mock_files):
                with patch.object(orchestrator_with_mocks, "_run_directories", mock_directories):
                    with patch.object(orchestrator_with_mocks, "_run_synthesis", mock_synthesis):
                        with patch.object(orchestrator_with_mocks, "_run_architecture", mock_architecture):
                            with patch.object(orchestrator_with_mocks, "_run_overview", mock_overview):
                                with patch.object(orchestrator_with_mocks, "_run_workflows", mock_workflows):
                                    with patch.object(orchestrator_with_mocks, "_save_page", AsyncMock()):
                                        await orchestrator_with_mocks.run()

        assert len(captured_file_summaries) == 1
        assert captured_file_summaries[0].file_path == "src/main.py"


class TestDirectorySummariesPassedToSynthesis:
    """Tests for Directory_Summaries being passed to Synthesis (Task 18.3).

    Requirements: 4.3 - WHEN the Directories phase completes, THE Generation_Pipeline
    SHALL pass all Directory_Summaries to the Synthesis phase.
    """

    @pytest.fixture
    def orchestrator_with_mocks(self, mock_llm_client, mock_repo, mock_db, tmp_path):
        """Create orchestrator for testing."""
        return GenerationOrchestrator(
            llm_client=mock_llm_client,
            repo=mock_repo,
            db=mock_db,
            wiki_path=tmp_path / "wiki",
        )

    @pytest.mark.asyncio
    async def test_run_directories_returns_directory_summaries(self, orchestrator_with_mocks):
        """_run_directories returns DirectorySummaries along with pages.

        Requirements: 4.3
        """
        mock_dir_summary = DirectorySummary(
            directory_path="src",
            purpose="Source code directory",
            contains=["main.py"],
            role_in_system="Contains application code",
        )

        mock_page = GeneratedPage(
            content="# Directory",
            page_type="directory",
            path="directories/src.md",
            word_count=1,
            target="src",
        )

        async def mock_generate(*args, **kwargs):
            return mock_page, mock_dir_summary

        orchestrator_with_mocks.directory_generator.generate = mock_generate

        analysis = {
            "files": ["src/main.py"],
            "symbols": [],
            "file_tree": "src/main.py",
            "file_contents": {"src/main.py": "print('hello')"},
        }
        file_hashes = {"src/main.py": "abc123"}
        file_summaries = []

        # Call _run_directories and check it returns directory_summaries
        result = await orchestrator_with_mocks._run_directories(
            analysis, file_hashes, file_summaries=file_summaries
        )

        # Should return tuple of (pages, directory_summaries)
        assert len(result) == 2, f"Expected 2 return values, got {len(result)}"
        pages, directory_summaries = result
        assert isinstance(directory_summaries, list)
        assert len(directory_summaries) >= 1

    @pytest.mark.asyncio
    async def test_directory_summaries_reach_synthesis(self, orchestrator_with_mocks):
        """Directory_Summaries from _run_directories reach _run_synthesis.

        Requirements: 4.3
        """
        captured_dir_summaries = []

        mock_dir_summary = DirectorySummary(
            directory_path="src",
            purpose="Source code directory",
            contains=["main.py"],
            role_in_system="Contains application code",
        )

        async def mock_analysis(progress_callback=None):
            return {"files": [], "symbols": [], "file_tree": "", "file_contents": {}}

        async def mock_files(analysis, progress_callback=None):
            return [], {}, []

        async def mock_directories(analysis, file_hashes, progress_callback=None, file_summaries=None):
            return [], [mock_dir_summary]

        async def mock_synthesis(file_summaries, directory_summaries):
            captured_dir_summaries.extend(directory_summaries)
            return SynthesisMap()

        async def mock_architecture(analysis, synthesis_map=None):
            return GeneratedPage(content="", page_type="architecture", path="architecture.md", word_count=0)

        async def mock_overview(analysis, synthesis_map=None):
            return GeneratedPage(content="", page_type="overview", path="overview.md", word_count=0)

        async def mock_workflows(analysis, progress_callback=None):
            return []

        with patch.object(orchestrator_with_mocks, "_run_analysis", mock_analysis):
            with patch.object(orchestrator_with_mocks, "_run_files", mock_files):
                with patch.object(orchestrator_with_mocks, "_run_directories", mock_directories):
                    with patch.object(orchestrator_with_mocks, "_run_synthesis", mock_synthesis):
                        with patch.object(orchestrator_with_mocks, "_run_architecture", mock_architecture):
                            with patch.object(orchestrator_with_mocks, "_run_overview", mock_overview):
                                with patch.object(orchestrator_with_mocks, "_run_workflows", mock_workflows):
                                    with patch.object(orchestrator_with_mocks, "_save_page", AsyncMock()):
                                        await orchestrator_with_mocks.run()

        assert len(captured_dir_summaries) == 1
        assert captured_dir_summaries[0].directory_path == "src"


class TestSynthesisMapPassedToArchAndOverview:
    """Tests for Synthesis_Map being passed to Architecture and Overview (Task 18.4).

    Requirements: 4.4, 4.5, 4.6 - WHEN the Synthesis phase completes, THE Generation_Pipeline
    SHALL pass the Synthesis_Map to the Architecture and Overview phases.
    """

    @pytest.fixture
    def orchestrator_with_mocks(self, mock_llm_client, mock_repo, mock_db, tmp_path):
        """Create orchestrator for testing."""
        return GenerationOrchestrator(
            llm_client=mock_llm_client,
            repo=mock_repo,
            db=mock_db,
            wiki_path=tmp_path / "wiki",
        )

    @pytest.mark.asyncio
    async def test_synthesis_map_reaches_architecture(self, orchestrator_with_mocks):
        """Synthesis_Map from _run_synthesis reaches _run_architecture.

        Requirements: 4.4, 4.5
        """
        captured_synthesis_map = []

        mock_synthesis_map = SynthesisMap(
            layers={"api": LayerInfo(name="api", purpose="API layer", directories=[], files=["src/main.py"])},
            key_components=[ComponentInfo(name="main", file="src/main.py", role="Entry point", layer="api")],
            dependency_graph={"api": ["domain"]},
            project_summary="Test project",
        )

        async def mock_analysis(progress_callback=None):
            return {"files": [], "symbols": [], "file_tree": "", "file_contents": {}}

        async def mock_files(analysis, progress_callback=None):
            return [], {}, []

        async def mock_directories(analysis, file_hashes, progress_callback=None, file_summaries=None):
            return [], []

        async def mock_synthesis(file_summaries, directory_summaries):
            return mock_synthesis_map

        async def mock_architecture(analysis, synthesis_map=None):
            captured_synthesis_map.append(synthesis_map)
            return GeneratedPage(content="", page_type="architecture", path="architecture.md", word_count=0)

        async def mock_overview(analysis, synthesis_map=None):
            return GeneratedPage(content="", page_type="overview", path="overview.md", word_count=0)

        async def mock_workflows(analysis, progress_callback=None):
            return []

        with patch.object(orchestrator_with_mocks, "_run_analysis", mock_analysis):
            with patch.object(orchestrator_with_mocks, "_run_files", mock_files):
                with patch.object(orchestrator_with_mocks, "_run_directories", mock_directories):
                    with patch.object(orchestrator_with_mocks, "_run_synthesis", mock_synthesis):
                        with patch.object(orchestrator_with_mocks, "_run_architecture", mock_architecture):
                            with patch.object(orchestrator_with_mocks, "_run_overview", mock_overview):
                                with patch.object(orchestrator_with_mocks, "_run_workflows", mock_workflows):
                                    with patch.object(orchestrator_with_mocks, "_save_page", AsyncMock()):
                                        await orchestrator_with_mocks.run()

        assert len(captured_synthesis_map) == 1
        assert captured_synthesis_map[0] is mock_synthesis_map
        assert captured_synthesis_map[0].project_summary == "Test project"

    @pytest.mark.asyncio
    async def test_synthesis_map_reaches_overview(self, orchestrator_with_mocks):
        """Synthesis_Map from _run_synthesis reaches _run_overview.

        Requirements: 4.4, 4.6
        """
        captured_synthesis_map = []

        mock_synthesis_map = SynthesisMap(
            layers={"api": LayerInfo(name="api", purpose="API layer", directories=[], files=["src/main.py"])},
            key_components=[],
            dependency_graph={},
            project_summary="Test project for overview",
        )

        async def mock_analysis(progress_callback=None):
            return {"files": [], "symbols": [], "file_tree": "", "file_contents": {}}

        async def mock_files(analysis, progress_callback=None):
            return [], {}, []

        async def mock_directories(analysis, file_hashes, progress_callback=None, file_summaries=None):
            return [], []

        async def mock_synthesis(file_summaries, directory_summaries):
            return mock_synthesis_map

        async def mock_architecture(analysis, synthesis_map=None):
            return GeneratedPage(content="", page_type="architecture", path="architecture.md", word_count=0)

        async def mock_overview(analysis, synthesis_map=None):
            captured_synthesis_map.append(synthesis_map)
            return GeneratedPage(content="", page_type="overview", path="overview.md", word_count=0)

        async def mock_workflows(analysis, progress_callback=None):
            return []

        with patch.object(orchestrator_with_mocks, "_run_analysis", mock_analysis):
            with patch.object(orchestrator_with_mocks, "_run_files", mock_files):
                with patch.object(orchestrator_with_mocks, "_run_directories", mock_directories):
                    with patch.object(orchestrator_with_mocks, "_run_synthesis", mock_synthesis):
                        with patch.object(orchestrator_with_mocks, "_run_architecture", mock_architecture):
                            with patch.object(orchestrator_with_mocks, "_run_overview", mock_overview):
                                with patch.object(orchestrator_with_mocks, "_run_workflows", mock_workflows):
                                    with patch.object(orchestrator_with_mocks, "_save_page", AsyncMock()):
                                        await orchestrator_with_mocks.run()

        assert len(captured_synthesis_map) == 1
        assert captured_synthesis_map[0] is mock_synthesis_map
        assert captured_synthesis_map[0].project_summary == "Test project for overview"


# ============================================================================
# Task 4: Parse Error Recovery Tests
# ============================================================================


class TestParseErrorRecovery:
    """Tests for parse error recovery with fallback parser."""

    @pytest.fixture
    def mock_orchestrator(self, tmp_path):
        """Create orchestrator with mocked dependencies."""
        llm_client = MagicMock()
        repo = MagicMock()
        repo.path = tmp_path
        db = MagicMock()
        wiki_path = tmp_path / ".oyawiki"
        wiki_path.mkdir()

        return GenerationOrchestrator(llm_client, repo, db, wiki_path)

    @pytest.mark.asyncio
    async def test_analysis_recovers_from_parse_errors(self, mock_orchestrator, tmp_path):
        """Analysis phase recovers symbols from files with syntax errors using fallback."""
        from oya.parsing.models import ParsedSymbol

        # Create a file with invalid Python syntax
        bad_file = tmp_path / "bad.py"
        bad_file.write_text("def broken(\n")  # Syntax error

        # Create a valid file
        good_file = tmp_path / "good.py"
        good_file.write_text("def valid_func():\n    pass\n")

        # Run analysis
        result = await mock_orchestrator._run_analysis()

        # Should have parse_errors tracking
        assert "parse_errors" in result

        # Good file should have symbols extracted
        good_symbols = [s for s in result["symbols"] if s.metadata.get("file") == "good.py"]
        assert len(good_symbols) > 0
        assert all(isinstance(s, ParsedSymbol) for s in good_symbols)

    @pytest.mark.asyncio
    async def test_analysis_tracks_parse_errors(self, mock_orchestrator, tmp_path):
        """Analysis phase tracks which files had parse errors."""
        # Create a file with invalid syntax
        bad_file = tmp_path / "syntax_error.py"
        bad_file.write_text("class Broken{}")  # Invalid Python syntax

        result = await mock_orchestrator._run_analysis()

        # Should track the error
        assert "parse_errors" in result
        errors = result["parse_errors"]
        error_files = [e["file"] for e in errors]
        assert "syntax_error.py" in error_files

    @pytest.mark.asyncio
    async def test_analysis_returns_file_imports(self, mock_orchestrator, tmp_path):
        """Analysis phase returns file_imports dict."""
        # Create a Python file with imports
        py_file = tmp_path / "example.py"
        py_file.write_text("import os\nfrom pathlib import Path\n\ndef hello(): pass\n")

        result = await mock_orchestrator._run_analysis()

        assert "file_imports" in result
        assert "example.py" in result["file_imports"]

    @pytest.mark.asyncio
    async def test_analysis_symbols_are_parsed_symbols(self, mock_orchestrator, tmp_path):
        """Analysis phase returns ParsedSymbol objects, not dicts."""
        from oya.parsing.models import ParsedSymbol

        # Create a valid Python file
        py_file = tmp_path / "valid.py"
        py_file.write_text("class MyClass:\n    pass\n\ndef my_func():\n    pass\n")

        result = await mock_orchestrator._run_analysis()

        # All symbols should be ParsedSymbol objects
        for symbol in result["symbols"]:
            assert isinstance(symbol, ParsedSymbol), f"Expected ParsedSymbol, got {type(symbol)}"

    @pytest.mark.asyncio
    async def test_analysis_symbols_have_file_metadata(self, mock_orchestrator, tmp_path):
        """Analysis phase sets file path in symbol metadata."""
        # Create a valid Python file
        py_file = tmp_path / "module.py"
        py_file.write_text("def some_function():\n    pass\n")

        result = await mock_orchestrator._run_analysis()

        # All symbols should have file in metadata
        for symbol in result["symbols"]:
            assert "file" in symbol.metadata, "Symbol should have 'file' in metadata"
            assert symbol.metadata["file"] == "module.py"

    @pytest.mark.asyncio
    async def test_fallback_parser_recovers_symbols(self, mock_orchestrator, tmp_path):
        """Fallback parser extracts symbols from files that primary parser fails on."""
        # Create a file with syntax that Python parser will fail on but fallback can handle
        go_file = tmp_path / "main.go"
        go_file.write_text("package main\n\nfunc main() {\n    fmt.Println(\"Hello\")\n}\n")

        result = await mock_orchestrator._run_analysis()

        # Go file should have symbols extracted by fallback parser
        go_symbols = [s for s in result["symbols"] if s.metadata.get("file") == "main.go"]
        assert len(go_symbols) > 0, "Fallback parser should extract symbols from Go file"

    @pytest.mark.asyncio
    async def test_symbol_to_dict_conversion(self, mock_orchestrator, tmp_path):
        """_symbol_to_dict correctly converts ParsedSymbol to dict format."""
        from oya.parsing.models import ParsedSymbol, SymbolType

        symbol = ParsedSymbol(
            name="test_func",
            symbol_type=SymbolType.FUNCTION,
            start_line=10,
            end_line=20,
            decorators=["@decorator"],
            metadata={"file": "test.py"},
        )

        result = mock_orchestrator._symbol_to_dict(symbol)

        assert result["name"] == "test_func"
        assert result["type"] == "function"
        assert result["file"] == "test.py"
        assert result["line"] == 10
        assert result["decorators"] == ["@decorator"]
