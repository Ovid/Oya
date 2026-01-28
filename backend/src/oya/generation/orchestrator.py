# backend/src/oya/generation/orchestrator.py
"""Generation orchestrator for wiki pipeline.

This module provides the GenerationOrchestrator class that coordinates all phases
of wiki generation in a bottom-up approach:

1. Analysis - Parse repository files and extract symbols
2. Files - Generate documentation for individual files, extracting FileSummaries
3. Directories - Generate documentation for directories using FileSummaries
4. Synthesis - Combine summaries into a SynthesisMap
5. Architecture - Generate architecture documentation using SynthesisMap
6. Overview - Generate project overview using SynthesisMap
7. Workflows - Generate workflow documentation from entry points
"""

import asyncio
import hashlib
import json
import tomllib
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from itertools import islice
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Coroutine, Iterator

from oya.generation.architecture import ArchitectureGenerator
from oya.generation.frontmatter import build_frontmatter
from oya.generation.directory import DirectoryGenerator
from oya.generation.file import FileGenerator
from oya.generation.prompts import format_call_site_synopsis, get_notes_for_target
from oya.generation.graph_architecture import GraphArchitectureGenerator
from oya.generation.mermaid import LayerDiagramGenerator
from oya.generation.snippets import extract_call_snippet, is_test_file, select_best_call_site
from oya.graph import load_graph
from oya.graph.query import get_call_sites
from oya.generation.metrics import compute_code_metrics
from oya.generation.overview import GeneratedPage, OverviewGenerator
from oya.generation.summaries import DirectorySummary, EntryPointInfo, FileSummary, SynthesisMap
from oya.generation.synthesis import SynthesisGenerator, load_synthesis_map, save_synthesis_map
from oya.generation.techstack import detect_tech_stack
from oya.generation.workflows import (
    WorkflowGenerator,
    WorkflowGrouper,
    extract_entry_point_description,
    find_entry_points,
)
from oya.config import ConfigError, EXTENSION_LANGUAGES, load_settings
from oya.db.code_index import CodeIndexBuilder
from oya.parsing.fallback_parser import FallbackParser
from oya.parsing.models import ParsedFile, ParsedSymbol
from oya.parsing.registry import ParserRegistry
from oya.repo.file_filter import FileFilter, extract_directories_from_files

if TYPE_CHECKING:
    from oya.vectorstore.issues import IssuesStore


class GenerationPhase(Enum):
    """Phases of wiki generation."""

    ANALYSIS = "analysis"
    FILES = "files"
    DIRECTORIES = "directories"
    SYNTHESIS = "synthesis"
    ARCHITECTURE = "architecture"
    OVERVIEW = "overview"
    WORKFLOWS = "workflows"


@dataclass
class GenerationProgress:
    """Progress update during generation.

    Attributes:
        phase: Current generation phase.
        step: Current step number within phase.
        total_steps: Total steps in current phase.
        message: Human-readable progress message.
        timestamp: Time of progress update.
    """

    phase: GenerationPhase
    step: int = 0
    total_steps: int = 0
    message: str = ""
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class GenerationResult:
    """Result from running the generation pipeline.

    Contains all data needed for downstream phases like indexing.

    Attributes:
        job_id: Unique identifier for this generation run.
        synthesis_map: The synthesis map with layers, entry points, etc.
        analysis_symbols: List of parsed symbol dicts from code analysis.
        file_imports: Mapping of file paths to their imports.
        files_regenerated: Whether any files were regenerated.
        directories_regenerated: Whether any directories were regenerated.
    """

    job_id: str
    synthesis_map: SynthesisMap | None = None
    analysis_symbols: list[dict[str, Any]] | None = None
    file_imports: dict[str, list[str]] | None = None
    files_regenerated: bool = False
    directories_regenerated: bool = False


# Type alias for progress callback
ProgressCallback = Callable[[GenerationProgress], Coroutine[Any, Any, None]]


def batched(iterable, n: int) -> Iterator[list]:
    """Batch an iterable into chunks of size n.

    Args:
        iterable: Items to batch.
        n: Batch size.

    Yields:
        Lists of up to n items.
    """
    it = iter(iterable)
    while batch := list(islice(it, n)):
        yield batch


def compute_content_hash(content: str) -> str:
    """Compute SHA-256 hash of content.

    Args:
        content: String content to hash.

    Returns:
        Hex digest of SHA-256 hash.
    """
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def compute_directory_signature(file_hashes: list[tuple[str, str]]) -> str:
    """Compute a signature hash for a directory based on its files.

    Args:
        file_hashes: List of (filename, content_hash) tuples for files in directory.

    Returns:
        Hex digest of SHA-256 hash of the sorted file hashes.
    """
    # Sort by filename for deterministic ordering
    sorted_hashes = sorted(file_hashes, key=lambda x: x[0])
    signature = "|".join(f"{name}:{hash}" for name, hash in sorted_hashes)
    return hashlib.sha256(signature.encode("utf-8")).hexdigest()


def compute_directory_signature_with_children(
    file_hashes: list[tuple[str, str]],
    child_summaries: list[DirectorySummary],
) -> str:
    """Compute a signature hash for a directory including child directory purposes.

    Args:
        file_hashes: List of (filename, content_hash) tuples for files in directory.
        child_summaries: List of DirectorySummary objects for child directories.

    Returns:
        Hex digest of SHA-256 hash combining file hashes and child purposes.
    """
    # Include file hashes
    sorted_hashes = sorted(file_hashes, key=lambda x: x[0])
    file_part = "|".join(f"{name}:{hash}" for name, hash in sorted_hashes)

    # Include child directory purposes
    sorted_children = sorted(child_summaries, key=lambda x: x.directory_path)
    child_part = "|".join(f"{c.directory_path}:{c.purpose}" for c in sorted_children)

    combined = f"{file_part}||{child_part}"
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()


def group_directories_by_depth(directories: list[str]) -> dict[int, list[str]]:
    """Group directories by their depth level.

    Args:
        directories: List of directory paths.

    Returns:
        Dict mapping depth to list of directories at that depth.
    """
    result: dict[int, list[str]] = defaultdict(list)
    for dir_path in directories:
        if dir_path == "":
            depth = -1  # Root is special, processed last
        else:
            depth = dir_path.count("/")
        result[depth].append(dir_path)
    return dict(result)


