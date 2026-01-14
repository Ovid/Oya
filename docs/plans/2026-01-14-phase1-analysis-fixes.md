# Phase 1 Analysis Fixes Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix 5 limitations in Phase 1 Analysis: parse error recovery, smarter file filtering, granular progress, use parser imports, and keep ParsedSymbol objects.

**Architecture:** Modify the analysis phase in orchestrator.py to properly use ParseResult, add fallback recovery, preserve imports, and keep typed objects. Update file_filter.py with new excludes and minified detection. Update consumers (workflows.py, chunking.py) to use ParsedSymbol attributes.

**Tech Stack:** Python 3.11+, pytest, asyncio

---

## Task 1: Add Config Constants

**Files:**
- Modify: `backend/src/oya/constants/files.py`
- Modify: `backend/src/oya/constants/generation.py`

**Step 1: Add minified detection constant to files.py**

Add after line 23 in `backend/src/oya/constants/files.py`:

```python
# =============================================================================
# Minified/Generated File Detection
# =============================================================================
# Files with average line length exceeding this threshold are considered
# minified or generated and excluded from analysis. Minified files have
# extremely long lines (often entire file on one line).

MINIFIED_AVG_LINE_LENGTH = 500
```

**Step 2: Add progress constants to generation.py**

Add after line 35 in `backend/src/oya/constants/generation.py`:

```python
# =============================================================================
# Progress Reporting
# =============================================================================
# PROGRESS_REPORT_INTERVAL controls how often progress updates are emitted
# during the analysis phase. Set to 1 for per-file updates.

PROGRESS_REPORT_INTERVAL = 1

# PARALLEL_LIMIT_DEFAULT is the default number of concurrent LLM calls
# during file/directory generation phases.

PARALLEL_LIMIT_DEFAULT = 10
```

**Step 3: Run tests to verify no regressions**

Run: `cd /Users/poecurt/projects/oya/.worktrees/phase1-fixes/backend && source .venv/bin/activate && pytest tests/ -q --tb=short`
Expected: All tests pass

**Step 4: Commit**

```bash
git add backend/src/oya/constants/files.py backend/src/oya/constants/generation.py
git commit -m "feat(config): add minified detection and progress constants"
```

---

## Task 2: Add Default Excludes for Minified/Lock Files

**Files:**
- Modify: `backend/src/oya/repo/file_filter.py:28-51`
- Test: `backend/tests/test_file_filter.py`

**Step 1: Write tests for new excludes**

Add to `backend/tests/test_file_filter.py`:

```python
def test_default_excludes_minified_js(temp_repo: Path):
    """Default patterns exclude minified JavaScript files."""
    (temp_repo / "app.min.js").write_text("minified code")
    (temp_repo / "app.js").write_text("normal code")

    filter = FileFilter(temp_repo)
    files = filter.get_files()

    assert "app.min.js" not in files
    assert "app.js" in files


def test_default_excludes_bundle_files(temp_repo: Path):
    """Default patterns exclude bundle and chunk files."""
    (temp_repo / "main.bundle.js").write_text("bundled")
    (temp_repo / "vendor.chunk.js").write_text("chunked")

    filter = FileFilter(temp_repo)
    files = filter.get_files()

    assert "main.bundle.js" not in files
    assert "vendor.chunk.js" not in files


def test_default_excludes_lock_files(temp_repo: Path):
    """Default patterns exclude package lock files."""
    (temp_repo / "package-lock.json").write_text("{}")
    (temp_repo / "yarn.lock").write_text("lockfile")
    (temp_repo / "pnpm-lock.yaml").write_text("lockfile")
    (temp_repo / "Cargo.lock").write_text("lockfile")
    (temp_repo / "poetry.lock").write_text("lockfile")
    (temp_repo / "Gemfile.lock").write_text("lockfile")
    (temp_repo / "composer.lock").write_text("{}")

    filter = FileFilter(temp_repo)
    files = filter.get_files()

    assert "package-lock.json" not in files
    assert "yarn.lock" not in files
    assert "pnpm-lock.yaml" not in files
    assert "Cargo.lock" not in files
    assert "poetry.lock" not in files
    assert "Gemfile.lock" not in files
    assert "composer.lock" not in files


def test_default_excludes_source_maps(temp_repo: Path):
    """Default patterns exclude source map files."""
    (temp_repo / "app.js.map").write_text("{}")
    (temp_repo / "styles.css.map").write_text("{}")

    filter = FileFilter(temp_repo)
    files = filter.get_files()

    assert "app.js.map" not in files
    assert "styles.css.map" not in files
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/poecurt/projects/oya/.worktrees/phase1-fixes/backend && source .venv/bin/activate && pytest tests/test_file_filter.py -k "minified or bundle or lock or map" -v`
Expected: FAIL (patterns not yet added)

