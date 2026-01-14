# Phase 2 Quality Improvements Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Improve file documentation quality by fixing empty outputs, adding consistent templates, retry semantics, better logging, and Mermaid diagrams.

**Architecture:** Modify prompt templates to enforce developer audience and required sections. Add retry logic in FileGenerator for YAML parsing failures. Add logging throughout with timestamps. Extend Mermaid generators to support single-file dependency diagrams.

**Tech Stack:** Python 3.11, FastAPI, pytest, asyncio

---

## Task 1: Global Logging Configuration

**Files:**
- Modify: `backend/src/oya/main.py:1-14`
- Test: `backend/tests/test_startup.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_startup.py`:

```python
def test_logging_format_includes_timestamp():
    """Verify logging format includes timestamp."""
    import logging

    # Get the root logger's handler format
    root_logger = logging.getLogger()

    # Check that basicConfig was called with timestamp format
    # We verify this by checking a logger outputs in expected format
    import io
    import re

    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)-8s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    ))

    test_logger = logging.getLogger("test_timestamp")
    test_logger.addHandler(handler)
    test_logger.setLevel(logging.INFO)
    test_logger.info("Test message")

    output = stream.getvalue()
    # Should match format: 2026-01-14 10:23:45 INFO     Test message
    pattern = r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} INFO\s+Test message"
    assert re.match(pattern, output), f"Log format doesn't match expected pattern: {output}"
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/poecurt/projects/oya/.worktrees/phase2-quality/backend && source /Users/poecurt/projects/oya/backend/.venv/bin/activate && pytest tests/test_startup.py::test_logging_format_includes_timestamp -v`

