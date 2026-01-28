# Call-Site Synopses Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Extract real code snippets from call sites to show how files are actually used in the codebase, replacing AI-generated examples when real usage exists.

**Architecture:** Query the existing code graph for edges targeting a file's symbols, extract ~20-line snippets around call sites, prioritize production code over tests, and integrate as Tier 2 in the synopsis priority chain (docs > call-site > AI).

**Tech Stack:** Python 3.11+, NetworkX (existing graph), pytest for TDD

**Design Doc:** `docs/plans/2026-01-28-call-site-synopses-design.md`

---

## Task 1: Add CallSite Dataclass to Graph Models

**Files:**
- Modify: `backend/src/oya/graph/models.py`
- Test: `backend/tests/test_graph_models.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_graph_models.py`:

```python
def test_call_site_dataclass():
    """CallSite holds call location metadata."""
    from oya.graph.models import CallSite

    site = CallSite(
        caller_file="handler.py",
        caller_symbol="process_request",
        line=42,
        target_symbol="verify_token",
    )

    assert site.caller_file == "handler.py"
    assert site.caller_symbol == "process_request"
    assert site.line == 42
    assert site.target_symbol == "verify_token"
```

**Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_graph_models.py::test_call_site_dataclass -v`
Expected: FAIL with "cannot import name 'CallSite'"

**Step 3: Write minimal implementation**

Add to `backend/src/oya/graph/models.py` after the `Edge` class:

```python
@dataclass
class CallSite:
    """Location where a symbol is called from."""

    caller_file: str      # File containing the call
    caller_symbol: str    # Function/method making the call
    line: int             # Exact line of the call
    target_symbol: str    # What's being called
```

**Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_graph_models.py::test_call_site_dataclass -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/oya/graph/models.py backend/tests/test_graph_models.py
git commit -m "feat(graph): add CallSite dataclass for call location tracking"
```

---

## Task 2: Add get_call_sites Query Function

**Files:**
- Modify: `backend/src/oya/graph/query.py`
- Test: `backend/tests/test_graph_query.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_graph_query.py`:

```python
def test_get_call_sites_for_file(sample_graph):
    """get_call_sites returns all calls to symbols in a target file."""
    from oya.graph.query import get_call_sites

    sites = get_call_sites(sample_graph, "db.py")

    assert len(sites) == 2
    # Both process_request and verify_token call get_user
    caller_symbols = [s.caller_symbol for s in sites]
    assert "process_request" in caller_symbols
    assert "verify_token" in caller_symbols
    # All target the same file
    assert all(s.target_symbol == "get_user" for s in sites)


def test_get_call_sites_includes_line_numbers(sample_graph):
    """get_call_sites includes exact line numbers from edges."""
    from oya.graph.query import get_call_sites

    sites = get_call_sites(sample_graph, "db.py")

    lines = {s.line for s in sites}
    assert 20 in lines  # process_request calls get_user at line 20
    assert 10 in lines  # verify_token calls get_user at line 10


def test_get_call_sites_empty_for_uncalled_file(sample_graph):
    """get_call_sites returns empty list for files with no callers."""
    from oya.graph.query import get_call_sites

    sites = get_call_sites(sample_graph, "handler.py")

    # handler.py::process_request has no incoming calls
    assert sites == []


def test_get_call_sites_nonexistent_file(sample_graph):
    """get_call_sites returns empty list for files not in graph."""
    from oya.graph.query import get_call_sites

    sites = get_call_sites(sample_graph, "nonexistent.py")

    assert sites == []
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_graph_query.py::test_get_call_sites_for_file -v`
Expected: FAIL with "cannot import name 'get_call_sites'"

**Step 3: Write minimal implementation**

Add to `backend/src/oya/graph/query.py`:

