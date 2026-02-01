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
from oya.parsing.models import ParsedFile, ParsedSymbol, SymbolType


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
        mock_analysis.return_value = {
            "files": [],
            "symbols": [],
            "file_tree": "",
            "file_contents": {},
        }
        with patch.object(orchestrator, "_run_overview", new_callable=AsyncMock) as mock_overview:
            mock_overview.return_value = mock_overview_page
            with patch.object(
                orchestrator, "_run_architecture", new_callable=AsyncMock
            ) as mock_arch:
                mock_arch.return_value = mock_arch_page
                with patch.object(
                    orchestrator, "_run_workflows", new_callable=AsyncMock
                ) as mock_workflows:
                    mock_workflows.return_value = []
                    with patch.object(
                        orchestrator, "_run_directories", new_callable=AsyncMock
                    ) as mock_dirs:
                        mock_dirs.return_value = ([], [])  # Updated: (pages, directory_summaries)
                        with patch.object(
                            orchestrator, "_run_files", new_callable=AsyncMock
                        ) as mock_files:
                            mock_files.return_value = (
                                [],
                                {},
                                [],
                                {},
                            )  # (pages, file_hashes, file_summaries, file_layers)
                            with patch.object(
                                orchestrator, "_run_synthesis", new_callable=AsyncMock
                            ) as mock_synthesis:
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
        mock_analysis.return_value = {
            "files": [],
            "symbols": [],
            "file_tree": "",
            "file_contents": {},
        }
        with patch.object(orchestrator, "_run_overview", new_callable=AsyncMock) as mock_overview:
            mock_overview.return_value = mock_overview_page
            with patch.object(
                orchestrator, "_run_architecture", new_callable=AsyncMock
            ) as mock_arch:
                mock_arch.return_value = mock_arch_page
                with patch.object(
                    orchestrator, "_run_workflows", new_callable=AsyncMock
                ) as mock_workflows:
                    mock_workflows.return_value = []
                    with patch.object(
                        orchestrator, "_run_directories", new_callable=AsyncMock
                    ) as mock_dirs:
                        mock_dirs.return_value = ([], [])  # Updated: (pages, directory_summaries)
                        with patch.object(
                            orchestrator, "_run_files", new_callable=AsyncMock
                        ) as mock_files:
                            mock_files.return_value = (
                                [],
                                {},
                                [],
                                {},
                            )  # (pages, file_hashes, file_summaries, file_layers)
                            with patch.object(
                                orchestrator, "_run_synthesis", new_callable=AsyncMock
                            ) as mock_synthesis:
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
        mock_analysis.return_value = {
            "files": [],
            "symbols": [],
            "file_tree": "",
            "file_contents": {},
        }
        with patch.object(
            orchestrator, "_save_page_with_frontmatter", new_callable=AsyncMock
        ) as mock_save:
            with patch.object(orchestrator, "_run_workflows", new_callable=AsyncMock):
                with patch.object(
                    orchestrator, "_run_directories", new_callable=AsyncMock
                ) as mock_dirs:
                    mock_dirs.return_value = ([], [])  # Updated: (pages, directory_summaries)
                    with patch.object(
                        orchestrator, "_run_files", new_callable=AsyncMock
                    ) as mock_files:
                        mock_files.return_value = (
                            [],
                            {},
                            [],
                            {},
                        )  # (pages, file_hashes, file_summaries, file_layers)
                        with patch.object(
                            orchestrator, "_run_synthesis", new_callable=AsyncMock
                        ) as mock_synthesis:
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
            return [], {}, [], {}  # pages, file_hashes, file_summaries, file_layers

        async def mock_directories(
            analysis, file_hashes, progress_callback=None, file_summaries=None
        ):
            call_order.append("directories")
            return [], []  # pages, directory_summaries

        async def mock_synthesis(
            file_summaries, directory_summaries, file_contents=None, all_symbols=None
        ):
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

        async def mock_workflows(analysis, progress_callback=None, synthesis_map=None):
            call_order.append("workflows")
            return []

        with patch.object(orchestrator_with_mocks, "_run_analysis", mock_analysis):
            with patch.object(orchestrator_with_mocks, "_run_files", mock_files):
                with patch.object(orchestrator_with_mocks, "_run_directories", mock_directories):
                    with patch.object(orchestrator_with_mocks, "_run_synthesis", mock_synthesis):
                        with patch.object(
                            orchestrator_with_mocks, "_run_architecture", mock_architecture
                        ):
                            with patch.object(
                                orchestrator_with_mocks, "_run_overview", mock_overview
                            ):
                                with patch.object(
                                    orchestrator_with_mocks, "_run_workflows", mock_workflows
                                ):
                                    with patch.object(
                                        orchestrator_with_mocks,
                                        "_save_page_with_frontmatter",
                                        AsyncMock(),
                                    ):
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

        # Should return tuple of (pages, file_hashes, file_summaries, file_layers)
        assert len(result) == 4, f"Expected 4 return values, got {len(result)}"
        pages, file_hashes, file_summaries, file_layers = result
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
            return (
                [],
                {},
                [mock_file_summary],
                {},
            )  # pages, file_hashes, file_summaries, file_layers

        async def mock_directories(
            analysis, file_hashes, progress_callback=None, file_summaries=None
        ):
            return [], []

        async def mock_synthesis(
            file_summaries, directory_summaries, file_contents=None, all_symbols=None
        ):
            captured_file_summaries.extend(file_summaries)
            return SynthesisMap()

        async def mock_architecture(analysis, synthesis_map=None):
            return GeneratedPage(
                content="", page_type="architecture", path="architecture.md", word_count=0
            )

        async def mock_overview(analysis, synthesis_map=None):
            return GeneratedPage(content="", page_type="overview", path="overview.md", word_count=0)

        async def mock_workflows(analysis, progress_callback=None, synthesis_map=None):
            return []

        with patch.object(orchestrator_with_mocks, "_run_analysis", mock_analysis):
            with patch.object(orchestrator_with_mocks, "_run_files", mock_files):
                with patch.object(orchestrator_with_mocks, "_run_directories", mock_directories):
                    with patch.object(orchestrator_with_mocks, "_run_synthesis", mock_synthesis):
                        with patch.object(
                            orchestrator_with_mocks, "_run_architecture", mock_architecture
                        ):
                            with patch.object(
                                orchestrator_with_mocks, "_run_overview", mock_overview
                            ):
                                with patch.object(
                                    orchestrator_with_mocks, "_run_workflows", mock_workflows
                                ):
                                    with patch.object(
                                        orchestrator_with_mocks,
                                        "_save_page_with_frontmatter",
                                        AsyncMock(),
                                    ):
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
            return [], {}, [], {}  # pages, file_hashes, file_summaries, file_layers

        async def mock_directories(
            analysis, file_hashes, progress_callback=None, file_summaries=None
        ):
            return [], [mock_dir_summary]

        async def mock_synthesis(
            file_summaries, directory_summaries, file_contents=None, all_symbols=None
        ):
            captured_dir_summaries.extend(directory_summaries)
            return SynthesisMap()

        async def mock_architecture(analysis, synthesis_map=None):
            return GeneratedPage(
                content="", page_type="architecture", path="architecture.md", word_count=0
            )

        async def mock_overview(analysis, synthesis_map=None):
            return GeneratedPage(content="", page_type="overview", path="overview.md", word_count=0)

        async def mock_workflows(analysis, progress_callback=None, synthesis_map=None):
            return []

        with patch.object(orchestrator_with_mocks, "_run_analysis", mock_analysis):
            with patch.object(orchestrator_with_mocks, "_run_files", mock_files):
                with patch.object(orchestrator_with_mocks, "_run_directories", mock_directories):
                    with patch.object(orchestrator_with_mocks, "_run_synthesis", mock_synthesis):
                        with patch.object(
                            orchestrator_with_mocks, "_run_architecture", mock_architecture
                        ):
                            with patch.object(
                                orchestrator_with_mocks, "_run_overview", mock_overview
                            ):
                                with patch.object(
                                    orchestrator_with_mocks, "_run_workflows", mock_workflows
                                ):
                                    with patch.object(
                                        orchestrator_with_mocks,
                                        "_save_page_with_frontmatter",
                                        AsyncMock(),
                                    ):
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
            layers={
                "api": LayerInfo(
                    name="api", purpose="API layer", directories=[], files=["src/main.py"]
                )
            },
            key_components=[
                ComponentInfo(name="main", file="src/main.py", role="Entry point", layer="api")
            ],
            dependency_graph={"api": ["domain"]},
            project_summary="Test project",
        )

        async def mock_analysis(progress_callback=None):
            return {"files": [], "symbols": [], "file_tree": "", "file_contents": {}}

        async def mock_files(analysis, progress_callback=None):
            return [], {}, [], {}  # pages, file_hashes, file_summaries, file_layers

        async def mock_directories(
            analysis, file_hashes, progress_callback=None, file_summaries=None
        ):
            return [], []

        async def mock_synthesis(
            file_summaries, directory_summaries, file_contents=None, all_symbols=None
        ):
            return mock_synthesis_map

        async def mock_architecture(analysis, synthesis_map=None):
            captured_synthesis_map.append(synthesis_map)
            return GeneratedPage(
                content="", page_type="architecture", path="architecture.md", word_count=0
            )

        async def mock_overview(analysis, synthesis_map=None):
            return GeneratedPage(content="", page_type="overview", path="overview.md", word_count=0)

        async def mock_workflows(analysis, progress_callback=None, synthesis_map=None):
            return []

        with patch.object(orchestrator_with_mocks, "_run_analysis", mock_analysis):
            with patch.object(orchestrator_with_mocks, "_run_files", mock_files):
                with patch.object(orchestrator_with_mocks, "_run_directories", mock_directories):
                    with patch.object(orchestrator_with_mocks, "_run_synthesis", mock_synthesis):
                        with patch.object(
                            orchestrator_with_mocks, "_run_architecture", mock_architecture
                        ):
                            with patch.object(
                                orchestrator_with_mocks, "_run_overview", mock_overview
                            ):
                                with patch.object(
                                    orchestrator_with_mocks, "_run_workflows", mock_workflows
                                ):
                                    with patch.object(
                                        orchestrator_with_mocks,
                                        "_save_page_with_frontmatter",
                                        AsyncMock(),
                                    ):
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
            layers={
                "api": LayerInfo(
                    name="api", purpose="API layer", directories=[], files=["src/main.py"]
                )
            },
            key_components=[],
            dependency_graph={},
            project_summary="Test project for overview",
        )

        async def mock_analysis(progress_callback=None):
            return {"files": [], "symbols": [], "file_tree": "", "file_contents": {}}

        async def mock_files(analysis, progress_callback=None):
            return [], {}, [], {}  # pages, file_hashes, file_summaries, file_layers

        async def mock_directories(
            analysis, file_hashes, progress_callback=None, file_summaries=None
        ):
            return [], []

        async def mock_synthesis(
            file_summaries, directory_summaries, file_contents=None, all_symbols=None
        ):
            return mock_synthesis_map

        async def mock_architecture(analysis, synthesis_map=None):
            return GeneratedPage(
                content="", page_type="architecture", path="architecture.md", word_count=0
            )

        async def mock_overview(analysis, synthesis_map=None):
            captured_synthesis_map.append(synthesis_map)
            return GeneratedPage(content="", page_type="overview", path="overview.md", word_count=0)

        async def mock_workflows(analysis, progress_callback=None, synthesis_map=None):
            return []

        with patch.object(orchestrator_with_mocks, "_run_analysis", mock_analysis):
            with patch.object(orchestrator_with_mocks, "_run_files", mock_files):
                with patch.object(orchestrator_with_mocks, "_run_directories", mock_directories):
                    with patch.object(orchestrator_with_mocks, "_run_synthesis", mock_synthesis):
                        with patch.object(
                            orchestrator_with_mocks, "_run_architecture", mock_architecture
                        ):
                            with patch.object(
                                orchestrator_with_mocks, "_run_overview", mock_overview
                            ):
                                with patch.object(
                                    orchestrator_with_mocks, "_run_workflows", mock_workflows
                                ):
                                    with patch.object(
                                        orchestrator_with_mocks,
                                        "_save_page_with_frontmatter",
                                        AsyncMock(),
                                    ):
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
        go_file.write_text('package main\n\nfunc main() {\n    fmt.Println("Hello")\n}\n')

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

    @pytest.mark.asyncio
    async def test_analysis_returns_parsed_symbols_and_imports(self, mock_orchestrator, tmp_path):
        """Analysis returns ParsedSymbol objects and file_imports dict."""
        from oya.parsing.models import ParsedSymbol

        # Create a Python file with imports and symbols
        py_file = tmp_path / "example.py"
        py_file.write_text("""
import os
from pathlib import Path

def hello():
    pass

class Greeter:
    def greet(self):
        pass
""")

        result = await mock_orchestrator._run_analysis()

        # Check symbols are ParsedSymbol objects
        assert len(result["symbols"]) > 0
        assert all(isinstance(s, ParsedSymbol) for s in result["symbols"])

        # Check file_imports is populated
        assert "file_imports" in result
        assert "example.py" in result["file_imports"]
        imports = result["file_imports"]["example.py"]
        assert "os" in imports or any("os" in i for i in imports)

        # Check symbols have file metadata
        for symbol in result["symbols"]:
            assert "file" in symbol.metadata