def get_processing_order(directories: list[str]) -> list[str]:
    """Get directories in processing order (deepest first, root last).

    Args:
        directories: List of directory paths.

    Returns:
        List of directories ordered for processing.
    """
    grouped = group_directories_by_depth(directories)
    result = []

    # Process by depth, deepest first (highest depth number first)
    for depth in sorted(grouped.keys(), reverse=True):
        if depth == -1:
            continue  # Skip root for now
        result.extend(sorted(grouped[depth]))

    # Root always last
    if -1 in grouped:
        result.extend(grouped[-1])

    return result


class GenerationOrchestrator:
    """Orchestrates the wiki generation pipeline.

    Coordinates all generation phases in the bottom-up sequence:
    Analysis → Files → Directories → Synthesis → Architecture → Overview → Workflows

    This ordering ensures that high-level documentation (Architecture, Overview)
    is informed by actual code understanding from lower-level summaries.

    Attributes:
        llm_client: LLM client for generation.
        repo: Repository wrapper for file access.
        db: Database for recording pages.
        wiki_path: Path where wiki files will be saved.
        parser_registry: Parser registry for code analysis.
        parallel_limit: Max concurrent LLM calls for file/directory generation.
        meta_path: Path for synthesis storage.
    """

    def __init__(
        self,
        llm_client,
        repo,
        db,
        wiki_path: Path,
        parser_registry: ParserRegistry | None = None,
        parallel_limit: int = 10,
        issues_store: "IssuesStore | None" = None,
        ignore_path: Path | None = None,
    ):
        """Initialize the orchestrator.

        Args:
            llm_client: LLM client for generation.
            repo: Repository wrapper.
            db: Database for recording pages.
            wiki_path: Path where wiki files will be saved.
            parser_registry: Optional parser registry for code analysis.
            parallel_limit: Max concurrent LLM calls for file/directory generation.
            issues_store: Optional IssuesStore for indexing detected code issues.
            ignore_path: Path to .oyaignore file. If None, defaults to repo_path/.oyaignore.
        """
        self.llm_client = llm_client
        self.repo = repo
        self.db = db
        self.wiki_path = Path(wiki_path)
        self.parser_registry = parser_registry or ParserRegistry()
        self._fallback_parser = FallbackParser()
        self.parallel_limit = parallel_limit
        self._issues_store = issues_store
        self.ignore_path = ignore_path

        # Initialize generators
        self.overview_generator = OverviewGenerator(llm_client, repo)
        self.architecture_generator = ArchitectureGenerator(llm_client, repo)
        self.graph_architecture_generator = GraphArchitectureGenerator(llm_client)
        self.workflow_generator = WorkflowGenerator(llm_client, repo)
        self.directory_generator = DirectoryGenerator(llm_client, repo)
        self.file_generator = FileGenerator(llm_client, repo)
        self.synthesis_generator = SynthesisGenerator(llm_client)

        # Diagram generator for overview architecture diagram
        self.layer_diagram_generator = LayerDiagramGenerator()

        # Graph directory for graph-based architecture generation
        self.graph_path = self.wiki_path.parent / "graph"

        # Meta path for synthesis storage
        self.meta_path = self.wiki_path.parent / "meta"

    def _get_existing_page_info(self, target: str, page_type: str) -> dict | None:
        """Get existing page info from database for incremental check.

        Args:
            target: Target path (file or directory path).
            page_type: Type of page ('file' or 'directory').

        Returns:
            Dict with 'source_hash' and 'generated_at' if page exists, None otherwise.
        """
        if not hasattr(self.db, "execute"):
            return None

        try:
            cursor = self.db.execute(
                """
                SELECT metadata, generated_at FROM wiki_pages
                WHERE target = ? AND type = ?
                """,
                (target, page_type),
            )
            row = cursor.fetchone()
            if row:
                metadata = json.loads(row[0]) if row[0] else {}
                return {
                    "source_hash": metadata.get("source_hash"),
                    "generated_at": row[1],
                    "purpose": metadata.get("purpose"),
                    "layer": metadata.get("layer"),
                }
        except Exception:
            pass
        return None

    def _has_new_notes(self, target: str, generated_at: str | None) -> bool:
        """Check if there are notes created after the page was generated.

        Args:
            target: Target path to check for notes.
            generated_at: Timestamp when the page was last generated.

        Returns:
            True if there are new notes, False otherwise.
        """
        if not generated_at or not hasattr(self.db, "execute"):
            return False

        try:
            cursor = self.db.execute(
                """
                SELECT COUNT(*) FROM notes
                WHERE target = ? AND updated_at > ?
                """,
                (target, generated_at),
            )
            row = cursor.fetchone()
            return row[0] > 0 if row else False
        except Exception:
            return False

    def _get_direct_child_summaries(
        self,
        parent_path: str,
        all_summaries: dict[str, DirectorySummary],
    ) -> list[DirectorySummary]:
        """Get DirectorySummaries for direct children of a directory.

        Args:
            parent_path: Path to the parent directory (empty string for root).
            all_summaries: Dict mapping directory path to its DirectorySummary.

        Returns:
            List of DirectorySummary objects for direct child directories.
        """
        result = []
        prefix = f"{parent_path}/" if parent_path else ""

        for child_path, summary in all_summaries.items():
            if not child_path.startswith(prefix):
                continue
            remaining = child_path[len(prefix) :]
            if "/" not in remaining and remaining:
                result.append(summary)

        return result

    def _should_regenerate_file(
        self, file_path: str, content: str, file_hashes: dict[str, str]
    ) -> tuple[bool, str, dict | None]:
        """Check if a file page needs regeneration.

        Args:
            file_path: Path to the source file.
            content: Content of the source file.
            file_hashes: Dict to store computed hashes (modified in place).

        Returns:
            Tuple of (should_regenerate, content_hash, existing_info).
            existing_info is the stored page info if not regenerating, None otherwise.
        """
        content_hash = compute_content_hash(content)
        file_hashes[file_path] = content_hash

        existing = self._get_existing_page_info(file_path, "file")
        if not existing:
            return True, content_hash, None

        # Check if content changed
        if existing.get("source_hash") != content_hash:
            return True, content_hash, None

        # Check if there are new notes
        if self._has_new_notes(file_path, existing.get("generated_at")):
            return True, content_hash, None

        return False, content_hash, existing

    def _should_regenerate_directory(
        self, dir_path: str, dir_files: list[str], file_hashes: dict[str, str]
    ) -> tuple[bool, str]:
        """Check if a directory page needs regeneration.

        Args:
            dir_path: Path to the directory.
            dir_files: List of files in this directory.
            file_hashes: Dict of file path to content hash.

        Returns:
            Tuple of (should_regenerate, signature_hash).
        """
        # Build signature from files in this directory
        file_hash_pairs = [
            (f.split("/")[-1], file_hashes.get(f, "")) for f in dir_files if f in file_hashes
        ]
        signature_hash = compute_directory_signature(file_hash_pairs)

        existing = self._get_existing_page_info(dir_path, "directory")
        if not existing:
            return True, signature_hash

        # Check if directory signature changed
        if existing.get("source_hash") != signature_hash:
            return True, signature_hash

        # Check if there are new notes
        if self._has_new_notes(dir_path, existing.get("generated_at")):
            return True, signature_hash

        return False, signature_hash

    def _should_regenerate_synthesis(
        self,
        files_regenerated: bool,
        directories_regenerated: bool,
    ) -> bool:
        """Check if synthesis needs to be regenerated.

        Synthesis should be regenerated when:
        - Any file's documentation was regenerated (cascade from files)
        - Any directory's documentation was regenerated (cascade from directories)
        - No existing synthesis.json exists

        Args:
            files_regenerated: True if any file was regenerated.
            directories_regenerated: True if any directory was regenerated.

        Returns:
            True if synthesis should be regenerated.
        """
        # If any files or directories were regenerated, synthesis must be regenerated
        if files_regenerated or directories_regenerated:
            return True

        # Check if synthesis.json exists
        synthesis_path = self.meta_path / "synthesis.json"
        if not synthesis_path.exists():
            return True

        return False

    async def run(
        self,
        progress_callback: ProgressCallback | None = None,
    ) -> GenerationResult:
        """Run the complete generation pipeline.

        Pipeline order: Analysis → Files → Directories → Synthesis →
        Architecture → Overview → Workflows

        This bottom-up approach ensures that:
        - File documentation is generated first, extracting structured summaries
        - Directory documentation uses file summaries for context
        - Synthesis combines all summaries into a coherent codebase map
        - Architecture and Overview use the synthesis map for accurate context

        Cascade behavior (Requirement 7.2):
        - If any file is regenerated, synthesis is regenerated
        - If synthesis is regenerated, architecture and overview are regenerated

        Args:
            progress_callback: Optional async callback for progress updates.

        Returns:
            GenerationResult containing job_id, synthesis_map, and analysis data.
        """
        job_id = str(uuid.uuid4())

        # Ensure wiki and meta directories exist
        self.wiki_path.mkdir(parents=True, exist_ok=True)
        self.meta_path.mkdir(parents=True, exist_ok=True)

        # Phase 1: Analysis (with progress tracking for file parsing)
        analysis = await self._run_analysis(progress_callback)

        # Build code index from parsed files if enabled
        self._build_code_index(analysis.get("parsed_files", []))

        # Phase 2: Files (run before directories to compute content hashes and collect summaries)
        file_pages, file_hashes, file_summaries, file_layers = await self._run_files(
            analysis, progress_callback
        )
        for page in file_pages:
            await self._save_page_with_frontmatter(page, layer=file_layers.get(page.path))

        # Track if any files were regenerated (for cascade)
        files_regenerated = len(file_pages) > 0

        # Phase 3: Directories
        # (uses file_hashes for signature computation and file_summaries for context)
        directory_pages, directory_summaries = await self._run_directories(
            analysis, file_hashes, progress_callback, file_summaries=file_summaries
        )
        for page in directory_pages:
            await self._save_page_with_frontmatter(page)

        # Track if any directories were regenerated (for cascade)
        directories_regenerated = len(directory_pages) > 0

        # Phase 4: Synthesis (combine file and directory summaries into SynthesisMap)
        # Cascade: regenerate synthesis if any files or directories were regenerated
        should_regenerate_synthesis = self._should_regenerate_synthesis(
            files_regenerated, directories_regenerated
        )

        synthesis_map: SynthesisMap | None = None
        if should_regenerate_synthesis:
            await self._emit_progress(
                progress_callback,
                GenerationProgress(
                    phase=GenerationPhase.SYNTHESIS,
                    step=0,
                    total_steps=1,
                    message="Synthesizing codebase understanding...",
                ),
            )
            synthesis_map = await self._run_synthesis(
                file_summaries,
                directory_summaries,
                file_contents=analysis["file_contents"],
                all_symbols=analysis["symbols"],
            )
            await self._emit_progress(
                progress_callback,
                GenerationProgress(
                    phase=GenerationPhase.SYNTHESIS,
                    step=1,
                    total_steps=1,
                    message="Synthesis complete",
                ),
            )
        else:
            # Load existing synthesis map
            synthesis_map, _ = load_synthesis_map(str(self.meta_path))
            if synthesis_map is None:
                # Fallback: regenerate if loading fails
                await self._emit_progress(
                    progress_callback,
                    GenerationProgress(
                        phase=GenerationPhase.SYNTHESIS,
                        message="Synthesizing codebase understanding...",
                    ),
                )
                synthesis_map = await self._run_synthesis(
                    file_summaries,
                    directory_summaries,
                    file_contents=analysis["file_contents"],
                    all_symbols=analysis["symbols"],
                )

        # At this point synthesis_map is guaranteed to be set
        assert synthesis_map is not None

        # Phase 5: Architecture (uses SynthesisMap as primary context)
        # Cascade: regenerate architecture only if synthesis was regenerated (Requirement 7.3, 7.5)
        if should_regenerate_synthesis:
            await self._emit_progress(
                progress_callback,
                GenerationProgress(
                    phase=GenerationPhase.ARCHITECTURE,
                    step=0,
                    total_steps=1,
                    message="Generating architecture page...",
                ),
            )
            architecture_page = await self._run_architecture(analysis, synthesis_map=synthesis_map)
            await self._save_page_with_frontmatter(architecture_page)
            await self._emit_progress(
                progress_callback,
                GenerationProgress(
                    phase=GenerationPhase.ARCHITECTURE,
                    step=1,
                    total_steps=1,
                    message="Architecture complete",
                ),
            )

        # Phase 6: Overview (uses SynthesisMap as primary context)
        # Cascade: regenerate overview only if synthesis was regenerated (Requirement 7.3, 7.5)
        if should_regenerate_synthesis:
            await self._emit_progress(
                progress_callback,
                GenerationProgress(
                    phase=GenerationPhase.OVERVIEW,
                    step=0,
                    total_steps=1,
                    message="Generating overview page...",
                ),
            )
            overview_page = await self._run_overview(analysis, synthesis_map=synthesis_map)
            await self._save_page_with_frontmatter(overview_page)
            await self._emit_progress(
                progress_callback,
                GenerationProgress(
                    phase=GenerationPhase.OVERVIEW,
                    step=1,
                    total_steps=1,
                    message="Overview complete",
                ),
            )

        # Phase 7: Workflows
        # Cascade: regenerate workflows only if synthesis was regenerated (Requirement 7.5)
        if should_regenerate_synthesis:
            workflow_pages = await self._run_workflows(
                analysis, progress_callback, synthesis_map=synthesis_map
            )
            for page in workflow_pages:
                await self._save_page_with_frontmatter(page)

        # Convert ParsedSymbol objects to dicts for indexing
        analysis_symbols = [
            {
                "name": s.name,
                "type": s.symbol_type.value,
                "file": s.metadata.get("file", ""),
                "line": s.start_line,
                "decorators": s.decorators,
            }
            for s in analysis.get("symbols", [])
        ]

        return GenerationResult(
            job_id=job_id,
            synthesis_map=synthesis_map,
            analysis_symbols=analysis_symbols,
            file_imports=analysis.get("file_imports"),
            files_regenerated=files_regenerated,
            directories_regenerated=directories_regenerated,
        )

    async def _emit_progress(
        self,
        callback: ProgressCallback | None,
        progress: GenerationProgress,
    ) -> None:
        """Emit a progress update if callback is provided.

        Args:
            callback: Optional progress callback.
            progress: Progress update to emit.
        """
        if callback:
            await callback(progress)

    async def _run_analysis(
        self,
        progress_callback: ProgressCallback | None = None,
    ) -> dict:
        """Run analysis phase.

        Args:
            progress_callback: Optional async callback for progress updates.

        Returns:
            Analysis results with files, symbols, file_tree, file_contents,
            file_imports, parse_errors, and parsed_files.
        """
        # Use FileFilter to respect .oyaignore and default exclusions
        file_filter = FileFilter(self.repo.path, ignore_path=self.ignore_path)
        files = file_filter.get_files()
        file_contents: dict[str, str] = {}

        # Build file tree
        file_tree = self._build_file_tree(files)

        total_files = len(files)

        # Emit initial progress
        await self._emit_progress(
            progress_callback,
            GenerationProgress(
                phase=GenerationPhase.ANALYSIS,
                step=0,
                total_steps=total_files,
                message=f"Parsing files (0/{total_files})...",
            ),
        )

        # Parse each file
        parse_errors: list[dict] = []
        all_symbols: list[ParsedSymbol] = []
        parsed_files: list[ParsedFile] = []
        file_imports: dict[str, list[str]] = {}

        for idx, file_path in enumerate(files):
            full_path = self.repo.path / file_path
            if not full_path.exists() or not full_path.is_file():
                continue

            try:
                content = full_path.read_text(encoding="utf-8", errors="ignore")
                file_contents[file_path] = content

                # Parse for symbols
                result = self.parser_registry.parse_file(Path(file_path), content)

                if result.ok and result.file:
                    # Successful parse - use full symbol data
                    file_imports[file_path] = result.file.imports
                    parsed_files.append(result.file)
                    for symbol in result.file.symbols:
                        symbol.metadata["file"] = file_path
                        all_symbols.append(symbol)
                else:
                    # Parse failed - try fallback for partial recovery
                    parse_errors.append(
                        {
                            "file": file_path,
                            "error": result.error or "Unknown parse error",
                            "recovered": True,
                        }
                    )
                    fallback_result = self._fallback_parser.parse(Path(file_path), content)
                    if fallback_result.ok and fallback_result.file:
                        file_imports[file_path] = fallback_result.file.imports
                        parsed_files.append(fallback_result.file)
                        for symbol in fallback_result.file.symbols:
                            symbol.metadata["file"] = file_path
                            all_symbols.append(symbol)

            except Exception as e:
                # File read error - track but continue
                parse_errors.append(
                    {
                        "file": file_path,
                        "error": str(e),
                        "recovered": False,
                    }
                )

            # Emit progress (configurable interval)
            try:
                settings = load_settings()
                progress_interval = settings.generation.progress_report_interval
            except (ValueError, OSError, ConfigError):
                # Settings not available
                progress_interval = 1  # Default from CONFIG_SCHEMA
            if (idx + 1) % progress_interval == 0 or idx == total_files - 1:
                await self._emit_progress(
                    progress_callback,
                    GenerationProgress(
                        phase=GenerationPhase.ANALYSIS,
                        step=idx + 1,
                        total_steps=total_files,
                        message=f"Parsed {idx + 1}/{total_files} files...",
                    ),
                )

        return {
            "files": files,
            "symbols": all_symbols,
            "file_tree": file_tree,
            "file_contents": file_contents,
            "file_imports": file_imports,
            "parse_errors": parse_errors,
            "parsed_files": parsed_files,
        }

    def _build_file_tree(self, files: list[str]) -> str:
        """Build a string representation of the file tree.

        Args:
            files: List of file paths.

        Returns:
            String representation of file tree.
        """
        if not files:
            return ""

        lines = []
        sorted_files = sorted(files)

        for file_path in sorted_files:
            # Simple indentation based on depth
            depth = file_path.count("/")
            indent = "  " * depth
            name = file_path.split("/")[-1]
            lines.append(f"{indent}{name}")

        return "\n".join(lines)

    async def _run_overview(
        self,
        analysis: dict,
        synthesis_map: SynthesisMap | None = None,
    ) -> GeneratedPage:
        """Run overview generation phase.

        Args:
            analysis: Analysis results.
            synthesis_map: Optional SynthesisMap for richer overview context.

        Returns:
            Generated overview page.
        """
        # Try to get README content
        readme_content = None
        for readme_name in ["README.md", "readme.md", "README.rst", "README"]:
            if readme_name in analysis["file_contents"]:
                readme_content = analysis["file_contents"][readme_name]
                break

        # Try to extract package info from package.json or pyproject.toml
        package_info = self._extract_package_info(analysis["file_contents"])

        # Generate architecture diagram from synthesis map
        architecture_diagram = ""
        if synthesis_map is not None:
            architecture_diagram = self.layer_diagram_generator.generate(synthesis_map)

        return await self.overview_generator.generate(
            readme_content=readme_content,
            file_tree=analysis["file_tree"],
            package_info=package_info,
            synthesis_map=synthesis_map,
            architecture_diagram=architecture_diagram,
        )

    def _extract_package_info(self, file_contents: dict[str, str]) -> dict:
        """Extract package information from project files.

        Args:
            file_contents: Mapping of file paths to contents.

        Returns:
            Package info dictionary.
        """
        package_info: dict[str, Any] = {}

        # Try package.json
        if "package.json" in file_contents:
            try:
                data = json.loads(file_contents["package.json"])
                package_info["name"] = data.get("name", "")
                package_info["version"] = data.get("version", "")
                package_info["description"] = data.get("description", "")
                package_info["dependencies"] = list(data.get("dependencies", {}).keys())
            except Exception:
                pass

        # Try pyproject.toml
        if "pyproject.toml" in file_contents:
            try:
                data = tomllib.loads(file_contents["pyproject.toml"])
                project = data.get("project", {})
                package_info["name"] = project.get("name", "")
                package_info["version"] = project.get("version", "")
                package_info["description"] = project.get("description", "")
                deps = project.get("dependencies", [])
                package_info["dependencies"] = deps if isinstance(deps, list) else []
            except Exception:
                pass

        return package_info

    async def _run_architecture(
        self,
        analysis: dict,
        synthesis_map: SynthesisMap | None = None,
    ) -> GeneratedPage:
        """Run architecture generation phase.

        Uses graph-based generation when a code graph with >= 5 nodes is available,
        otherwise falls back to standard LLM-only generation.

        Args:
            analysis: Analysis results.
            synthesis_map: Optional SynthesisMap for richer architecture context.

        Returns:
            Generated architecture page.
        """
        # Try to load graph for graph-based architecture generation
        graph = load_graph(self.graph_path)

        # Use graph-based generation if graph has >= 5 nodes
        min_graph_nodes = 5
        if graph.number_of_nodes() >= min_graph_nodes:
            # Build component summaries from synthesis map if available
            component_summaries: dict[str, str] = {}
            if synthesis_map is not None:
                for component in synthesis_map.key_components:
                    component_summaries[component.name] = component.role

            return await self.graph_architecture_generator.generate(
                repo_name=self.repo.path.name,
                graph=graph,
                component_summaries=component_summaries,
            )

        # Fall back to standard generation
        # Extract dependencies from package info
        package_info = self._extract_package_info(analysis["file_contents"])
        dependencies = package_info.get("dependencies", [])

        # If we have a synthesis map, use it as primary context
        if synthesis_map is not None:
            return await self.architecture_generator.generate(
                file_tree=analysis["file_tree"],
                dependencies=dependencies,
                synthesis_map=synthesis_map,
                file_imports=analysis.get("file_imports", {}),
                symbols=analysis.get("symbols", []),
            )

        # Legacy mode: use key symbols (convert ParsedSymbol to dict)
        key_symbols = [
            self._symbol_to_dict(s)
            for s in analysis["symbols"]
            if s.symbol_type.value in ("class", "function", "method")
        ][:50]  # Limit to top 50

        return await self.architecture_generator.generate(
            file_tree=analysis["file_tree"],
            key_symbols=key_symbols,
            dependencies=dependencies,
            file_imports=analysis.get("file_imports", {}),
            symbols=analysis.get("symbols", []),
        )

    async def _run_workflows(
        self,
        analysis: dict,
        progress_callback: ProgressCallback | None = None,
        synthesis_map: SynthesisMap | None = None,
    ) -> list[GeneratedPage]:
        """Run workflow generation phase.

        Uses entry points from SynthesisMap (computed during synthesis phase)
        and groups them by domain using pattern heuristics.

        Args:
            analysis: Analysis results.
            progress_callback: Optional async callback for progress updates.
            synthesis_map: SynthesisMap containing entry points and context.

        Returns:
            List of generated workflow pages.
        """
        pages: list[GeneratedPage] = []

        # Use entry points from synthesis_map (already discovered during synthesis)
        if not synthesis_map or not synthesis_map.entry_points:
            return pages

        # Group entry points by domain
        grouper = WorkflowGrouper()
        workflow_groups = grouper.group(
            entry_points=synthesis_map.entry_points,
            file_imports=analysis.get("file_imports", {}),
            synthesis_map=synthesis_map,
        )

        total_workflows = len(workflow_groups)

        # Emit initial progress
        await self._emit_progress(
            progress_callback,
            GenerationProgress(
                phase=GenerationPhase.WORKFLOWS,
                step=0,
                total_steps=total_workflows,
                message=f"Generating workflow pages (0/{total_workflows})...",
            ),
        )

        # Generate page for each workflow group
        for idx, workflow_group in enumerate(workflow_groups):
            page = await self.workflow_generator.generate(
                workflow_group=workflow_group,
                synthesis_map=synthesis_map,
                symbols=analysis.get("symbols", []),
                file_imports=analysis.get("file_imports", {}),
            )
            pages.append(page)

            # Emit progress after each workflow
            await self._emit_progress(
                progress_callback,
                GenerationProgress(
                    phase=GenerationPhase.WORKFLOWS,
                    step=idx + 1,
                    total_steps=total_workflows,
                    message=f"Generated {idx + 1}/{total_workflows} workflows...",
                ),
            )

        return pages

    async def _run_synthesis(
        self,
        file_summaries: list[FileSummary],
        directory_summaries: list[DirectorySummary],
        file_contents: dict[str, str] | None = None,
        all_symbols: list[ParsedSymbol] | None = None,
    ) -> SynthesisMap:
        """Run synthesis phase to combine summaries into a SynthesisMap.

        Args:
            file_summaries: List of FileSummary objects from files phase.
            directory_summaries: List of DirectorySummary objects from directories phase.
            file_contents: Optional dict mapping file paths to contents (for metrics).
            all_symbols: Optional list of all parsed symbols (for entry point discovery).

        Returns:
            SynthesisMap containing aggregated codebase understanding.
        """
        # Generate the synthesis map
        synthesis_map = await self.synthesis_generator.generate(
            file_summaries=file_summaries,
            directory_summaries=directory_summaries,
        )

        # Populate tech_stack from file summaries
        synthesis_map.tech_stack = detect_tech_stack(file_summaries)

        # Populate metrics if file_contents available
        if file_contents:
            synthesis_map.metrics = compute_code_metrics(file_summaries, file_contents)

        # Discover and populate entry points if symbols available
        if all_symbols:
            entry_point_symbols = find_entry_points(all_symbols)
            synthesis_map.entry_points = [
                EntryPointInfo(
                    name=ep.name,
                    entry_type=ep.symbol_type.value,
                    file=ep.metadata.get("file", ""),
                    description=extract_entry_point_description(ep),
                )
                for ep in entry_point_symbols
            ]

        # Save to synthesis.json
        save_synthesis_map(synthesis_map, str(self.meta_path))

        return synthesis_map

    async def _run_directories(
        self,
        analysis: dict,
        file_hashes: dict[str, str],
        progress_callback: ProgressCallback | None = None,
        file_summaries: list[FileSummary] | None = None,
    ) -> tuple[list[GeneratedPage], list[DirectorySummary]]:
        """Run directory generation phase with depth-first processing and incremental support.

        Directories are processed in depth-first order (deepest first, root last) so that
        child directory summaries are available when generating parent directories.

        Args:
            analysis: Analysis results.
            file_hashes: Dict of file_path to content_hash from files phase.
            progress_callback: Optional async callback for progress updates.
            file_summaries: Optional list of FileSummary objects for context.

        Returns:
            Tuple of (list of generated directory pages, list of DirectorySummaries).
        """
        pages: list[GeneratedPage] = []
        directory_summaries: list[DirectorySummary] = []
        file_summaries = file_summaries or []

        # Track all generated summaries for parent access
        all_summaries: dict[str, DirectorySummary] = {}

        # Build a lookup of file summaries by file path for quick access
        file_summary_lookup: dict[str, FileSummary] = {
            fs.file_path: fs for fs in file_summaries if isinstance(fs, FileSummary)
        }

        # Get unique directories using the shared utility function
        all_directories = extract_directories_from_files(analysis["files"])

        # Build directories dict with their direct files
        directories: dict[str, list[str]] = {d: [] for d in all_directories}

        # Compute direct files for each directory
        for file_path in analysis["files"]:
            parts = file_path.split("/")
            if len(parts) == 1:
                # Root-level file (e.g., README.md)
                directories[""].append(file_path)
            else:
                parent_dir = "/".join(parts[:-1])
                if parent_dir in directories:
                    directories[parent_dir].append(file_path)

        # Get processing order: depth-first (deepest directories first, root last)
        processing_order = get_processing_order(all_directories)
        total_dirs = len(processing_order)

        # Project name for breadcrumbs
        project_name = self.repo.path.name

        # Emit initial progress
        await self._emit_progress(
            progress_callback,
            GenerationProgress(
                phase=GenerationPhase.DIRECTORIES,
                step=0,
                total_steps=total_dirs,
                message=f"Generating directory pages (0/{total_dirs})...",
            ),
        )

        # Process directories sequentially in depth-first order
        # (children must complete before parents to provide child summaries)
        completed = 0
        skipped_count = 0

        for dir_path in processing_order:
            dir_files = directories[dir_path]

            # Get child summaries for this directory
            child_summaries = self._get_direct_child_summaries(dir_path, all_summaries)

            # Compute signature including child purposes
            file_hash_pairs = [
                (f.split("/")[-1], file_hashes.get(f, "")) for f in dir_files if f in file_hashes
            ]
            signature_hash = compute_directory_signature_with_children(
                file_hash_pairs, child_summaries
            )

            # Check if regeneration is needed
            existing = self._get_existing_page_info(dir_path, "directory")
            should_regenerate = True

            if existing:
                if existing.get("source_hash") == signature_hash:
                    if not self._has_new_notes(dir_path, existing.get("generated_at")):
                        should_regenerate = False

            if not should_regenerate:
                skipped_count += 1
                completed += 1
                # For skipped directories, we need a placeholder summary for parent access
                # Use the stored purpose from the database to maintain signature consistency
                stored_purpose = existing.get("purpose", "") if existing else ""
                placeholder_summary = DirectorySummary(
                    directory_path=dir_path,
                    purpose=stored_purpose,
                    contains=[f.split("/")[-1] for f in dir_files],
                    role_in_system="",
                )
                all_summaries[dir_path] = placeholder_summary
                continue

            # Get direct files for this directory
            if dir_path == "":
                # Root directory: files without "/" are root-level
                direct_files = [f for f in analysis["files"] if "/" not in f]
            else:
                direct_files = [
                    f
                    for f in analysis["files"]
                    if f.startswith(dir_path + "/") and "/" not in f[len(dir_path) + 1 :]
                ]

            # Filter symbols by file path and convert to dicts for generator
            if dir_path == "":
                # Root: symbols from root-level files
                dir_symbols = [
                    self._symbol_to_dict(s)
                    for s in analysis["symbols"]
                    if "/" not in s.metadata.get("file", "")
                ]
            else:
                dir_symbols = [
                    self._symbol_to_dict(s)
                    for s in analysis["symbols"]
                    if s.metadata.get("file", "").startswith(dir_path + "/")
                ]

            # Get file summaries for files in this directory
            dir_file_summaries = [
                file_summary_lookup[f] for f in direct_files if f in file_summary_lookup
            ]

            # Load notes for this directory
            notes = get_notes_for_target(self.db, "directory", dir_path)

            # Generate directory page with child summaries
            page, directory_summary = await self.directory_generator.generate(
                directory_path=dir_path,
                file_list=direct_files,
                symbols=dir_symbols,
                architecture_context="",
                file_summaries=dir_file_summaries,
                child_summaries=child_summaries,
                project_name=project_name,
                notes=notes,
            )

            # Add signature hash and purpose to the page for storage
            page.source_hash = signature_hash
            page.purpose = directory_summary.purpose

            pages.append(page)
            directory_summaries.append(directory_summary)
            all_summaries[dir_path] = directory_summary

            completed += 1
            generated_so_far = completed - skipped_count
            await self._emit_progress(
                progress_callback,
                GenerationProgress(
                    phase=GenerationPhase.DIRECTORIES,
                    step=completed,
                    total_steps=total_dirs,
                    message=(
                        f"Generated {generated_so_far}/{total_dirs - skipped_count} "
                        f"directories ({skipped_count} unchanged)..."
                    ),
                ),
            )

        return pages, directory_summaries

    async def _run_files(
        self,
        analysis: dict,
        progress_callback: ProgressCallback | None = None,
    ) -> tuple[list[GeneratedPage], dict[str, str], list[FileSummary], dict[str, str | None]]:
        """Run file generation phase with parallel processing and incremental support.

        Args:
            analysis: Analysis results.
            progress_callback: Optional async callback for progress updates.

        Returns:
            Tuple of (list of generated file pages, dict of file_path to content_hash,
            list of FileSummaries, dict mapping page path to layer).
        """
        pages: list[GeneratedPage] = []
        file_hashes: dict[str, str] = {}
        file_summaries: list[FileSummary] = []
        file_layers: dict[str, str | None] = {}

        # Generate page for each source file
        # Use denylist approach: document everything EXCEPT known non-code files
        # This ensures we support any programming language without maintaining an allowlist
        non_code_extensions = {
            # Documentation
            ".md",
            ".rst",
            ".txt",
            ".adoc",
            ".asciidoc",
            # Data/config formats
            ".json",
            ".yaml",
            ".yml",
            ".toml",
            ".ini",
            ".cfg",
            ".conf",
            ".xml",
            ".csv",
            ".tsv",
            # Lock files
            ".lock",
            # Images (shouldn't be here, but just in case binary detection missed them)
            ".png",
            ".jpg",
            ".jpeg",
            ".gif",
            ".svg",
            ".ico",
            ".webp",
            # Other non-code
            ".log",
            ".pid",
            ".env",
            ".env.example",
        }
        non_code_names = {
            # Common non-code files (case-insensitive matching below)
            "readme",
            "readme.md",
            "readme.rst",
            "readme.txt",
            "license",
            "license.md",
            "license.txt",
            "copying",
            "changelog",
            "changelog.md",
            "changes",
            "changes.md",
            "history.md",
            "contributing",
            "contributing.md",
            "authors",
            "authors.md",
            "contributors",
            "makefile",
            "dockerfile",
            "vagrantfile",
            "gemfile",
            "gemfile.lock",
            "package.json",
            "package-lock.json",
            "composer.json",
            "composer.lock",
            "cargo.toml",
            "cargo.lock",
            "pyproject.toml",
            "poetry.lock",
            "pipfile",
            "pipfile.lock",
            "requirements.txt",
            "setup.py",
            "setup.cfg",
            ".gitignore",
            ".gitattributes",
            ".dockerignore",
            ".editorconfig",
            ".prettierrc",
            ".eslintrc",
        }

        # Filter to source files and check which need regeneration
        files_to_generate: list[tuple[str, str]] = []  # (file_path, content_hash)
        skipped_files: list[tuple[str, dict]] = []  # (file_path, existing_info)

        for file_path in analysis["files"]:
            ext = Path(file_path).suffix.lower()
            filename = Path(file_path).name.lower()

            # Skip known non-code files
            if ext in non_code_extensions or filename in non_code_names:
                continue

            # Process all other text files as source code
            content = analysis["file_contents"].get(file_path, "")
            if content:
                should_regen, content_hash, existing_info = self._should_regenerate_file(
                    file_path, content, file_hashes
                )
                if should_regen:
                    files_to_generate.append((file_path, content_hash))
                else:
                    skipped_files.append((file_path, existing_info or {}))

        # Create placeholder FileSummaries for skipped files
        for file_path, existing_info in skipped_files:
            stored_purpose = existing_info.get("purpose") or ""
            stored_layer = existing_info.get("layer") or "utility"  # Default to utility
            placeholder_summary = FileSummary(
                file_path=file_path,
                purpose=stored_purpose,
                layer=stored_layer,
                key_abstractions=[],
                internal_deps=[],
                external_deps=[],
                issues=[],
            )
            file_summaries.append(placeholder_summary)

        skipped_count = len(skipped_files)

        # Total includes both generated and skipped for accurate progress display
        total_files = len(files_to_generate) + skipped_count

        # Emit initial progress with total count
        await self._emit_progress(
            progress_callback,
            GenerationProgress(
                phase=GenerationPhase.FILES,
                step=skipped_count,
                total_steps=total_files,
                message=(
                    f"Generating file pages ({skipped_count} unchanged, "
                    f"0/{len(files_to_generate)} generating)..."
                ),
            ),
        )

        # Get all imports for dependency diagram
        all_file_imports = analysis.get("file_imports", {})

        # Get all parsed symbols from analysis (these are ParsedSymbol objects)
        all_parsed_symbols: list[ParsedSymbol] = analysis.get("symbols", [])

        # Build lookup of parsed files by path for synopsis extraction
        all_parsed_files: list[ParsedFile] = analysis.get("parsed_files", [])
        parsed_file_lookup: dict[str, ParsedFile] = {pf.path: pf for pf in all_parsed_files}

        # Get graph for call-site extraction (try analysis dict first, then load from disk)
        graph = analysis.get("graph")
        if graph is None:
            graph = load_graph(self.graph_path)
            # If graph is empty or too small, treat as None
            if graph.number_of_nodes() == 0:
                graph = None

        # Helper to generate a single file page with hash and return both page and summary
        async def generate_file_page(
            file_path: str, content_hash: str
        ) -> tuple[GeneratedPage, FileSummary]:
            content = analysis["file_contents"].get(file_path, "")
            # Filter symbols by file path and convert to dicts for generator
            file_symbols = [
                self._symbol_to_dict(s)
                for s in all_parsed_symbols
                if s.metadata.get("file") == file_path
            ]
            # Use imports collected during parsing (Task 4)
            imports = all_file_imports.get(file_path, [])

            # Filter parsed symbols for this specific file (for class diagrams)
            file_parsed_symbols = [
                s for s in all_parsed_symbols if s.metadata.get("file") == file_path
            ]

            # Load notes for this file
            notes = get_notes_for_target(self.db, "file", file_path)

            # Extract synopsis from parsed file (if available) - Tier 1
            parsed_file = parsed_file_lookup.get(file_path)
            synopsis = parsed_file.synopsis if parsed_file else None

            # Try call-site extraction if no doc synopsis - Tier 2
            call_site_synopsis = None
            if not synopsis and graph is not None:
                call_sites = get_call_sites(graph, file_path)
                if call_sites:
                    best_site, other_sites = select_best_call_site(
                        call_sites, analysis["file_contents"]
                    )
                    if best_site:
                        snippet = extract_call_snippet(
                            best_site.caller_file,
                            best_site.line,
                            analysis["file_contents"],
                        )
                        if snippet:
                            # Detect language from caller file extension (snippet is from caller)
                            ext = Path(best_site.caller_file).suffix.lower()
                            lang = EXTENSION_LANGUAGES.get(ext, "")

                            # Format other callers for display
                            other_refs = [(s.caller_file, s.line) for s in other_sites]

                            # Add note if only test callers
                            is_test_only = is_test_file(best_site.caller_file)

                            call_site_synopsis = format_call_site_synopsis(
                                snippet=snippet,
                                caller_file=best_site.caller_file,
                                line=best_site.line,
                                language=lang,
                                other_callers=other_refs if other_refs else None,
                            )

                            if is_test_only:
                                call_site_synopsis += (
                                    "\n\n**Note:** Only test usage found in this codebase."
                                )

            # FileGenerator.generate() returns (GeneratedPage, FileSummary)
            page, file_summary = await self.file_generator.generate(
                file_path=file_path,
                content=content,
                symbols=file_symbols,
                imports=imports,
                architecture_summary="",
                parsed_symbols=file_parsed_symbols,
                file_imports=all_file_imports,
                notes=notes,
                synopsis=synopsis,
                call_site_synopsis=call_site_synopsis,
            )
            # Add source hash to the page for storage
            page.source_hash = content_hash
            return page, file_summary

        # Process files in parallel batches, report as each completes
        completed = skipped_count
        for batch in batched(files_to_generate, self.parallel_limit):
            tasks = [
                asyncio.create_task(generate_file_page(file_path, content_hash))
                for file_path, content_hash in batch
            ]

            for coro in asyncio.as_completed(tasks):
                page, summary = await coro
                # Store summary data on page for incremental regeneration
                page.purpose = summary.purpose
                page.layer = summary.layer
                pages.append(page)
                file_summaries.append(summary)
                file_layers[page.path] = summary.layer

                # Index issues to IssuesStore
                if summary.issues and self._issues_store:
                    self._issues_store.add_issues(summary.file_path, summary.issues)

                completed += 1
                generated_so_far = completed - skipped_count
                await self._emit_progress(
                    progress_callback,
                    GenerationProgress(
                        phase=GenerationPhase.FILES,
                        step=completed,
                        total_steps=total_files,
                        message=(
                            f"Generated {generated_so_far}/{len(files_to_generate)} "
                            f"files ({skipped_count} unchanged)..."
                        ),
                    ),
                )

        return pages, file_hashes, file_summaries, file_layers

    def _symbol_to_dict(self, symbol: ParsedSymbol) -> dict:
        """Convert a ParsedSymbol to a dictionary for legacy consumers.

        Args:
            symbol: ParsedSymbol object.

        Returns:
            Dictionary with name, type, file, line, decorators keys.
        """
        return {
            "name": symbol.name,
            "type": symbol.symbol_type.value,
            "file": symbol.metadata.get("file", ""),
            "line": symbol.start_line,
            "decorators": symbol.decorators,
        }

    def _build_code_index(self, parsed_files: list[ParsedFile]) -> None:
        """Build code index from parsed files if enabled in settings.

        Args:
            parsed_files: List of ParsedFile objects from analysis phase.
        """
        # Check if code index is enabled
        try:
            settings = load_settings()
            if not settings.ask.use_code_index:
                return
        except (ValueError, OSError, ConfigError):
            # Settings not available, skip code index
            return

        # Skip if no database or it's a mock without execute method
        if not hasattr(self.db, "execute"):
            return

        # Skip if no parsed files
        if not parsed_files:
            return

        # Build code index
        builder = CodeIndexBuilder(self.db)
        source_hash = self.repo.get_head_commit()

        builder.build(parsed_files, source_hash)
        builder.compute_called_by()

    async def _save_page(self, page: GeneratedPage) -> None:
        """Save a generated page to the wiki directory.

        Args:
            page: Generated page to save.
        """
        # Determine full path
        page_path = self.wiki_path / page.path

        # Ensure parent directory exists
        page_path.parent.mkdir(parents=True, exist_ok=True)

        # Write content
        page_path.write_text(page.content, encoding="utf-8")

        # Build metadata JSON with source hash for incremental regeneration
        metadata = {}
        if page.source_hash:
            metadata["source_hash"] = page.source_hash

        # Record in database (if method exists)
        if hasattr(self.db, "execute"):
            try:
                self.db.execute(
                    """
                    INSERT OR REPLACE INTO wiki_pages
                    (path, type, word_count, target, metadata, generated_at)
                    VALUES (?, ?, ?, ?, ?, datetime('now'))
                    """,
                    (
                        page.path,
                        page.page_type,
                        page.word_count,
                        page.target,
                        json.dumps(metadata) if metadata else None,
                    ),
                )
                self.db.commit()
            except Exception:
                # Table might not exist yet, skip recording
                pass

    async def _save_page_with_frontmatter(
        self,
        page: GeneratedPage,
        layer: str | None = None,
    ) -> None:
        """Save a generated page with frontmatter metadata.

        Args:
            page: Generated page to save.
            layer: Architectural layer (for file pages).
        """
        # Determine full path
        page_path = self.wiki_path / page.path

        # Ensure parent directory exists
        page_path.parent.mkdir(parents=True, exist_ok=True)

        # Get current commit hash (short form for readability)
        commit = self.repo.get_head_commit()[:12]

        # Build frontmatter
        frontmatter = build_frontmatter(
            source=page.target,
            page_type=page.page_type,
            commit=commit,
            generated=datetime.now(timezone.utc),
            layer=layer,
        )

        # Write content with frontmatter
        page_path.write_text(frontmatter + page.content, encoding="utf-8")

        # Build metadata JSON with source hash for incremental regeneration
        metadata = {}
        if page.source_hash:
            metadata["source_hash"] = page.source_hash
        if page.purpose:
            metadata["purpose"] = page.purpose
        if page.layer:
            metadata["layer"] = page.layer

        # Record in database (if method exists)
        if hasattr(self.db, "execute"):
            try:
                self.db.execute(
                    """
                    INSERT OR REPLACE INTO wiki_pages
                    (path, type, word_count, target, metadata, generated_at)
                    VALUES (?, ?, ?, ?, ?, datetime('now'))
                    """,
                    (
                        page.path,
                        page.page_type,
                        page.word_count,
                        page.target,
                        json.dumps(metadata) if metadata else None,
                    ),
                )
                self.db.commit()
            except Exception:
                # Table might not exist yet, skip recording
                pass
