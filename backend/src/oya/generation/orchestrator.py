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
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from itertools import islice
from pathlib import Path
from typing import Any, Callable, Coroutine, Iterator

from oya.generation.architecture import ArchitectureGenerator
from oya.generation.directory import DirectoryGenerator
from oya.generation.file import FileGenerator
from oya.generation.overview import GeneratedPage, OverviewGenerator
from oya.generation.summaries import DirectorySummary, FileSummary, SynthesisMap
from oya.generation.synthesis import SynthesisGenerator, save_synthesis_map
from oya.generation.workflows import WorkflowDiscovery, WorkflowGenerator
from oya.constants.generation import PROGRESS_REPORT_INTERVAL
from oya.parsing.fallback_parser import FallbackParser
from oya.parsing.models import ParsedSymbol
from oya.parsing.registry import ParserRegistry
from oya.repo.file_filter import FileFilter, extract_directories_from_files


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
    ):
        """Initialize the orchestrator.

        Args:
            llm_client: LLM client for generation.
            repo: Repository wrapper.
            db: Database for recording pages.
            wiki_path: Path where wiki files will be saved.
            parser_registry: Optional parser registry for code analysis.
            parallel_limit: Max concurrent LLM calls for file/directory generation.
        """
        self.llm_client = llm_client
        self.repo = repo
        self.db = db
        self.wiki_path = Path(wiki_path)
        self.parser_registry = parser_registry or ParserRegistry()
        self._fallback_parser = FallbackParser()
        self.parallel_limit = parallel_limit

        # Initialize generators
        self.overview_generator = OverviewGenerator(llm_client, repo)
        self.architecture_generator = ArchitectureGenerator(llm_client, repo)
        self.workflow_generator = WorkflowGenerator(llm_client, repo)
        self.directory_generator = DirectoryGenerator(llm_client, repo)
        self.file_generator = FileGenerator(llm_client, repo)
        self.synthesis_generator = SynthesisGenerator(llm_client)

        # Workflow discovery helper
        self.workflow_discovery = WorkflowDiscovery()

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
                WHERE target = ? AND created_at > ?
                """,
                (target, generated_at),
            )
            row = cursor.fetchone()
            return row[0] > 0 if row else False
        except Exception:
            return False

    def _should_regenerate_file(
        self, file_path: str, content: str, file_hashes: dict[str, str]
    ) -> tuple[bool, str]:
        """Check if a file page needs regeneration.

        Args:
            file_path: Path to the source file.
            content: Content of the source file.
            file_hashes: Dict to store computed hashes (modified in place).

        Returns:
            Tuple of (should_regenerate, content_hash).
        """
        content_hash = compute_content_hash(content)
        file_hashes[file_path] = content_hash

        existing = self._get_existing_page_info(file_path, "file")
        if not existing:
            return True, content_hash

        # Check if content changed
        if existing.get("source_hash") != content_hash:
            return True, content_hash

        # Check if there are new notes
        if self._has_new_notes(file_path, existing.get("generated_at")):
            return True, content_hash

        return False, content_hash

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
            (f.split("/")[-1], file_hashes.get(f, ""))
            for f in dir_files
            if f in file_hashes
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
    ) -> str:
        """Run the complete generation pipeline.

        Pipeline order: Analysis → Files → Directories → Synthesis → Architecture → Overview → Workflows

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
            Job ID for the generation run.
        """
        job_id = str(uuid.uuid4())

        # Ensure wiki and meta directories exist
        self.wiki_path.mkdir(parents=True, exist_ok=True)
        self.meta_path.mkdir(parents=True, exist_ok=True)

        # Phase 1: Analysis (with progress tracking for file parsing)
        analysis = await self._run_analysis(progress_callback)

        # Phase 2: Files (run before directories to compute content hashes and collect summaries)
        file_pages, file_hashes, file_summaries = await self._run_files(
            analysis, progress_callback
        )
        for page in file_pages:
            await self._save_page(page)

        # Track if any files were regenerated (for cascade)
        files_regenerated = len(file_pages) > 0

        # Phase 3: Directories (uses file_hashes for signature computation and file_summaries for context)
        directory_pages, directory_summaries = await self._run_directories(
            analysis, file_hashes, progress_callback, file_summaries=file_summaries
        )
        for page in directory_pages:
            await self._save_page(page)

        # Track if any directories were regenerated (for cascade)
        directories_regenerated = len(directory_pages) > 0

        # Phase 4: Synthesis (combine file and directory summaries into SynthesisMap)
        # Cascade: regenerate synthesis if any files or directories were regenerated
        should_regenerate_synthesis = self._should_regenerate_synthesis(
            files_regenerated, directories_regenerated
        )

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
            synthesis_map = await self._run_synthesis(file_summaries, directory_summaries)
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
            from oya.generation.synthesis import load_synthesis_map
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
                synthesis_map = await self._run_synthesis(file_summaries, directory_summaries)

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
            await self._save_page(architecture_page)
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
            await self._save_page(overview_page)
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
            workflow_pages = await self._run_workflows(analysis, progress_callback)
            for page in workflow_pages:
                await self._save_page(page)

        return job_id

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
            file_imports, and parse_errors.
        """
        # Use FileFilter to respect .oyaignore and default exclusions
        file_filter = FileFilter(self.repo.path)
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
                    for symbol in result.file.symbols:
                        symbol.metadata["file"] = file_path
                        all_symbols.append(symbol)
                else:
                    # Parse failed - try fallback for partial recovery
                    parse_errors.append({
                        "file": file_path,
                        "error": result.error or "Unknown parse error",
                        "recovered": True,
                    })
                    fallback_result = self._fallback_parser.parse(Path(file_path), content)
                    if fallback_result.ok and fallback_result.file:
                        file_imports[file_path] = fallback_result.file.imports
                        for symbol in fallback_result.file.symbols:
                            symbol.metadata["file"] = file_path
                            all_symbols.append(symbol)

            except Exception as e:
                # File read error - track but continue
                parse_errors.append({
                    "file": file_path,
                    "error": str(e),
                    "recovered": False,
                })

            # Emit progress (configurable interval)
            if (idx + 1) % PROGRESS_REPORT_INTERVAL == 0 or idx == total_files - 1:
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

        return await self.overview_generator.generate(
            readme_content=readme_content,
            file_tree=analysis["file_tree"],
            package_info=package_info,
            synthesis_map=synthesis_map,
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
                import tomllib
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

        Args:
            analysis: Analysis results.
            synthesis_map: Optional SynthesisMap for richer architecture context.

        Returns:
            Generated architecture page.
        """
        # Extract dependencies from package info
        package_info = self._extract_package_info(analysis["file_contents"])
        dependencies = package_info.get("dependencies", [])

        # If we have a synthesis map, use it as primary context
        if synthesis_map is not None:
            return await self.architecture_generator.generate(
                file_tree=analysis["file_tree"],
                dependencies=dependencies,
                synthesis_map=synthesis_map,
            )

        # Legacy mode: use key symbols (convert ParsedSymbol to dict)
        key_symbols = [
            self._symbol_to_dict(s) for s in analysis["symbols"]
            if s.symbol_type.value in ("class", "function", "method")
        ][:50]  # Limit to top 50

        return await self.architecture_generator.generate(
            file_tree=analysis["file_tree"],
            key_symbols=key_symbols,
            dependencies=dependencies,
        )

    async def _run_workflows(
        self,
        analysis: dict,
        progress_callback: ProgressCallback | None = None,
    ) -> list[GeneratedPage]:
        """Run workflow generation phase.

        Args:
            analysis: Analysis results.
            progress_callback: Optional async callback for progress updates.

        Returns:
            List of generated workflow pages.
        """
        pages = []

        # Discover entry points (workflows.py now accepts ParsedSymbol objects directly)
        entry_points = self.workflow_discovery.find_entry_points(analysis["symbols"])

        # Group into workflows
        workflows = self.workflow_discovery.group_into_workflows(entry_points)

        # Limit to 10 workflows
        workflows_to_generate = workflows[:10]
        total_workflows = len(workflows_to_generate)

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

        # Generate page for each workflow
        for idx, workflow in enumerate(workflows_to_generate):
            # Gather code context for the workflow
            code_context = ""
            for related_file in workflow.related_files:
                if related_file in analysis["file_contents"]:
                    content = analysis["file_contents"][related_file]
                    code_context += f"\n### {related_file}\n```\n{content[:2000]}\n```\n"

            page = await self.workflow_generator.generate(
                workflow=workflow,
                code_context=code_context,
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
    ) -> SynthesisMap:
        """Run synthesis phase to combine summaries into a SynthesisMap.

        Args:
            file_summaries: List of FileSummary objects from files phase.
            directory_summaries: List of DirectorySummary objects from directories phase.

        Returns:
            SynthesisMap containing aggregated codebase understanding.
        """
        # Generate the synthesis map
        synthesis_map = await self.synthesis_generator.generate(
            file_summaries=file_summaries,
            directory_summaries=directory_summaries,
        )

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
        """Run directory generation phase with parallel processing and incremental support.

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
            if len(parts) > 1:
                parent_dir = "/".join(parts[:-1])
                if parent_dir in directories:
                    directories[parent_dir].append(file_path)

        # Check which directories need regeneration
        dirs_to_generate: list[tuple[str, str]] = []  # (dir_path, signature_hash)
        skipped_count = 0

        for dir_path in sorted(directories.keys()):
            dir_files = directories[dir_path]
            should_regen, signature_hash = self._should_regenerate_directory(
                dir_path, dir_files, file_hashes
            )
            if should_regen:
                dirs_to_generate.append((dir_path, signature_hash))
            else:
                skipped_count += 1

        # Total includes both generated and skipped for accurate progress display
        total_dirs = len(dirs_to_generate) + skipped_count

        # Emit initial progress with total count
        await self._emit_progress(
            progress_callback,
            GenerationProgress(
                phase=GenerationPhase.DIRECTORIES,
                step=skipped_count,
                total_steps=total_dirs,
                message=f"Generating directory pages ({skipped_count} unchanged, 0/{len(dirs_to_generate)} generating)...",
            ),
        )

        # Helper to generate a single directory page with hash and return both page and summary
        async def generate_dir_page(
            dir_path: str, signature_hash: str
        ) -> tuple[GeneratedPage, DirectorySummary]:
            dir_files = [
                f for f in analysis["files"]
                if f.startswith(dir_path + "/") and "/" not in f[len(dir_path) + 1:]
            ]
            # Filter symbols by file path and convert to dicts for generator
            dir_symbols = [
                self._symbol_to_dict(s) for s in analysis["symbols"]
                if s.metadata.get("file", "").startswith(dir_path + "/")
            ]
            # Get file summaries for files in this directory
            dir_file_summaries = [
                file_summary_lookup[f]
                for f in dir_files
                if f in file_summary_lookup
            ]
            # DirectoryGenerator.generate() returns (GeneratedPage, DirectorySummary)
            page, directory_summary = await self.directory_generator.generate(
                directory_path=dir_path,
                file_list=dir_files,
                symbols=dir_symbols,
                architecture_context="",
                file_summaries=dir_file_summaries,
            )
            # Add signature hash to the page for storage
            page.source_hash = signature_hash
            return page, directory_summary

        # Process directories in parallel batches
        completed = skipped_count
        for batch in batched(dirs_to_generate, self.parallel_limit):
            # Process batch concurrently
            batch_results = await asyncio.gather(*[
                generate_dir_page(dir_path, signature_hash)
                for dir_path, signature_hash in batch
            ])
            # Unpack results into pages and summaries
            for page, summary in batch_results:
                pages.append(page)
                directory_summaries.append(summary)

            # Report progress after batch completes
            completed += len(batch)
            generated_so_far = completed - skipped_count
            await self._emit_progress(
                progress_callback,
                GenerationProgress(
                    phase=GenerationPhase.DIRECTORIES,
                    step=completed,
                    total_steps=total_dirs,
                    message=f"Generated {generated_so_far}/{len(dirs_to_generate)} directories ({skipped_count} unchanged)...",
                ),
            )

        return pages, directory_summaries

    async def _run_files(
        self,
        analysis: dict,
        progress_callback: ProgressCallback | None = None,
    ) -> tuple[list[GeneratedPage], dict[str, str], list[FileSummary]]:
        """Run file generation phase with parallel processing and incremental support.

        Args:
            analysis: Analysis results.
            progress_callback: Optional async callback for progress updates.

        Returns:
            Tuple of (list of generated file pages, dict of file_path to content_hash, list of FileSummaries).
        """
        pages: list[GeneratedPage] = []
        file_hashes: dict[str, str] = {}
        file_summaries: list[FileSummary] = []

        # Generate page for each source file
        # Use denylist approach: document everything EXCEPT known non-code files
        # This ensures we support any programming language without maintaining an allowlist
        non_code_extensions = {
            # Documentation
            ".md", ".rst", ".txt", ".adoc", ".asciidoc",
            # Data/config formats
            ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf",
            ".xml", ".csv", ".tsv",
            # Lock files
            ".lock",
            # Images (shouldn't be here, but just in case binary detection missed them)
            ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".webp",
            # Other non-code
            ".log", ".pid", ".env", ".env.example",
        }
        non_code_names = {
            # Common non-code files (case-insensitive matching below)
            "readme", "readme.md", "readme.rst", "readme.txt",
            "license", "license.md", "license.txt", "copying",
            "changelog", "changelog.md", "changes", "changes.md", "history.md",
            "contributing", "contributing.md",
            "authors", "authors.md", "contributors",
            "makefile", "dockerfile", "vagrantfile",
            "gemfile", "gemfile.lock",
            "package.json", "package-lock.json",
            "composer.json", "composer.lock",
            "cargo.toml", "cargo.lock",
            "pyproject.toml", "poetry.lock", "pipfile", "pipfile.lock",
            "requirements.txt", "setup.py", "setup.cfg",
            ".gitignore", ".gitattributes", ".dockerignore",
            ".editorconfig", ".prettierrc", ".eslintrc",
        }

        # Filter to source files and check which need regeneration
        files_to_generate: list[tuple[str, str]] = []  # (file_path, content_hash)
        skipped_count = 0

        for file_path in analysis["files"]:
            ext = Path(file_path).suffix.lower()
            filename = Path(file_path).name.lower()

            # Skip known non-code files
            if ext in non_code_extensions or filename in non_code_names:
                continue

            # Process all other text files as source code
            content = analysis["file_contents"].get(file_path, "")
            if content:
                should_regen, content_hash = self._should_regenerate_file(
                    file_path, content, file_hashes
                )
                if should_regen:
                    files_to_generate.append((file_path, content_hash))
                else:
                    skipped_count += 1

        # Total includes both generated and skipped for accurate progress display
        total_files = len(files_to_generate) + skipped_count

        # Emit initial progress with total count
        await self._emit_progress(
            progress_callback,
            GenerationProgress(
                phase=GenerationPhase.FILES,
                step=skipped_count,
                total_steps=total_files,
                message=f"Generating file pages ({skipped_count} unchanged, 0/{len(files_to_generate)} generating)...",
            ),
        )

        # Helper to generate a single file page with hash and return both page and summary
        async def generate_file_page(
            file_path: str, content_hash: str
        ) -> tuple[GeneratedPage, FileSummary]:
            content = analysis["file_contents"].get(file_path, "")
            ext = Path(file_path).suffix.lower()
            # Filter symbols by file path and convert to dicts for generator
            file_symbols = [
                self._symbol_to_dict(s) for s in analysis["symbols"]
                if s.metadata.get("file") == file_path
            ]
            imports = self._extract_imports(content, ext)
            # FileGenerator.generate() returns (GeneratedPage, FileSummary)
            page, file_summary = await self.file_generator.generate(
                file_path=file_path,
                content=content,
                symbols=file_symbols,
                imports=imports,
                architecture_summary="",
            )
            # Add source hash to the page for storage
            page.source_hash = content_hash
            return page, file_summary

        # Process files in parallel batches
        completed = skipped_count
        for batch in batched(files_to_generate, self.parallel_limit):
            # Process batch concurrently
            batch_results = await asyncio.gather(*[
                generate_file_page(file_path, content_hash)
                for file_path, content_hash in batch
            ])
            # Unpack results into pages and summaries
            for page, summary in batch_results:
                pages.append(page)
                file_summaries.append(summary)

            # Report progress after batch completes
            completed += len(batch)
            generated_so_far = completed - skipped_count
            await self._emit_progress(
                progress_callback,
                GenerationProgress(
                    phase=GenerationPhase.FILES,
                    step=completed,
                    total_steps=total_files,
                    message=f"Generated {generated_so_far}/{len(files_to_generate)} files ({skipped_count} unchanged)...",
                ),
            )

        return pages, file_hashes, file_summaries

    def _extract_imports(self, content: str, ext: str) -> list[str]:
        """Extract import statements from file content.

        Args:
            content: File content.
            ext: File extension.

        Returns:
            List of import statements.
        """
        imports = []
        lines = content.split("\n")

        for line in lines[:50]:  # Only check first 50 lines
            line = line.strip()
            if ext == ".py":
                if line.startswith("import ") or line.startswith("from "):
                    imports.append(line)
            elif ext in {".js", ".ts", ".tsx", ".jsx"}:
                if line.startswith("import ") or line.startswith("const ") and "require(" in line:
                    imports.append(line)
            elif ext == ".java":
                if line.startswith("import "):
                    imports.append(line)

        return imports

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
