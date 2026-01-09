# backend/src/oya/generation/orchestrator.py
"""Generation orchestrator for wiki pipeline."""

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
from oya.generation.workflows import WorkflowDiscovery, WorkflowGenerator
from oya.parsing.registry import ParserRegistry
from oya.repo.file_filter import FileFilter


class GenerationPhase(Enum):
    """Phases of wiki generation."""

    ANALYSIS = "analysis"
    OVERVIEW = "overview"
    ARCHITECTURE = "architecture"
    WORKFLOWS = "workflows"
    DIRECTORIES = "directories"
    FILES = "files"


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

    Coordinates all generation phases in sequence:
    Analysis -> Overview -> Architecture -> Workflows -> Directories -> Files
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
        self.parallel_limit = parallel_limit

        # Initialize generators
        self.overview_generator = OverviewGenerator(llm_client, repo)
        self.architecture_generator = ArchitectureGenerator(llm_client, repo)
        self.workflow_generator = WorkflowGenerator(llm_client, repo)
        self.directory_generator = DirectoryGenerator(llm_client, repo)
        self.file_generator = FileGenerator(llm_client, repo)

        # Workflow discovery helper
        self.workflow_discovery = WorkflowDiscovery()

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

    async def run(
        self,
        progress_callback: ProgressCallback | None = None,
    ) -> str:
        """Run the complete generation pipeline.

        Args:
            progress_callback: Optional async callback for progress updates.

        Returns:
            Job ID for the generation run.
        """
        job_id = str(uuid.uuid4())

        # Ensure wiki directory exists
        self.wiki_path.mkdir(parents=True, exist_ok=True)

        # Phase 1: Analysis
        await self._emit_progress(
            progress_callback,
            GenerationProgress(
                phase=GenerationPhase.ANALYSIS,
                message="Analyzing repository...",
            ),
        )
        analysis = await self._run_analysis()

        # Phase 2: Overview
        await self._emit_progress(
            progress_callback,
            GenerationProgress(
                phase=GenerationPhase.OVERVIEW,
                message="Generating overview page...",
            ),
        )
        overview_page = await self._run_overview(analysis)
        await self._save_page(overview_page)

        # Phase 3: Architecture
        await self._emit_progress(
            progress_callback,
            GenerationProgress(
                phase=GenerationPhase.ARCHITECTURE,
                message="Generating architecture page...",
            ),
        )
        architecture_page = await self._run_architecture(analysis)
        await self._save_page(architecture_page)

        # Phase 4: Workflows
        await self._emit_progress(
            progress_callback,
            GenerationProgress(
                phase=GenerationPhase.WORKFLOWS,
                message="Generating workflow pages...",
            ),
        )
        workflow_pages = await self._run_workflows(analysis)
        for page in workflow_pages:
            await self._save_page(page)

        # Phase 5: Files (run before directories to compute content hashes)
        file_pages, file_hashes = await self._run_files(analysis, progress_callback)
        for page in file_pages:
            await self._save_page(page)

        # Phase 6: Directories (uses file_hashes for signature computation)
        directory_pages = await self._run_directories(
            analysis, file_hashes, progress_callback
        )
        for page in directory_pages:
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

    async def _run_analysis(self) -> dict:
        """Run analysis phase.

        Returns:
            Analysis results with files, symbols, file_tree, file_contents.
        """
        # Use FileFilter to respect .oyaignore and default exclusions
        file_filter = FileFilter(self.repo.path)
        files = file_filter.get_files()
        symbols: list[dict] = []
        file_contents: dict[str, str] = {}

        # Build file tree
        file_tree = self._build_file_tree(files)

        # Parse each file
        for file_path in files:
            try:
                full_path = self.repo.path / file_path
                if full_path.exists() and full_path.is_file():
                    content = full_path.read_text(encoding="utf-8", errors="ignore")
                    file_contents[file_path] = content

                    # Parse for symbols
                    result = self.parser_registry.parse_file(
                        Path(file_path), content
                    )

                    for symbol in result.symbols:
                        symbol_dict = {
                            "name": symbol.name,
                            "type": symbol.type.value,
                            "file": file_path,
                            "line": symbol.line,
                            "decorators": symbol.decorators,
                        }
                        symbols.append(symbol_dict)
            except Exception:
                # Skip files that can't be parsed
                pass

        return {
            "files": files,
            "symbols": symbols,
            "file_tree": file_tree,
            "file_contents": file_contents,
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

    async def _run_overview(self, analysis: dict) -> GeneratedPage:
        """Run overview generation phase.

        Args:
            analysis: Analysis results.

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
        )

    def _extract_package_info(self, file_contents: dict[str, str]) -> dict:
        """Extract package information from project files.

        Args:
            file_contents: Mapping of file paths to contents.

        Returns:
            Package info dictionary.
        """
        package_info = {}

        # Try package.json
        if "package.json" in file_contents:
            try:
                import json
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

    async def _run_architecture(self, analysis: dict) -> GeneratedPage:
        """Run architecture generation phase.

        Args:
            analysis: Analysis results.

        Returns:
            Generated architecture page.
        """
        # Extract key symbols (classes and functions)
        key_symbols = [
            s for s in analysis["symbols"]
            if s.get("type") in ("class", "function", "method")
        ][:50]  # Limit to top 50

        # Extract dependencies from package info
        package_info = self._extract_package_info(analysis["file_contents"])
        dependencies = package_info.get("dependencies", [])

        return await self.architecture_generator.generate(
            file_tree=analysis["file_tree"],
            key_symbols=key_symbols,
            dependencies=dependencies,
        )

    async def _run_workflows(self, analysis: dict) -> list[GeneratedPage]:
        """Run workflow generation phase.

        Args:
            analysis: Analysis results.

        Returns:
            List of generated workflow pages.
        """
        pages = []

        # Discover entry points
        entry_points = self.workflow_discovery.find_entry_points(analysis["symbols"])

        # Group into workflows
        workflows = self.workflow_discovery.group_into_workflows(entry_points)

        # Generate page for each workflow
        for workflow in workflows[:10]:  # Limit to 10 workflows
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

        return pages

    async def _run_directories(
        self,
        analysis: dict,
        file_hashes: dict[str, str],
        progress_callback: ProgressCallback | None = None,
    ) -> list[GeneratedPage]:
        """Run directory generation phase with parallel processing and incremental support.

        Args:
            analysis: Analysis results.
            file_hashes: Dict of file_path to content_hash from files phase.
            progress_callback: Optional async callback for progress updates.

        Returns:
            List of generated directory pages.
        """
        pages = []

        # Get unique directories and their direct files
        directories: dict[str, list[str]] = {}
        for file_path in analysis["files"]:
            parts = file_path.split("/")
            for i in range(1, len(parts)):
                dir_path = "/".join(parts[:i])
                if dir_path not in directories:
                    directories[dir_path] = []
                # Only add files directly in this directory (not in subdirs)
                if i == len(parts) - 1 or (i < len(parts) - 1 and parts[i] != parts[-1]):
                    continue

        # Re-compute direct files for each directory
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

        # Helper to generate a single directory page with hash
        async def generate_dir_page(dir_path: str, signature_hash: str) -> GeneratedPage:
            dir_files = [
                f for f in analysis["files"]
                if f.startswith(dir_path + "/") and "/" not in f[len(dir_path) + 1:]
            ]
            dir_symbols = [
                s for s in analysis["symbols"]
                if s.get("file", "").startswith(dir_path + "/")
            ]
            # DirectoryGenerator.generate() returns (GeneratedPage, DirectorySummary)
            page, _directory_summary = await self.directory_generator.generate(
                directory_path=dir_path,
                file_list=dir_files,
                symbols=dir_symbols,
                architecture_context="",
            )
            # Add signature hash to the page for storage
            page.source_hash = signature_hash
            return page

        # Process directories in parallel batches
        completed = skipped_count
        for batch in batched(dirs_to_generate, self.parallel_limit):
            # Process batch concurrently
            batch_pages = await asyncio.gather(*[
                generate_dir_page(dir_path, signature_hash)
                for dir_path, signature_hash in batch
            ])
            pages.extend(batch_pages)

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

        return pages

    async def _run_files(
        self,
        analysis: dict,
        progress_callback: ProgressCallback | None = None,
    ) -> tuple[list[GeneratedPage], dict[str, str]]:
        """Run file generation phase with parallel processing and incremental support.

        Args:
            analysis: Analysis results.
            progress_callback: Optional async callback for progress updates.

        Returns:
            Tuple of (list of generated file pages, dict of file_path to content_hash).
        """
        pages = []
        file_hashes: dict[str, str] = {}

        # Generate page for each code file
        code_extensions = {".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".go", ".rs"}

        # Filter to code files and check which need regeneration
        files_to_generate: list[tuple[str, str]] = []  # (file_path, content_hash)
        skipped_count = 0

        for file_path in analysis["files"]:
            ext = Path(file_path).suffix.lower()
            if ext in code_extensions:
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

        # Helper to generate a single file page with hash
        async def generate_file_page(file_path: str, content_hash: str) -> GeneratedPage:
            content = analysis["file_contents"].get(file_path, "")
            ext = Path(file_path).suffix.lower()
            file_symbols = [
                s for s in analysis["symbols"]
                if s.get("file") == file_path
            ]
            imports = self._extract_imports(content, ext)
            # FileGenerator.generate() returns (GeneratedPage, FileSummary)
            page, _file_summary = await self.file_generator.generate(
                file_path=file_path,
                content=content,
                symbols=file_symbols,
                imports=imports,
                architecture_summary="",
            )
            # Add source hash to the page for storage
            page.source_hash = content_hash
            return page

        # Process files in parallel batches
        completed = skipped_count
        for batch in batched(files_to_generate, self.parallel_limit):
            # Process batch concurrently
            batch_pages = await asyncio.gather(*[
                generate_file_page(file_path, content_hash)
                for file_path, content_hash in batch
            ])
            pages.extend(batch_pages)

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

        return pages, file_hashes

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