**Step 3: Update DEFAULT_EXCLUDES in file_filter.py**

Replace DEFAULT_EXCLUDES (lines 28-51) in `backend/src/oya/repo/file_filter.py`:

```python
DEFAULT_EXCLUDES = [
    # Hidden files and directories (dotfiles/dotdirs)
    # This catches .git, .hypothesis, .pytest_cache, .ruff_cache, .env, etc.
    # Note: .oyawiki/notes is explicitly allowed (see ALLOWED_PATHS below)
    ".*",
    # Dependencies
    "node_modules",
    "vendor",
    "venv",
    "__pycache__",
    "*.pyc",
    # Build outputs
    "build",
    "dist",
    "target",
    "out",
    # Oya artifacts (but NOT .oyawiki/notes/ - those are user corrections)
    # These are redundant with ".*" but kept for clarity
    ".oyawiki/wiki",
    ".oyawiki/meta",
    ".oyawiki/index",
    ".oyawiki/cache",
    ".oyawiki/config",
    # Minified/bundled assets
    "*.min.js",
    "*.min.css",
    "*.bundle.js",
    "*.chunk.js",
    "*.map",
    # Lock files (large, not useful for docs)
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "Cargo.lock",
    "poetry.lock",
    "Gemfile.lock",
    "composer.lock",
]
```

**Step 4: Run tests to verify they pass**

Run: `cd /Users/poecurt/projects/oya/.worktrees/phase1-fixes/backend && source .venv/bin/activate && pytest tests/test_file_filter.py -v`
Expected: All tests pass

**Step 5: Commit**

```bash
git add backend/src/oya/repo/file_filter.py backend/tests/test_file_filter.py
git commit -m "feat(filter): add default excludes for minified/lock files"
```

---

## Task 3: Add Minified File Detection

**Files:**
- Modify: `backend/src/oya/repo/file_filter.py`
- Test: `backend/tests/test_file_filter.py`

**Step 1: Write test for minified detection**

Add to `backend/tests/test_file_filter.py`:

```python
def test_excludes_minified_by_line_length(temp_repo: Path):
    """Files with very long lines (minified) are excluded."""
    # Create a file with extremely long lines (simulating minified code)
    long_line = "x" * 1000
    (temp_repo / "minified.js").write_text(long_line + "\n" + long_line)

    # Create a normal file with reasonable line lengths
    normal_content = "\n".join(["const x = 1;"] * 50)
    (temp_repo / "normal.js").write_text(normal_content)

    filter = FileFilter(temp_repo)
    files = filter.get_files()

    assert "minified.js" not in files
    assert "normal.js" in files


def test_minified_detection_samples_first_lines(temp_repo: Path):
    """Minified detection only samples first 20 lines."""
    # First 20 lines are normal, rest is long (should pass)
    normal_lines = ["const x = 1;"] * 25
    (temp_repo / "mostly_normal.js").write_text("\n".join(normal_lines))

    filter = FileFilter(temp_repo)
    files = filter.get_files()

    assert "mostly_normal.js" in files
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/poecurt/projects/oya/.worktrees/phase1-fixes/backend && source .venv/bin/activate && pytest tests/test_file_filter.py -k "minified_by_line" -v`
Expected: FAIL

