# Directory Pages Redesign Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Improve directory page navigation with standardized templates, clickable breadcrumbs, subdirectory summaries, and proper cascade regeneration.

**Architecture:** Add breadcrumb generation helpers to prompts.py, update DirectoryGenerator to accept child summaries, modify orchestrator to process directories depth-first (children before parents), and enhance signature computation to include child directory purposes.

**Tech Stack:** Python 3.11+, pytest, AsyncMock for testing

---

## Task 1: Add Breadcrumb Generation Helper

**Files:**
- Modify: `backend/src/oya/generation/prompts.py:564-592` (add after `_format_directory_summaries`)
- Test: `backend/tests/test_prompts.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_prompts.py`:

```python
class TestBreadcrumbGeneration:
    """Tests for breadcrumb generation helper."""

    def test_generate_breadcrumb_shallow_directory(self):
        """Shallow directories show full path."""
        from oya.generation.prompts import generate_breadcrumb

        result = generate_breadcrumb("src/api/routes", "my-project")

        assert "[my-project](./root.md)" in result
        assert "[src](./src.md)" in result
        assert "[api](./src-api.md)" in result
        assert "routes" in result
        assert "..." not in result

    def test_generate_breadcrumb_deep_directory_truncates(self):
        """Deep directories (>4 levels) truncate middle."""
        from oya.generation.prompts import generate_breadcrumb

        result = generate_breadcrumb(
            "src/components/ui/forms/inputs/validation",
            "my-project"
        )

        assert "[my-project](./root.md)" in result
        assert "..." in result
        assert "[inputs](./src-components-ui-forms-inputs.md)" in result
        assert "validation" in result
        # Middle segments should be truncated
        assert "[ui]" not in result
        assert "[forms]" not in result

    def test_generate_breadcrumb_root_directory(self):
        """Root directory shows only project name."""
        from oya.generation.prompts import generate_breadcrumb

        result = generate_breadcrumb("", "my-project")

        assert result == "my-project"

    def test_generate_breadcrumb_single_level(self):
        """Single level directory shows root and current."""
        from oya.generation.prompts import generate_breadcrumb

        result = generate_breadcrumb("src", "my-project")

        assert "[my-project](./root.md)" in result
        assert "src" in result
        assert "..." not in result
```

**Step 2: Run test to verify it fails**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_prompts.py::TestBreadcrumbGeneration -v`
Expected: FAIL with "cannot import name 'generate_breadcrumb'"

**Step 3: Write minimal implementation**

Add to `backend/src/oya/generation/prompts.py` after line 592:

```python
def generate_breadcrumb(directory_path: str, project_name: str) -> str:
    """Generate a breadcrumb trail for directory navigation.

    For shallow directories (depth <= 4), shows full path.
    For deep directories (depth > 4), truncates middle: root / ... / parent / current.

    Args:
        directory_path: Path to the directory (empty string for root).
        project_name: Name of the project for the root link.

    Returns:
        Markdown string with clickable breadcrumb links.
    """
    # Root directory - just show project name
    if not directory_path:
        return project_name

    parts = directory_path.split("/")
    depth = len(parts)

    # Build slugs for each ancestor
    def build_slug(path_parts: list[str]) -> str:
        return "-".join(path_parts).lower()

    # Root link
    root_link = f"[{project_name}](./root.md)"

    if depth <= 4:
        # Show full path
        links = [root_link]
        for i in range(len(parts) - 1):
            ancestor_path = "/".join(parts[: i + 1])
            slug = build_slug(parts[: i + 1])
            links.append(f"[{parts[i]}](./{slug}.md)")
        links.append(parts[-1])  # Current directory (no link)
        return " / ".join(links)
    else:
        # Truncate middle: root / ... / parent / current
        parent_path = "/".join(parts[:-1])
        parent_slug = build_slug(parts[:-1])
        parent_link = f"[{parts[-2]}](./{parent_slug}.md)"
        return f"{root_link} / ... / {parent_link} / {parts[-1]}"
```

**Step 4: Run test to verify it passes**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_prompts.py::TestBreadcrumbGeneration -v`
Expected: PASS (4 tests)

**Step 5: Commit**

