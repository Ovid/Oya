# Phase 2 (File Documentation) in the Oya Generation Pipeline

## What It Does

Phase 2 is the **Files phase** of the bottom-up generation pipeline, responsible for generating documentation for individual source files and extracting structured metadata. [1](#7-0)  It executes after Phase 1 (Analysis) and before Phase 3 (Directories), processing each source file in the repository to create detailed documentation pages and structured `FileSummary` objects. [2](#7-1) 

## How It Works

### Pipeline Flow

Phase 2 is executed by the `_run_files()` method in the `GenerationOrchestrator` class. [2](#7-1)  The process follows these steps:

1. **File Filtering**: Uses a denylist approach to filter out non-code files like `.md`, `.json`, `.yaml`, configuration files, and documentation files. [3](#7-2)  This ensures only programming language files receive documentation.

2. **Incremental Regeneration**: For each file, computes a SHA-256 content hash and compares it with the existing page's hash in the database. [4](#7-3)  Files are skipped if their content hasn't changed and there are no new notes.

3. **Parallel Processing**: Files are processed in parallel batches using `asyncio.gather()`, with a configurable `parallel_limit` (default: 10). [5](#7-4) 

4. **LLM Generation**: Each file is sent to the LLM with its content, symbols, imports, and architecture context. [6](#7-5) 

5. **YAML Extraction**: The generated content is parsed to extract a YAML frontmatter block containing structured metadata. [7](#7-6) 

6. **Summary Creation**: A `FileSummary` object is created from the parsed YAML data. [8](#7-7) 

## Main Components and Responsibilities

### FileGenerator

The `FileGenerator` class generates documentation for individual files using LLM-based generation. [9](#7-8)  It detects the programming language, formats the prompt, calls the LLM, and returns both a `GeneratedPage` and `FileSummary`. [10](#7-9) 

### SummaryParser

The `SummaryParser` class extracts structured summaries from LLM-generated markdown. [11](#7-10)  It uses regex to locate YAML blocks delimited by `---`, parses the YAML safely, validates the structure, and returns clean markdown with the YAML removed. [12](#7-11) 

### FILE_TEMPLATE

The prompt template that instructs the LLM to generate file documentation with a specific YAML frontmatter format. [13](#7-12)  It mandates that responses include a `file_summary` block with fields like `purpose`, `layer`, `key_abstractions`, `internal_deps`, and `external_deps`.

### Content Hash System

Functions for computing and comparing file content hashes to enable incremental regeneration. [14](#7-13)  The system also checks for new notes that would require regeneration even if content is unchanged. [15](#7-14) 

## Data Structures Produced

### FileSummary

The primary data structure produced by Phase 2, containing structured metadata about each file: [16](#7-15) 

- **file_path**: Path relative to repository root
- **purpose**: One-sentence description of the file's role
- **layer**: Architectural layer classification (api, domain, infrastructure, utility, config, or test) [17](#7-16) 
- **key_abstractions**: Primary classes/functions defined in the file
- **internal_deps**: Internal file dependencies
- **external_deps**: External library imports

FileSummary objects support serialization to/from dictionaries for JSON storage. [18](#7-17) 

### GeneratedPage

Standard page objects containing the markdown content, metadata, and file paths. [19](#7-18) 

### Return Values

`_run_files()` returns a tuple of three values: a list of generated pages, a dictionary mapping file paths to content hashes, and a list of FileSummary objects. [20](#7-19)  The file hashes are used by Phase 3 for directory signature computation, and the FileSummaries are passed to Phase 4 (Synthesis).

## Strengths

### 1. Robust Fallback Behavior
When YAML parsing fails or produces invalid data, the parser returns safe default FileSummary objects with `purpose="Unknown"` and `layer="utility"`. [21](#7-20)  This prevents pipeline failures and allows generation to continue even with LLM errors.

### 2. Efficient Incremental Regeneration
The content hash system efficiently skips unchanged files, reducing token costs and generation time. [4](#7-3)  Progress tracking accounts for both generated and skipped files for accurate reporting. [22](#7-21) 

### 3. Language-Agnostic File Filtering
The denylist approach documents all programming language files without maintaining an allowlist, supporting any language automatically. [3](#7-2) 

### 4. Structured Metadata Extraction
The YAML block approach provides structured, parseable metadata that can be validated and used programmatically in later phases. [8](#7-7) 

### 5. Parallel Processing
Batched parallel execution with `asyncio.gather()` maintains good throughput while preventing API overload. [5](#7-4) 

## Weaknesses and Limitations

### 1. File Filtering False Positives
The denylist approach may send non-code files to the LLM if they have unusual extensions not in the exclusion list, wasting tokens. [23](#7-22) 

### 2. Low-Quality Fallback Summaries
When YAML parsing fails, the fallback summary provides no useful information (`purpose="Unknown"`, `layer="utility"`), which can propagate to Phase 4 and degrade higher-level documentation quality. [21](#7-20) 

### 3. No LLM Output Quality Validation
The system only validates YAML structure, not semantic correctness. The LLM could generate syntactically valid but meaningless summaries (wrong layer classifications, missing dependencies, incorrect purposes). [24](#7-23) 

### 4. Limited Layer Classification System
The fixed set of six architectural layers may not fit all projects. Invalid layers are silently coerced to "utility" without warning. [25](#7-24) 

### 5. Static Parallel Limit
The default `parallel_limit=10` is fixed and doesn't adapt to API performance or rate limits. [26](#7-25) 

### 6. Incremental Regeneration Edge Cases
Content hash comparison doesn't account for changes in architecture context, prompt templates, or LLM model versions. A file might need regeneration even if its content is unchanged. [4](#7-3) 

### 7. Layer Validation Weakness
Invalid layer values are automatically coerced to "utility" rather than raising an error or warning, which can hide prompt issues. [27](#7-26) 

## Notes

Phase 2 is critical to the bottom-up generation approach because the FileSummary objects it produces are consumed by Phase 4 (Synthesis) to create the SynthesisMap, which informs all higher-level documentation. [28](#7-27)  The quality and accuracy of Phase 2's output directly impacts the quality of Architecture, Overview, and other high-level pages.

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

**File:** backend/src/oya/generation/orchestrator.py (L88-97)
```python
def compute_content_hash(content: str) -> str:
    """Compute SHA-256 hash of content.

    Args:
        content: String content to hash.

    Returns:
        Hex digest of SHA-256 hash.
    """
    return hashlib.sha256(content.encode("utf-8")).hexdigest()
```

**File:** backend/src/oya/generation/orchestrator.py (L141-151)
```python
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
```

**File:** backend/src/oya/generation/orchestrator.py (L206-230)
```python
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
```

**File:** backend/src/oya/generation/orchestrator.py (L232-260)
```python
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
```

**File:** backend/src/oya/generation/orchestrator.py (L360-396)
```python
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
```

**File:** backend/src/oya/generation/orchestrator.py (L919-932)
```python
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
```

**File:** backend/src/oya/generation/orchestrator.py (L938-982)
```python
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

```

**File:** backend/src/oya/generation/orchestrator.py (L997-1006)
```python
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
```

**File:** backend/src/oya/generation/orchestrator.py (L1031-1042)
```python
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
```

**File:** backend/src/oya/generation/file.py (L37-48)
```python
class FileGenerator:
    """Generates file documentation pages."""

    def __init__(self, llm_client, repo):
        """Initialize the file generator.

        Args:
            llm_client: LLM client for generation.
            repo: Repository wrapper for context.
        """
        self.llm_client = llm_client
        self.repo = repo
```

**File:** backend/src/oya/generation/file.py (L51-101)
```python
    async def generate(
        self,
        file_path: str,
        content: str,
        symbols: list[dict],
        imports: list[str],
        architecture_summary: str,
    ) -> tuple[GeneratedPage, FileSummary]:
        """Generate documentation for a file.

        Args:
            file_path: Path to the file being documented.
            content: Content of the file.
            symbols: List of symbol dictionaries defined in the file.
            imports: List of import statements.
            architecture_summary: Summary of how this file fits in the architecture.

        Returns:
            Tuple of (GeneratedPage with file documentation, FileSummary extracted from output).
        """
        language = self._detect_language(file_path)

        prompt = get_file_prompt(
            file_path=file_path,
            content=content,
            symbols=symbols,
            imports=imports,
            architecture_summary=architecture_summary,
            language=language,
        )

        generated_content = await self.llm_client.generate(
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
        )

        # Parse the YAML summary block and get clean markdown
        clean_content, file_summary = self._parser.parse_file_summary(generated_content, file_path)

        word_count = len(clean_content.split())
        slug = path_to_slug(file_path, include_extension=True)

        page = GeneratedPage(
            content=clean_content,
            page_type="file",
            path=f"files/{slug}.md",
            word_count=word_count,
            target=file_path,
        )

        return page, file_summary
```

**File:** backend/src/oya/generation/summaries.py (L16-18)
```python
VALID_LAYERS: frozenset[str] = frozenset(
    ["api", "domain", "infrastructure", "utility", "config", "test"]
)
```

**File:** backend/src/oya/generation/summaries.py (L40-62)
```python
@dataclass
class FileSummary:
    """Structured summary extracted from file documentation.

    Captures the essential information about a source file including its purpose,
    architectural layer, key abstractions, and dependencies.

    Attributes:
        file_path: Path to the source file relative to repository root.
        purpose: One-sentence description of what the file does.
        layer: Classification of code responsibility (api, domain, infrastructure,
               utility, config, or test).
        key_abstractions: Primary classes, functions, or types defined in the file.
        internal_deps: Paths to other files in the repository that this file depends on.
        external_deps: External libraries or packages the file imports.
    """

    file_path: str
    purpose: str
    layer: str
    key_abstractions: list[str] = field(default_factory=list)
    internal_deps: list[str] = field(default_factory=list)
    external_deps: list[str] = field(default_factory=list)
```

**File:** backend/src/oya/generation/summaries.py (L64-69)
```python
    def __post_init__(self):
        """Validate layer field after initialization."""
        if self.layer not in VALID_LAYERS:
            raise ValueError(
                f"Invalid layer '{self.layer}'. Must be one of: {', '.join(sorted(VALID_LAYERS))}"
            )
```

**File:** backend/src/oya/generation/summaries.py (L71-103)
```python
    def to_dict(self) -> dict[str, Any]:
        """Serialize the FileSummary to a dictionary.

        Returns:
            Dictionary representation of the FileSummary for JSON storage.
        """
        return {
            "file_path": self.file_path,
            "purpose": self.purpose,
            "layer": self.layer,
            "key_abstractions": self.key_abstractions,
            "internal_deps": self.internal_deps,
            "external_deps": self.external_deps,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FileSummary":
        """Deserialize a FileSummary from a dictionary.

        Args:
            data: Dictionary representation of a FileSummary.

        Returns:
            A new FileSummary instance.
        """
        return cls(
            file_path=data.get("file_path", ""),
            purpose=data.get("purpose", "Unknown"),
            layer=data.get("layer", "utility"),
            key_abstractions=data.get("key_abstractions", []),
            internal_deps=data.get("internal_deps", []),
            external_deps=data.get("external_deps", []),
        )
```

**File:** backend/src/oya/generation/summaries.py (L286-292)
```python
class SummaryParser:
    """Parses structured summaries from LLM-generated markdown.

    Extracts YAML summary blocks from markdown content and converts them
    to FileSummary or DirectorySummary objects. The YAML block is stripped
    from the returned markdown content.
    """
```

**File:** backend/src/oya/generation/summaries.py (L294-315)
```python
    # Regex pattern to match YAML blocks delimited by ---
    YAML_BLOCK_PATTERN = re.compile(r"^---\s*\n(.*?)\n---\s*\n?", re.MULTILINE | re.DOTALL)

    def _extract_yaml_block(self, markdown: str) -> tuple[str | None, str]:
        """Extract YAML content from markdown and return clean markdown.

        Args:
            markdown: The full markdown content potentially containing a YAML block.

        Returns:
            A tuple of (yaml_content, clean_markdown) where yaml_content is None
            if no valid YAML block was found.
        """
        match = self.YAML_BLOCK_PATTERN.search(markdown)

        if not match:
            return None, markdown

        yaml_content = match.group(1)
        clean_markdown = self.YAML_BLOCK_PATTERN.sub("", markdown).strip()

        return yaml_content, clean_markdown
```

**File:** backend/src/oya/generation/summaries.py (L343-390)
```python
    def parse_file_summary(self, markdown: str, file_path: str) -> tuple[str, FileSummary]:
        """Parse File_Summary from markdown, return (clean_markdown, summary).

        Extracts the YAML block containing file_summary data from the markdown,
        parses it into a FileSummary object, and returns the markdown with the
        YAML block removed.

        Args:
            markdown: The full markdown content potentially containing a YAML block.
            file_path: The path to the file being summarized.

        Returns:
            A tuple of (clean_markdown, FileSummary) where clean_markdown has
            the YAML block removed.
        """
        yaml_content, clean_markdown = self._extract_yaml_block(markdown)

        if yaml_content is None:
            return markdown, self._fallback_file_summary(file_path)

        data = self._parse_yaml_safely(yaml_content)

        if data is None or "file_summary" not in data:
            return markdown, self._fallback_file_summary(file_path)

        summary_data = data["file_summary"]

        if not isinstance(summary_data, dict):
            return markdown, self._fallback_file_summary(file_path)

        # Extract and validate fields
        purpose = summary_data.get("purpose", "Unknown")
        layer = summary_data.get("layer", "utility")

        # Validate layer, default to utility if invalid
        if layer not in VALID_LAYERS:
            layer = "utility"

        summary = FileSummary(
            file_path=file_path,
            purpose=purpose,
            layer=layer,
            key_abstractions=self._ensure_list(summary_data.get("key_abstractions", [])),
            internal_deps=self._ensure_list(summary_data.get("internal_deps", [])),
            external_deps=self._ensure_list(summary_data.get("external_deps", [])),
        )

        return clean_markdown, summary
```

**File:** backend/src/oya/generation/summaries.py (L392-404)
```python
    def _fallback_file_summary(self, file_path: str) -> FileSummary:
        """Create a fallback FileSummary with default values.

        Used when YAML parsing fails or no YAML block is found.
        """
        return FileSummary(
            file_path=file_path,
            purpose="Unknown",
            layer="utility",
            key_abstractions=[],
            internal_deps=[],
            external_deps=[],
        )
```

**File:** backend/src/oya/generation/prompts.py (L315-367)
```python
FILE_TEMPLATE = PromptTemplate(
    """Generate documentation for the file "{file_path}".

## File Content
```{language}
{content}
```

## Symbols
{symbols}

## Imports
{imports}

## Architecture Context
{architecture_summary}

---

IMPORTANT: You MUST start your response with a YAML summary block in the following format:

```
---
file_summary:
  purpose: "One-sentence description of what this file does"
  layer: <one of: api, domain, infrastructure, utility, config, test>
  key_abstractions:
    - "ClassName or function_name"
  internal_deps:
    - "path/to/other/file.py"
  external_deps:
    - "library_name"
---
```

Layer classification guide:
- api: REST endpoints, request handlers, API routes
- domain: Core business logic, services, use cases
- infrastructure: Database, external services, I/O operations
- utility: Helper functions, shared utilities, common tools
- config: Configuration, settings, environment handling
- test: Test files, test utilities, fixtures

After the YAML block, create file documentation that includes:
1. **File Purpose**: What this file does and its role in the project
2. **Classes**: Document each class with its purpose and methods
3. **Functions**: Document each function with parameters and return values
4. **Constants/Variables**: Document important module-level definitions
5. **Dependencies**: What this file imports and why
6. **Usage Examples**: How to use the components defined in this file

Format the output as clean Markdown suitable for a wiki page."""
)
```