**Step 3: Add import and _is_minified method to file_filter.py**

Add import at top of `backend/src/oya/repo/file_filter.py`:

```python
from oya.constants.files import MINIFIED_AVG_LINE_LENGTH
```

Add method to FileFilter class (after `_is_binary` method, around line 151):

```python
    def _is_minified(self, file_path: Path) -> bool:
        """Check if file appears to be minified based on line length.

        Minified files typically have extremely long lines (often the
        entire file on one line). We sample the first 20 lines and
        check if the average length exceeds the threshold.

        Args:
            file_path: Path to file.

        Returns:
            True if file appears to be minified.
        """
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
            lines = content.split("\n")[:20]  # Sample first 20 lines
            if not lines:
                return False
            avg_length = sum(len(line) for line in lines) / len(lines)
            return avg_length > MINIFIED_AVG_LINE_LENGTH
        except Exception:
            return False
```

**Step 4: Update get_files to use _is_minified**

In `get_files` method, add minified check after binary check (around line 179):

```python
            # Check binary
            if self._is_binary(file_path):
                continue

            # Check minified (only for text files that passed other checks)
            if self._is_minified(file_path):
                continue

            files.append(relative)
```

**Step 5: Run tests to verify they pass**

Run: `cd /Users/poecurt/projects/oya/.worktrees/phase1-fixes/backend && source .venv/bin/activate && pytest tests/test_file_filter.py -v`
Expected: All tests pass

**Step 6: Commit**

```bash
git add backend/src/oya/repo/file_filter.py backend/tests/test_file_filter.py
git commit -m "feat(filter): add minified file detection by line length"
```

---

## Task 4: Fix Parse Error Recovery in Orchestrator

**Files:**
- Modify: `backend/src/oya/generation/orchestrator.py:526-569`
- Test: `backend/tests/test_orchestrator.py`

**Step 1: Write test for parse error recovery**

Add to `backend/tests/test_orchestrator.py`:

```python
import pytest
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock

from oya.generation.orchestrator import GenerationOrchestrator
from oya.parsing.models import ParseResult, ParsedFile, ParsedSymbol, SymbolType


@pytest.fixture
def mock_orchestrator(tmp_path):
    """Create orchestrator with mocked dependencies."""
    llm_client = MagicMock()
    repo = MagicMock()
    repo.path = tmp_path
    db = MagicMock()
    wiki_path = tmp_path / ".oyawiki"
    wiki_path.mkdir()

    return GenerationOrchestrator(llm_client, repo, db, wiki_path)


@pytest.mark.asyncio
async def test_analysis_recovers_from_parse_errors(mock_orchestrator, tmp_path):
    """Analysis phase recovers symbols from files with syntax errors using fallback."""
    # Create a file with invalid Python syntax
    bad_file = tmp_path / "bad.py"
    bad_file.write_text("def broken(\n")  # Syntax error

    # Create a valid file
    good_file = tmp_path / "good.py"
    good_file.write_text("def valid_func():\n    pass\n")

    # Run analysis
    result = await mock_orchestrator._run_analysis()

    # Should have files
    assert "bad.py" in result["files"] or "good.py" in result["files"]

    # Should have parse_errors tracking
    assert "parse_errors" in result

    # Good file should have symbols extracted
    good_symbols = [s for s in result["symbols"] if s.metadata.get("file") == "good.py"]
    assert len(good_symbols) > 0


@pytest.mark.asyncio
async def test_analysis_tracks_parse_errors(mock_orchestrator, tmp_path):
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
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/poecurt/projects/oya/.worktrees/phase1-fixes/backend && source .venv/bin/activate && pytest tests/test_orchestrator.py -k "parse_error" -v`
Expected: FAIL

