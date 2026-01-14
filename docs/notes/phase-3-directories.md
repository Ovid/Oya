# Phase 3: Directory Documentation in the Oya Generation Pipeline

## Overview

Phase 3 (Directory Documentation) is the third phase in Oya's 8-phase wiki generation pipeline. It runs after Phase 2 (Files) and before Phase 4 (Synthesis), generating documentation for each directory in the codebase while extracting structured `DirectorySummary` objects. [1](#8-0) 

## Main Components

### 1. **GenerationOrchestrator._run_directories()**
The orchestration method that coordinates the entire directory generation phase, handling incremental regeneration, parallel processing, and progress tracking. [2](#8-1) 

### 2. **DirectoryGenerator**
The core generator class that creates directory documentation by calling the LLM with a structured prompt. [3](#8-2) 

The generator's `generate()` method accepts file summaries from Phase 2 as context and returns both a `GeneratedPage` and a `DirectorySummary`. [4](#8-3) 

### 3. **SummaryParser**
Extracts structured `DirectorySummary` objects from the YAML blocks in LLM-generated markdown. [5](#8-4) 

### 4. **DIRECTORY_TEMPLATE Prompt**
The LLM prompt template that instructs the model to generate directory documentation with a YAML summary block. [6](#8-5) 

## Responsibilities

### Directory Discovery
Directories are extracted from the file list using a shared utility function that ensures consistency with Phase 1's analysis: [7](#8-6) 

### Incremental Regeneration via Directory Signatures
Phase 3 implements smart change detection using directory signatures computed from direct file content hashes (not recursive): [8](#8-7) 

The signature only changes when direct files are added, removed, or modified, preventing unnecessary regeneration when nested subdirectories change: [9](#8-8) 

### FileSummary Context Integration
A key innovation of Phase 3 is using `FileSummary` objects from Phase 2 as context. The orchestrator builds a lookup and passes relevant file summaries to the directory generator: [10](#8-9) [11](#8-10) 

These summaries are formatted into the prompt to provide structured information about each file's purpose, layer, and key abstractions: [12](#8-11) 

### Parallel Batch Processing
Directories are processed in parallel batches (default: 10 concurrent requests) to optimize throughput while avoiding API rate limits: [13](#8-12) 

### YAML Summary Extraction
The LLM is instructed to prepend a YAML block containing structured directory information. The parser extracts this block and converts it to a `DirectorySummary` object: [14](#8-13) 

### Fallback Handling
If YAML parsing fails or produces invalid data, the system returns a fallback summary with safe defaults, ensuring the pipeline continues without exceptions: [15](#8-14) 

## Data Structures Produced

### DirectorySummary
The primary structured output containing: [16](#8-15) 

This data model supports serialization for storage and includes methods for JSON conversion: [17](#8-16) 

### GeneratedPage
Each directory produces a `GeneratedPage` object with the markdown content, metadata, and a signature hash for incremental regeneration: [18](#8-17) 

### Return Tuple
Phase 3 returns both the generated pages and the extracted summaries for use in Phase 4: [19](#8-18) 

## Pipeline Integration

### Input from Phase 2
Phase 3 receives file hashes and file summaries from Phase 2, enabling both incremental regeneration and enriched context: [20](#8-19) 

### Output to Phase 4
The extracted `DirectorySummary` objects are passed to Phase 4 (Synthesis) along with file summaries to create a unified `SynthesisMap`: [21](#8-20) 

### Cascade Regeneration
If any directories are regenerated, the synthesis phase must also regenerate to maintain consistency: [22](#8-21) 

## Strengths

1. **Efficient Incremental Regeneration**: Directory signatures based on direct file hashes minimize unnecessary LLM calls, significantly reducing token costs during regeneration.

2. **Rich Contextual Information**: Integration of `FileSummary` objects provides the LLM with structured context about each file's purpose and architecture, leading to more accurate directory documentation.

3. **Resilient YAML Parsing**: Fallback mechanisms ensure the pipeline continues even when LLM output is malformed, preventing cascading failures.

4. **Parallel Processing**: Batched concurrent requests optimize throughput while respecting API rate limits.

5. **Bottom-Up Architecture**: Generating directory documentation after file documentation ensures directories can accurately reflect the actual contents based on file-level analysis.

6. **Structured Output**: `DirectorySummary` objects provide machine-readable metadata that enables sophisticated synthesis in Phase 4.

## Weaknesses

1. **Non-Recursive Signatures**: Directory signatures only consider direct files, not nested subdirectories. Changes in deeply nested files won't trigger parent directory regeneration unless those files are direct children.

2. **LLM Dependency for Structure**: The quality of extracted summaries depends on the LLM correctly following YAML formatting instructions. While fallbacks exist, malformed output reduces the quality of synthesis inputs.

3. **Limited Architectural Context**: The `architecture_context` parameter is currently passed as an empty string in the orchestrator, meaning directories don't receive higher-level architectural guidance during generation. [23](#8-22) 

4. **Fixed Batch Size**: The parallel limit is set at initialization and cannot be dynamically adjusted based on API response times or rate limiting.

5. **No Cross-Directory Analysis**: Each directory is generated independently without awareness of sibling or parent directories, potentially missing important relationships in the module hierarchy.

## Notes

Phase 3 is a critical bridge between file-level analysis and codebase-wide synthesis. Its use of `FileSummary` objects as context represents a significant architectural improvement over generating directory documentation from raw file lists alone. The incremental regeneration system, while not perfect (non-recursive signatures), provides substantial efficiency gains for large codebases. The structured `DirectorySummary` outputs enable Phase 4 (Synthesis) to build a comprehensive architectural understanding of the entire codebase.

### Citations

**File:** backend/src/oya/generation/orchestrator.py (L2-14)
```python
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
```

**File:** backend/src/oya/generation/orchestrator.py (L100-112)
```python
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
```

**File:** backend/src/oya/generation/orchestrator.py (L262-295)
```python
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
```

**File:** backend/src/oya/generation/orchestrator.py (L297-325)
```python
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
```

**File:** backend/src/oya/generation/orchestrator.py (L370-373)
```python
        # Phase 3: Directories (uses file_hashes for signature computation and file_summaries for context)
        directory_pages, directory_summaries = await self._run_directories(
            analysis, file_hashes, progress_callback, file_summaries=file_summaries
        )
```

**File:** backend/src/oya/generation/orchestrator.py (L767-790)
```python
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
```

**File:** backend/src/oya/generation/orchestrator.py (L792-798)
```python
    async def _run_directories(
        self,
        analysis: dict,
        file_hashes: dict[str, str],
        progress_callback: ProgressCallback | None = None,
        file_summaries: list[FileSummary] | None = None,
    ) -> tuple[list[GeneratedPage], list[DirectorySummary]]:
```

**File:** backend/src/oya/generation/orchestrator.py (L814-817)
```python
        # Build a lookup of file summaries by file path for quick access
        file_summary_lookup: dict[str, FileSummary] = {
            fs.file_path: fs for fs in file_summaries if isinstance(fs, FileSummary)
        }
```

**File:** backend/src/oya/generation/orchestrator.py (L819-831)
```python
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
```

**File:** backend/src/oya/generation/orchestrator.py (L873-886)
```python
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
```

**File:** backend/src/oya/generation/orchestrator.py (L891-915)
```python
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
```

**File:** backend/src/oya/generation/orchestrator.py (L917-917)
```python
        return pages, directory_summaries
```

**File:** backend/src/oya/generation/directory.py (L14-27)
```python
class DirectoryGenerator:
    """Generates directory documentation pages."""

    def __init__(self, llm_client, repo):
        """Initialize the directory generator.

        Args:
            llm_client: LLM client for generation.
            repo: Repository wrapper for context.
        """
        self.llm_client = llm_client
        self.repo = repo
        self._parser = SummaryParser()

```

**File:** backend/src/oya/generation/directory.py (L28-47)
```python
    async def generate(
        self,
        directory_path: str,
        file_list: list[str],
        symbols: list[dict],
        architecture_context: str,
        file_summaries: list[FileSummary] | None = None,
    ) -> tuple[GeneratedPage, DirectorySummary]:
        """Generate directory documentation and extract summary.

        Args:
            directory_path: Path to the directory.
            file_list: List of files in the directory.
            symbols: List of symbol dictionaries defined in the directory.
            architecture_context: Summary of how this directory fits in the architecture.
            file_summaries: Optional list of FileSummary objects for files in the directory.

        Returns:
            A tuple of (GeneratedPage, DirectorySummary).
        """
```

**File:** backend/src/oya/generation/directory.py (L64-77)
```python
        # Parse the DirectorySummary from the LLM output
        clean_content, summary = self._parser.parse_directory_summary(content, directory_path)

        word_count = len(clean_content.split())
        slug = path_to_slug(directory_path, include_extension=False)

        page = GeneratedPage(
            content=clean_content,
            page_type="directory",
            path=f"directories/{slug}.md",
            word_count=word_count,
            target=directory_path,
        )

```

**File:** backend/src/oya/generation/summaries.py (L106-123)
```python
@dataclass
class DirectorySummary:
    """Structured summary extracted from directory documentation.

    Captures the essential information about a directory/module including its purpose,
    contained files, and role in the overall system architecture.

    Attributes:
        directory_path: Path to the directory relative to repository root.
        purpose: One-sentence description of what the directory/module is responsible for.
        contains: List of files contained in the directory.
        role_in_system: Description of how this directory fits into the overall architecture.
    """

    directory_path: str
    purpose: str
    contains: list[str] = field(default_factory=list)
    role_in_system: str = ""
```

**File:** backend/src/oya/generation/summaries.py (L125-153)
```python
    def to_dict(self) -> dict[str, Any]:
        """Serialize the DirectorySummary to a dictionary.

        Returns:
            Dictionary representation of the DirectorySummary for JSON storage.
        """
        return {
            "directory_path": self.directory_path,
            "purpose": self.purpose,
            "contains": self.contains,
            "role_in_system": self.role_in_system,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DirectorySummary":
        """Deserialize a DirectorySummary from a dictionary.

        Args:
            data: Dictionary representation of a DirectorySummary.

        Returns:
            A new DirectorySummary instance.
        """
        return cls(
            directory_path=data.get("directory_path", ""),
            purpose=data.get("purpose", "Unknown"),
            contains=data.get("contains", []),
            role_in_system=data.get("role_in_system", ""),
        )
```

**File:** backend/src/oya/generation/summaries.py (L406-422)
```python
    def parse_directory_summary(
        self, markdown: str, directory_path: str
    ) -> tuple[str, DirectorySummary]:
        """Parse Directory_Summary from markdown, return (clean_markdown, summary).

        Extracts the YAML block containing directory_summary data from the markdown,
        parses it into a DirectorySummary object, and returns the markdown with the
        YAML block removed.

        Args:
            markdown: The full markdown content potentially containing a YAML block.
            directory_path: The path to the directory being summarized.

        Returns:
            A tuple of (clean_markdown, DirectorySummary) where clean_markdown has
            the YAML block removed.
        """
```

**File:** backend/src/oya/generation/summaries.py (L423-445)
```python
        yaml_content, clean_markdown = self._extract_yaml_block(markdown)

        if yaml_content is None:
            return markdown, self._fallback_directory_summary(directory_path)

        data = self._parse_yaml_safely(yaml_content)

        if data is None or "directory_summary" not in data:
            return markdown, self._fallback_directory_summary(directory_path)

        summary_data = data["directory_summary"]

        if not isinstance(summary_data, dict):
            return markdown, self._fallback_directory_summary(directory_path)

        summary = DirectorySummary(
            directory_path=directory_path,
            purpose=summary_data.get("purpose", "Unknown"),
            contains=self._ensure_list(summary_data.get("contains", [])),
            role_in_system=summary_data.get("role_in_system", ""),
        )

        return clean_markdown, summary
```

**File:** backend/src/oya/generation/summaries.py (L447-457)
```python
    def _fallback_directory_summary(self, directory_path: str) -> DirectorySummary:
        """Create a fallback DirectorySummary with default values.

        Used when YAML parsing fails or no YAML block is found.
        """
        return DirectorySummary(
            directory_path=directory_path,
            purpose="Unknown",
            contains=[],
            role_in_system="",
        )
```

**File:** backend/src/oya/generation/prompts.py (L270-308)
```python
DIRECTORY_TEMPLATE = PromptTemplate(
    """Generate a directory documentation page for "{directory_path}" in "{repo_name}".

## Files in Directory
{file_list}

## File Summaries
{file_summaries}

## Symbols Defined
{symbols}

## Architecture Context
{architecture_context}

---

IMPORTANT: You MUST start your response with a YAML summary block in the following format:

```
---
directory_summary:
  purpose: "One-sentence description of what this directory/module is responsible for"
  contains:
    - "file1.py"
    - "file2.py"
  role_in_system: "Description of how this directory fits into the overall architecture"
---
```

After the YAML block, create directory documentation that includes:
1. **Directory Purpose**: What this directory contains and why
2. **File Overview**: Brief description of each file
3. **Key Components**: Important classes, functions, or modules
4. **Dependencies**: What this directory depends on and what depends on it
5. **Usage Examples**: How to use the components in this directory

Format the output as clean Markdown suitable for a wiki page."""
)
```

**File:** backend/src/oya/generation/prompts.py (L530-558)
```python
def _format_file_summaries(file_summaries: list[Any]) -> str:
    """Format a list of FileSummaries for inclusion in a prompt.

    Args:
        file_summaries: List of FileSummary objects.

    Returns:
        Formatted string representation of file summaries.
    """
    if not file_summaries:
        return "No file summaries available."

    lines = []
    for summary in file_summaries:
        lines.append(f"### {summary.file_path}")
        lines.append(f"- **Purpose**: {summary.purpose}")
        lines.append(f"- **Layer**: {summary.layer}")
        if summary.key_abstractions:
            abstractions = ", ".join(summary.key_abstractions)
            lines.append(f"- **Key Abstractions**: {abstractions}")
        if summary.internal_deps:
            deps = ", ".join(summary.internal_deps)
            lines.append(f"- **Internal Dependencies**: {deps}")
        if summary.external_deps:
            ext_deps = ", ".join(summary.external_deps)
            lines.append(f"- **External Dependencies**: {ext_deps}")
        lines.append("")

    return "\n".join(lines)
```