```python
from oya.graph.models import Node, NodeType, Edge, EdgeType, Subgraph, CallSite


def get_call_sites(
    graph: nx.DiGraph,
    target_file: str,
) -> list[CallSite]:
    """Find all call sites targeting symbols defined in a file.

    Args:
        graph: The code graph with edges containing line numbers.
        target_file: Path to the file whose callers we want.

    Returns:
        List of CallSite objects with caller file, symbol, line, and target.
    """
    sites = []

    for source, target, edge_data in graph.edges(data=True):
        # Only consider call edges
        if edge_data.get("type") != "calls":
            continue

        # Check if target is in the target file
        target_node_data = graph.nodes.get(target, {})
        if target_node_data.get("file_path") != target_file:
            continue

        # Get source node data for caller info
        source_node_data = graph.nodes.get(source, {})
        caller_file = source_node_data.get("file_path", "")
        caller_symbol = source_node_data.get("name", "")
        target_symbol = target_node_data.get("name", "")
        line = edge_data.get("line", 0)

        sites.append(
            CallSite(
                caller_file=caller_file,
                caller_symbol=caller_symbol,
                line=line,
                target_symbol=target_symbol,
            )
        )

    return sites
```

**Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_graph_query.py -k "call_sites" -v`
Expected: All 4 tests PASS

**Step 5: Commit**

```bash
git add backend/src/oya/graph/query.py backend/tests/test_graph_query.py
git commit -m "feat(graph): add get_call_sites query for finding file callers"
```

---

## Task 3: Create Snippet Extraction Module - Test File Detection

**Files:**
- Create: `backend/src/oya/generation/snippets.py`
- Create: `backend/tests/test_snippets.py`

**Step 1: Write the failing test**

Create `backend/tests/test_snippets.py`:

```python
"""Tests for call-site snippet extraction."""

import pytest


class TestIsTestFile:
    """Tests for is_test_file detection."""

    def test_test_prefix(self):
        """Detects test_*.py files."""
        from oya.generation.snippets import is_test_file

        assert is_test_file("test_something.py") is True
        assert is_test_file("src/test_module.py") is True

    def test_test_suffix(self):
        """Detects *_test.py files."""
        from oya.generation.snippets import is_test_file

        assert is_test_file("something_test.py") is True
        assert is_test_file("module_test.py") is True

    def test_spec_suffix(self):
        """Detects *_spec.py files."""
        from oya.generation.snippets import is_test_file

        assert is_test_file("something_spec.py") is True

    def test_tests_directory(self):
        """Detects files in tests/ directories."""
        from oya.generation.snippets import is_test_file

        assert is_test_file("tests/test_foo.py") is True
        assert is_test_file("tests/helpers.py") is True
        assert is_test_file("src/tests/utils.py") is True

    def test_test_directory(self):
        """Detects files in test/ directories."""
        from oya.generation.snippets import is_test_file

        assert is_test_file("test/test_bar.py") is True

    def test_spec_directory(self):
        """Detects files in spec/ directories."""
        from oya.generation.snippets import is_test_file

        assert is_test_file("spec/foo_spec.py") is True

    def test_dunder_tests_directory(self):
        """Detects files in __tests__/ directories (JS convention)."""
        from oya.generation.snippets import is_test_file

        assert is_test_file("src/__tests__/component.test.js") is True

    def test_conftest(self):
        """Detects conftest.py files."""
        from oya.generation.snippets import is_test_file

        assert is_test_file("conftest.py") is True
        assert is_test_file("tests/conftest.py") is True

    def test_fixtures(self):
        """Detects fixtures.py files."""
        from oya.generation.snippets import is_test_file

        assert is_test_file("fixtures.py") is True

    def test_production_files(self):
        """Does not flag production files as tests."""
        from oya.generation.snippets import is_test_file

        assert is_test_file("main.py") is False
        assert is_test_file("src/handler.py") is False
        assert is_test_file("api/routes.py") is False
        assert is_test_file("utils/testing_utils.py") is False  # "testing" in name but not a test
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_snippets.py::TestIsTestFile -v`
Expected: FAIL with "No module named 'oya.generation.snippets'"

**Step 3: Write minimal implementation**

Create `backend/src/oya/generation/snippets.py`:

```python
"""Call-site snippet extraction for synopsis generation."""

import re
from pathlib import Path