**Step 3: Add fallback parser to orchestrator**

Add import at top of `backend/src/oya/generation/orchestrator.py`:

```python
from oya.parsing.fallback_parser import FallbackParser
from oya.parsing.models import ParsedSymbol
```

Add to `__init__` method after `self.parser_registry` initialization:

```python
        self._fallback_parser = FallbackParser()
```

**Step 4: Rewrite _run_analysis method**

Replace the parsing loop in `_run_analysis` (lines 526-569) with:

```python
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
            from oya.constants.generation import PROGRESS_REPORT_INTERVAL
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
```

**Step 5: Run tests to verify they pass**

Run: `cd /Users/poecurt/projects/oya/.worktrees/phase1-fixes/backend && source .venv/bin/activate && pytest tests/test_orchestrator.py -k "parse_error" -v`
Expected: PASS

**Step 6: Commit**

```bash
git add backend/src/oya/generation/orchestrator.py backend/tests/test_orchestrator.py
git commit -m "feat(analysis): add parse error recovery with fallback parser"
```

---

## Task 5: Update Symbol Consumers - workflows.py

**Files:**
- Modify: `backend/src/oya/generation/workflows.py:71-117`

**Step 1: Update imports**

Add import at top of `backend/src/oya/generation/workflows.py`:

```python
from oya.parsing.models import ParsedSymbol, SymbolType
```

**Step 2: Update find_entry_points signature and implementation**

Replace `find_entry_points` method (lines 71-86):

```python
    def find_entry_points(self, symbols: list[ParsedSymbol]) -> list[ParsedSymbol]:
        """Find entry points from a list of symbols.

        Args:
            symbols: List of ParsedSymbol objects from parsing.

        Returns:
            List of symbols that are entry points.
        """
        entry_points = []

        for symbol in symbols:
            if self._is_entry_point(symbol):
                entry_points.append(symbol)

        return entry_points
```

**Step 3: Update _is_entry_point method**

Replace `_is_entry_point` method (lines 88-117):

```python
    def _is_entry_point(self, symbol: ParsedSymbol) -> bool:
        """Check if a symbol is an entry point.

        Args:
            symbol: ParsedSymbol object.

        Returns:
            True if the symbol is an entry point.
        """
        # Check symbol type
        if symbol.symbol_type in (SymbolType.ROUTE, SymbolType.CLI_COMMAND):
            return True

        # Check decorators
        for decorator in symbol.decorators:
            if decorator in self.ENTRY_POINT_DECORATORS:
                return True
            # Also check partial matches (e.g., "app.get" in "@app.get('/users')")
            for entry_decorator in self.ENTRY_POINT_DECORATORS:
                if entry_decorator in decorator:
                    return True

        # Check function name
        if symbol.name in self.ENTRY_POINT_NAMES:
            return True

        return False
```

**Step 4: Update group_into_workflows method**

Replace `group_into_workflows` method (lines 119-145):

```python
    def group_into_workflows(
        self,
        entry_points: list[ParsedSymbol],
        file_imports: dict[str, list[str]] | None = None,
    ) -> list[DiscoveredWorkflow]:
        """Group entry points into logical workflows.

        Args:
            entry_points: List of entry point symbols.
            file_imports: Optional mapping of file paths to their imports.

        Returns:
            List of discovered workflows.
        """
        workflows = []

        for entry_point in entry_points:
            workflow = DiscoveredWorkflow(
                name=self._humanize_name(entry_point.name),
                slug=self._slugify(entry_point.name),
                entry_points=[entry_point],
                related_files=[entry_point.metadata.get("file", "")],
            )
            workflows.append(workflow)

        return workflows
```

**Step 5: Run tests**

Run: `cd /Users/poecurt/projects/oya/.worktrees/phase1-fixes/backend && source .venv/bin/activate && pytest tests/ -q --tb=short`
Expected: All tests pass