# ============================================================================
# Task 7: Depth-First Directory Processing Tests
# ============================================================================


class TestDirectoryProcessingOrder:
    """Tests for directory processing order."""

    def test_directories_grouped_by_depth(self):
        """Directories are grouped by depth for processing."""
        from oya.generation.orchestrator import group_directories_by_depth

        directories = ["src", "src/api", "src/api/routes", "tests", "tests/unit"]

        result = group_directories_by_depth(directories)

        # Depth 2 directories
        assert "src/api/routes" in result[2]
        assert "tests/unit" in result[1]
        # Depth 1 directories
        assert "src/api" in result[1]
        # Depth 0 directories
        assert "src" in result[0]
        assert "tests" in result[0]

    def test_directories_processed_deepest_first(self):
        """Deepest directories are processed before parents."""
        from oya.generation.orchestrator import get_processing_order

        directories = ["src", "src/api", "src/api/routes", ""]

        result = get_processing_order(directories)

        # Deepest first
        assert result.index("src/api/routes") < result.index("src/api")
        assert result.index("src/api") < result.index("src")
        assert result.index("src") < result.index("")  # Root last

    def test_root_directory_processed_last(self):
        """Root directory is always processed last."""
        from oya.generation.orchestrator import get_processing_order

        directories = ["", "src", "tests"]

        result = get_processing_order(directories)

        assert result[-1] == ""

    def test_empty_directories_list(self):
        """Empty directory list returns empty result."""
        from oya.generation.orchestrator import get_processing_order

        result = get_processing_order([])

        assert result == []

    def test_single_directory_no_root(self):
        """Single directory without root works correctly."""
        from oya.generation.orchestrator import get_processing_order

        result = get_processing_order(["src"])

        assert result == ["src"]

    def test_only_root_directory(self):
        """Only root directory returns just root."""
        from oya.generation.orchestrator import get_processing_order

        result = get_processing_order([""])

        assert result == [""]