def is_test_file(file_path: str) -> bool:
    """Check if a file is a test file.

    Patterns detected:
    - test_*.py, *_test.py, *_spec.py
    - Paths containing: tests/, test/, spec/, __tests__/
    - Special files: conftest.py, fixtures.py

    Args:
        file_path: Path to the file.

    Returns:
        True if the file appears to be a test file.
    """
    path = Path(file_path)
    name = path.name

    # Check filename patterns
    if name.startswith("test_"):
        return True
    if name.endswith("_test.py") or name.endswith("_spec.py"):
        return True
    if name.endswith(".test.js") or name.endswith(".spec.js"):
        return True
    if name.endswith(".test.ts") or name.endswith(".spec.ts"):
        return True

    # Check special files
    if name in ("conftest.py", "fixtures.py"):
        return True

    # Check directory patterns
    parts = path.parts
    test_dirs = {"tests", "test", "spec", "__tests__"}
    if any(part in test_dirs for part in parts):
        return True

    return False
```

**Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_snippets.py::TestIsTestFile -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add backend/src/oya/generation/snippets.py backend/tests/test_snippets.py
git commit -m "feat(snippets): add is_test_file detection function"
```

---

## Task 4: Add Snippet Extraction Function

**Files:**
- Modify: `backend/src/oya/generation/snippets.py`
- Modify: `backend/tests/test_snippets.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_snippets.py`:

```python
class TestExtractCallSnippet:
    """Tests for extract_call_snippet function."""

    @pytest.fixture
    def sample_file_contents(self):
        """Sample file contents for testing."""
        return {
            "handler.py": """\
import logging
from auth import verify_token
from db import get_user

logger = logging.getLogger(__name__)


def process_request(request):
    \"\"\"Process an incoming request.\"\"\"
    token = request.headers.get("Authorization")
    user = verify_token(token)
    if not user:
        return {"error": "Unauthorized"}

    data = get_user(user.id)
    return {"user": data}


def other_function():
    pass
""",
        }

    def test_extracts_context_around_call(self, sample_file_contents):
        """Extracts lines around the call site."""
        from oya.generation.snippets import extract_call_snippet

        # Call to verify_token is on line 12
        snippet = extract_call_snippet(
            file_path="handler.py",
            call_line=12,
            file_contents=sample_file_contents,
        )

        assert "verify_token(token)" in snippet
        assert "token = request.headers.get" in snippet

    def test_includes_function_signature(self, sample_file_contents):
        """Includes the containing function's signature."""
        from oya.generation.snippets import extract_call_snippet

        snippet = extract_call_snippet(
            file_path="handler.py",
            call_line=12,
            file_contents=sample_file_contents,
        )

        assert "def process_request(request):" in snippet

    def test_respects_context_limits(self, sample_file_contents):
        """Respects context_before and context_after parameters."""
        from oya.generation.snippets import extract_call_snippet

        snippet = extract_call_snippet(
            file_path="handler.py",
            call_line=12,
            file_contents=sample_file_contents,
            context_before=2,
            context_after=2,
        )

        lines = snippet.strip().split("\n")
        # Should have roughly 5 lines (2 before, call line, 2 after)
        assert len(lines) <= 6

    def test_returns_empty_for_missing_file(self, sample_file_contents):
        """Returns empty string for missing file."""
        from oya.generation.snippets import extract_call_snippet

        snippet = extract_call_snippet(
            file_path="nonexistent.py",
            call_line=10,
            file_contents=sample_file_contents,
        )

        assert snippet == ""

    def test_handles_line_out_of_bounds(self, sample_file_contents):
        """Handles line number beyond file length."""
        from oya.generation.snippets import extract_call_snippet

        snippet = extract_call_snippet(
            file_path="handler.py",
            call_line=1000,
            file_contents=sample_file_contents,
        )

        # Should return something reasonable, not crash
        assert isinstance(snippet, str)
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_snippets.py::TestExtractCallSnippet -v`
Expected: FAIL with "cannot import name 'extract_call_snippet'"

**Step 3: Write minimal implementation**

Add to `backend/src/oya/generation/snippets.py`:

```python
def extract_call_snippet(
    file_path: str,
    call_line: int,
    file_contents: dict[str, str],
    context_before: int = 10,
    context_after: int = 10,
) -> str:
    """Extract code context around a call site.

    Args:
        file_path: Path to the file containing the call.
        call_line: Line number of the call (1-indexed).
        file_contents: Dict mapping file paths to their contents.
        context_before: Maximum lines to include before the call.
        context_after: Maximum lines to include after the call.

    Returns:
        Code snippet as string, or empty string if file not found.
    """
    content = file_contents.get(file_path)
    if not content:
        return ""

    lines = content.split("\n")
    total_lines = len(lines)

    # Convert to 0-indexed
    call_idx = call_line - 1

    # Handle out of bounds
    if call_idx < 0 or call_idx >= total_lines:
        # Return last few lines if line is beyond file
        if call_idx >= total_lines and total_lines > 0:
            start = max(0, total_lines - context_after)
            return "\n".join(lines[start:])
        return ""

    # Calculate window
    start = max(0, call_idx - context_before)
    end = min(total_lines, call_idx + context_after + 1)

    # Expand upward to find function/class definition if within range
    for i in range(call_idx, max(start - 1, -1), -1):
        line = lines[i].lstrip()
        if line.startswith("def ") or line.startswith("class ") or line.startswith("async def "):
            start = i
            break

    return "\n".join(lines[start:end])
```

**Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_snippets.py::TestExtractCallSnippet -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add backend/src/oya/generation/snippets.py backend/tests/test_snippets.py
git commit -m "feat(snippets): add extract_call_snippet function"
```

---

## Task 5: Add Call Site Selection Function

**Files:**
- Modify: `backend/src/oya/generation/snippets.py`
- Modify: `backend/tests/test_snippets.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_snippets.py`:

```python
class TestSelectBestCallSite:
    """Tests for select_best_call_site function."""

    def test_prefers_production_over_test(self):
        """Production files are preferred over test files."""
        from oya.generation.snippets import select_best_call_site
        from oya.graph.models import CallSite

        sites = [
            CallSite(caller_file="tests/test_auth.py", caller_symbol="test_verify", line=10, target_symbol="verify"),
            CallSite(caller_file="handler.py", caller_symbol="process", line=20, target_symbol="verify"),
        ]

        best, others = select_best_call_site(sites, {})

        assert best is not None
        assert best.caller_file == "handler.py"
        assert len(others) == 1

    def test_returns_test_if_only_option(self):
        """Returns test file if it's the only caller."""
        from oya.generation.snippets import select_best_call_site
        from oya.graph.models import CallSite

        sites = [
            CallSite(caller_file="tests/test_auth.py", caller_symbol="test_verify", line=10, target_symbol="verify"),
        ]

        best, others = select_best_call_site(sites, {})

        assert best is not None
        assert best.caller_file == "tests/test_auth.py"
        assert others == []

    def test_returns_none_for_empty_list(self):
        """Returns None when no call sites provided."""
        from oya.generation.snippets import select_best_call_site

        best, others = select_best_call_site([], {})

        assert best is None
        assert others == []

    def test_prefers_different_files(self):
        """When multiple callers, prefers showing diversity."""
        from oya.generation.snippets import select_best_call_site
        from oya.graph.models import CallSite

        sites = [
            CallSite(caller_file="handler.py", caller_symbol="func1", line=10, target_symbol="util"),
            CallSite(caller_file="handler.py", caller_symbol="func2", line=20, target_symbol="util"),
            CallSite(caller_file="api.py", caller_symbol="route", line=30, target_symbol="util"),
        ]

        best, others = select_best_call_site(sites, {})

        # Should pick one, others should include remaining
        assert best is not None
        assert len(others) == 2

    def test_limits_other_callers(self):
        """Limits other callers list to reasonable size."""
        from oya.generation.snippets import select_best_call_site
        from oya.graph.models import CallSite

        # Create 20 call sites
        sites = [
            CallSite(caller_file=f"file{i}.py", caller_symbol=f"func{i}", line=i, target_symbol="util")
            for i in range(20)
        ]

        best, others = select_best_call_site(sites, {})

        assert best is not None
        # Should limit others to reasonable number (design says 5)
        assert len(others) <= 5
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_snippets.py::TestSelectBestCallSite -v`
Expected: FAIL with "cannot import name 'select_best_call_site'"

**Step 3: Write minimal implementation**

Add to `backend/src/oya/generation/snippets.py`:

```python
from oya.graph.models import CallSite