```bash
cd /Users/poecurt/projects/oya/.worktrees/directory-pages-redesign
git add backend/src/oya/generation/prompts.py backend/tests/test_prompts.py
git commit -m "feat: add breadcrumb generation helper for directory navigation"
```

---

## Task 2: Add Subdirectory Summaries Formatter

**Files:**
- Modify: `backend/src/oya/generation/prompts.py`
- Test: `backend/tests/test_prompts.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_prompts.py`:

```python
class TestSubdirectorySummariesFormatter:
    """Tests for subdirectory summaries formatter."""

    def test_format_subdirectory_summaries_with_data(self):
        """Formats subdirectories as markdown table with links."""
        from oya.generation.prompts import format_subdirectory_summaries
        from oya.generation.summaries import DirectorySummary

        summaries = [
            DirectorySummary(
                directory_path="src/api/routes",
                purpose="HTTP route handlers for all endpoints",
                contains=["user.py", "auth.py"],
                role_in_system="API layer",
            ),
            DirectorySummary(
                directory_path="src/api/middleware",
                purpose="Request/response middleware",
                contains=["cors.py"],
                role_in_system="Cross-cutting concerns",
            ),
        ]

        result = format_subdirectory_summaries(summaries, "src/api")

        assert "| Directory | Purpose |" in result
        assert "[routes](./src-api-routes.md)" in result
        assert "HTTP route handlers" in result
        assert "[middleware](./src-api-middleware.md)" in result
        assert "Request/response middleware" in result

    def test_format_subdirectory_summaries_empty(self):
        """Returns message when no subdirectories."""
        from oya.generation.prompts import format_subdirectory_summaries

        result = format_subdirectory_summaries([], "src/api")

        assert "No subdirectories" in result

    def test_format_subdirectory_summaries_filters_to_direct_children(self):
        """Only includes direct child directories, not nested ones."""
        from oya.generation.prompts import format_subdirectory_summaries
        from oya.generation.summaries import DirectorySummary

        summaries = [
            DirectorySummary(
                directory_path="src/api/routes",
                purpose="Routes",
                contains=[],
                role_in_system="",
            ),
            DirectorySummary(
                directory_path="src/api/routes/v1",  # Nested - should be excluded
                purpose="V1 routes",
                contains=[],
                role_in_system="",
            ),
        ]

        result = format_subdirectory_summaries(summaries, "src/api")

        assert "routes" in result
        assert "v1" not in result.lower() or "[v1]" not in result
```

**Step 2: Run test to verify it fails**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_prompts.py::TestSubdirectorySummariesFormatter -v`
Expected: FAIL with "cannot import name 'format_subdirectory_summaries'"

**Step 3: Write minimal implementation**

Add to `backend/src/oya/generation/prompts.py`:

```python
def format_subdirectory_summaries(
    summaries: list[Any],
    parent_directory: str
) -> str:
    """Format subdirectory summaries as a markdown table with links.

    Only includes direct child directories of the parent.

    Args:
        summaries: List of DirectorySummary objects.
        parent_directory: Path of the parent directory.

    Returns:
        Markdown table string with directory links and purposes.
    """
    if not summaries:
        return "No subdirectories."

    # Filter to direct children only
    prefix = f"{parent_directory}/" if parent_directory else ""
    direct_children = []
    for summary in summaries:
        path = summary.directory_path
        # Must start with parent path
        if not path.startswith(prefix):
            continue
        # Remaining path after prefix should have no slashes (direct child)
        remaining = path[len(prefix):]
        if "/" not in remaining and remaining:
            direct_children.append(summary)

    if not direct_children:
        return "No subdirectories."

    lines = ["| Directory | Purpose |", "|-----------|---------|"]
    for summary in sorted(direct_children, key=lambda s: s.directory_path):
        name = summary.directory_path.split("/")[-1]
        slug = summary.directory_path.replace("/", "-").lower()
        link = f"[{name}](./{slug}.md)"
        purpose = summary.purpose or "No description"
        lines.append(f"| {link} | {purpose} |")

    return "\n".join(lines)
```

**Step 4: Run test to verify it passes**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_prompts.py::TestSubdirectorySummariesFormatter -v`
Expected: PASS (3 tests)

**Step 5: Commit**

```bash
git add backend/src/oya/generation/prompts.py backend/tests/test_prompts.py
git commit -m "feat: add subdirectory summaries formatter with markdown table"
```