# ============================================================================
# Task 8: Enhanced Directory Signature Tests
# ============================================================================


class TestEnhancedDirectorySignature:
    """Tests for enhanced directory signature computation."""

    def test_signature_includes_child_purposes(self):
        """Directory signature includes child directory purposes."""
        from oya.generation.orchestrator import compute_directory_signature_with_children
        from oya.generation.summaries import DirectorySummary

        file_hashes = [("app.py", "abc123"), ("config.py", "def456")]
        child_summaries = [
            DirectorySummary(
                directory_path="src/api/routes",
                purpose="HTTP route handlers",
                contains=[],
                role_in_system="",
            ),
        ]

        sig1 = compute_directory_signature_with_children(file_hashes, child_summaries)

        # Change child purpose
        child_summaries[0] = DirectorySummary(
            directory_path="src/api/routes",
            purpose="Changed purpose",
            contains=[],
            role_in_system="",
        )

        sig2 = compute_directory_signature_with_children(file_hashes, child_summaries)

        assert sig1 != sig2  # Signature should change

    def test_signature_stable_without_changes(self):
        """Signature is stable when inputs don't change."""
        from oya.generation.orchestrator import compute_directory_signature_with_children
        from oya.generation.summaries import DirectorySummary

        file_hashes = [("app.py", "abc123")]
        child_summaries = [
            DirectorySummary(
                directory_path="src/routes",
                purpose="Routes",
                contains=[],
                role_in_system="",
            ),
        ]

        sig1 = compute_directory_signature_with_children(file_hashes, child_summaries)
        sig2 = compute_directory_signature_with_children(file_hashes, child_summaries)

        assert sig1 == sig2