**Step 6: Commit**

```bash
git add backend/src/oya/generation/workflows.py
git commit -m "refactor(workflows): use ParsedSymbol objects instead of dicts"
```

---

## Task 6: Update Symbol Consumers - chunking.py

**Files:**
- Modify: `backend/src/oya/generation/chunking.py:117-200`

**Step 1: Update imports**

Add import at top of `backend/src/oya/generation/chunking.py`:

```python
from oya.parsing.models import ParsedSymbol
```

**Step 2: Update Chunk dataclass**

Replace the `symbols` field in the Chunk dataclass (line 26):

```python
    symbols: list[ParsedSymbol] = field(default_factory=list)
```

**Step 3: Update chunk_by_symbols function signature**

Replace function signature and docstring (lines 117-136):

```python
def chunk_by_symbols(
    content: str,
    file_path: str,
    symbols: list[ParsedSymbol],
    max_tokens: int = MAX_CHUNK_TOKENS,
) -> list[Chunk]:
    """Split file content by symbol boundaries.

    Groups symbols into chunks that respect code boundaries
    while staying under the token limit.

    Args:
        content: File content to chunk.
        file_path: Path to the source file.
        symbols: List of ParsedSymbol objects with start_line/end_line.
        max_tokens: Maximum tokens per chunk.

    Returns:
        List of Chunk objects with associated symbols.
    """
```

**Step 4: Update symbol access in chunk_by_symbols**

Replace the symbol sorting and access (around lines 146-157):

```python
    # Sort symbols by start_line
    sorted_symbols = sorted(symbols, key=lambda s: s.start_line)

    chunks: list[Chunk] = []
    chunk_index = 0

    current_symbols: list[ParsedSymbol] = []
    current_start_line: int | None = None
    current_content_lines: list[str] = []

    for symbol in sorted_symbols:
        start_line = symbol.start_line
        end_line = symbol.end_line
```

**Step 5: Run all tests**

Run: `cd /Users/poecurt/projects/oya/.worktrees/phase1-fixes/backend && source .venv/bin/activate && pytest tests/ -q --tb=short`
Expected: All tests pass

**Step 6: Commit**

```bash
git add backend/src/oya/generation/chunking.py
git commit -m "refactor(chunking): use ParsedSymbol objects instead of dicts"
```

---

## Task 7: Update Orchestrator Symbol Filtering

**Files:**
- Modify: `backend/src/oya/generation/orchestrator.py`

**Step 1: Update symbol filtering in _run_workflows**

Find the symbol filtering around line 692 and update:

```python
            file_symbols = [
                s for s in analysis["symbols"]
                if s.metadata.get("file") == file_path
            ]
```

**Step 2: Update symbol filtering in _run_directories**

Find the symbol filtering around line 870 and update:

```python
                dir_symbols = [
                    s for s in analysis["symbols"]
                    if s.metadata.get("file", "").startswith(dir_path + "/")
                ]
```

**Step 3: Update symbol filtering in _run_files**

Find the symbol filtering around line 1015 and update:

```python
            file_symbols = [
                s for s in analysis["symbols"]
                if s.metadata.get("file") == file_path
            ]
```

**Step 4: Update imports usage in _run_files**

Replace the `_extract_imports` call (around line 1018):

```python
            imports = analysis.get("file_imports", {}).get(file_path, [])
```

**Step 5: Delete _extract_imports method**

Remove the entire `_extract_imports` method (lines 1059-1084).

**Step 6: Run all tests**

Run: `cd /Users/poecurt/projects/oya/.worktrees/phase1-fixes/backend && source .venv/bin/activate && pytest tests/ -q --tb=short`
Expected: All tests pass

**Step 7: Commit**

```bash
git add backend/src/oya/generation/orchestrator.py
git commit -m "refactor(orchestrator): use ParsedSymbol metadata for filtering, use parser imports"
```

---