---

## Task 3: Add File Links Formatter

**Files:**
- Modify: `backend/src/oya/generation/prompts.py`
- Test: `backend/tests/test_prompts.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_prompts.py`:

```python
class TestFileLinksFormatter:
    """Tests for file links formatter."""

    def test_format_file_links_with_summaries(self):
        """Formats files as markdown table with links."""
        from oya.generation.prompts import format_file_links
        from oya.generation.summaries import FileSummary

        summaries = [
            FileSummary(
                file_path="src/api/app.py",
                purpose="FastAPI application setup",
                layer="api",
                key_abstractions=["create_app"],
                internal_deps=[],
                external_deps=["fastapi"],
            ),
            FileSummary(
                file_path="src/api/__init__.py",
                purpose="Package initialization",
                layer="config",
                key_abstractions=[],
                internal_deps=[],
                external_deps=[],
            ),
        ]

        result = format_file_links(summaries)

        assert "| File | Purpose |" in result
        assert "[app.py](../files/src-api-app-py.md)" in result
        assert "FastAPI application setup" in result
        assert "[__init__.py](../files/src-api-__init__-py.md)" in result

    def test_format_file_links_empty(self):
        """Returns message when no files."""
        from oya.generation.prompts import format_file_links

        result = format_file_links([])

        assert "No files" in result
```

**Step 2: Run test to verify it fails**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_prompts.py::TestFileLinksFormatter -v`
Expected: FAIL with "cannot import name 'format_file_links'"

**Step 3: Write minimal implementation**

Add to `backend/src/oya/generation/prompts.py`:

```python
def format_file_links(file_summaries: list[Any]) -> str:
    """Format file summaries as a markdown table with links.

    Args:
        file_summaries: List of FileSummary objects.

    Returns:
        Markdown table string with file links and purposes.
    """
    if not file_summaries:
        return "No files in this directory."

    lines = ["| File | Purpose |", "|------|---------|"]
    for summary in sorted(file_summaries, key=lambda s: s.file_path):
        filename = summary.file_path.split("/")[-1]
        # File slug: replace / with - and . with -
        slug = summary.file_path.replace("/", "-").replace(".", "-").lower()
        link = f"[{filename}](../files/{slug}.md)"
        purpose = summary.purpose or "No description"
        lines.append(f"| {link} | {purpose} |")

    return "\n".join(lines)
```

**Step 4: Run test to verify it passes**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_prompts.py::TestFileLinksFormatter -v`
Expected: PASS (2 tests)

**Step 5: Commit**

```bash
git add backend/src/oya/generation/prompts.py backend/tests/test_prompts.py
git commit -m "feat: add file links formatter with markdown table"
```

---

## Task 4: Update extract_directories_from_files to Include Root

**Files:**
- Modify: `backend/src/oya/repo/file_filter.py:9-27`
- Test: `backend/tests/test_file_filter.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_file_filter.py`:

```python
class TestExtractDirectoriesIncludesRoot:
    """Tests for root directory inclusion."""

    def test_extract_directories_includes_root(self):
        """Root directory ('') is included in extracted directories."""
        files = ["src/main.py", "README.md", "tests/test_main.py"]

        result = extract_directories_from_files(files)

        assert "" in result  # Root directory
        assert "src" in result
        assert "tests" in result

    def test_extract_directories_root_only_for_top_level_files(self):
        """Root is included even when only top-level files exist."""
        files = ["README.md", "setup.py"]

        result = extract_directories_from_files(files)

        assert "" in result
        assert len(result) == 1  # Only root

    def test_extract_directories_root_first_in_sorted_order(self):
        """Root directory comes first in sorted output."""
        files = ["src/main.py", "tests/test.py"]

        result = extract_directories_from_files(files)

        assert result[0] == ""  # Root is first
```

**Step 2: Run test to verify it fails**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_file_filter.py::TestExtractDirectoriesIncludesRoot -v`
Expected: FAIL with AssertionError (root not in result)

**Step 3: Write minimal implementation**

Update `backend/src/oya/repo/file_filter.py` function `extract_directories_from_files`:

```python
def extract_directories_from_files(files: list[str]) -> list[str]:
    """Extract unique parent directories from a list of file paths.

    This replicates the logic from GenerationOrchestrator._run_directories
    to ensure consistency between preview and generation.

    Args:
        files: List of file paths.

    Returns:
        Sorted list of unique directory paths, including root ("").
    """
    directories: set[str] = set()
    # Always include root directory
    directories.add("")
    for file_path in files:
        parts = file_path.split("/")
        for i in range(1, len(parts)):
            dir_path = "/".join(parts[:i])
            directories.add(dir_path)
    return sorted(directories)