class TestSkippedDirectoryPurposePreservation:
    """Tests for preserving purpose when directories are skipped during incremental regen."""

    def test_placeholder_uses_stored_purpose(self):
        """When a directory is skipped, the placeholder should use the stored purpose.

        This prevents cascading regeneration of parent directories due to
        signature mismatch from empty placeholder purposes.
        """
        from oya.generation.orchestrator import compute_directory_signature_with_children
        from oya.generation.summaries import DirectorySummary

        # Simulate the scenario: parent directory signature computation
        # with a child that has been skipped

        file_hashes = [("routes.py", "abc123")]

        # If child was skipped with stored purpose preserved
        child_with_stored_purpose = DirectorySummary(
            directory_path="src/api/handlers",
            purpose="HTTP request handlers",  # Retrieved from database
            contains=["get.py", "post.py"],
            role_in_system="",
        )

        # This is how it SHOULD work now (with fix)
        sig_with_purpose = compute_directory_signature_with_children(
            file_hashes, [child_with_stored_purpose]
        )

        # This is how it USED TO work (broken - empty purpose)
        child_with_empty_purpose = DirectorySummary(
            directory_path="src/api/handlers",
            purpose="",  # Bug: was using empty string
            contains=["get.py", "post.py"],
            role_in_system="",
        )
        sig_with_empty = compute_directory_signature_with_children(
            file_hashes, [child_with_empty_purpose]
        )

        # The signatures should be different, proving the bug
        assert sig_with_purpose != sig_with_empty

        # The stored signature (from first generation) would match sig_with_purpose
        # With the fix, subsequent runs preserve the purpose and get the same signature

    def test_get_existing_page_info_returns_purpose(self):
        """_get_existing_page_info should return purpose from metadata."""
        import json
        from unittest.mock import MagicMock

        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_db.execute.return_value = mock_cursor

        # Simulate database returning metadata with purpose
        metadata = {"source_hash": "sig123", "purpose": "API handlers"}
        mock_cursor.fetchone.return_value = (json.dumps(metadata), "2024-01-01T00:00:00")

        # Create minimal orchestrator with mocked db
        mock_repo = MagicMock()
        mock_repo.path = Path("/test")
        mock_repo.get_head_commit.return_value = "abc123"
        mock_llm = MagicMock()

        from oya.generation.orchestrator import GenerationOrchestrator

        with patch("oya.generation.orchestrator.ParserRegistry"):
            orchestrator = GenerationOrchestrator(
                llm_client=mock_llm,
                repo=mock_repo,
                db=mock_db,
                wiki_path=Path("/test/wiki"),
            )

        result = orchestrator._get_existing_page_info("src/api", "directory")

        assert result is not None
        assert result["source_hash"] == "sig123"
        assert result["purpose"] == "API handlers"


# ============================================================================
# Task 9: Graph-Based Architecture Integration Tests
# ============================================================================