def select_best_call_site(
    call_sites: list[CallSite],
    file_contents: dict[str, str],
) -> tuple[CallSite | None, list[CallSite]]:
    """Select the best call site for synopsis, return others for reference.

    Selection criteria:
    1. Filter out test files (prefer production code)
    2. If only test files exist, use best test example
    3. Prefer diversity (different files over same file)

    Args:
        call_sites: List of CallSite objects.
        file_contents: Dict mapping file paths to contents (for future heuristics).

    Returns:
        Tuple of (best_site, other_sites) where best_site may be None if no callers.
        other_sites is limited to 5 entries.
    """
    if not call_sites:
        return None, []

    # Separate production and test files
    production = [s for s in call_sites if not is_test_file(s.caller_file)]
    tests = [s for s in call_sites if is_test_file(s.caller_file)]

    # Prefer production code
    candidates = production if production else tests

    if not candidates:
        return None, []

    # Sort by file path for determinism, pick first as best
    candidates.sort(key=lambda s: (s.caller_file, s.line))
    best = candidates[0]

    # Build others list - prefer different files
    others = []
    seen_files = {best.caller_file}

    for site in candidates[1:]:
        if len(others) >= 5:
            break
        # Prefer sites from different files
        if site.caller_file not in seen_files:
            others.append(site)
            seen_files.add(site.caller_file)

    # Fill remaining slots if we have space
    for site in candidates[1:]:
        if len(others) >= 5:
            break
        if site not in others:
            others.append(site)

    return best, others
```

**Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_snippets.py::TestSelectBestCallSite -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add backend/src/oya/generation/snippets.py backend/tests/test_snippets.py
git commit -m "feat(snippets): add select_best_call_site function"
```

---

## Task 6: Add Call-Site Synopsis Prompt Templates

**Files:**
- Modify: `backend/src/oya/generation/prompts.py`
- Test: `backend/tests/test_prompts.py` (if exists, otherwise manual verification)

**Step 1: Add new prompt constants**

Add to `backend/src/oya/generation/prompts.py` after `SYNOPSIS_INSTRUCTIONS_WITHOUT_EXTRACTED` (around line 569):

```python
SYNOPSIS_INSTRUCTIONS_WITH_CALL_SITE = """
A real usage example from this codebase has been extracted and is shown above.

**Include it verbatim in the Synopsis section**, formatted as:

## 2. Synopsis

**From `{caller_file}` line {line}:**
```{language}
{snippet}
```

{other_callers_note}

Do NOT modify the extracted code. It shows actual usage in this codebase.
"""

SYNOPSIS_NO_CALLERS_NOTE = """
**Note:** No internal callers found in this codebase. This may be:
- A public API intended for external consumers
- An entry point (CLI command, API route, etc.)
- Potentially unused code
"""

SYNOPSIS_TEST_ONLY_NOTE = """
**Note:** Only test usage found in this codebase.
"""


def format_call_site_synopsis(
    snippet: str,
    caller_file: str,
    line: int,
    language: str,
    other_callers: list[tuple[str, int]] | None = None,
) -> str:
    """Format a call-site synopsis for inclusion in prompt.

    Args:
        snippet: The extracted code snippet.
        caller_file: File where the call was found.
        line: Line number of the call.
        language: Programming language for syntax highlighting.
        other_callers: Optional list of (file, line) tuples for other callers.

    Returns:
        Formatted synopsis string ready for prompt inclusion.
    """
    other_note = ""
    if other_callers:
        refs = [f"`{f}:{l}`" for f, l in other_callers[:5]]
        if len(other_callers) > 5:
            refs.append(f"and {len(other_callers) - 5} more")
        other_note = f"\nAlso called from: {', '.join(refs)}"

    return f"""**From `{caller_file}` line {line}:**
```{language}
{snippet}
```{other_note}"""
```

