# Dead Code Detection Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a "Code Health" wiki page that identifies potentially unused code symbols by analyzing the existing call graph.

**Architecture:** Pure analysis of existing graph data (nodes.json, edges.json). No new parsing. The deadcode module reads the graph, computes unused symbols, and generates a markdown page written alongside other wiki pages during generation.

**Tech Stack:** Python, networkx (already in use), pytest

---

## Task 1: Create DeadcodeReport Data Model

**Files:**
- Create: `backend/src/oya/generation/deadcode.py`
- Test: `backend/tests/test_deadcode.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_deadcode.py
"""Tests for dead code detection."""

import pytest
from oya.generation.deadcode import DeadcodeReport, UnusedSymbol


def test_deadcode_report_structure():
    """DeadcodeReport contains categorized unused symbols."""
    report = DeadcodeReport(
        probably_unused_functions=[
            UnusedSymbol(
                name="old_func",
                file_path="utils/legacy.py",
                line=42,
                symbol_type="function",
            )
        ],
        probably_unused_classes=[],
        possibly_unused_functions=[],
        possibly_unused_classes=[],
        possibly_unused_variables=[],
    )

    assert len(report.probably_unused_functions) == 1
    assert report.probably_unused_functions[0].name == "old_func"
```

**Step 2: Run test to verify it fails**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_deadcode.py::test_deadcode_report_structure -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'oya.generation.deadcode'"

**Step 3: Write minimal implementation**

```python
# backend/src/oya/generation/deadcode.py
"""Dead code detection for wiki generation.

Analyzes the code graph to identify symbols with no incoming references,
categorizing them as "probably unused" (zero edges) or "possibly unused"
(only low-confidence edges).
"""

from dataclasses import dataclass, field


@dataclass
class UnusedSymbol:
    """A symbol identified as potentially unused."""

    name: str
    file_path: str
    line: int
    symbol_type: str  # "function", "class", "method", or "variable"


@dataclass
class DeadcodeReport:
    """Report of potentially unused code symbols.

    Attributes:
        probably_unused_functions: Functions with no incoming edges.
        probably_unused_classes: Classes with no incoming edges.
        possibly_unused_functions: Functions with only low-confidence edges.
        possibly_unused_classes: Classes with only low-confidence edges.
        possibly_unused_variables: Variables with only low-confidence edges.
    """

    probably_unused_functions: list[UnusedSymbol] = field(default_factory=list)
    probably_unused_classes: list[UnusedSymbol] = field(default_factory=list)
    possibly_unused_functions: list[UnusedSymbol] = field(default_factory=list)
    possibly_unused_classes: list[UnusedSymbol] = field(default_factory=list)
    possibly_unused_variables: list[UnusedSymbol] = field(default_factory=list)
```

**Step 4: Run test to verify it passes**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_deadcode.py::test_deadcode_report_structure -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/oya/generation/deadcode.py backend/tests/test_deadcode.py
git commit -m "feat(deadcode): add DeadcodeReport and UnusedSymbol data models"
```

---

## Task 2: Implement Exclusion Pattern Matching

**Files:**
- Modify: `backend/src/oya/generation/deadcode.py`
- Test: `backend/tests/test_deadcode.py`

**Step 1: Write the failing test**

```python
# Add to backend/tests/test_deadcode.py

def test_is_excluded_test_functions():
    """Test functions are excluded."""
    from oya.generation.deadcode import is_excluded

    assert is_excluded("test_login") is True
    assert is_excluded("login_test") is True
    assert is_excluded("test_") is True


def test_is_excluded_dunders():
    """Python dunders are excluded."""
    from oya.generation.deadcode import is_excluded

    assert is_excluded("__init__") is True
    assert is_excluded("__str__") is True
    assert is_excluded("__all__") is True


def test_is_excluded_entry_points():
    """Entry point names are excluded."""
    from oya.generation.deadcode import is_excluded

    assert is_excluded("main") is True
    assert is_excluded("app") is True


def test_is_excluded_private():
    """Private symbols (underscore prefix) are excluded."""
    from oya.generation.deadcode import is_excluded

    assert is_excluded("_internal_helper") is True
    assert is_excluded("_cache") is True