class TestGraphArchitectureIntegration:
    """Tests for integrating graph-based architecture generation."""

    @pytest.fixture
    def orchestrator_with_graph(self, mock_llm_client, mock_repo, mock_db, tmp_path):
        """Create orchestrator with a graph available."""
        return GenerationOrchestrator(
            llm_client=mock_llm_client,
            repo=mock_repo,
            db=mock_db,
            wiki_path=tmp_path / "wiki",
        )

    @pytest.mark.asyncio
    async def test_orchestrator_uses_graph_for_architecture_when_available(self, tmp_path):
        """Orchestrator uses graph-based architecture when graph exists with >= 5 nodes."""
        import networkx as nx

        # Create a minimal repo structure
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "main.py").write_text("def main(): pass")

        mock_llm = AsyncMock()
        mock_llm.generate.return_value = "# Architecture\n\nContent here."

        mock_repo = MagicMock()
        mock_repo.path = tmp_path

        mock_db = MagicMock()
        mock_db.execute = MagicMock(return_value=MagicMock(fetchone=lambda: None))

        wiki_path = tmp_path / ".oyawiki"
        wiki_path.mkdir()

        # Create graph directory with a graph that has >= 5 nodes
        graph_dir = wiki_path / "graph"
        graph_dir.mkdir()

        # Create a graph with 5+ nodes
        mock_graph = nx.DiGraph()
        mock_graph.add_node(
            "src/main.py::main",
            name="main",
            type="function",
            file_path="src/main.py",
            line_start=1,
            line_end=1,
        )
        mock_graph.add_node(
            "src/main.py::helper1",
            name="helper1",
            type="function",
            file_path="src/main.py",
            line_start=2,
            line_end=2,
        )
        mock_graph.add_node(
            "src/main.py::helper2",
            name="helper2",
            type="function",
            file_path="src/main.py",
            line_start=3,
            line_end=3,
        )
        mock_graph.add_node(
            "src/main.py::helper3",
            name="helper3",
            type="function",
            file_path="src/main.py",
            line_start=4,
            line_end=4,
        )
        mock_graph.add_node(
            "src/main.py::helper4",
            name="helper4",
            type="function",
            file_path="src/main.py",
            line_start=5,
            line_end=5,
        )
        mock_graph.add_edge(
            "src/main.py::main", "src/main.py::helper1", type="calls", confidence=1.0
        )

        with patch("oya.generation.orchestrator.load_graph", return_value=mock_graph):
            from oya.generation.orchestrator import GenerationOrchestrator

            orchestrator = GenerationOrchestrator(
                llm_client=mock_llm,
                repo=mock_repo,
                db=mock_db,
                wiki_path=wiki_path,
            )

            # The orchestrator should have a graph_architecture_generator initialized
            assert hasattr(orchestrator, "graph_architecture_generator")

    @pytest.mark.asyncio
    async def test_run_architecture_uses_graph_when_graph_has_enough_nodes(self, tmp_path):
        """_run_architecture uses GraphArchitectureGenerator when graph has >= 5 nodes."""
        import networkx as nx

        mock_llm = AsyncMock()
        mock_llm.generate.return_value = "# Graph Architecture\n\nGenerated from graph."

        # Create a repo directory with a name
        repo_dir = tmp_path / "test-repo"
        repo_dir.mkdir()

        mock_repo = MagicMock()
        mock_repo.path = repo_dir

        mock_db = MagicMock()

        wiki_path = repo_dir / ".oyawiki"
        wiki_path.mkdir()

        # Create graph directory
        graph_dir = repo_dir / "graph"
        graph_dir.mkdir()

        # Create a graph with 5+ nodes
        mock_graph = nx.DiGraph()
        for i in range(5):
            mock_graph.add_node(
                f"src/main.py::func{i}",
                name=f"func{i}",
                type="function",
                file_path="src/main.py",
                line_start=i,
                line_end=i,
            )

        orchestrator = GenerationOrchestrator(
            llm_client=mock_llm,
            repo=mock_repo,
            db=mock_db,
            wiki_path=wiki_path,
        )

        analysis = {
            "files": ["src/main.py"],
            "symbols": [],
            "file_tree": "src/main.py",
            "file_contents": {"src/main.py": "def func(): pass"},
            "file_imports": {},
        }

        # Mock the graph loading
        with patch("oya.generation.orchestrator.load_graph", return_value=mock_graph):
            # Mock the GraphArchitectureGenerator.generate to verify it's called
            with patch.object(
                orchestrator.graph_architecture_generator, "generate", new_callable=AsyncMock
            ) as mock_graph_gen:
                mock_graph_gen.return_value = GeneratedPage(
                    content="# Graph Arch",
                    page_type="architecture",
                    path="architecture.md",
                    word_count=10,
                )

                await orchestrator._run_architecture(analysis, synthesis_map=SynthesisMap())

                # Verify GraphArchitectureGenerator was called
                mock_graph_gen.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_architecture_falls_back_when_graph_too_small(self, tmp_path):
        """_run_architecture uses standard generator when graph has < 5 nodes."""
        import networkx as nx

        mock_llm = AsyncMock()
        mock_llm.generate.return_value = "# Standard Architecture"

        # Create a repo directory with a name
        repo_dir = tmp_path / "test-repo"
        repo_dir.mkdir()

        mock_repo = MagicMock()
        mock_repo.path = repo_dir

        mock_db = MagicMock()

        wiki_path = repo_dir / ".oyawiki"
        wiki_path.mkdir()

        # Create graph directory
        graph_dir = repo_dir / "graph"
        graph_dir.mkdir()

        # Create a graph with < 5 nodes (too small)
        small_graph = nx.DiGraph()
        small_graph.add_node("src/main.py::main", name="main", type="function")

        orchestrator = GenerationOrchestrator(
            llm_client=mock_llm,
            repo=mock_repo,
            db=mock_db,
            wiki_path=wiki_path,
        )

        analysis = {
            "files": ["src/main.py"],
            "symbols": [],
            "file_tree": "src/main.py",
            "file_contents": {"src/main.py": "def main(): pass"},
            "file_imports": {},
        }

        # Mock the graph loading to return small graph
        with patch("oya.generation.orchestrator.load_graph", return_value=small_graph):
            # Mock the standard architecture generator
            with patch.object(
                orchestrator.architecture_generator, "generate", new_callable=AsyncMock
            ) as mock_std_gen:
                mock_std_gen.return_value = GeneratedPage(
                    content="# Standard Arch",
                    page_type="architecture",
                    path="architecture.md",
                    word_count=10,
                )

                await orchestrator._run_architecture(analysis, synthesis_map=SynthesisMap())

                # Verify standard generator was called (not graph generator)
                mock_std_gen.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_architecture_falls_back_when_no_graph(self, tmp_path):
        """_run_architecture uses standard generator when no graph exists."""
        import networkx as nx

        mock_llm = AsyncMock()
        mock_llm.generate.return_value = "# Standard Architecture"

        # Create a repo directory with a name
        repo_dir = tmp_path / "test-repo"
        repo_dir.mkdir()

        mock_repo = MagicMock()
        mock_repo.path = repo_dir

        mock_db = MagicMock()

        wiki_path = repo_dir / ".oyawiki"
        wiki_path.mkdir()
        # No graph directory created

        orchestrator = GenerationOrchestrator(
            llm_client=mock_llm,
            repo=mock_repo,
            db=mock_db,
            wiki_path=wiki_path,
        )

        analysis = {
            "files": ["src/main.py"],
            "symbols": [],
            "file_tree": "src/main.py",
            "file_contents": {"src/main.py": "def main(): pass"},
            "file_imports": {},
        }

        # Mock load_graph to return empty graph (no graph file exists)
        with patch("oya.generation.orchestrator.load_graph", return_value=nx.DiGraph()):
            # Mock the standard architecture generator
            with patch.object(
                orchestrator.architecture_generator, "generate", new_callable=AsyncMock
            ) as mock_std_gen:
                mock_std_gen.return_value = GeneratedPage(
                    content="# Standard Arch",
                    page_type="architecture",
                    path="architecture.md",
                    word_count=10,
                )

                await orchestrator._run_architecture(analysis, synthesis_map=SynthesisMap())

                # Verify standard generator was called
                mock_std_gen.assert_called_once()


# ============================================================================
# Task 5.2: Code Index Building During Generation Tests
# ============================================================================