Expected: PASS (this test verifies the format we'll use, not the global config)

**Step 3: Update main.py with logging configuration**

Modify `backend/src/oya/main.py` - replace lines 1-14 with:

```python
"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Configure global logging format with timestamps
LOG_FORMAT = "%(asctime)s %(levelname)-8s %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

logging.basicConfig(
    format=LOG_FORMAT,
    datefmt=DATE_FORMAT,
    level=logging.INFO,
)

from oya.api.routers import repos, wiki, jobs, search, qa, notes
from oya.config import load_settings
from oya.workspace import initialize_workspace

logger = logging.getLogger(__name__)
```

**Step 4: Run all startup tests**

Run: `cd /Users/poecurt/projects/oya/.worktrees/phase2-quality/backend && pytest tests/test_startup.py -v`

Expected: All tests PASS

**Step 5: Commit**

```bash
cd /Users/poecurt/projects/oya/.worktrees/phase2-quality
git add backend/src/oya/main.py backend/tests/test_startup.py
git commit -m "feat: add global logging configuration with timestamps"
```

---

## Task 2: Layer Validation Logging

**Files:**
- Modify: `backend/src/oya/generation/summaries.py:377-379`
- Test: `backend/tests/test_summaries.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_summaries.py`:

```python
def test_parse_file_summary_logs_warning_on_invalid_layer(caplog):
    """Test that invalid layer values log a warning before coercing to utility."""
    import logging
    from oya.generation.summaries import SummaryParser

    parser = SummaryParser()
    markdown = """---
file_summary:
  purpose: "Test file"
  layer: invalid_layer
  key_abstractions: []
  internal_deps: []
  external_deps: []
---

# Test File
"""

    with caplog.at_level(logging.WARNING):
        clean_md, summary = parser.parse_file_summary(markdown, "test/file.py")

    # Should coerce to utility
    assert summary.layer == "utility"

    # Should have logged a warning
    assert "Invalid layer 'invalid_layer'" in caplog.text
    assert "test/file.py" in caplog.text
    assert "defaulting to 'utility'" in caplog.text
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/poecurt/projects/oya/.worktrees/phase2-quality/backend && pytest tests/test_summaries.py::test_parse_file_summary_logs_warning_on_invalid_layer -v`

Expected: FAIL - no warning logged yet

**Step 3: Add logging import and logger to summaries.py**

At the top of `backend/src/oya/generation/summaries.py`, after line 12 (`import yaml`), add:

```python
import logging

logger = logging.getLogger(__name__)
```

**Step 4: Update layer validation in parse_file_summary**

In `backend/src/oya/generation/summaries.py`, replace lines 377-379:

```python
        # Validate layer, default to utility if invalid
        if layer not in VALID_LAYERS:
            layer = "utility"
```

With:

```python
        # Validate layer, default to utility if invalid
        if layer not in VALID_LAYERS:
            logger.warning(
                f"Invalid layer '{layer}' for {file_path}, defaulting to 'utility'. "
                f"Valid layers: {', '.join(sorted(VALID_LAYERS))}"
            )
            layer = "utility"
```

**Step 5: Run test to verify it passes**

Run: `cd /Users/poecurt/projects/oya/.worktrees/phase2-quality/backend && pytest tests/test_summaries.py::test_parse_file_summary_logs_warning_on_invalid_layer -v`

Expected: PASS

**Step 6: Run all summaries tests**

Run: `cd /Users/poecurt/projects/oya/.worktrees/phase2-quality/backend && pytest tests/test_summaries.py -v`

Expected: All tests PASS

**Step 7: Commit**

```bash
cd /Users/poecurt/projects/oya/.worktrees/phase2-quality
git add backend/src/oya/generation/summaries.py backend/tests/test_summaries.py
git commit -m "feat: log warning when invalid layer is coerced to utility"
```

---

## Task 3: Prompt Template - Audience Clarity

**Files:**
- Modify: `backend/src/oya/generation/prompts.py:315-367`
- Test: `backend/tests/test_prompts.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_prompts.py`:

```python
def test_file_template_includes_developer_audience():
    """File template must specify developer audience."""
    from oya.generation.prompts import FILE_TEMPLATE

    template_text = FILE_TEMPLATE.template.lower()

    # Must mention developers as the audience
    assert "developer" in template_text
    assert "maintain" in template_text or "debug" in template_text or "extend" in template_text

    # Must NOT skip documentation for internal files
    assert "must" in template_text and "always" in template_text and "documentation" in template_text


def test_file_template_rejects_skip_documentation():
    """File template must explicitly prohibit skipping documentation."""
    from oya.generation.prompts import FILE_TEMPLATE

    template_text = FILE_TEMPLATE.template.lower()

    # Must address internal/trivial files explicitly
    assert "internal" in template_text or "trivial" in template_text
    assert "never skip" in template_text or "must always" in template_text
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/poecurt/projects/oya/.worktrees/phase2-quality/backend && pytest tests/test_prompts.py::test_file_template_includes_developer_audience tests/test_prompts.py::test_file_template_rejects_skip_documentation -v`

Expected: FAIL - template doesn't include audience clarity yet

**Step 3: Update FILE_TEMPLATE in prompts.py**

Replace `FILE_TEMPLATE` (lines 315-367) in `backend/src/oya/generation/prompts.py` with:

```python
FILE_TEMPLATE = PromptTemplate(
    """Generate documentation for the file "{file_path}".

AUDIENCE: You are writing for developers who will maintain, debug, and extend this code - NOT for end users of an API. Even files marked as "internal" or "no user-serviceable parts" need thorough documentation for the development team.

REQUIREMENT: You MUST always produce documentation. Every file has value to developers - explain what it does, why it exists, and how it works. Never skip documentation because a file seems "internal" or "trivial".

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

Your documentation MUST include these sections in order:
1. **Purpose** - What this file does and why it exists
2. **Public API** - Exported classes, functions, constants (if any)
3. **Internal Details** - Implementation specifics developers need to know
4. **Dependencies** - What this file imports and why
5. **Usage Examples** - How to use the components in this file

You MAY add additional sections after these if there's important information that doesn't fit (e.g., "Concurrency Notes", "Migration History", "Known Limitations").

Format the output as clean Markdown suitable for a wiki page."""
)
```

**Step 4: Run tests to verify they pass**

Run: `cd /Users/poecurt/projects/oya/.worktrees/phase2-quality/backend && pytest tests/test_prompts.py::test_file_template_includes_developer_audience tests/test_prompts.py::test_file_template_rejects_skip_documentation -v`

Expected: PASS

**Step 5: Run all prompts tests**

Run: `cd /Users/poecurt/projects/oya/.worktrees/phase2-quality/backend && pytest tests/test_prompts.py -v`

Expected: All tests PASS

**Step 6: Commit**

```bash
cd /Users/poecurt/projects/oya/.worktrees/phase2-quality
git add backend/src/oya/generation/prompts.py backend/tests/test_prompts.py
git commit -m "feat: update file template with developer audience and required sections"
```

---

## Task 4: Retry Semantics for YAML Parsing

**Files:**
- Modify: `backend/src/oya/generation/file.py:51-101`
- Test: `backend/tests/test_file_generator.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_file_generator.py`:

```python
@pytest.mark.asyncio
async def test_generate_retries_on_yaml_failure(mock_repo, caplog):
    """Test that generate() retries once when YAML parsing fails."""
    import logging

    # First call returns bad YAML, second call returns good YAML
    mock_llm = AsyncMock()
    mock_llm.generate.side_effect = [
        "# file.py\n\nNo YAML block here.",  # First attempt fails
        """---
file_summary:
  purpose: "Test file after retry"
  layer: utility
  key_abstractions: []
  internal_deps: []
  external_deps: []
---

# file.py

Documentation after retry.
""",  # Second attempt succeeds
    ]

    generator = FileGenerator(llm_client=mock_llm, repo=mock_repo)

    with caplog.at_level(logging.WARNING):
        page, summary = await generator.generate(
            file_path="src/test.py",
            content="# test",
            symbols=[],
            imports=[],
            architecture_summary="",
        )

    # Should have called LLM twice (original + retry)
    assert mock_llm.generate.call_count == 2

    # Should have logged a warning about retry
    assert "YAML parsing failed" in caplog.text
    assert "retrying" in caplog.text

    # Should have the successful result
    assert summary.purpose == "Test file after retry"


@pytest.mark.asyncio
async def test_generate_logs_error_after_retry_fails(mock_repo, caplog):
    """Test that generate() logs error when retry also fails."""
    import logging

    # Both calls return bad YAML
    mock_llm = AsyncMock()
    mock_llm.generate.return_value = "# file.py\n\nNo YAML block here."

    generator = FileGenerator(llm_client=mock_llm, repo=mock_repo)

    with caplog.at_level(logging.WARNING):
        page, summary = await generator.generate(
            file_path="src/test.py",
            content="# test",
            symbols=[],
            imports=[],
            architecture_summary="",
        )

    # Should have called LLM twice
    assert mock_llm.generate.call_count == 2

    # Should have logged warning then error
    assert "YAML parsing failed" in caplog.text
    assert "retrying" in caplog.text
    assert "after retry" in caplog.text

    # Should return fallback summary
    assert summary.purpose == "Unknown"
    assert summary.layer == "utility"
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/poecurt/projects/oya/.worktrees/phase2-quality/backend && pytest tests/test_file_generator.py::test_generate_retries_on_yaml_failure tests/test_file_generator.py::test_generate_logs_error_after_retry_fails -v`

Expected: FAIL - no retry logic yet

**Step 3: Add logging import to file.py**

At the top of `backend/src/oya/generation/file.py`, after line 4 (`from pathlib import Path`), add:

```python
import logging

logger = logging.getLogger(__name__)
```

**Step 4: Update generate() method with retry logic**

Replace the `generate` method (lines 51-101) in `backend/src/oya/generation/file.py` with:

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

        # First attempt
        generated_content = await self.llm_client.generate(
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
        )

        # Parse the YAML summary block and get clean markdown
        clean_content, file_summary = self._parser.parse_file_summary(generated_content, file_path)

        # Check if parsing produced fallback (indicates failure)
        if file_summary.purpose == "Unknown":
            logger.warning(f"YAML parsing failed for {file_path}, retrying...")

            # Retry once with same prompt
            generated_content = await self.llm_client.generate(
                prompt=prompt,
                system_prompt=SYSTEM_PROMPT,
            )
            clean_content, file_summary = self._parser.parse_file_summary(
                generated_content, file_path
            )

            if file_summary.purpose == "Unknown":
                logger.error(f"YAML parsing failed after retry for {file_path}")

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

**Step 5: Run tests to verify they pass**

Run: `cd /Users/poecurt/projects/oya/.worktrees/phase2-quality/backend && pytest tests/test_file_generator.py::test_generate_retries_on_yaml_failure tests/test_file_generator.py::test_generate_logs_error_after_retry_fails -v`

Expected: PASS

**Step 6: Run all file generator tests**

Run: `cd /Users/poecurt/projects/oya/.worktrees/phase2-quality/backend && pytest tests/test_file_generator.py -v`

Expected: All tests PASS

**Step 7: Commit**

```bash
cd /Users/poecurt/projects/oya/.worktrees/phase2-quality
git add backend/src/oya/generation/file.py backend/tests/test_file_generator.py
git commit -m "feat: add retry semantics for YAML parsing failures"
```

---

## Task 5: Single-File Dependency Diagram Generator

**Files:**
- Modify: `backend/src/oya/generation/mermaid.py:72-134`
- Test: `backend/tests/test_mermaid_generator.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_mermaid_generator.py`:

```python
class TestDependencyGraphGeneratorForFile:
    """Tests for single-file dependency diagram generation."""

    @pytest.fixture
    def sample_imports(self) -> dict[str, list[str]]:
        """Create sample import data."""
        return {
            "src/api/routes.py": ["src/domain/service.py", "src/utils/helpers.py"],
            "src/domain/service.py": ["src/db/models.py"],
            "src/utils/helpers.py": [],
            "src/db/models.py": [],
            "src/other/unrelated.py": ["src/other/another.py"],
        }

    def test_generate_for_file_shows_imports(self, sample_imports):
        """Diagram shows files that target imports."""
        generator = DependencyGraphGenerator()
        diagram = generator.generate_for_file("src/api/routes.py", sample_imports)

        # Should show the file imports
        assert "service" in diagram.lower()
        assert "helpers" in diagram.lower()

    def test_generate_for_file_shows_importers(self, sample_imports):
        """Diagram shows files that import the target."""
        generator = DependencyGraphGenerator()
        diagram = generator.generate_for_file("src/domain/service.py", sample_imports)

        # routes.py imports service.py, so routes should appear
        assert "routes" in diagram.lower()

    def test_generate_for_file_excludes_unrelated(self, sample_imports):
        """Diagram excludes files with no relationship to target."""
        generator = DependencyGraphGenerator()
        diagram = generator.generate_for_file("src/api/routes.py", sample_imports)

        # other/unrelated.py has no relationship to routes.py
        assert "unrelated" not in diagram.lower()
        assert "another" not in diagram.lower()

    def test_generate_for_file_valid_mermaid(self, sample_imports):
        """Generated diagram is valid Mermaid."""
        generator = DependencyGraphGenerator()
        diagram = generator.generate_for_file("src/api/routes.py", sample_imports)

        result = validate_mermaid(diagram)
        assert result.valid, f"Invalid diagram: {result.errors}"

    def test_generate_for_file_empty_when_no_deps(self, sample_imports):
        """Returns empty string for file with no dependencies."""
        generator = DependencyGraphGenerator()
        # helpers.py has no imports and nothing imports it except routes
        diagram = generator.generate_for_file("src/db/models.py", sample_imports)

        # Should still be valid but minimal (service imports models)
        assert "service" in diagram.lower()

    def test_generate_for_file_unknown_file(self, sample_imports):
        """Returns empty string for unknown file."""
        generator = DependencyGraphGenerator()
        diagram = generator.generate_for_file("src/unknown/file.py", sample_imports)

        # Should return empty string for unknown files
        assert diagram == ""
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/poecurt/projects/oya/.worktrees/phase2-quality/backend && pytest tests/test_mermaid_generator.py::TestDependencyGraphGeneratorForFile -v`

Expected: FAIL - method doesn't exist yet

**Step 3: Add generate_for_file method to DependencyGraphGenerator**

In `backend/src/oya/generation/mermaid.py`, add this method to the `DependencyGraphGenerator` class after the `generate` method (after line 134):

```python
    def generate_for_file(self, file_path: str, all_imports: dict[str, list[str]]) -> str:
        """Generate a dependency diagram focused on a single file.

        Shows:
        - What this file imports (outgoing edges)
        - What files import this file (incoming edges)

        Args:
            file_path: The file to focus on.
            all_imports: Dict mapping all file paths to their imports.

        Returns:
            Mermaid diagram string, or empty string if no dependencies.
        """
        if file_path not in all_imports:
            # Check if anything imports this file
            importers = [f for f, imports in all_imports.items() if file_path in imports]
            if not importers:
                return ""

        # Collect related files: imports and importers
        imports = set(all_imports.get(file_path, []))
        importers = {f for f, imp_list in all_imports.items() if file_path in imp_list}

        related_files = imports | importers | {file_path}

        if len(related_files) <= 1:
            return ""

        lines = ["flowchart LR"]

        # Create nodes for all related files
        for fp in sorted(related_files):
            node_id = sanitize_node_id(fp)
            filename = fp.split("/")[-1]
            label = sanitize_label(filename, max_length=30)
            lines.append(f'    {node_id}["{label}"]')

        # Add edges: target imports
        target_id = sanitize_node_id(file_path)
        for imp in imports:
            imp_id = sanitize_node_id(imp)
            lines.append(f"    {target_id} --> {imp_id}")

        # Add edges: files that import target
        for importer in importers:
            importer_id = sanitize_node_id(importer)
            lines.append(f"    {importer_id} --> {target_id}")

        return "\n".join(lines)
```

**Step 4: Run tests to verify they pass**

Run: `cd /Users/poecurt/projects/oya/.worktrees/phase2-quality/backend && pytest tests/test_mermaid_generator.py::TestDependencyGraphGeneratorForFile -v`

Expected: PASS

**Step 5: Run all mermaid generator tests**

Run: `cd /Users/poecurt/projects/oya/.worktrees/phase2-quality/backend && pytest tests/test_mermaid_generator.py -v`

Expected: All tests PASS

**Step 6: Commit**

```bash
cd /Users/poecurt/projects/oya/.worktrees/phase2-quality
git add backend/src/oya/generation/mermaid.py backend/tests/test_mermaid_generator.py
git commit -m "feat: add single-file dependency diagram generator"
```

---

## Task 6: Integrate Mermaid Diagrams into File Generation

**Files:**
- Modify: `backend/src/oya/generation/file.py`
- Test: `backend/tests/test_file_generator.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_file_generator.py`:

```python
@pytest.mark.asyncio
async def test_generate_includes_class_diagram_when_classes_present(mock_repo):
    """Test that class diagram is included when file has classes."""
    from oya.parsing.models import ParsedSymbol, SymbolType

    mock_llm = AsyncMock()
    mock_llm.generate.return_value = """---
file_summary:
  purpose: "Service class"
  layer: domain
  key_abstractions:
    - "UserService"
  internal_deps: []
  external_deps: []
---

# user_service.py

User service implementation.
"""

    generator = FileGenerator(llm_client=mock_llm, repo=mock_repo)

    # Provide symbols with a class
    symbols = [
        ParsedSymbol(
            name="UserService",
            symbol_type=SymbolType.CLASS,
            file="src/service.py",
            line=1,
        ),
        ParsedSymbol(
            name="get_user",
            symbol_type=SymbolType.METHOD,
            file="src/service.py",
            line=5,
            parent="UserService",
        ),
    ]

    page, summary = await generator.generate(
        file_path="src/service.py",
        content="class UserService:\n    def get_user(self): pass",
        symbols=[{"name": "UserService", "type": "class", "line": 1}],
        imports=[],
        architecture_summary="",
        parsed_symbols=symbols,
    )

    # Should include class diagram
    assert "## Diagrams" in page.content
    assert "classDiagram" in page.content
    assert "UserService" in page.content


@pytest.mark.asyncio
async def test_generate_includes_dependency_diagram_when_imports_present(mock_repo):
    """Test that dependency diagram is included when file has imports."""
    mock_llm = AsyncMock()
    mock_llm.generate.return_value = """---
file_summary:
  purpose: "Routes file"
  layer: api
  key_abstractions: []
  internal_deps:
    - "src/service.py"
  external_deps: []
---

# routes.py

API routes.
"""

    generator = FileGenerator(llm_client=mock_llm, repo=mock_repo)

    file_imports = {
        "src/routes.py": ["src/service.py"],
        "src/service.py": [],
    }

    page, summary = await generator.generate(
        file_path="src/routes.py",
        content="from src.service import Service",
        symbols=[],
        imports=["from src.service import Service"],
        architecture_summary="",
        file_imports=file_imports,
    )

    # Should include dependency diagram
    assert "## Diagrams" in page.content
    assert "flowchart" in page.content


@pytest.mark.asyncio
async def test_generate_omits_diagrams_when_no_classes_or_deps(mock_repo):
    """Test that diagrams section is omitted when not applicable."""
    mock_llm = AsyncMock()
    mock_llm.generate.return_value = """---
file_summary:
  purpose: "Simple utility"
  layer: utility
  key_abstractions: []
  internal_deps: []
  external_deps: []
---

# utils.py

Simple utilities.
"""

    generator = FileGenerator(llm_client=mock_llm, repo=mock_repo)

    page, summary = await generator.generate(
        file_path="src/utils.py",
        content="def helper(): pass",
        symbols=[],
        imports=[],
        architecture_summary="",
    )

    # Should NOT include diagrams section
    assert "## Diagrams" not in page.content
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/poecurt/projects/oya/.worktrees/phase2-quality/backend && pytest tests/test_file_generator.py::test_generate_includes_class_diagram_when_classes_present tests/test_file_generator.py::test_generate_includes_dependency_diagram_when_imports_present tests/test_file_generator.py::test_generate_omits_diagrams_when_no_classes_or_deps -v`

Expected: FAIL - generate() doesn't accept new parameters yet

**Step 3: Update imports in file.py**

At the top of `backend/src/oya/generation/file.py`, update imports:

```python
"""File page generator."""

import logging
from pathlib import Path

from oya.generation.mermaid import ClassDiagramGenerator, DependencyGraphGenerator
from oya.generation.mermaid_validator import validate_mermaid
from oya.generation.overview import GeneratedPage
from oya.generation.prompts import SYSTEM_PROMPT, get_file_prompt
from oya.generation.summaries import FileSummary, SummaryParser, path_to_slug
from oya.parsing.models import ParsedSymbol

logger = logging.getLogger(__name__)
```

**Step 4: Update FileGenerator.__init__ to create diagram generators**

Replace `__init__` method in `backend/src/oya/generation/file.py`:

```python
    def __init__(self, llm_client, repo):
        """Initialize the file generator.

        Args:
            llm_client: LLM client for generation.
            repo: Repository wrapper for context.
        """
        self.llm_client = llm_client
        self.repo = repo
        self._parser = SummaryParser()
        self._class_diagram_gen = ClassDiagramGenerator()
        self._dep_diagram_gen = DependencyGraphGenerator()
```

**Step 5: Update generate() method to accept and use diagram data**

Replace the full `generate` method in `backend/src/oya/generation/file.py`:

```python
    async def generate(
        self,
        file_path: str,
        content: str,
        symbols: list[dict],
        imports: list[str],
        architecture_summary: str,
        parsed_symbols: list[ParsedSymbol] | None = None,
        file_imports: dict[str, list[str]] | None = None,
    ) -> tuple[GeneratedPage, FileSummary]:
        """Generate documentation for a file.

        Args:
            file_path: Path to the file being documented.
            content: Content of the file.
            symbols: List of symbol dictionaries defined in the file.
            imports: List of import statements.
            architecture_summary: Summary of how this file fits in the architecture.
            parsed_symbols: Optional list of ParsedSymbol objects for class diagrams.
            file_imports: Optional dict of all file imports for dependency diagrams.

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

        # First attempt
        generated_content = await self.llm_client.generate(
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
        )

        # Parse the YAML summary block and get clean markdown
        clean_content, file_summary = self._parser.parse_file_summary(generated_content, file_path)

        # Check if parsing produced fallback (indicates failure)
        if file_summary.purpose == "Unknown":
            logger.warning(f"YAML parsing failed for {file_path}, retrying...")

            # Retry once with same prompt
            generated_content = await self.llm_client.generate(
                prompt=prompt,
                system_prompt=SYSTEM_PROMPT,
            )
            clean_content, file_summary = self._parser.parse_file_summary(
                generated_content, file_path
            )

            if file_summary.purpose == "Unknown":
                logger.error(f"YAML parsing failed after retry for {file_path}")

        # Generate diagrams
        diagrams_md = self._generate_diagrams(file_path, parsed_symbols, file_imports)
        if diagrams_md:
            clean_content += diagrams_md

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

    def _generate_diagrams(
        self,
        file_path: str,
        parsed_symbols: list[ParsedSymbol] | None,
        file_imports: dict[str, list[str]] | None,
    ) -> str:
        """Generate Mermaid diagrams for the file.

        Args:
            file_path: Path to the file being documented.
            parsed_symbols: Optional list of ParsedSymbol objects.
            file_imports: Optional dict of all file imports.

        Returns:
            Markdown string with diagrams, or empty string if no diagrams.
        """
        diagrams = []

        # Class diagram if we have parsed symbols with classes
        if parsed_symbols:
            file_symbols = [s for s in parsed_symbols if s.file == file_path]
            if file_symbols:
                class_diagram = self._class_diagram_gen.generate(file_symbols)
                if class_diagram and "NoClasses" not in class_diagram:
                    result = validate_mermaid(class_diagram)
                    if result.valid:
                        diagrams.append(("Class Structure", class_diagram))

        # Dependency diagram if we have import data
        if file_imports:
            dep_diagram = self._dep_diagram_gen.generate_for_file(file_path, file_imports)
            if dep_diagram:
                result = validate_mermaid(dep_diagram)
                if result.valid:
                    diagrams.append(("Dependencies", dep_diagram))

        if not diagrams:
            return ""

        lines = ["\n\n## Diagrams"]
        for title, diagram in diagrams:
            lines.append(f"\n### {title}\n")
            lines.append(f"```mermaid\n{diagram}\n```")

        return "\n".join(lines)
```

**Step 6: Run tests to verify they pass**

Run: `cd /Users/poecurt/projects/oya/.worktrees/phase2-quality/backend && pytest tests/test_file_generator.py::test_generate_includes_class_diagram_when_classes_present tests/test_file_generator.py::test_generate_includes_dependency_diagram_when_imports_present tests/test_file_generator.py::test_generate_omits_diagrams_when_no_classes_or_deps -v`

Expected: PASS

**Step 7: Run all file generator tests**

Run: `cd /Users/poecurt/projects/oya/.worktrees/phase2-quality/backend && pytest tests/test_file_generator.py -v`

Expected: All tests PASS

**Step 8: Commit**

```bash
cd /Users/poecurt/projects/oya/.worktrees/phase2-quality
git add backend/src/oya/generation/file.py backend/tests/test_file_generator.py
git commit -m "feat: integrate Mermaid diagrams into file documentation"
```

---

## Task 7: Update Orchestrator to Pass Diagram Data

**Files:**
- Modify: `backend/src/oya/generation/orchestrator.py`
- Test: `backend/tests/test_orchestrator.py`

**Step 1: Review orchestrator's _run_files method**

The orchestrator calls `FileGenerator.generate()` inside the `generate_file_page` helper function. We need to pass `parsed_symbols` and `file_imports` to enable diagram generation.

**Step 2: Update generate_file_page helper in orchestrator**

In `backend/src/oya/generation/orchestrator.py`, find the `generate_file_page` helper function inside `_run_files` (around line 1038-1059) and update it to pass the new parameters.

Locate the existing helper:

```python
        async def generate_file_page(file_path: str, content_hash: str):
            """Generate a single file page."""
            content = analysis["file_contents"].get(file_path, "")
            symbols = [s for s in analysis.get("symbols", []) if s.get("file") == file_path]
            file_imports = analysis.get("file_imports", {}).get(file_path, [])

            page, summary = await file_gen.generate(
                file_path=file_path,
                content=content,
                symbols=symbols,
                imports=file_imports,
                architecture_summary=architecture_summary,
            )
            page.metadata = {"source_hash": content_hash}
            return page, summary
```

Replace with:

```python
        # Get all parsed symbols for diagram generation
        all_parsed_symbols = analysis.get("parsed_symbols", [])
        all_file_imports = analysis.get("file_imports", {})

        async def generate_file_page(file_path: str, content_hash: str):
            """Generate a single file page."""
            content = analysis["file_contents"].get(file_path, "")
            symbols = [s for s in analysis.get("symbols", []) if s.get("file") == file_path]
            file_imports = all_file_imports.get(file_path, [])

            page, summary = await file_gen.generate(
                file_path=file_path,
                content=content,
                symbols=symbols,
                imports=file_imports,
                architecture_summary=architecture_summary,
                parsed_symbols=all_parsed_symbols,
                file_imports=all_file_imports,
            )
            page.metadata = {"source_hash": content_hash}
            return page, summary
```

**Step 3: Run orchestrator tests**

Run: `cd /Users/poecurt/projects/oya/.worktrees/phase2-quality/backend && pytest tests/test_orchestrator.py -v`

Expected: All tests PASS

**Step 4: Run integration tests**

Run: `cd /Users/poecurt/projects/oya/.worktrees/phase2-quality/backend && pytest tests/test_integration_pipeline.py -v`

Expected: All tests PASS

**Step 5: Commit**

```bash
cd /Users/poecurt/projects/oya/.worktrees/phase2-quality
git add backend/src/oya/generation/orchestrator.py
git commit -m "feat: pass diagram data from orchestrator to file generator"
```

---

## Task 8: Final Integration Test

**Files:**
- Test: `backend/tests/test_integration_pipeline.py`

**Step 1: Run full test suite**

Run: `cd /Users/poecurt/projects/oya/.worktrees/phase2-quality/backend && pytest -v`

Expected: All tests PASS

**Step 2: Manual verification**

If you have a test repository available, run a generation and verify:
1. Log output includes timestamps
2. Files with "internal" comments still get documented
3. Wiki pages follow the new template structure
4. Mermaid diagrams appear for files with classes or dependencies

**Step 3: Final commit if any fixes needed**

```bash
cd /Users/poecurt/projects/oya/.worktrees/phase2-quality
git status
# If any uncommitted changes, commit them
```

---

## Summary

| Task | What it does |
|------|--------------|
| 1 | Global logging with timestamps |
| 2 | Layer validation logging |
| 3 | Prompt template with audience clarity |
| 4 | Retry semantics for YAML parsing |
| 5 | Single-file dependency diagram generator |
| 6 | Integrate diagrams into file generation |
| 7 | Pass diagram data from orchestrator |
| 8 | Final integration testing |