def test_is_excluded_normal_names():
    """Normal function names are not excluded."""
    from oya.generation.deadcode import is_excluded

    assert is_excluded("calculate_total") is False
    assert is_excluded("UserService") is False
    assert is_excluded("process_data") is False
```

**Step 2: Run test to verify it fails**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_deadcode.py::test_is_excluded_test_functions -v`
Expected: FAIL with "cannot import name 'is_excluded'"

**Step 3: Write minimal implementation**

```python
# Add to backend/src/oya/generation/deadcode.py after the dataclasses

import re

# Patterns for symbols that should never be flagged as dead code
EXCLUDED_PATTERNS = [
    re.compile(r"^test_"),      # Test functions (prefix)
    re.compile(r"_test$"),      # Test functions (suffix)
    re.compile(r"^__.*__$"),    # Python dunders
    re.compile(r"^main$"),      # Entry points
    re.compile(r"^app$"),       # FastAPI/Flask app
    re.compile(r"^_"),          # Private by convention
]


def is_excluded(name: str) -> bool:
    """Check if a symbol name should be excluded from dead code detection.

    Args:
        name: Symbol name to check.

    Returns:
        True if the symbol should be excluded.
    """
    return any(pattern.match(name) for pattern in EXCLUDED_PATTERNS)
```

**Step 4: Run tests to verify they pass**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_deadcode.py -k "is_excluded" -v`
Expected: All 5 tests PASS

**Step 5: Commit**

```bash
git add backend/src/oya/generation/deadcode.py backend/tests/test_deadcode.py
git commit -m "feat(deadcode): add is_excluded function for pattern matching"
```

---

## Task 3: Implement Core Analysis Function

**Files:**
- Modify: `backend/src/oya/generation/deadcode.py`
- Test: `backend/tests/test_deadcode.py`

**Step 1: Write the failing test**

```python
# Add to backend/tests/test_deadcode.py
import json
from pathlib import Path


def test_analyze_deadcode_finds_unused_function(tmp_path):
    """analyze_deadcode identifies function with no incoming edges."""
    from oya.generation.deadcode import analyze_deadcode

    # Create graph files
    graph_dir = tmp_path / "graph"
    graph_dir.mkdir()

    nodes = [
        {
            "id": "main.py::main",
            "name": "main",
            "type": "function",
            "file_path": "main.py",
            "line_start": 1,
            "line_end": 10,
            "docstring": None,
            "signature": None,
            "parent": None,
        },
        {
            "id": "utils.py::unused_helper",
            "name": "unused_helper",
            "type": "function",
            "file_path": "utils.py",
            "line_start": 5,
            "line_end": 15,
            "docstring": None,
            "signature": None,
            "parent": None,
        },
        {
            "id": "utils.py::used_helper",
            "name": "used_helper",
            "type": "function",
            "file_path": "utils.py",
            "line_start": 20,
            "line_end": 30,
            "docstring": None,
            "signature": None,
            "parent": None,
        },
    ]

    edges = [
        {
            "source": "main.py::main",
            "target": "utils.py::used_helper",
            "type": "calls",
            "confidence": 0.9,
            "line": 5,
        }
    ]

    (graph_dir / "nodes.json").write_text(json.dumps(nodes))
    (graph_dir / "edges.json").write_text(json.dumps(edges))

    report = analyze_deadcode(graph_dir)

    # unused_helper has no incoming edges, should be flagged
    assert len(report.probably_unused_functions) == 1
    assert report.probably_unused_functions[0].name == "unused_helper"
    assert report.probably_unused_functions[0].file_path == "utils.py"
    assert report.probably_unused_functions[0].line == 5

    # used_helper and main should not be flagged
    # (main is excluded, used_helper has incoming edge)


def test_analyze_deadcode_excludes_test_functions(tmp_path):
    """Test functions are not flagged even without callers."""
    from oya.generation.deadcode import analyze_deadcode

    graph_dir = tmp_path / "graph"
    graph_dir.mkdir()

    nodes = [
        {
            "id": "tests/test_utils.py::test_something",
            "name": "test_something",
            "type": "function",
            "file_path": "tests/test_utils.py",
            "line_start": 1,
            "line_end": 10,
            "docstring": None,
            "signature": None,
            "parent": None,
        },
    ]

    (graph_dir / "nodes.json").write_text(json.dumps(nodes))
    (graph_dir / "edges.json").write_text(json.dumps([]))

    report = analyze_deadcode(graph_dir)

    assert len(report.probably_unused_functions) == 0