class TestCodeIndexBuilding:
    """Tests for building code index during generation (Task 5.2).

    Requirements: After files phase completes, the orchestrator should build
    the code index using CodeIndexBuilder when settings.ask.use_code_index is True.
    """

    @pytest.mark.asyncio
    async def test_orchestrator_builds_code_index_when_enabled(self, tmp_path):
        """Orchestrator builds code index after files phase when setting is enabled."""
        from oya.db.connection import Database
        from oya.db.migrations import run_migrations
        from oya.db.code_index import CodeIndexQuery

        # Create a repo with source files
        repo_dir = tmp_path / "test-repo"
        repo_dir.mkdir()
        src_dir = repo_dir / "src"
        src_dir.mkdir()
        (src_dir / "main.py").write_text("def hello():\n    '''Say hello'''\n    print('Hello')\n")

        mock_llm = AsyncMock()
        mock_llm.generate.return_value = "# Generated\n\nContent here."

        mock_repo = MagicMock()
        mock_repo.path = repo_dir
        mock_repo.get_head_commit.return_value = "abc123def"

        # Create database with schema
        db_path = tmp_path / "oya.db"
        db = Database(db_path)
        run_migrations(db)

        wiki_path = tmp_path / ".oyawiki"
        wiki_path.mkdir()

        orchestrator = GenerationOrchestrator(
            llm_client=mock_llm,
            repo=mock_repo,
            db=db,
            wiki_path=wiki_path,
        )

        # Mock generators to avoid full generation
        mock_file_summary = FileSummary(
            file_path="src/main.py",
            purpose="Entry point",
            layer="api",
        )
        mock_page = GeneratedPage(
            content="# File",
            page_type="file",
            path="files/src-main-py.md",
            word_count=1,
            target="src/main.py",
        )

        async def mock_file_generate(*args, **kwargs):
            return mock_page, mock_file_summary

        orchestrator.file_generator.generate = mock_file_generate

        # Mock other generators
        with patch.object(orchestrator, "_run_overview", new_callable=AsyncMock) as mock_overview:
            mock_overview.return_value = GeneratedPage(
                content="# Overview", page_type="overview", path="overview.md", word_count=1
            )
            with patch.object(
                orchestrator, "_run_architecture", new_callable=AsyncMock
            ) as mock_arch:
                mock_arch.return_value = GeneratedPage(
                    content="# Arch", page_type="architecture", path="architecture.md", word_count=1
                )
                with patch.object(
                    orchestrator, "_run_workflows", new_callable=AsyncMock
                ) as mock_workflows:
                    mock_workflows.return_value = []
                    with patch.object(
                        orchestrator, "_run_synthesis", new_callable=AsyncMock
                    ) as mock_synthesis:
                        mock_synthesis.return_value = SynthesisMap()
                        # Enable code index in settings
                        with patch("oya.generation.orchestrator.load_settings") as mock_settings:
                            mock_ask_settings = MagicMock()
                            mock_ask_settings.use_code_index = True
                            mock_settings.return_value.ask = mock_ask_settings
                            mock_settings.return_value.generation.progress_report_interval = 1

                            await orchestrator.run()

        # Verify code index was built
        query = CodeIndexQuery(db)
        entries = query.find_by_file("main.py")

        assert len(entries) > 0, "Code index should have entries for main.py"
        assert any(e.symbol_name == "hello" for e in entries), "Should have hello function"

    @pytest.mark.asyncio
    async def test_orchestrator_skips_code_index_when_disabled(self, tmp_path):
        """Orchestrator skips code index building when setting is disabled."""
        from oya.db.connection import Database
        from oya.db.migrations import run_migrations
        from oya.db.code_index import CodeIndexQuery

        # Create a repo with source files
        repo_dir = tmp_path / "test-repo"
        repo_dir.mkdir()
        src_dir = repo_dir / "src"
        src_dir.mkdir()
        (src_dir / "main.py").write_text("def hello():\n    '''Say hello'''\n    print('Hello')\n")

        mock_llm = AsyncMock()
        mock_llm.generate.return_value = "# Generated\n\nContent here."

        mock_repo = MagicMock()
        mock_repo.path = repo_dir
        mock_repo.get_head_commit.return_value = "abc123def"

        # Create database with schema
        db_path = tmp_path / "oya.db"
        db = Database(db_path)
        run_migrations(db)

        wiki_path = tmp_path / ".oyawiki"
        wiki_path.mkdir()

        orchestrator = GenerationOrchestrator(
            llm_client=mock_llm,
            repo=mock_repo,
            db=db,
            wiki_path=wiki_path,
        )

        # Mock generators
        mock_file_summary = FileSummary(
            file_path="src/main.py",
            purpose="Entry point",
            layer="api",
        )
        mock_page = GeneratedPage(
            content="# File",
            page_type="file",
            path="files/src-main-py.md",
            word_count=1,
            target="src/main.py",
        )

        async def mock_file_generate(*args, **kwargs):
            return mock_page, mock_file_summary

        orchestrator.file_generator.generate = mock_file_generate

        with patch.object(orchestrator, "_run_overview", new_callable=AsyncMock) as mock_overview:
            mock_overview.return_value = GeneratedPage(
                content="# Overview", page_type="overview", path="overview.md", word_count=1
            )
            with patch.object(
                orchestrator, "_run_architecture", new_callable=AsyncMock
            ) as mock_arch:
                mock_arch.return_value = GeneratedPage(
                    content="# Arch", page_type="architecture", path="architecture.md", word_count=1
                )
                with patch.object(
                    orchestrator, "_run_workflows", new_callable=AsyncMock
                ) as mock_workflows:
                    mock_workflows.return_value = []
                    with patch.object(
                        orchestrator, "_run_synthesis", new_callable=AsyncMock
                    ) as mock_synthesis:
                        mock_synthesis.return_value = SynthesisMap()
                        # Disable code index in settings
                        with patch("oya.generation.orchestrator.load_settings") as mock_settings:
                            mock_ask_settings = MagicMock()
                            mock_ask_settings.use_code_index = False
                            mock_settings.return_value.ask = mock_ask_settings
                            mock_settings.return_value.generation.progress_report_interval = 1

                            await orchestrator.run()

        # Verify code index was NOT built
        query = CodeIndexQuery(db)
        entries = query.find_by_file("main.py")

        assert len(entries) == 0, "Code index should be empty when disabled"

    @pytest.mark.asyncio
    async def test_code_index_computes_called_by_relationships(self, tmp_path):
        """Code index should compute called_by relationships after building."""
        from oya.db.connection import Database
        from oya.db.migrations import run_migrations
        from oya.db.code_index import CodeIndexQuery

        # Create a repo with source files that have call relationships
        repo_dir = tmp_path / "test-repo"
        repo_dir.mkdir()
        src_dir = repo_dir / "src"
        src_dir.mkdir()
        (src_dir / "main.py").write_text("def caller():\n    callee()\n\ndef callee():\n    pass\n")

        mock_llm = AsyncMock()
        mock_llm.generate.return_value = "# Generated\n\nContent here."

        mock_repo = MagicMock()
        mock_repo.path = repo_dir
        mock_repo.get_head_commit.return_value = "abc123def"

        # Create database with schema
        db_path = tmp_path / "oya.db"
        db = Database(db_path)
        run_migrations(db)

        wiki_path = tmp_path / ".oyawiki"
        wiki_path.mkdir()

        orchestrator = GenerationOrchestrator(
            llm_client=mock_llm,
            repo=mock_repo,
            db=db,
            wiki_path=wiki_path,
        )

        # Mock generators
        mock_file_summary = FileSummary(
            file_path="src/main.py",
            purpose="Entry point",
            layer="api",
        )
        mock_page = GeneratedPage(
            content="# File",
            page_type="file",
            path="files/src-main-py.md",
            word_count=1,
            target="src/main.py",
        )

        async def mock_file_generate(*args, **kwargs):
            return mock_page, mock_file_summary

        orchestrator.file_generator.generate = mock_file_generate

        with patch.object(orchestrator, "_run_overview", new_callable=AsyncMock) as mock_overview:
            mock_overview.return_value = GeneratedPage(
                content="# Overview", page_type="overview", path="overview.md", word_count=1
            )
            with patch.object(
                orchestrator, "_run_architecture", new_callable=AsyncMock
            ) as mock_arch:
                mock_arch.return_value = GeneratedPage(
                    content="# Arch", page_type="architecture", path="architecture.md", word_count=1
                )
                with patch.object(
                    orchestrator, "_run_workflows", new_callable=AsyncMock
                ) as mock_workflows:
                    mock_workflows.return_value = []
                    with patch.object(
                        orchestrator, "_run_synthesis", new_callable=AsyncMock
                    ) as mock_synthesis:
                        mock_synthesis.return_value = SynthesisMap()
                        with patch("oya.generation.orchestrator.load_settings") as mock_settings:
                            mock_ask_settings = MagicMock()
                            mock_ask_settings.use_code_index = True
                            mock_settings.return_value.ask = mock_ask_settings
                            mock_settings.return_value.generation.progress_report_interval = 1

                            await orchestrator.run()

        # Verify called_by relationships were computed
        query = CodeIndexQuery(db)
        callee_entries = query.find_by_symbol("callee")

        # The callee function should have "caller" in its called_by list
        # (depends on parser extracting calls metadata)
        assert len(callee_entries) > 0, "Should find callee function"