```

**Step 4: Run test to verify it passes**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_file_filter.py::TestExtractDirectoriesIncludesRoot -v`
Expected: PASS (3 tests)

**Step 5: Commit**

```bash
git add backend/src/oya/repo/file_filter.py backend/tests/test_file_filter.py
git commit -m "feat: include root directory in extract_directories_from_files"
```

---

## Task 5: Update Directory Template

**Files:**
- Modify: `backend/src/oya/generation/prompts.py:270-308` (DIRECTORY_TEMPLATE)
- Modify: `backend/src/oya/generation/prompts.py:719-751` (get_directory_prompt)

**Step 1: Update the template**

Replace `DIRECTORY_TEMPLATE` in `backend/src/oya/generation/prompts.py`:

```python
DIRECTORY_TEMPLATE = PromptTemplate(
    """Generate a directory documentation page for "{directory_path}" in "{repo_name}".

## Breadcrumb
{breadcrumb}

## Direct Files
{file_list}

## File Summaries
{file_summaries}

## Subdirectories
{subdirectory_summaries}

## Symbols Defined
{symbols}

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

After the YAML block, create directory documentation with these sections IN ORDER:

1. **Overview**: One paragraph describing the directory's purpose (do NOT include a heading, start directly with the paragraph)

2. **Subdirectories** (if any exist): Use this exact table format:
| Directory | Purpose |
|-----------|---------|
| [name](./slug.md) | One-line description |

3. **Files**: Use this exact table format:
| File | Purpose |
|------|---------|
| [name.py](../files/slug.md) | One-line description |

4. **Key Components**: Bullet list of important classes/functions

5. **Dependencies**:
   - **Internal**: Other directories/modules this depends on
   - **External**: Third-party libraries used

Use the breadcrumb, file summaries, and subdirectory summaries provided to generate accurate content.
Do NOT invent files or subdirectories that aren't listed above.
Format all file and directory names as markdown links using the link formats shown in the tables."""
)
```

**Step 2: Update get_directory_prompt function**

Replace `get_directory_prompt` function:

```python
def get_directory_prompt(
    repo_name: str,
    directory_path: str,
    file_list: list[str],
    symbols: list[dict[str, Any]],
    architecture_context: str,
    file_summaries: list[Any] | None = None,
    subdirectory_summaries: list[Any] | None = None,
    project_name: str | None = None,
) -> str:
    """Generate a prompt for creating a directory page.

    Args:
        repo_name: Name of the repository.
        directory_path: Path to the directory (empty string for root).
        file_list: List of files in the directory.
        symbols: List of symbol dictionaries defined in the directory.
        architecture_context: Summary of how this directory fits in the architecture.
        file_summaries: Optional list of FileSummary objects for files in the directory.
        subdirectory_summaries: Optional list of DirectorySummary objects for child directories.
        project_name: Project name for breadcrumb (defaults to repo_name).

    Returns:
        The rendered prompt string.
    """
    file_list_str = (
        "\n".join(f"- {f}" for f in file_list) if file_list else "No files in directory."
    )

    proj_name = project_name or repo_name
    breadcrumb = generate_breadcrumb(directory_path, proj_name)

    # Format display path - use project name for root
    display_path = directory_path if directory_path else proj_name

    return DIRECTORY_TEMPLATE.render(
        repo_name=repo_name,
        directory_path=display_path,
        breadcrumb=breadcrumb,
        file_list=file_list_str,
        file_summaries=format_file_links(file_summaries or []),
        subdirectory_summaries=format_subdirectory_summaries(
            subdirectory_summaries or [], directory_path
        ),
        symbols=_format_symbols(symbols),
    )
```