def test_analyze_deadcode_low_confidence_to_possibly(tmp_path):
    """Symbols with only low-confidence edges go to 'possibly unused'."""
    from oya.generation.deadcode import analyze_deadcode

    graph_dir = tmp_path / "graph"
    graph_dir.mkdir()

    nodes = [
        {
            "id": "a.py::caller",
            "name": "caller",
            "type": "function",
            "file_path": "a.py",
            "line_start": 1,
            "line_end": 10,
            "docstring": None,
            "signature": None,
            "parent": None,
        },
        {
            "id": "b.py::maybe_used",
            "name": "maybe_used",
            "type": "function",
            "file_path": "b.py",
            "line_start": 1,
            "line_end": 10,
            "docstring": None,
            "signature": None,
            "parent": None,
        },
    ]

    edges = [
        {
            "source": "a.py::caller",
            "target": "b.py::maybe_used",
            "type": "calls",
            "confidence": 0.5,  # Below threshold
            "line": 5,
        }
    ]

    (graph_dir / "nodes.json").write_text(json.dumps(nodes))
    (graph_dir / "edges.json").write_text(json.dumps(edges))

    report = analyze_deadcode(graph_dir)

    # maybe_used has only low-confidence edge, goes to possibly_unused
    assert len(report.probably_unused_functions) == 0
    assert len(report.possibly_unused_functions) == 1
    assert report.possibly_unused_functions[0].name == "maybe_used"
```

**Step 2: Run test to verify it fails**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_deadcode.py::test_analyze_deadcode_finds_unused_function -v`
Expected: FAIL with "cannot import name 'analyze_deadcode'"

**Step 3: Write minimal implementation**

```python
# Add to backend/src/oya/generation/deadcode.py

from pathlib import Path
import json

CONFIDENCE_THRESHOLD = 0.7


def analyze_deadcode(graph_dir: Path) -> DeadcodeReport:
    """Analyze graph data to find potentially unused symbols.

    Args:
        graph_dir: Directory containing nodes.json and edges.json.

    Returns:
        DeadcodeReport with categorized unused symbols.
    """
    graph_dir = Path(graph_dir)

    # Load nodes
    nodes_file = graph_dir / "nodes.json"
    if not nodes_file.exists():
        return DeadcodeReport()

    with open(nodes_file) as f:
        nodes = json.load(f)

    # Load edges
    edges_file = graph_dir / "edges.json"
    edges = []
    if edges_file.exists():
        with open(edges_file) as f:
            edges = json.load(f)

    # Build sets of targets by confidence level
    high_confidence_targets: set[str] = set()
    low_confidence_targets: set[str] = set()

    for edge in edges:
        target = edge.get("target", "")
        confidence = edge.get("confidence", 0.0)
        if confidence >= CONFIDENCE_THRESHOLD:
            high_confidence_targets.add(target)
        else:
            low_confidence_targets.add(target)

    # Categorize nodes
    report = DeadcodeReport()

    for node in nodes:
        node_id = node.get("id", "")
        name = node.get("name", "")
        node_type = node.get("type", "")
        file_path = node.get("file_path", "")
        line = node.get("line_start", 0)

        # Skip excluded names
        if is_excluded(name):
            continue

        # Check if this node has incoming edges
        has_high_conf = node_id in high_confidence_targets
        has_low_conf = node_id in low_confidence_targets

        if has_high_conf:
            # Used with high confidence - not dead code
            continue

        symbol = UnusedSymbol(
            name=name,
            file_path=file_path,
            line=line,
            symbol_type=node_type,
        )

        if has_low_conf:
            # Only low-confidence edges - possibly unused
            if node_type == "function" or node_type == "method":
                report.possibly_unused_functions.append(symbol)
            elif node_type == "class":
                report.possibly_unused_classes.append(symbol)
            elif node_type == "variable":
                report.possibly_unused_variables.append(symbol)
        else:
            # No edges at all - probably unused
            # Variables only go to possibly (design decision)
            if node_type == "variable":
                report.possibly_unused_variables.append(symbol)
            elif node_type == "function" or node_type == "method":
                report.probably_unused_functions.append(symbol)
            elif node_type == "class":
                report.probably_unused_classes.append(symbol)

    return report
```