**Step 2: Verify syntax is correct**

Run: `cd backend && python -c "from oya.generation.prompts import SYNOPSIS_INSTRUCTIONS_WITH_CALL_SITE, format_call_site_synopsis; print('OK')"`
Expected: Prints "OK" with no errors

**Step 3: Commit**

```bash
git add backend/src/oya/generation/prompts.py
git commit -m "feat(prompts): add call-site synopsis templates"
```

---

## Task 7: Update FileGenerator to Accept Call-Site Synopsis

**Files:**
- Modify: `backend/src/oya/generation/file.py`
- Modify: `backend/src/oya/generation/prompts.py`
- Test: `backend/tests/test_file_generator.py` (if exists)

**Step 1: Update get_file_prompt signature**

Modify `get_file_prompt` in `backend/src/oya/generation/prompts.py` (around line 1226):

```python
def get_file_prompt(
    file_path: str,
    content: str,
    symbols: list[dict[str, Any]],
    imports: list[str],
    architecture_summary: str,
    language: str = "",
    notes: list[dict[str, Any]] | None = None,
    synopsis: str | None = None,
    call_site_synopsis: str | None = None,
) -> str:
    """Generate a prompt for creating a file documentation page.

    Args:
        file_path: Path to the file.
        content: Content of the file.
        symbols: List of symbol dictionaries defined in the file.
        imports: List of import statements.
        architecture_summary: Summary of how this file fits in the architecture.
        language: Programming language for syntax highlighting.
        notes: Optional list of correction notes affecting this file.
        synopsis: Optional extracted synopsis from source file documentation (Tier 1).
        call_site_synopsis: Optional pre-formatted call-site synopsis (Tier 2).

    Returns:
        The rendered prompt string.
    """
    # Priority: doc synopsis > call-site synopsis > AI-generated
    if synopsis:
        synopsis_instructions = SYNOPSIS_INSTRUCTIONS_WITH_EXTRACTED
        lang_tag = language if language else ""
        extracted_synopsis = f"```{lang_tag}\n{synopsis}\n```"
    elif call_site_synopsis:
        synopsis_instructions = "A real usage example from this codebase is provided above. Include it verbatim in the Synopsis section. Do NOT modify the extracted code."
        extracted_synopsis = call_site_synopsis
    else:
        synopsis_instructions = SYNOPSIS_INSTRUCTIONS_WITHOUT_EXTRACTED
        extracted_synopsis = "No synopsis found in source file documentation."

    prompt = FILE_TEMPLATE.render(
        file_path=file_path,
        content=content,
        symbols=_format_symbols(symbols),
        imports=_format_imports(imports),
        architecture_summary=architecture_summary or "No architecture context provided.",
        language=language,
        extracted_synopsis=extracted_synopsis,
        synopsis_instructions=synopsis_instructions,
    )

    if notes:
        prompt = _add_notes_to_prompt(prompt, notes)

    return prompt
```

**Step 2: Update FileGenerator.generate signature**