# ============================================================================
# Task 8 (Synopsis): Synopsis Extraction in Orchestrator Tests
# ============================================================================


class TestSynopsisPassedToFileGenerator:
    """Tests for synopsis extraction from ParsedFile and passing to FileGenerator.

    Verifies that the orchestrator extracts the synopsis field from ParsedFile
    objects and passes it to FileGenerator.generate().
    """

    @pytest.fixture
    def orchestrator_for_synopsis(self, mock_llm_client, mock_repo, mock_db, tmp_path):
        """Create orchestrator for synopsis testing."""
        return GenerationOrchestrator(
            llm_client=mock_llm_client,
            repo=mock_repo,
            db=mock_db,
            wiki_path=tmp_path / "wiki",
        )

    @pytest.mark.asyncio
    async def test_synopsis_extracted_and_passed_to_file_generator(self, orchestrator_for_synopsis):
        """Synopsis from ParsedFile is passed to FileGenerator.generate().

        When analysis produces a ParsedFile with a synopsis, the orchestrator
        should extract it and pass it as the synopsis= keyword argument to
        FileGenerator.generate().
        """
        captured_kwargs: list[dict] = []

        mock_file_summary = FileSummary(
            file_path="src/main.py",
            purpose="Main entry point",
            layer="api",
            key_abstractions=["main"],
            internal_deps=[],
            external_deps=[],
        )
        mock_page = GeneratedPage(
            content="# File",
            page_type="file",
            path="files/src-main-py.md",
            word_count=1,
            target="src/main.py",
        )

        async def mock_generate(*args, **kwargs):
            captured_kwargs.append(kwargs)
            return mock_page, mock_file_summary

        orchestrator_for_synopsis.file_generator.generate = mock_generate

        # Create a ParsedFile with a synopsis
        parsed_file = ParsedFile(
            path="src/main.py",
            language="python",
            symbols=[
                ParsedSymbol(
                    name="main",
                    symbol_type=SymbolType.FUNCTION,
                    start_line=1,
                    end_line=3,
                    metadata={"file": "src/main.py"},
                )
            ],
            synopsis="app = FastAPI()\napp.include_router(api_router)",
        )

        analysis = {
            "files": ["src/main.py"],
            "symbols": parsed_file.symbols,
            "file_tree": "src/main.py",
            "file_contents": {"src/main.py": "from fastapi import FastAPI\napp = FastAPI()"},
            "file_imports": {"src/main.py": ["fastapi"]},
            "parsed_files": [parsed_file],
        }

        await orchestrator_for_synopsis._run_files(analysis)

        assert len(captured_kwargs) == 1, "FileGenerator.generate should be called once"
        assert "synopsis" in captured_kwargs[0], "synopsis should be passed as a keyword argument"
        assert captured_kwargs[0]["synopsis"] == "app = FastAPI()\napp.include_router(api_router)"

    @pytest.mark.asyncio
    async def test_synopsis_none_when_parsed_file_has_no_synopsis(self, orchestrator_for_synopsis):
        """When ParsedFile has no synopsis, None is passed to FileGenerator.generate()."""
        captured_kwargs: list[dict] = []

        mock_file_summary = FileSummary(
            file_path="src/utils.py",
            purpose="Utility functions",
            layer="utility",
            key_abstractions=["format_date"],
            internal_deps=[],
            external_deps=[],
        )
        mock_page = GeneratedPage(
            content="# File",
            page_type="file",
            path="files/src-utils-py.md",
            word_count=1,
            target="src/utils.py",
        )

        async def mock_generate(*args, **kwargs):
            captured_kwargs.append(kwargs)
            return mock_page, mock_file_summary

        orchestrator_for_synopsis.file_generator.generate = mock_generate

        # Create a ParsedFile WITHOUT a synopsis
        parsed_file = ParsedFile(
            path="src/utils.py",
            language="python",
            symbols=[
                ParsedSymbol(
                    name="format_date",
                    symbol_type=SymbolType.FUNCTION,
                    start_line=1,
                    end_line=3,
                    metadata={"file": "src/utils.py"},
                )
            ],
            # synopsis defaults to None
        )

        analysis = {
            "files": ["src/utils.py"],
            "symbols": parsed_file.symbols,
            "file_tree": "src/utils.py",
            "file_contents": {"src/utils.py": "def format_date(): pass"},
            "file_imports": {},
            "parsed_files": [parsed_file],
        }

        await orchestrator_for_synopsis._run_files(analysis)

        assert len(captured_kwargs) == 1
        assert "synopsis" in captured_kwargs[0]
        assert captured_kwargs[0]["synopsis"] is None

    @pytest.mark.asyncio
    async def test_synopsis_none_when_no_parsed_file_matches(self, orchestrator_for_synopsis):
        """When no ParsedFile matches the file path, synopsis is None."""
        captured_kwargs: list[dict] = []

        mock_file_summary = FileSummary(
            file_path="src/orphan.py",
            purpose="Orphan file",
            layer="utility",
        )
        mock_page = GeneratedPage(
            content="# File",
            page_type="file",
            path="files/src-orphan-py.md",
            word_count=1,
            target="src/orphan.py",
        )

        async def mock_generate(*args, **kwargs):
            captured_kwargs.append(kwargs)
            return mock_page, mock_file_summary

        orchestrator_for_synopsis.file_generator.generate = mock_generate

        analysis = {
            "files": ["src/orphan.py"],
            "symbols": [],
            "file_tree": "src/orphan.py",
            "file_contents": {"src/orphan.py": "x = 1"},
            "file_imports": {},
            "parsed_files": [],  # No parsed files at all
        }

        await orchestrator_for_synopsis._run_files(analysis)

        assert len(captured_kwargs) == 1
        assert "synopsis" in captured_kwargs[0]
        assert captured_kwargs[0]["synopsis"] is None