**Step 4: Run tests to verify they pass**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_deadcode.py -k "analyze_deadcode" -v`
Expected: All 3 tests PASS

**Step 5: Commit**

```bash
git add backend/src/oya/generation/deadcode.py backend/tests/test_deadcode.py
git commit -m "feat(deadcode): implement analyze_deadcode core function"
```

---

## Task 4: Implement Markdown Page Generation

**Files:**
- Modify: `backend/src/oya/generation/deadcode.py`
- Test: `backend/tests/test_deadcode.py`

**Step 1: Write the failing test**

```python
# Add to backend/tests/test_deadcode.py

def test_generate_deadcode_page_content():
    """generate_deadcode_page creates markdown with tables."""
    from oya.generation.deadcode import generate_deadcode_page, DeadcodeReport, UnusedSymbol

    report = DeadcodeReport(
        probably_unused_functions=[
            UnusedSymbol(
                name="old_func",
                file_path="utils/legacy.py",
                line=42,
                symbol_type="function",
            ),
        ],
        probably_unused_classes=[
            UnusedSymbol(
                name="DeprecatedParser",
                file_path="parsing/old.py",
                line=10,
                symbol_type="class",
            ),
        ],
        possibly_unused_functions=[],
        possibly_unused_classes=[],
        possibly_unused_variables=[
            UnusedSymbol(
                name="OLD_CONFIG",
                file_path="config.py",
                line=5,
                symbol_type="variable",
            ),
        ],
    )

    content = generate_deadcode_page(report)

    # Check header
    assert "# Potential Dead Code" in content

    # Check probably unused section
    assert "## Probably Unused" in content
    assert "### Functions (1)" in content
    assert "old_func" in content
    assert "utils/legacy.py" in content

    # Check classes section
    assert "### Classes (1)" in content
    assert "DeprecatedParser" in content

    # Check possibly unused section
    assert "## Possibly Unused" in content
    assert "### Variables (1)" in content
    assert "OLD_CONFIG" in content


def test_generate_deadcode_page_empty_sections():
    """Empty sections show 'None detected'."""
    from oya.generation.deadcode import generate_deadcode_page, DeadcodeReport

    report = DeadcodeReport()

    content = generate_deadcode_page(report)

    assert "None detected" in content


def test_generate_deadcode_page_links_to_files():
    """Symbol names link to file pages."""
    from oya.generation.deadcode import generate_deadcode_page, DeadcodeReport, UnusedSymbol

    report = DeadcodeReport(
        probably_unused_functions=[
            UnusedSymbol(
                name="old_func",
                file_path="utils/legacy.py",
                line=42,
                symbol_type="function",
            ),
        ],
    )

    content = generate_deadcode_page(report)

    # Check for markdown link format
    assert "[old_func](files/utils/legacy.py#L42)" in content
```

**Step 2: Run test to verify it fails**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_deadcode.py::test_generate_deadcode_page_content -v`
Expected: FAIL with "cannot import name 'generate_deadcode_page'"

**Step 3: Write minimal implementation**