Modify `FileGenerator.generate` in `backend/src/oya/generation/file.py`:

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
    notes: list[dict] | None = None,
    synopsis: str | None = None,
    call_site_synopsis: str | None = None,
) -> tuple[GeneratedPage, FileSummary]:
```

And update the `get_file_prompt` call inside the method:

```python
prompt = get_file_prompt(
    file_path=file_path,
    content=content,
    symbols=symbols,
    imports=imports,
    architecture_summary=architecture_summary,
    language=language,
    notes=notes,
    synopsis=synopsis,
    call_site_synopsis=call_site_synopsis,
)
```

**Step 3: Verify the changes compile**

Run: `cd backend && python -c "from oya.generation.file import FileGenerator; print('OK')"`
Expected: Prints "OK"

**Step 4: Commit**

```bash
git add backend/src/oya/generation/file.py backend/src/oya/generation/prompts.py
git commit -m "feat(file): add call_site_synopsis parameter to FileGenerator"
```

---

## Task 8: Wire Up Call-Site Extraction in Orchestrator

**Files:**
- Modify: `backend/src/oya/generation/orchestrator.py`

**Step 1: Add imports at top of file**

Add these imports to `backend/src/oya/generation/orchestrator.py`:

```python
from oya.graph.query import get_call_sites
from oya.generation.snippets import select_best_call_site, extract_call_snippet, is_test_file
from oya.generation.prompts import format_call_site_synopsis
```

**Step 2: Update generate_file_page helper**

Find the `generate_file_page` nested function in `_run_files` (around line 1430) and update it:

```python
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
                    # Detect language from file extension
                    ext = Path(file_path).suffix.lower()
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
                        call_site_synopsis += "\n\n**Note:** Only test usage found in this codebase."

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
```

**Step 3: Ensure graph is available before file generation**

Find where `_run_files` is called and ensure `graph` is accessible. Add at the start of `_run_files` method, after getting analysis data:

```python
# Get graph for call-site extraction (built in analysis phase)
graph = analysis.get("graph")
```

**Step 4: Verify the changes compile**

Run: `cd backend && python -c "from oya.generation.orchestrator import WikiOrchestrator; print('OK')"`
Expected: Prints "OK"

**Step 5: Commit**

```bash
git add backend/src/oya/generation/orchestrator.py
git commit -m "feat(orchestrator): integrate call-site synopsis extraction in file generation"
```

---

## Task 9: Add Integration Tests

**Files:**
- Create or modify: `backend/tests/test_call_site_synopsis_integration.py`

**Step 1: Write integration test**

Create `backend/tests/test_call_site_synopsis_integration.py`:

```python
"""Integration tests for call-site synopsis feature."""

import pytest
import networkx as nx

from oya.graph.models import CallSite
from oya.graph.query import get_call_sites
from oya.generation.snippets import (
    is_test_file,
    extract_call_snippet,
    select_best_call_site,
)
from oya.generation.prompts import format_call_site_synopsis


@pytest.fixture
def realistic_graph():
    """Create a realistic graph for integration testing."""
    G = nx.DiGraph()

    # Add file nodes
    G.add_node(
        "api/routes.py::handle_login",
        name="handle_login",
        type="function",
        file_path="api/routes.py",
        line_start=50,
        line_end=70,
    )
    G.add_node(
        "auth/verify.py::verify_token",
        name="verify_token",
        type="function",
        file_path="auth/verify.py",
        line_start=10,
        line_end=30,
    )
    G.add_node(
        "tests/test_auth.py::test_verify_token",
        name="test_verify_token",
        type="function",
        file_path="tests/test_auth.py",
        line_start=20,
        line_end=35,
    )

    # Production code calls verify_token
    G.add_edge(
        "api/routes.py::handle_login",
        "auth/verify.py::verify_token",
        type="calls",
        confidence=0.95,
        line=55,
    )

    # Test code also calls verify_token
    G.add_edge(
        "tests/test_auth.py::test_verify_token",
        "auth/verify.py::verify_token",
        type="calls",
        confidence=0.9,
        line=25,
    )

    return G


@pytest.fixture
def file_contents():
    """Sample file contents."""
    return {
        "api/routes.py": """\
from flask import request, jsonify
from auth.verify import verify_token


@app.route("/login", methods=["POST"])
def handle_login():
    token = request.headers.get("Authorization")
    user = verify_token(token)
    if not user:
        return jsonify({"error": "Invalid token"}), 401
    return jsonify({"user_id": user.id})
""",
        "tests/test_auth.py": """\
import pytest
from auth.verify import verify_token


def test_verify_token():
    result = verify_token("valid_token")
    assert result is not None
""",
    }