**Step 3: Run existing tests to ensure no regressions**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_prompts.py tests/test_directory_generator.py -v`
Expected: Some failures due to changed template (expected)

**Step 4: Update test_directory_generator.py for new parameters**

The existing tests will need minor updates to pass the new parameters. Update the test fixtures and assertions.

**Step 5: Commit**

```bash
git add backend/src/oya/generation/prompts.py
git commit -m "feat: update directory template with breadcrumb and navigation tables"
```

---

## Task 6: Update DirectoryGenerator to Accept Child Summaries

**Files:**
- Modify: `backend/src/oya/generation/directory.py`
- Test: `backend/tests/test_directory_generator.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_directory_generator.py`:

```python
class TestDirectoryGeneratorWithChildSummaries:
    """Tests for DirectoryGenerator with child directory summaries."""

    @pytest.fixture
    def sample_child_summaries(self):
        """Create sample child DirectorySummaries for testing."""
        return [
            DirectorySummary(
                directory_path="src/auth/providers",
                purpose="Authentication provider implementations",
                contains=["oauth.py", "jwt.py"],
                role_in_system="Pluggable auth backends",
            ),
            DirectorySummary(
                directory_path="src/auth/middleware",
                purpose="Auth middleware for request processing",
                contains=["verify.py"],
                role_in_system="Request authentication layer",
            ),
        ]

    @pytest.mark.asyncio
    async def test_generate_accepts_child_summaries(
        self, generator_with_yaml, sample_file_summaries, sample_child_summaries
    ):
        """Test that generate() accepts child_summaries parameter."""
        page, summary = await generator_with_yaml.generate(
            directory_path="src/auth",
            file_list=["login.py", "session.py"],
            symbols=[],
            architecture_context="",
            file_summaries=sample_file_summaries,
            child_summaries=sample_child_summaries,
        )

        assert page.content
        assert isinstance(summary, DirectorySummary)

    @pytest.mark.asyncio
    async def test_generate_includes_child_summaries_in_prompt(
        self, generator_with_yaml, mock_llm_client_with_yaml, sample_child_summaries
    ):
        """Test that child summaries appear in the LLM prompt."""
        await generator_with_yaml.generate(
            directory_path="src/auth",
            file_list=["login.py"],
            symbols=[],
            architecture_context="",
            file_summaries=[],
            child_summaries=sample_child_summaries,
        )

        call_args = mock_llm_client_with_yaml.generate.call_args
        prompt = call_args.kwargs.get("prompt") or call_args.args[0]

        # Should contain subdirectory info
        assert "providers" in prompt
        assert "middleware" in prompt

    @pytest.mark.asyncio
    async def test_generate_accepts_project_name(
        self, generator_with_yaml, mock_llm_client_with_yaml
    ):
        """Test that generate() accepts project_name for breadcrumb."""
        await generator_with_yaml.generate(
            directory_path="src/auth",
            file_list=["login.py"],
            symbols=[],
            architecture_context="",
            file_summaries=[],
            child_summaries=[],
            project_name="my-awesome-project",
        )

        call_args = mock_llm_client_with_yaml.generate.call_args
        prompt = call_args.kwargs.get("prompt") or call_args.args[0]

        assert "my-awesome-project" in prompt
```

**Step 2: Run test to verify it fails**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_directory_generator.py::TestDirectoryGeneratorWithChildSummaries -v`
Expected: FAIL with TypeError (unexpected keyword argument)

**Step 3: Write minimal implementation**

Update `backend/src/oya/generation/directory.py`:

```python
"""Directory page generator."""

from oya.generation.overview import GeneratedPage
from oya.generation.prompts import SYSTEM_PROMPT, get_directory_prompt
from oya.generation.summaries import (
    DirectorySummary,
    FileSummary,
    SummaryParser,
    path_to_slug,
)


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

    async def generate(
        self,
        directory_path: str,
        file_list: list[str],
        symbols: list[dict],
        architecture_context: str,
        file_summaries: list[FileSummary] | None = None,
        child_summaries: list[DirectorySummary] | None = None,
        project_name: str | None = None,
    ) -> tuple[GeneratedPage, DirectorySummary]:
        """Generate directory documentation and extract summary.

        Args:
            directory_path: Path to the directory (empty string for root).
            file_list: List of files in the directory.
            symbols: List of symbol dictionaries defined in the directory.
            architecture_context: Summary of how this directory fits in the architecture.
            file_summaries: Optional list of FileSummary objects for files in the directory.
            child_summaries: Optional list of DirectorySummary objects for child directories.
            project_name: Optional project name for breadcrumb (defaults to repo name).

        Returns:
            A tuple of (GeneratedPage, DirectorySummary).
        """
        repo_name = self.repo.path.name
        proj_name = project_name or repo_name

        prompt = get_directory_prompt(
            repo_name=repo_name,
            directory_path=directory_path,
            file_list=file_list,
            symbols=symbols,
            architecture_context=architecture_context,
            file_summaries=file_summaries or [],
            subdirectory_summaries=child_summaries or [],
            project_name=proj_name,
        )

        content = await self.llm_client.generate(
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
        )

        # Parse the DirectorySummary from the LLM output
        clean_content, summary = self._parser.parse_directory_summary(content, directory_path)

        word_count = len(clean_content.split())

        # Handle root directory slug
        if directory_path:
            slug = path_to_slug(directory_path, include_extension=False)
        else:
            slug = "root"

        page = GeneratedPage(
            content=clean_content,
            page_type="directory",
            path=f"directories/{slug}.md",
            word_count=word_count,
            target=directory_path,
        )

        return page, summary
```

**Step 4: Run test to verify it passes**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_directory_generator.py -v`
Expected: PASS (all tests)

**Step 5: Commit**

```bash
git add backend/src/oya/generation/directory.py backend/tests/test_directory_generator.py
git commit -m "feat: update DirectoryGenerator to accept child summaries and project name"
```

---

## Task 7: Update Orchestrator - Depth-First Processing

**Files:**
- Modify: `backend/src/oya/generation/orchestrator.py:821-946`
- Test: `backend/tests/test_orchestrator.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_orchestrator.py`:

```python
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
```

**Step 2: Run test to verify it fails**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_orchestrator.py::TestDirectoryProcessingOrder -v`
Expected: FAIL with ImportError

**Step 3: Write minimal implementation**

Add helper functions to `backend/src/oya/generation/orchestrator.py` after `compute_directory_signature`:

```python
def group_directories_by_depth(directories: list[str]) -> dict[int, list[str]]:
    """Group directories by their depth level.

    Args:
        directories: List of directory paths.

    Returns:
        Dict mapping depth to list of directories at that depth.
    """
    from collections import defaultdict

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
```

**Step 4: Run test to verify it passes**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_orchestrator.py::TestDirectoryProcessingOrder -v`
Expected: PASS (3 tests)

**Step 5: Commit**

```bash
git add backend/src/oya/generation/orchestrator.py backend/tests/test_orchestrator.py
git commit -m "feat: add depth-first directory processing helpers"
```

---

## Task 8: Update Orchestrator - Enhanced Signature with Child Purposes

**Files:**
- Modify: `backend/src/oya/generation/orchestrator.py`
- Test: `backend/tests/test_orchestrator.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_orchestrator.py`:

```python
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
```

**Step 2: Run test to verify it fails**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_orchestrator.py::TestEnhancedDirectorySignature -v`
Expected: FAIL with ImportError

**Step 3: Write minimal implementation**

Add to `backend/src/oya/generation/orchestrator.py`:

```python
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
    child_part = "|".join(
        f"{c.directory_path}:{c.purpose}" for c in sorted_children
    )

    combined = f"{file_part}||{child_part}"
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()
```