```python
# Add to backend/src/oya/generation/deadcode.py

def generate_deadcode_page(report: DeadcodeReport) -> str:
    """Generate markdown content for the Code Health wiki page.

    Args:
        report: DeadcodeReport with categorized unused symbols.

    Returns:
        Markdown string for the wiki page.
    """
    lines = [
        "# Potential Dead Code",
        "",
        "Analysis of code symbols with no detected callers. Review before removing -",
        "some may be entry points, event handlers, or called via reflection.",
        "",
        "**Note:** Cross-language calls are not tracked. A Python function called from",
        "JavaScript (or vice versa) may appear unused.",
        "",
    ]

    # Probably Unused section
    lines.append("## Probably Unused")
    lines.append("")
    lines.append("These symbols have no incoming references in the codebase.")
    lines.append("")

    _add_symbol_section(lines, "Functions", report.probably_unused_functions)
    _add_symbol_section(lines, "Classes", report.probably_unused_classes)

    # Possibly Unused section
    lines.append("## Possibly Unused")
    lines.append("")
    lines.append("These symbols only have low-confidence references (may be false positives).")
    lines.append("")

    _add_symbol_section(lines, "Functions", report.possibly_unused_functions)
    _add_symbol_section(lines, "Classes", report.possibly_unused_classes)
    _add_symbol_section(lines, "Variables", report.possibly_unused_variables)

    return "\n".join(lines)


def _add_symbol_section(lines: list[str], title: str, symbols: list[UnusedSymbol]) -> None:
    """Add a section for a category of symbols.

    Args:
        lines: List of lines to append to.
        title: Section title (e.g., "Functions").
        symbols: List of unused symbols.
    """
    count = len(symbols)
    lines.append(f"### {title} ({count})")
    lines.append("")

    if not symbols:
        lines.append("None detected.")
        lines.append("")
        return

    # Table header
    lines.append("| Name | File | Line |")
    lines.append("|------|------|------|")

    # Sort by file path, then line for determinism
    sorted_symbols = sorted(symbols, key=lambda s: (s.file_path, s.line))

    for symbol in sorted_symbols:
        # Link to file page with line anchor
        link = f"[{symbol.name}](files/{symbol.file_path}#L{symbol.line})"
        lines.append(f"| {link} | {symbol.file_path} | {symbol.line} |")

    lines.append("")
```

**Step 4: Run tests to verify they pass**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_deadcode.py -k "generate_deadcode_page" -v`
Expected: All 3 tests PASS

**Step 5: Commit**

```bash
git add backend/src/oya/generation/deadcode.py backend/tests/test_deadcode.py
git commit -m "feat(deadcode): implement generate_deadcode_page markdown writer"
```

---

## Task 5: Integrate with Orchestrator

**Files:**
- Modify: `backend/src/oya/generation/orchestrator.py`
- Test: `backend/tests/test_orchestrator.py`

**Step 1: Write the failing test**

```python
# Add to backend/tests/test_orchestrator.py (find appropriate location)

@pytest.mark.asyncio
async def test_orchestrator_generates_code_health_page(tmp_path, mock_llm_client):
    """Orchestrator generates code-health.md from graph analysis."""
    from oya.generation.orchestrator import GenerationOrchestrator
    from oya.repo.git_repo import GitRepo

    # Set up minimal repo structure
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    (repo_path / "main.py").write_text("def main(): pass\ndef unused(): pass")

    wiki_path = tmp_path / "wiki"

    # Create mock repo
    class MockRepo:
        path = repo_path

        def get_head_commit(self):
            return "abc123def456"

    # Create mock db
    class MockDb:
        def execute(self, *args):
            class Cursor:
                def fetchone(self):
                    return None
            return Cursor()

        def commit(self):
            pass

    orchestrator = GenerationOrchestrator(
        llm_client=mock_llm_client,
        repo=MockRepo(),
        db=MockDb(),
        wiki_path=wiki_path,
    )

    await orchestrator.run()

    # Check code-health.md was generated
    code_health_path = wiki_path / "code-health.md"
    assert code_health_path.exists(), "code-health.md should be generated"

    content = code_health_path.read_text()
    assert "Potential Dead Code" in content
```

**Step 2: Run test to verify it fails**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_orchestrator.py::test_orchestrator_generates_code_health_page -v`
Expected: FAIL (code-health.md not generated)

**Step 3: Write minimal implementation**

Add to `orchestrator.py` imports at top:

```python
from oya.generation.deadcode import analyze_deadcode, generate_deadcode_page
```

Add to `orchestrator.py` in the `run()` method, after workflows phase (around line 652) and before the return statement:

```python
        # Phase 8: Code Health (dead code analysis)
        # Only regenerate if synthesis was regenerated (same cascade as architecture/overview)
        if should_regenerate_synthesis:
            await self._emit_progress(
                progress_callback,
                GenerationProgress(
                    phase=GenerationPhase.SYNTHESIS,  # Reuse synthesis phase for now
                    message="Analyzing code health...",
                ),
            )
            code_health_page = self._generate_code_health_page()
            if code_health_page:
                await self._save_page_with_frontmatter(code_health_page)
```