class TestEndToEndCallSiteSynopsis:
    """End-to-end tests for call-site synopsis generation."""

    def test_full_pipeline_prefers_production(self, realistic_graph, file_contents):
        """Full pipeline extracts production code over test code."""
        # 1. Query call sites
        sites = get_call_sites(realistic_graph, "auth/verify.py")
        assert len(sites) == 2

        # 2. Select best call site
        best, others = select_best_call_site(sites, file_contents)
        assert best is not None
        assert best.caller_file == "api/routes.py"  # Production preferred
        assert len(others) == 1

        # 3. Extract snippet
        snippet = extract_call_snippet(
            best.caller_file,
            best.line,
            file_contents,
        )
        assert "verify_token(token)" in snippet

        # 4. Format for prompt
        formatted = format_call_site_synopsis(
            snippet=snippet,
            caller_file=best.caller_file,
            line=best.line,
            language="python",
            other_callers=[(s.caller_file, s.line) for s in others],
        )
        assert "api/routes.py" in formatted
        assert "```python" in formatted
        assert "tests/test_auth.py" in formatted  # Listed as other caller

    def test_pipeline_with_only_test_callers(self, realistic_graph, file_contents):
        """Pipeline works when only test files call the target."""
        # Create graph where only tests call the target
        G = nx.DiGraph()
        G.add_node(
            "utils/helper.py::format_date",
            name="format_date",
            type="function",
            file_path="utils/helper.py",
            line_start=1,
            line_end=10,
        )
        G.add_node(
            "tests/test_utils.py::test_format",
            name="test_format",
            type="function",
            file_path="tests/test_utils.py",
            line_start=5,
            line_end=15,
        )
        G.add_edge(
            "tests/test_utils.py::test_format",
            "utils/helper.py::format_date",
            type="calls",
            confidence=0.9,
            line=10,
        )

        sites = get_call_sites(G, "utils/helper.py")
        best, others = select_best_call_site(sites, {})

        # Should still select test file when it's the only option
        assert best is not None
        assert is_test_file(best.caller_file)

    def test_pipeline_with_no_callers(self, realistic_graph, file_contents):
        """Pipeline handles files with no callers gracefully."""
        sites = get_call_sites(realistic_graph, "api/routes.py")

        # api/routes.py has no incoming calls in this graph
        assert sites == []

        best, others = select_best_call_site(sites, file_contents)
        assert best is None
        assert others == []
```

**Step 2: Run integration tests**

Run: `cd backend && pytest tests/test_call_site_synopsis_integration.py -v`
Expected: All tests PASS

**Step 3: Commit**

```bash
git add backend/tests/test_call_site_synopsis_integration.py
git commit -m "test: add integration tests for call-site synopsis feature"
```

---

## Task 10: Ensure Graph is Passed Through Analysis

**Files:**
- Modify: `backend/src/oya/generation/orchestrator.py` (verify graph propagation)

**Step 1: Verify graph is in analysis dict**

Check that the analysis phase stores the graph. Search for where `analysis` dict is populated in `_run_analysis` and ensure graph is included:

```python
# In _run_analysis method, ensure this returns the graph:
analysis["graph"] = graph  # NetworkX DiGraph from graph builder
```

**Step 2: Run full test suite**

Run: `cd backend && pytest -v`
Expected: All existing tests PASS

**Step 3: Commit if any changes were needed**

```bash
git add backend/src/oya/generation/orchestrator.py
git commit -m "fix(orchestrator): ensure graph is passed through analysis dict"
```

---

## Summary

| Task | Description | Files |
|------|-------------|-------|
| 1 | Add CallSite dataclass | `graph/models.py` |
| 2 | Add get_call_sites query | `graph/query.py` |
| 3 | Create snippets module + test detection | `generation/snippets.py` |
| 4 | Add snippet extraction | `generation/snippets.py` |
| 5 | Add call site selection | `generation/snippets.py` |
| 6 | Add prompt templates | `generation/prompts.py` |
| 7 | Update FileGenerator | `generation/file.py`, `prompts.py` |
| 8 | Wire up in orchestrator | `generation/orchestrator.py` |
| 9 | Integration tests | `tests/test_call_site_synopsis_integration.py` |
| 10 | Verify graph propagation | `generation/orchestrator.py` |

**Estimated commits:** 10