**Step 4: Run test to verify it passes**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_orchestrator.py::TestEnhancedDirectorySignature -v`
Expected: PASS (2 tests)

**Step 5: Commit**

```bash
git add backend/src/oya/generation/orchestrator.py backend/tests/test_orchestrator.py
git commit -m "feat: add enhanced directory signature including child purposes"
```

---

## Task 9: Integrate Changes in _run_directories

**Files:**
- Modify: `backend/src/oya/generation/orchestrator.py:821-946` (`_run_directories` method)

**Step 1: Update _run_directories to use new processing order and pass child summaries**

This is a larger refactor. Replace the `_run_directories` method:

```python
async def _run_directories(
    self,
    analysis: dict,
    file_hashes: dict[str, str],
    progress_callback: ProgressCallback | None = None,
    file_summaries: list[FileSummary] | None = None,
) -> tuple[list[GeneratedPage], list[DirectorySummary]]:
    """Run directory generation phase with depth-first processing.

    Processes directories from deepest to shallowest, ensuring child
    summaries are available when generating parent directories.

    Args:
        analysis: Analysis results.
        file_hashes: Dict of file_path to content_hash from files phase.
        progress_callback: Optional async callback for progress updates.
        file_summaries: Optional list of FileSummary objects for context.

    Returns:
        Tuple of (list of generated directory pages, list of DirectorySummaries).
    """
    pages: list[GeneratedPage] = []
    file_summaries = file_summaries or []

    # Build a lookup of file summaries by file path
    file_summary_lookup: dict[str, FileSummary] = {
        fs.file_path: fs for fs in file_summaries if isinstance(fs, FileSummary)
    }

    # Get unique directories including root
    all_directories = extract_directories_from_files(analysis["files"])

    # Build directories dict with their direct files
    directories: dict[str, list[str]] = {d: [] for d in all_directories}
    for file_path in analysis["files"]:
        parts = file_path.split("/")
        if len(parts) == 1:
            # Top-level file belongs to root
            directories[""].append(file_path)
        else:
            parent_dir = "/".join(parts[:-1])
            if parent_dir in directories:
                directories[parent_dir].append(file_path)

    # Get processing order (deepest first, root last)
    processing_order = get_processing_order(all_directories)

    # Store generated summaries for parent access
    all_summaries: dict[str, DirectorySummary] = {}

    # Track what needs regeneration
    dirs_to_generate: list[tuple[str, str]] = []
    skipped_count = 0

    # First pass: determine what needs regeneration
    for dir_path in processing_order:
        dir_files = directories.get(dir_path, [])

        # Get child summaries for this directory
        child_summaries = self._get_direct_child_summaries(dir_path, all_summaries)

        # Build file hash pairs for signature
        file_hash_pairs = [
            (f.split("/")[-1], file_hashes.get(f, ""))
            for f in dir_files
            if f in file_hashes
        ]

        # Compute enhanced signature including child purposes
        signature_hash = compute_directory_signature_with_children(
            file_hash_pairs, child_summaries
        )

        existing = self._get_existing_page_info(dir_path, "directory")
        needs_regen = (
            not existing
            or existing.get("source_hash") != signature_hash
            or self._has_new_notes(dir_path, existing.get("generated_at"))
        )

        if needs_regen:
            dirs_to_generate.append((dir_path, signature_hash))
        else:
            skipped_count += 1

    total_dirs = len(processing_order)

    # Emit initial progress
    await self._emit_progress(
        progress_callback,
        GenerationProgress(
            phase=GenerationPhase.DIRECTORIES,
            step=skipped_count,
            total_steps=total_dirs,
            message=f"Generating directory pages ({skipped_count} unchanged, 0/{len(dirs_to_generate)} generating)...",
        ),
    )

    # Get project name for breadcrumbs
    project_name = self.repo.path.name

    # Second pass: generate in order (must be sequential for child summaries)
    generated_count = 0
    for dir_path in processing_order:
        # Check if this directory needs generation
        signature_hash = None
        for d, sig in dirs_to_generate:
            if d == dir_path:
                signature_hash = sig
                break

        if signature_hash is None:
            # Load existing summary for parent use (if needed)
            # For now, skip loading - parents will just have fewer child summaries
            continue

        dir_files = directories.get(dir_path, [])

        # Get file summaries for this directory
        dir_file_summaries = [
            file_summary_lookup[f]
            for f in dir_files
            if f in file_summary_lookup
        ]

        # Get child summaries
        child_summaries = self._get_direct_child_summaries(dir_path, all_summaries)

        # Filter symbols
        dir_symbols = [
            self._symbol_to_dict(s) for s in analysis["symbols"]
            if s.metadata.get("file", "").startswith(f"{dir_path}/" if dir_path else "")
            and (not dir_path or "/" not in s.metadata.get("file", "")[len(dir_path) + 1:])
        ]

        # Generate
        page, summary = await self.directory_generator.generate(
            directory_path=dir_path,
            file_list=[f.split("/")[-1] for f in dir_files],
            symbols=dir_symbols,
            architecture_context="",
            file_summaries=dir_file_summaries,
            child_summaries=child_summaries,
            project_name=project_name,
        )

        # Store summary for parent access
        all_summaries[dir_path] = summary
        page.source_hash = signature_hash
        pages.append(page)

        generated_count += 1
        await self._emit_progress(
            progress_callback,
            GenerationProgress(
                phase=GenerationPhase.DIRECTORIES,
                step=skipped_count + generated_count,
                total_steps=total_dirs,
                message=f"Generated {generated_count}/{len(dirs_to_generate)} directories ({skipped_count} unchanged)...",
            ),
        )

    return pages, list(all_summaries.values())