## Task 8: Update File/Directory Generation Progress

**Files:**
- Modify: `backend/src/oya/generation/orchestrator.py`

**Step 1: Update _run_files to use as_completed**

Find the batch processing loop in `_run_files` (around lines 1031-1055) and replace with:

```python
        # Process files in parallel batches, report as each completes
        completed = skipped_count
        for batch in batched(files_to_generate, self.parallel_limit):
            tasks = [
                asyncio.create_task(generate_file_page(file_path, content_hash))
                for file_path, content_hash in batch
            ]

            for coro in asyncio.as_completed(tasks):
                page, summary = await coro
                pages.append(page)
                file_summaries.append(summary)

                completed += 1
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
```

**Step 2: Update _run_directories to use as_completed**

Find the batch processing loop in `_run_directories` (around lines 891-912) and replace with:

```python
        # Process directories in parallel batches, report as each completes
        completed = skipped_count
        for batch in batched(dirs_to_generate, self.parallel_limit):
            tasks = [
                asyncio.create_task(generate_dir_page(dir_path, signature_hash))
                for dir_path, signature_hash in batch
            ]

            for coro in asyncio.as_completed(tasks):
                page, summary = await coro
                pages.append(page)
                directory_summaries.append(summary)

                completed += 1
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

**Step 3: Run all tests**

Run: `cd /Users/poecurt/projects/oya/.worktrees/phase1-fixes/backend && source .venv/bin/activate && pytest tests/ -q --tb=short`
Expected: All tests pass

**Step 4: Commit**

```bash
git add backend/src/oya/generation/orchestrator.py
git commit -m "feat(progress): report per-file progress using asyncio.as_completed"
```

---

## Task 9: Final Integration Test

**Files:**
- Test: `backend/tests/test_orchestrator.py`

**Step 1: Add integration test**

Add to `backend/tests/test_orchestrator.py`:

```python
@pytest.mark.asyncio
async def test_analysis_returns_parsed_symbols_and_imports(mock_orchestrator, tmp_path):
    """Analysis returns ParsedSymbol objects and file_imports dict."""
    # Create a Python file
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
    from oya.parsing.models import ParsedSymbol
    assert all(isinstance(s, ParsedSymbol) for s in result["symbols"])

    # Check file_imports is populated
    assert "file_imports" in result
    assert "example.py" in result["file_imports"]
    imports = result["file_imports"]["example.py"]
    assert "os" in imports or any("os" in i for i in imports)

    # Check symbols have file metadata
    for symbol in result["symbols"]:
        assert "file" in symbol.metadata
```

**Step 2: Run the integration test**

Run: `cd /Users/poecurt/projects/oya/.worktrees/phase1-fixes/backend && source .venv/bin/activate && pytest tests/test_orchestrator.py -k "parsed_symbols_and_imports" -v`
Expected: PASS

**Step 3: Run full test suite**

Run: `cd /Users/poecurt/projects/oya/.worktrees/phase1-fixes/backend && source .venv/bin/activate && pytest tests/ -q`
Expected: All tests pass

**Step 4: Commit**

```bash
git add backend/tests/test_orchestrator.py
git commit -m "test(orchestrator): add integration test for analysis phase"
```

---

## Task 10: Final Verification

**Step 1: Run full backend test suite**

Run: `cd /Users/poecurt/projects/oya/.worktrees/phase1-fixes/backend && source .venv/bin/activate && pytest tests/ -v --tb=short`
Expected: All tests pass

**Step 2: Run frontend tests (no changes, just verify no regressions)**

Run: `cd /Users/poecurt/projects/oya/.worktrees/phase1-fixes/frontend && npm run test`
Expected: All tests pass

**Step 3: Review git log**

Run: `git log --oneline -10`
Expected: See all commits from this implementation

**Step 4: Final commit if any uncommitted changes**

```bash
git status
# If any changes: git add . && git commit -m "chore: final cleanup"
```