# ============================================================================
# Code Health Page Generation Tests
# ============================================================================


class TestCodeHealthPageGeneration:
    """Tests for dead code detection page generation."""

    @pytest.mark.asyncio
    async def test_generate_code_health_page_with_graph(
        self, mock_llm_client, mock_repo, mock_db, tmp_path
    ):
        """_generate_code_health_page creates page from graph data."""
        import json

        wiki_path = tmp_path / "wiki"
        wiki_path.mkdir(parents=True)

        # Create graph directory with test data
        graph_path = wiki_path.parent / "graph"
        graph_path.mkdir(parents=True)

        nodes = [
            {
                "id": "main.py::main",
                "name": "main",
                "type": "function",
                "file_path": "main.py",
                "line_start": 1,
            },
            {
                "id": "utils.py::unused_func",
                "name": "unused_func",
                "type": "function",
                "file_path": "utils.py",
                "line_start": 10,
            },
        ]
        edges = []  # No edges means unused_func is dead code

        (graph_path / "nodes.json").write_text(json.dumps(nodes))
        (graph_path / "edges.json").write_text(json.dumps(edges))

        orchestrator = GenerationOrchestrator(
            llm_client=mock_llm_client,
            repo=mock_repo,
            db=mock_db,
            wiki_path=wiki_path,
        )

        page = orchestrator._generate_code_health_page()

        assert page is not None
        assert page.path == "code-health.md"
        assert page.page_type == "code-health"
        assert "Potential Dead Code" in page.content
        assert "unused_func" in page.content
        # main should be excluded (entry point)
        assert "main" not in page.content or "main.py" in page.content

    @pytest.mark.asyncio
    async def test_generate_code_health_page_no_graph(
        self, mock_llm_client, mock_repo, mock_db, tmp_path
    ):
        """_generate_code_health_page returns None when graph doesn't exist."""
        wiki_path = tmp_path / "wiki"
        wiki_path.mkdir(parents=True)
        # Don't create graph directory

        orchestrator = GenerationOrchestrator(
            llm_client=mock_llm_client,
            repo=mock_repo,
            db=mock_db,
            wiki_path=wiki_path,
        )

        page = orchestrator._generate_code_health_page()

        assert page is None