def _get_direct_child_summaries(
    self,
    parent_path: str,
    all_summaries: dict[str, DirectorySummary]
) -> list[DirectorySummary]:
    """Get DirectorySummaries for direct children of a directory.

    Args:
        parent_path: Path of the parent directory.
        all_summaries: Dict of all generated summaries so far.

    Returns:
        List of DirectorySummary objects for direct children.
    """
    result = []
    prefix = f"{parent_path}/" if parent_path else ""

    for child_path, summary in all_summaries.items():
        if not child_path.startswith(prefix):
            continue
        # Check if it's a direct child (no more slashes after prefix)
        remaining = child_path[len(prefix):]
        if "/" not in remaining and remaining:
            result.append(summary)

    return result
```

**Step 2: Run full test suite to ensure no regressions**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_orchestrator.py tests/test_directory_generator.py -v`
Expected: PASS (may need fixture updates)

**Step 3: Commit**

```bash
git add backend/src/oya/generation/orchestrator.py
git commit -m "feat: integrate depth-first processing and child summaries in orchestrator"
```

---

## Task 10: Integration Test

**Files:**
- Test: `backend/tests/test_integration_pipeline.py`

**Step 1: Write integration test**

Add to `backend/tests/test_integration_pipeline.py`:

```python
class TestDirectoryPagesRedesign:
    """Integration tests for directory pages redesign."""

    @pytest.mark.asyncio
    async def test_directory_pages_have_breadcrumbs(self, temp_wiki_repo):
        """Generated directory pages contain breadcrumb navigation."""
        # Create test files
        (temp_wiki_repo / "src").mkdir()
        (temp_wiki_repo / "src" / "api").mkdir()
        (temp_wiki_repo / "src" / "api" / "app.py").write_text("app = None")

        # Run generation
        # ... (setup orchestrator and run)

        # Check generated directory page
        dir_page = (temp_wiki_repo / ".oyawiki" / "wiki" / "directories" / "src-api.md")
        content = dir_page.read_text()

        assert "src" in content  # Breadcrumb should reference src

    @pytest.mark.asyncio
    async def test_root_directory_page_generated(self, temp_wiki_repo):
        """Root directory page is generated."""
        (temp_wiki_repo / "main.py").write_text("print('hello')")

        # Run generation
        # ...

        root_page = (temp_wiki_repo / ".oyawiki" / "wiki" / "directories" / "root.md")
        assert root_page.exists()

    @pytest.mark.asyncio
    async def test_parent_regenerates_when_child_purpose_changes(self, temp_wiki_repo):
        """Parent directory regenerates when child directory purpose changes."""
        # This would require a more complex test setup
        pass
```

**Step 2: Run integration tests**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_integration_pipeline.py::TestDirectoryPagesRedesign -v`

**Step 3: Commit**

```bash
git add backend/tests/test_integration_pipeline.py
git commit -m "test: add integration tests for directory pages redesign"
```

---

## Task 11: Run Full Test Suite and Fix Any Failures

**Step 1: Run all tests**

Run: `cd backend && source .venv/bin/activate && pytest -v`

**Step 2: Fix any failures**

Address any test failures that arise from the changes.

**Step 3: Final commit**

```bash
git add -A
git commit -m "fix: address test failures from directory pages redesign"
```

---

## Summary

This plan implements the directory pages redesign in 11 tasks:

1. Breadcrumb generation helper
2. Subdirectory summaries formatter
3. File links formatter
4. Root directory inclusion
5. Updated directory template
6. DirectoryGenerator child summaries support
7. Depth-first processing helpers
8. Enhanced signature with child purposes
9. Orchestrator integration
10. Integration tests
11. Full test suite verification

Each task follows TDD with specific test-first development, exact file paths, and commit points.