Add helper method to `GenerationOrchestrator` class:

```python
    def _generate_code_health_page(self) -> GeneratedPage | None:
        """Generate the Code Health page from graph analysis.

        Returns:
            GeneratedPage with dead code analysis, or None if graph is empty.
        """
        report = analyze_deadcode(self.graph_path)

        # Check if report has any content
        total = (
            len(report.probably_unused_functions)
            + len(report.probably_unused_classes)
            + len(report.possibly_unused_functions)
            + len(report.possibly_unused_classes)
            + len(report.possibly_unused_variables)
        )

        if total == 0:
            # Generate empty page to indicate analysis ran
            pass

        content = generate_deadcode_page(report)
        word_count = len(content.split())

        return GeneratedPage(
            content=content,
            page_type="code-health",
            path="code-health.md",
            word_count=word_count,
            target=None,
        )
```

**Step 4: Run test to verify it passes**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_orchestrator.py::test_orchestrator_generates_code_health_page -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/oya/generation/orchestrator.py backend/tests/test_orchestrator.py
git commit -m "feat(deadcode): integrate code health generation into orchestrator"
```

---

## Task 6: Add Code Health to Navigation

**Files:**
- Modify: `backend/src/oya/api/routers/wiki.py` (if tree is built there)
- Test: Manual verification via API

**Step 1: Verify wiki tree includes code-health.md**

The wiki tree is typically built by scanning the wiki directory. Since we're writing `code-health.md` to the wiki root, it should automatically appear. Let's verify by checking how the tree endpoint works.

```bash
cd backend && grep -r "tree" src/oya/api/routers/wiki.py | head -20
```

**Step 2: Manual verification**

After running the orchestrator:
1. Start the backend: `uvicorn oya.main:app --reload`
2. Trigger wiki generation for a repo
3. Check `GET /api/wiki/tree` includes `code-health.md`
4. Check `GET /api/wiki/page?path=code-health.md` returns the content

**Step 3: Document in design if changes needed**

If the tree doesn't automatically pick up the new page, we'll need to modify the tree builder. Based on typical implementations, files in the wiki root should be included.

**Step 4: Commit (if changes needed)**

```bash
git add backend/src/oya/api/routers/wiki.py
git commit -m "feat(deadcode): ensure code-health.md appears in wiki tree"
```

---

## Task 7: Run Full Test Suite

**Files:** None (verification only)

**Step 1: Run all backend tests**

```bash
cd backend && source .venv/bin/activate && pytest
```

Expected: All tests pass (1063+ tests)

**Step 2: Run linting**

```bash
cd backend && ruff check src/oya/generation/deadcode.py
cd backend && ruff format src/oya/generation/deadcode.py --check
```

Expected: No issues

**Step 3: Commit any fixes**

If tests fail or linting issues found, fix and commit.

---

## Task 8: Integration Test with Real Wiki Generation

**Files:** None (manual verification)

**Step 1: Generate wiki for Oya itself**

```bash
# Start backend
cd backend && source .venv/bin/activate && uvicorn oya.main:app --reload
```

**Step 2: Trigger generation via frontend or API**

```bash
curl -X POST http://localhost:8000/api/repos/init -H "Content-Type: application/json" \
  -d '{"url": "file:///Users/poecurt/projects/oya"}'
```

**Step 3: Verify code-health.md**

```bash
cat ~/.oya/wikis/*/meta/.oyawiki/wiki/code-health.md
```

Expected: Page with "Potential Dead Code" header and tables of unused symbols.

**Step 4: Final commit**

```bash
git add -A
git commit -m "feat(deadcode): complete dead code detection feature"
```

---

## Summary

| Task | Description | Files |
|------|-------------|-------|
| 1 | Data models | deadcode.py, test_deadcode.py |
| 2 | Exclusion patterns | deadcode.py, test_deadcode.py |
| 3 | Core analysis | deadcode.py, test_deadcode.py |
| 4 | Markdown generation | deadcode.py, test_deadcode.py |
| 5 | Orchestrator integration | orchestrator.py, test_orchestrator.py |
| 6 | Navigation | wiki.py (if needed) |
| 7 | Full test suite | verification |
| 8 | Integration test | manual verification |
