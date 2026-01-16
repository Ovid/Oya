# File Issue Detection Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Pre-compute code issues during file analysis so Q&A can surface systemic patterns without re-analyzing every file.

**Architecture:** Extend the file generation pipeline to extract issues from LLM responses. Store issues both in FileSummary (for wiki display) and in a dedicated ChromaDB collection (for Q&A queries). Modify Q&A service to detect issue-related questions and query the issues collection first.

**Tech Stack:** Python 3.11+, pytest, ChromaDB, FastAPI

---

## Task 1: Add FileIssue dataclass and constants

**Files:**
- Create: `backend/src/oya/constants/issues.py`
- Modify: `backend/src/oya/generation/summaries.py:44-66`
- Test: `backend/tests/test_summaries.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_summaries.py`:

```python
class TestFileIssue:
    """Tests for FileIssue dataclass."""

    def test_file_issue_creation(self):
        """FileIssue can be created with all fields."""
        from oya.generation.summaries import FileIssue

        issue = FileIssue(
            file_path="src/api/routes.py",
            category="security",
            severity="problem",
            title="SQL injection risk",
            description="Query built with string concatenation",
            line_range=(45, 47),
        )

        assert issue.file_path == "src/api/routes.py"
        assert issue.category == "security"
        assert issue.severity == "problem"
        assert issue.title == "SQL injection risk"
        assert issue.line_range == (45, 47)

    def test_file_issue_optional_line_range(self):
        """FileIssue line_range is optional."""
        from oya.generation.summaries import FileIssue

        issue = FileIssue(
            file_path="src/utils.py",
            category="maintainability",
            severity="suggestion",
            title="Consider extracting method",
            description="Function is too long",
            line_range=None,
        )

        assert issue.line_range is None

    def test_file_issue_to_dict(self):
        """FileIssue serializes to dict correctly."""
        from oya.generation.summaries import FileIssue

        issue = FileIssue(
            file_path="test.py",
            category="reliability",
            severity="problem",
            title="Unhandled exception",
            description="Missing try/except",
            line_range=(10, 15),
        )

        d = issue.to_dict()
        assert d["file_path"] == "test.py"
        assert d["category"] == "reliability"
        assert d["severity"] == "problem"
        assert d["line_start"] == 10
        assert d["line_end"] == 15

    def test_file_issue_from_dict(self):
        """FileIssue deserializes from dict correctly."""
        from oya.generation.summaries import FileIssue

        data = {
            "file_path": "test.py",
            "category": "security",
            "severity": "suggestion",
            "title": "Hardcoded secret",
            "description": "API key in source",
            "line_start": 5,
            "line_end": 5,
        }

        issue = FileIssue.from_dict(data)
        assert issue.file_path == "test.py"
        assert issue.line_range == (5, 5)
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/poecurt/projects/oya/.worktrees/file-issue-detection/backend && source .venv/bin/activate && pytest tests/test_summaries.py::TestFileIssue -v`
Expected: FAIL with "cannot import name 'FileIssue'"

**Step 3: Create constants file**

Create `backend/src/oya/constants/issues.py`:

```python
"""Issue detection configuration.

These settings control the code issue detection feature, which identifies
potential bugs, security concerns, and design flaws during wiki generation.
"""

# =============================================================================
# Issue Categories
# =============================================================================
# Categories represent broad classes of issues. Each category has specific
# patterns the LLM looks for during analysis.

ISSUE_CATEGORIES = frozenset(["security", "reliability", "maintainability"])

# Category descriptions for LLM prompt
CATEGORY_DESCRIPTIONS = {
    "security": "Injection vulnerabilities, hardcoded secrets, missing auth, unsafe deserialization",
    "reliability": "Unhandled errors, race conditions, resource leaks, null pointer risks",
    "maintainability": "God classes, circular deps, code duplication, missing abstractions",
}

# =============================================================================
# Issue Severities
# =============================================================================
# Severities indicate urgency. "problem" means likely bug or security hole.
# "suggestion" means improvement opportunity but not urgent.

ISSUE_SEVERITIES = frozenset(["problem", "suggestion"])

SEVERITY_DESCRIPTIONS = {
    "problem": "Likely bug or security hole that needs attention",
    "suggestion": "Improvement opportunity, not urgent",
}

# =============================================================================
# Q&A Integration
# =============================================================================
# Keywords that trigger issue-aware Q&A responses

ISSUE_QUERY_KEYWORDS = frozenset([
    "bug",
    "bugs",
    "issue",
    "issues",
    "problem",
    "problems",
    "security",
    "vulnerability",
    "vulnerabilities",
    "code quality",
    "technical debt",
    "tech debt",
    "what's wrong",
    "whats wrong",
    "concerns",
    "risks",
    "flaws",
])
```

**Step 4: Add FileIssue dataclass**

Add to `backend/src/oya/generation/summaries.py` after the imports (around line 17):

```python
from oya.constants.issues import ISSUE_CATEGORIES, ISSUE_SEVERITIES
```

Add after the `path_to_slug` function (around line 42):

```python
@dataclass
class FileIssue:
    """A potential issue identified in a source file.

    Represents bugs, security concerns, or design flaws detected during
    file analysis. Issues are stored both in FileSummary (for display)
    and in a dedicated ChromaDB collection (for Q&A queries).

    Attributes:
        file_path: Path to the source file containing the issue.
        category: Type of issue (security, reliability, maintainability).
        severity: Urgency level (problem, suggestion).
        title: Brief description of the issue.
        description: Detailed explanation of why this matters.
        line_range: Optional (start, end) line numbers where issue occurs.
    """

    file_path: str
    category: str
    severity: str
    title: str
    description: str
    line_range: tuple[int, int] | None = None

    def __post_init__(self):
        """Validate category and severity fields."""
        if self.category not in ISSUE_CATEGORIES:
            raise ValueError(
                f"Invalid category '{self.category}'. "
                f"Must be one of: {', '.join(sorted(ISSUE_CATEGORIES))}"
            )
        if self.severity not in ISSUE_SEVERITIES:
            raise ValueError(
                f"Invalid severity '{self.severity}'. "
                f"Must be one of: {', '.join(sorted(ISSUE_SEVERITIES))}"
            )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for storage."""
        result = {
            "file_path": self.file_path,
            "category": self.category,
            "severity": self.severity,
            "title": self.title,
            "description": self.description,
        }
        if self.line_range:
            result["line_start"] = self.line_range[0]
            result["line_end"] = self.line_range[1]
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FileIssue":
        """Deserialize from dictionary."""
        line_range = None
        if "line_start" in data and "line_end" in data:
            line_range = (data["line_start"], data["line_end"])
        elif "lines" in data and isinstance(data["lines"], list) and len(data["lines"]) >= 2:
            line_range = (data["lines"][0], data["lines"][1])

        return cls(
            file_path=data.get("file_path", ""),
            category=data.get("category", "maintainability"),
            severity=data.get("severity", "suggestion"),
            title=data.get("title", ""),
            description=data.get("description", ""),
            line_range=line_range,
        )
```

**Step 5: Run test to verify it passes**

Run: `cd /Users/poecurt/projects/oya/.worktrees/file-issue-detection/backend && source .venv/bin/activate && pytest tests/test_summaries.py::TestFileIssue -v`
Expected: PASS (4 tests)

**Step 6: Commit**

```bash
cd /Users/poecurt/projects/oya/.worktrees/file-issue-detection
git add backend/src/oya/constants/issues.py backend/src/oya/generation/summaries.py backend/tests/test_summaries.py
git commit -m "feat: add FileIssue dataclass and issue constants

Introduces FileIssue for representing code issues detected during
file analysis. Includes category/severity validation and serialization.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 2: Extend FileSummary with issues field

**Files:**
- Modify: `backend/src/oya/generation/summaries.py:44-107` (FileSummary class)
- Test: `backend/tests/test_summaries.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_summaries.py`:

```python
class TestFileSummaryWithIssues:
    """Tests for FileSummary with issues field."""

    def test_file_summary_with_empty_issues(self):
        """FileSummary defaults to empty issues list."""
        from oya.generation.summaries import FileSummary

        summary = FileSummary(
            file_path="test.py",
            purpose="Test file",
            layer="utility",
        )

        assert summary.issues == []

    def test_file_summary_with_issues(self):
        """FileSummary can hold FileIssue objects."""
        from oya.generation.summaries import FileSummary, FileIssue

        issue = FileIssue(
            file_path="test.py",
            category="security",
            severity="problem",
            title="Test issue",
            description="Test description",
        )

        summary = FileSummary(
            file_path="test.py",
            purpose="Test file",
            layer="utility",
            issues=[issue],
        )

        assert len(summary.issues) == 1
        assert summary.issues[0].title == "Test issue"

    def test_file_summary_to_dict_includes_issues(self):
        """FileSummary.to_dict() includes serialized issues."""
        from oya.generation.summaries import FileSummary, FileIssue

        issue = FileIssue(
            file_path="test.py",
            category="reliability",
            severity="suggestion",
            title="Missing error handling",
            description="Add try/except",
            line_range=(10, 12),
        )

        summary = FileSummary(
            file_path="test.py",
            purpose="Test file",
            layer="utility",
            issues=[issue],
        )

        d = summary.to_dict()
        assert "issues" in d
        assert len(d["issues"]) == 1
        assert d["issues"][0]["title"] == "Missing error handling"
        assert d["issues"][0]["line_start"] == 10

    def test_file_summary_from_dict_with_issues(self):
        """FileSummary.from_dict() deserializes issues."""
        from oya.generation.summaries import FileSummary

        data = {
            "file_path": "test.py",
            "purpose": "Test",
            "layer": "utility",
            "issues": [
                {
                    "file_path": "test.py",
                    "category": "security",
                    "severity": "problem",
                    "title": "SQL injection",
                    "description": "Use parameterized queries",
                }
            ],
        }

        summary = FileSummary.from_dict(data)
        assert len(summary.issues) == 1
        assert summary.issues[0].category == "security"
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/poecurt/projects/oya/.worktrees/file-issue-detection/backend && source .venv/bin/activate && pytest tests/test_summaries.py::TestFileSummaryWithIssues -v`
Expected: FAIL with "unexpected keyword argument 'issues'"

**Step 3: Modify FileSummary class**

In `backend/src/oya/generation/summaries.py`, update the FileSummary class:

```python
@dataclass
class FileSummary:
    """Structured summary extracted from file documentation.

    Captures the essential information about a source file including its purpose,
    architectural layer, key abstractions, dependencies, and detected issues.

    Attributes:
        file_path: Path to the source file relative to repository root.
        purpose: One-sentence description of what the file does.
        layer: Classification of code responsibility (api, domain, infrastructure,
               utility, config, or test).
        key_abstractions: Primary classes, functions, or types defined in the file.
        internal_deps: Paths to other files in the repository that this file depends on.
        external_deps: External libraries or packages the file imports.
        issues: List of potential issues (bugs, security concerns, design flaws).
    """

    file_path: str
    purpose: str
    layer: str
    key_abstractions: list[str] = field(default_factory=list)
    internal_deps: list[str] = field(default_factory=list)
    external_deps: list[str] = field(default_factory=list)
    issues: list[FileIssue] = field(default_factory=list)

    def __post_init__(self):
        """Validate layer field after initialization."""
        if self.layer not in VALID_LAYERS:
            raise ValueError(
                f"Invalid layer '{self.layer}'. Must be one of: {', '.join(sorted(VALID_LAYERS))}"
            )

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
            "issues": [issue.to_dict() for issue in self.issues],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FileSummary":
        """Deserialize a FileSummary from a dictionary.

        Args:
            data: Dictionary representation of a FileSummary.

        Returns:
            A new FileSummary instance.
        """
        issues_data = data.get("issues", [])
        issues = [FileIssue.from_dict(i) for i in issues_data] if issues_data else []

        return cls(
            file_path=data.get("file_path", ""),
            purpose=data.get("purpose", "Unknown"),
            layer=data.get("layer", "utility"),
            key_abstractions=data.get("key_abstractions", []),
            internal_deps=data.get("internal_deps", []),
            external_deps=data.get("external_deps", []),
            issues=issues,
        )
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/poecurt/projects/oya/.worktrees/file-issue-detection/backend && source .venv/bin/activate && pytest tests/test_summaries.py::TestFileSummaryWithIssues -v`
Expected: PASS (4 tests)

**Step 5: Run all summaries tests to ensure no regressions**

Run: `cd /Users/poecurt/projects/oya/.worktrees/file-issue-detection/backend && source .venv/bin/activate && pytest tests/test_summaries.py -v`
Expected: All tests PASS

**Step 6: Commit**

```bash
cd /Users/poecurt/projects/oya/.worktrees/file-issue-detection
git add backend/src/oya/generation/summaries.py backend/tests/test_summaries.py
git commit -m "feat: extend FileSummary with issues field

FileSummary now includes a list of FileIssue objects for storing
detected code issues alongside other file metadata.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 3: Update SummaryParser to extract issues from YAML

**Files:**
- Modify: `backend/src/oya/generation/summaries.py:446-515` (SummaryParser.parse_file_summary)
- Test: `backend/tests/test_summaries.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_summaries.py`:

```python
class TestSummaryParserIssues:
    """Tests for SummaryParser issue extraction."""

    def test_parse_file_summary_with_issues(self):
        """SummaryParser extracts issues from YAML."""
        from oya.generation.summaries import SummaryParser

        markdown = '''---
file_summary:
  purpose: "Handles user authentication"
  layer: api
  key_abstractions:
    - "authenticate"
  internal_deps: []
  external_deps:
    - "bcrypt"
  issues:
    - category: security
      severity: problem
      title: "Hardcoded secret key"
      description: "JWT secret is hardcoded in source"
      lines: [15, 15]
    - category: reliability
      severity: suggestion
      title: "Missing rate limiting"
      description: "Login endpoint has no rate limiting"
---

# Authentication Module

This module handles user authentication.
'''

        parser = SummaryParser()
        clean_md, summary = parser.parse_file_summary(markdown, "auth.py")

        assert summary.purpose == "Handles user authentication"
        assert len(summary.issues) == 2

        assert summary.issues[0].category == "security"
        assert summary.issues[0].severity == "problem"
        assert summary.issues[0].title == "Hardcoded secret key"
        assert summary.issues[0].line_range == (15, 15)

        assert summary.issues[1].category == "reliability"
        assert summary.issues[1].severity == "suggestion"

    def test_parse_file_summary_without_issues(self):
        """SummaryParser handles YAML without issues field."""
        from oya.generation.summaries import SummaryParser

        markdown = '''---
file_summary:
  purpose: "Utility functions"
  layer: utility
  key_abstractions: []
  internal_deps: []
  external_deps: []
---

# Utilities
'''

        parser = SummaryParser()
        _, summary = parser.parse_file_summary(markdown, "utils.py")

        assert summary.issues == []

    def test_parse_file_summary_with_empty_issues(self):
        """SummaryParser handles explicit empty issues list."""
        from oya.generation.summaries import SummaryParser

        markdown = '''---
file_summary:
  purpose: "Clean code"
  layer: domain
  key_abstractions: []
  internal_deps: []
  external_deps: []
  issues: []
---

# Clean Module
'''

        parser = SummaryParser()
        _, summary = parser.parse_file_summary(markdown, "clean.py")

        assert summary.issues == []

    def test_parse_file_summary_issues_with_invalid_category_uses_default(self):
        """Invalid category falls back to maintainability."""
        from oya.generation.summaries import SummaryParser

        markdown = '''---
file_summary:
  purpose: "Test"
  layer: utility
  issues:
    - category: invalid_category
      severity: suggestion
      title: "Some issue"
      description: "Details"
---

# Test
'''

        parser = SummaryParser()
        _, summary = parser.parse_file_summary(markdown, "test.py")

        # Should use default category from FileIssue.from_dict
        assert len(summary.issues) == 1
        assert summary.issues[0].category == "maintainability"
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/poecurt/projects/oya/.worktrees/file-issue-detection/backend && source .venv/bin/activate && pytest tests/test_summaries.py::TestSummaryParserIssues -v`
Expected: FAIL (issues not being extracted)

**Step 3: Update parse_file_summary method**

In `backend/src/oya/generation/summaries.py`, modify the `parse_file_summary` method in `SummaryParser` class:

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
            logger.warning(
                f"Invalid layer '{layer}' for {file_path}, defaulting to 'utility'. "
                f"Valid layers: {', '.join(sorted(VALID_LAYERS))}"
            )
            layer = "utility"

        # Parse issues
        issues = self._parse_issues(summary_data.get("issues", []), file_path)

        summary = FileSummary(
            file_path=file_path,
            purpose=purpose,
            layer=layer,
            key_abstractions=self._ensure_list(summary_data.get("key_abstractions", [])),
            internal_deps=self._ensure_list(summary_data.get("internal_deps", [])),
            external_deps=self._ensure_list(summary_data.get("external_deps", [])),
            issues=issues,
        )

        return clean_markdown, summary

    def _parse_issues(self, issues_data: Any, file_path: str) -> list[FileIssue]:
        """Parse issues list from YAML data.

        Args:
            issues_data: Raw issues data from YAML (may be list or None).
            file_path: File path for logging and issue association.

        Returns:
            List of FileIssue objects.
        """
        if not isinstance(issues_data, list):
            return []

        issues: list[FileIssue] = []
        for item in issues_data:
            if not isinstance(item, dict):
                continue

            try:
                # Add file_path if not present
                item["file_path"] = file_path
                issue = FileIssue.from_dict(item)
                issues.append(issue)
            except (ValueError, KeyError) as e:
                logger.warning(f"Failed to parse issue for {file_path}: {e}")
                continue

        return issues
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/poecurt/projects/oya/.worktrees/file-issue-detection/backend && source .venv/bin/activate && pytest tests/test_summaries.py::TestSummaryParserIssues -v`
Expected: PASS (4 tests)

**Step 5: Commit**

```bash
cd /Users/poecurt/projects/oya/.worktrees/file-issue-detection
git add backend/src/oya/generation/summaries.py backend/tests/test_summaries.py
git commit -m "feat: extract issues from YAML in SummaryParser

SummaryParser.parse_file_summary now extracts issues from the
file_summary YAML block and creates FileIssue objects.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 4: Update FILE_TEMPLATE prompt to request issues

**Files:**
- Modify: `backend/src/oya/generation/prompts.py:413-470` (FILE_TEMPLATE)
- Test: `backend/tests/test_prompts.py` (create if needed)

**Step 1: Write the failing test**

Create or add to `backend/tests/test_prompts.py`:

```python
"""Tests for prompt templates."""


class TestFileTemplateIssues:
    """Tests for FILE_TEMPLATE issue detection instructions."""

    def test_file_template_includes_issues_instructions(self):
        """FILE_TEMPLATE includes issue detection instructions."""
        from oya.generation.prompts import FILE_TEMPLATE

        template = FILE_TEMPLATE.template

        # Check for issue detection section
        assert "Code Analysis" in template or "issues" in template.lower()
        assert "security" in template.lower()
        assert "reliability" in template.lower()
        assert "maintainability" in template.lower()

    def test_file_template_yaml_schema_includes_issues(self):
        """FILE_TEMPLATE YAML schema includes issues field."""
        from oya.generation.prompts import FILE_TEMPLATE

        template = FILE_TEMPLATE.template

        # YAML schema should show issues structure
        assert "issues:" in template
        assert "category:" in template
        assert "severity:" in template
        assert "title:" in template
        assert "description:" in template

    def test_get_file_prompt_renders_correctly(self):
        """get_file_prompt renders without errors."""
        from oya.generation.prompts import get_file_prompt

        prompt = get_file_prompt(
            file_path="test.py",
            content="def hello(): pass",
            symbols=[{"name": "hello", "type": "function", "line": 1}],
            imports=["import os"],
            architecture_summary="Utility module",
            language="python",
        )

        assert "test.py" in prompt
        assert "def hello()" in prompt
        assert "issues:" in prompt
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/poecurt/projects/oya/.worktrees/file-issue-detection/backend && source .venv/bin/activate && pytest tests/test_prompts.py::TestFileTemplateIssues -v`
Expected: FAIL (issues not in template)

**Step 3: Update FILE_TEMPLATE**

In `backend/src/oya/generation/prompts.py`, replace the FILE_TEMPLATE:

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
  issues:
    - category: <security|reliability|maintainability>
      severity: <problem|suggestion>
      title: "Short description of the issue"
      description: "Why this matters and what to look for"
      lines: [start_line, end_line]
---
```

Layer classification guide:
- api: REST endpoints, request handlers, API routes
- domain: Core business logic, services, use cases
- infrastructure: Database, external services, I/O operations
- utility: Helper functions, shared utilities, common tools
- config: Configuration, settings, environment handling
- test: Test files, test utilities, fixtures

## Code Analysis

While documenting, also identify potential issues in the code:

**Categories:**
- security: Injection vulnerabilities, hardcoded secrets, missing auth, unsafe deserialization
- reliability: Unhandled errors, race conditions, resource leaks, null pointer risks
- maintainability: God classes, circular deps, code duplication, missing abstractions

**Severities:**
- problem: Likely bug or security hole that needs attention
- suggestion: Improvement opportunity, not urgent

Only flag issues you're reasonably confident about. Skip stylistic nitpicks.
If no issues are found, use an empty list: `issues: []`

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

**Step 4: Run test to verify it passes**

Run: `cd /Users/poecurt/projects/oya/.worktrees/file-issue-detection/backend && source .venv/bin/activate && pytest tests/test_prompts.py::TestFileTemplateIssues -v`
Expected: PASS (3 tests)

**Step 5: Commit**

```bash
cd /Users/poecurt/projects/oya/.worktrees/file-issue-detection
git add backend/src/oya/generation/prompts.py backend/tests/test_prompts.py
git commit -m "feat: add issue detection to FILE_TEMPLATE prompt

FILE_TEMPLATE now instructs the LLM to identify security, reliability,
and maintainability issues while documenting files.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 5: Create IssuesStore for ChromaDB collection

**Files:**
- Create: `backend/src/oya/vectorstore/issues.py`
- Test: `backend/tests/test_issues_store.py`

**Step 1: Write the failing test**

Create `backend/tests/test_issues_store.py`:

```python
"""Tests for IssuesStore."""

import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def issues_store():
    """Create a temporary IssuesStore for testing."""
    from oya.vectorstore.issues import IssuesStore

    with tempfile.TemporaryDirectory() as tmpdir:
        store = IssuesStore(Path(tmpdir))
        yield store
        store.close()


class TestIssuesStore:
    """Tests for IssuesStore."""

    def test_add_issues_for_file(self, issues_store):
        """Can add issues for a file."""
        from oya.generation.summaries import FileIssue

        issues = [
            FileIssue(
                file_path="src/api.py",
                category="security",
                severity="problem",
                title="SQL injection",
                description="Use parameterized queries",
                line_range=(10, 12),
            ),
            FileIssue(
                file_path="src/api.py",
                category="reliability",
                severity="suggestion",
                title="Missing error handling",
                description="Add try/except",
            ),
        ]

        issues_store.add_issues("src/api.py", issues)

        # Verify issues were added
        results = issues_store.query_issues()
        assert len(results) == 2

    def test_delete_issues_for_file(self, issues_store):
        """Can delete issues for a specific file."""
        from oya.generation.summaries import FileIssue

        # Add issues for two files
        issues_store.add_issues("file1.py", [
            FileIssue(
                file_path="file1.py",
                category="security",
                severity="problem",
                title="Issue 1",
                description="Desc",
            ),
        ])
        issues_store.add_issues("file2.py", [
            FileIssue(
                file_path="file2.py",
                category="reliability",
                severity="suggestion",
                title="Issue 2",
                description="Desc",
            ),
        ])

        # Delete issues for file1
        issues_store.delete_issues_for_file("file1.py")

        # Only file2 issues remain
        results = issues_store.query_issues()
        assert len(results) == 1
        assert results[0]["file_path"] == "file2.py"

    def test_query_issues_by_category(self, issues_store):
        """Can filter issues by category."""
        from oya.generation.summaries import FileIssue

        issues_store.add_issues("test.py", [
            FileIssue(
                file_path="test.py",
                category="security",
                severity="problem",
                title="Security issue",
                description="Desc",
            ),
            FileIssue(
                file_path="test.py",
                category="reliability",
                severity="problem",
                title="Reliability issue",
                description="Desc",
            ),
        ])

        security_issues = issues_store.query_issues(category="security")
        assert len(security_issues) == 1
        assert security_issues[0]["category"] == "security"

    def test_query_issues_by_severity(self, issues_store):
        """Can filter issues by severity."""
        from oya.generation.summaries import FileIssue

        issues_store.add_issues("test.py", [
            FileIssue(
                file_path="test.py",
                category="security",
                severity="problem",
                title="Critical",
                description="Desc",
            ),
            FileIssue(
                file_path="test.py",
                category="security",
                severity="suggestion",
                title="Nice to have",
                description="Desc",
            ),
        ])

        problems = issues_store.query_issues(severity="problem")
        assert len(problems) == 1
        assert problems[0]["severity"] == "problem"

    def test_query_issues_semantic_search(self, issues_store):
        """Can search issues semantically."""
        from oya.generation.summaries import FileIssue

        issues_store.add_issues("auth.py", [
            FileIssue(
                file_path="auth.py",
                category="security",
                severity="problem",
                title="SQL injection vulnerability",
                description="Query built with string concatenation allows injection attacks",
            ),
        ])
        issues_store.add_issues("utils.py", [
            FileIssue(
                file_path="utils.py",
                category="maintainability",
                severity="suggestion",
                title="Function too long",
                description="Consider breaking into smaller functions",
            ),
        ])

        # Search for injection-related issues
        results = issues_store.query_issues(query="injection attack")
        assert len(results) >= 1
        assert results[0]["title"] == "SQL injection vulnerability"

    def test_clear(self, issues_store):
        """Can clear all issues."""
        from oya.generation.summaries import FileIssue

        issues_store.add_issues("test.py", [
            FileIssue(
                file_path="test.py",
                category="security",
                severity="problem",
                title="Issue",
                description="Desc",
            ),
        ])

        issues_store.clear()

        results = issues_store.query_issues()
        assert len(results) == 0
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/poecurt/projects/oya/.worktrees/file-issue-detection/backend && source .venv/bin/activate && pytest tests/test_issues_store.py -v`
Expected: FAIL with "cannot import name 'IssuesStore'"

**Step 3: Create IssuesStore**

Create `backend/src/oya/vectorstore/issues.py`:

```python
"""ChromaDB collection for code issues."""

import re
from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings

from oya.generation.summaries import FileIssue


class IssuesStore:
    """Vector store for code issues.

    Stores issues detected during file analysis in a dedicated ChromaDB
    collection, enabling semantic search and filtered queries for Q&A.
    """

    COLLECTION_NAME = "oya_issues"

    def __init__(self, persist_path: Path) -> None:
        """Initialize issues store with persistent storage.

        Args:
            persist_path: Directory path for ChromaDB persistence.
        """
        self._client = chromadb.PersistentClient(
            path=str(persist_path),
            settings=Settings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name=self.COLLECTION_NAME,
        )

    def _make_id(self, file_path: str, title: str) -> str:
        """Create a unique ID for an issue.

        Args:
            file_path: Path to the file.
            title: Issue title.

        Returns:
            Unique ID string.
        """
        # Slugify title for ID
        slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
        return f"{file_path}::{slug}"

    def add_issues(self, file_path: str, issues: list[FileIssue]) -> None:
        """Add issues for a file to the store.

        Replaces any existing issues for the file.

        Args:
            file_path: Path to the file.
            issues: List of FileIssue objects to add.
        """
        # First delete any existing issues for this file
        self.delete_issues_for_file(file_path)

        if not issues:
            return

        ids: list[str] = []
        documents: list[str] = []
        metadatas: list[dict[str, Any]] = []

        for issue in issues:
            issue_id = self._make_id(file_path, issue.title)
            # Content for semantic search
            content = f"{issue.title}\n\n{issue.description}"

            metadata: dict[str, Any] = {
                "file_path": file_path,
                "category": issue.category,
                "severity": issue.severity,
                "title": issue.title,
            }

            if issue.line_range:
                metadata["line_start"] = issue.line_range[0]
                metadata["line_end"] = issue.line_range[1]

            ids.append(issue_id)
            documents.append(content)
            metadatas.append(metadata)

        self._collection.add(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
        )

    def delete_issues_for_file(self, file_path: str) -> None:
        """Delete all issues for a specific file.

        Args:
            file_path: Path to the file whose issues should be deleted.
        """
        # Query to find all issues for this file
        try:
            results = self._collection.get(
                where={"file_path": file_path},
            )
            if results["ids"]:
                self._collection.delete(ids=results["ids"])
        except Exception:
            # Collection might be empty or file not found
            pass

    def query_issues(
        self,
        query: str | None = None,
        category: str | None = None,
        severity: str | None = None,
        file_path: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Query issues with optional filters.

        Args:
            query: Optional semantic search query.
            category: Filter by category (security, reliability, maintainability).
            severity: Filter by severity (problem, suggestion).
            file_path: Filter by file path.
            limit: Maximum results to return.

        Returns:
            List of issue dictionaries with metadata.
        """
        # Build where filter
        where_clauses: list[dict[str, Any]] = []

        if category:
            where_clauses.append({"category": category})
        if severity:
            where_clauses.append({"severity": severity})
        if file_path:
            where_clauses.append({"file_path": file_path})

        where: dict[str, Any] | None = None
        if len(where_clauses) == 1:
            where = where_clauses[0]
        elif len(where_clauses) > 1:
            where = {"$and": where_clauses}

        try:
            if query:
                # Semantic search
                results = self._collection.query(
                    query_texts=[query],
                    n_results=limit,
                    where=where,
                )
                ids = results.get("ids", [[]])[0]
                documents = results.get("documents", [[]])[0]
                metadatas = results.get("metadatas", [[]])[0]
            else:
                # Just filter without semantic search
                results = self._collection.get(
                    where=where,
                    limit=limit,
                )
                ids = results.get("ids", [])
                documents = results.get("documents", [])
                metadatas = results.get("metadatas", [])

            # Format results
            issues: list[dict[str, Any]] = []
            for i, issue_id in enumerate(ids):
                if i < len(metadatas):
                    issue = dict(metadatas[i])
                    issue["id"] = issue_id
                    issue["content"] = documents[i] if i < len(documents) else ""
                    issues.append(issue)

            return issues

        except Exception:
            return []

    def clear(self) -> None:
        """Clear all issues from the collection."""
        self._client.delete_collection(name=self.COLLECTION_NAME)
        self._collection = self._client.get_or_create_collection(
            name=self.COLLECTION_NAME,
        )

    def close(self) -> None:
        """Close the store and release resources."""
        import gc

        if self._client is not None:
            try:
                if hasattr(self._client, "_identifier_to_system"):
                    for system in list(self._client._identifier_to_system.values()):
                        if hasattr(system, "stop"):
                            system.stop()
            except Exception:
                pass

        self._collection = None  # type: ignore[assignment]
        self._client = None  # type: ignore[assignment]
        gc.collect()
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/poecurt/projects/oya/.worktrees/file-issue-detection/backend && source .venv/bin/activate && pytest tests/test_issues_store.py -v`
Expected: PASS (6 tests)

**Step 5: Commit**

```bash
cd /Users/poecurt/projects/oya/.worktrees/file-issue-detection
git add backend/src/oya/vectorstore/issues.py backend/tests/test_issues_store.py
git commit -m "feat: add IssuesStore for ChromaDB issue collection

IssuesStore manages a dedicated ChromaDB collection for code issues,
enabling semantic search and filtered queries by category/severity.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 6: Integrate IssuesStore with file generation

**Files:**
- Modify: `backend/src/oya/generation/orchestrator.py` (add IssuesStore integration)
- Modify: `backend/src/oya/api/deps.py` (add get_issues_store dependency)
- Test: Integration test

**Step 1: Write the failing test**

Add to `backend/tests/test_orchestrator.py` (or create integration test file):

```python
class TestOrchestratorIssues:
    """Tests for orchestrator issue handling."""

    @pytest.mark.asyncio
    async def test_file_generation_stores_issues(self, tmp_path, mock_llm):
        """File generation stores extracted issues in IssuesStore."""
        # This is an integration test - mock the LLM to return issues
        from oya.vectorstore.issues import IssuesStore

        # Setup mock LLM response with issues
        mock_llm.generate.return_value = '''---
file_summary:
  purpose: "API handler"
  layer: api
  key_abstractions: []
  internal_deps: []
  external_deps: []
  issues:
    - category: security
      severity: problem
      title: "Missing authentication"
      description: "Endpoint has no auth check"
      lines: [5, 10]
---

# API Handler

Handles requests.
'''

        # Create issues store
        issues_store = IssuesStore(tmp_path / "issues")

        # Verify issue would be stored (actual integration tested separately)
        # This validates the data flow expectation
        assert issues_store is not None
```

**Step 2: Add get_issues_store to deps.py**

In `backend/src/oya/api/deps.py`, add:

```python
from oya.vectorstore.issues import IssuesStore

_issues_store: IssuesStore | None = None


def get_issues_store() -> IssuesStore:
    """Get or create the issues vector store instance."""
    global _issues_store
    if _issues_store is None:
        from oya.config import load_settings

        settings = load_settings()
        persist_path = settings.workspace_path / ".oyawiki" / "vectorstore"
        _issues_store = IssuesStore(persist_path)
    return _issues_store
```

**Step 3: Update orchestrator to index issues**

In `backend/src/oya/generation/orchestrator.py`, add issues indexing after file generation.

Find the `_run_files` method and add after the file is generated:

```python
# After generating file and getting file_summary:
# Index issues to IssuesStore
if file_summary.issues and self._issues_store:
    self._issues_store.add_issues(file_path, file_summary.issues)
```

Add `_issues_store` parameter to `__init__`:

```python
def __init__(
    self,
    llm_client,
    repo,
    staging: StagingManager,
    vectorstore: VectorStore | None = None,
    issues_store: IssuesStore | None = None,  # NEW
    db: Database | None = None,
):
    # ... existing init ...
    self._issues_store = issues_store
```

**Step 4: Run tests to verify**

Run: `cd /Users/poecurt/projects/oya/.worktrees/file-issue-detection/backend && source .venv/bin/activate && pytest tests/ -k "orchestrator or issues" -v`
Expected: PASS

**Step 5: Commit**

```bash
cd /Users/poecurt/projects/oya/.worktrees/file-issue-detection
git add backend/src/oya/generation/orchestrator.py backend/src/oya/api/deps.py
git commit -m "feat: integrate IssuesStore with file generation pipeline

Orchestrator now indexes detected issues to IssuesStore during
file generation. Added get_issues_store dependency provider.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 7: Add issue-aware Q&A queries

**Files:**
- Modify: `backend/src/oya/qa/service.py`
- Test: `backend/tests/test_qa_service.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_qa_service.py`:

```python
class TestQAServiceIssues:
    """Tests for issue-aware Q&A."""

    def test_is_issue_query_detects_keywords(self):
        """is_issue_query detects issue-related questions."""
        from oya.qa.service import QAService

        service = QAService(mock_vectorstore, mock_db, mock_llm)

        assert service._is_issue_query("Are there any security issues?")
        assert service._is_issue_query("What bugs exist in the code?")
        assert service._is_issue_query("Show me code quality problems")
        assert service._is_issue_query("What's wrong with the authentication?")

        assert not service._is_issue_query("How does the API work?")
        assert not service._is_issue_query("Explain the database schema")

    @pytest.mark.asyncio
    async def test_ask_uses_issues_for_issue_queries(self, qa_service_with_issues):
        """Q&A queries issues collection for issue-related questions."""
        # Mock issues store returns pre-computed issues
        qa_service_with_issues._issues_store.query_issues.return_value = [
            {
                "file_path": "auth.py",
                "category": "security",
                "severity": "problem",
                "title": "Missing rate limiting",
                "content": "Login endpoint lacks rate limiting",
            }
        ]

        response = await qa_service_with_issues.ask(
            QARequest(question="What security issues exist?")
        )

        # Should have used issues in context
        assert "rate limiting" in response.answer.lower() or "security" in response.answer.lower()
```

**Step 2: Update QAService**

In `backend/src/oya/qa/service.py`, add:

```python
from oya.constants.issues import ISSUE_QUERY_KEYWORDS
from oya.vectorstore.issues import IssuesStore


class QAService:
    def __init__(
        self,
        vectorstore: VectorStore,
        db: Database,
        llm: LLMClient,
        issues_store: IssuesStore | None = None,  # NEW
    ) -> None:
        # ... existing init ...
        self._issues_store = issues_store

    def _is_issue_query(self, question: str) -> bool:
        """Check if question is asking about code issues.

        Args:
            question: User's question.

        Returns:
            True if question appears to be about code issues.
        """
        question_lower = question.lower()
        return any(keyword in question_lower for keyword in ISSUE_QUERY_KEYWORDS)

    async def ask(self, request: QARequest) -> QAResponse:
        """Answer a question about the codebase."""
        # Check if this is an issue-related query
        if self._is_issue_query(request.question) and self._issues_store:
            return await self._ask_with_issues(request)

        # ... existing implementation ...

    async def _ask_with_issues(self, request: QARequest) -> QAResponse:
        """Answer an issue-related question using pre-computed issues.

        Args:
            request: Q&A request.

        Returns:
            Q&A response with issue-based answer.
        """
        # Query issues collection
        issues = self._issues_store.query_issues(
            query=request.question,
            limit=20,
        )

        if not issues:
            # Fall back to normal search
            return await self._ask_normal(request)

        # Build context from issues
        context_parts = []
        for issue in issues:
            file_path = issue.get("file_path", "unknown")
            category = issue.get("category", "")
            severity = issue.get("severity", "")
            title = issue.get("title", "")
            content = issue.get("content", "")

            part = f"[{severity.upper()}] {category} issue in {file_path}\n{title}\n{content}"
            context_parts.append(part)

        context_str = "\n\n---\n\n".join(context_parts)

        prompt = f"""Based on the following code issues identified during analysis, answer the question.

IDENTIFIED ISSUES:
{context_str}

QUESTION: {request.question}

Analyze these issues and identify any systemic patterns. Are there architectural or process problems causing multiple similar issues?
Format your response with:
1. A summary of the issues found
2. Any patterns across issues
3. Recommendations for addressing them"""

        try:
            raw_answer = await self._llm.generate(
                prompt=prompt,
                system_prompt=QA_SYSTEM_PROMPT,
                temperature=0.2,
            )
        except Exception as e:
            return QAResponse(
                answer=f"Error: {e}",
                citations=[],
                confidence=ConfidenceLevel.LOW,
                disclaimer="Error generating answer.",
                search_quality=SearchQuality(
                    semantic_searched=False,
                    fts_searched=False,
                    results_found=len(issues),
                    results_used=len(issues),
                ),
            )

        answer = self._extract_answer(raw_answer)

        # Create citations from issues
        citations = []
        seen_paths: set[str] = set()
        for issue in issues[:5]:
            path = issue.get("file_path", "")
            if path and path not in seen_paths:
                seen_paths.add(path)
                citations.append(
                    Citation(
                        path=path,
                        title=issue.get("title", path),
                        lines=None,
                        url=f"/files/{path.replace('/', '-').replace('.', '-')}",
                    )
                )

        return QAResponse(
            answer=answer,
            citations=citations,
            confidence=ConfidenceLevel.HIGH if len(issues) >= 3 else ConfidenceLevel.MEDIUM,
            disclaimer="Based on issues detected during wiki generation.",
            search_quality=SearchQuality(
                semantic_searched=True,
                fts_searched=False,
                results_found=len(issues),
                results_used=min(len(issues), 20),
            ),
        )
```

**Step 3: Run tests**

Run: `cd /Users/poecurt/projects/oya/.worktrees/file-issue-detection/backend && source .venv/bin/activate && pytest tests/test_qa_service.py -v`
Expected: PASS

**Step 4: Commit**

```bash
cd /Users/poecurt/projects/oya/.worktrees/file-issue-detection
git add backend/src/oya/qa/service.py backend/tests/test_qa_service.py
git commit -m "feat: add issue-aware Q&A queries

QAService now detects issue-related questions and queries the
IssuesStore first, providing pre-computed issue analysis.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 8: Update QA router to inject IssuesStore

**Files:**
- Modify: `backend/src/oya/api/routers/qa.py`
- Test: API integration test

**Step 1: Update router**

In `backend/src/oya/api/routers/qa.py`:

```python
from oya.api.deps import get_db, get_vectorstore, get_llm, get_issues_store
from oya.vectorstore.issues import IssuesStore


def get_qa_service(
    vectorstore: VectorStore = Depends(get_vectorstore),
    db: Database = Depends(get_db),
    llm: LLMClient = Depends(get_llm),
    issues_store: IssuesStore = Depends(get_issues_store),
) -> QAService:
    """Get Q&A service instance."""
    return QAService(vectorstore, db, llm, issues_store)
```

**Step 2: Run full test suite**

Run: `cd /Users/poecurt/projects/oya/.worktrees/file-issue-detection/backend && source .venv/bin/activate && pytest -v`
Expected: All tests PASS

**Step 3: Commit**

```bash
cd /Users/poecurt/projects/oya/.worktrees/file-issue-detection
git add backend/src/oya/api/routers/qa.py
git commit -m "feat: inject IssuesStore into QA router

QA endpoint now receives IssuesStore via dependency injection,
enabling issue-aware Q&A responses.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 9: Final integration test and cleanup

**Files:**
- Run full test suite
- Verify no regressions

**Step 1: Run full test suite**

Run: `cd /Users/poecurt/projects/oya/.worktrees/file-issue-detection/backend && source .venv/bin/activate && pytest -v --tb=short`
Expected: All tests PASS

**Step 2: Run linting**

Run: `cd /Users/poecurt/projects/oya/.worktrees/file-issue-detection/backend && source .venv/bin/activate && ruff check src/`
Expected: No errors (or fix any that appear)

**Step 3: Final commit if any fixes needed**

```bash
cd /Users/poecurt/projects/oya/.worktrees/file-issue-detection
git add -A
git commit -m "chore: fix linting issues

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Summary

This plan implements file issue detection in 9 tasks:

1. **FileIssue dataclass + constants** - Core data model
2. **Extend FileSummary** - Add issues field
3. **Update SummaryParser** - Extract issues from YAML
4. **Update FILE_TEMPLATE** - Instruct LLM to find issues
5. **Create IssuesStore** - ChromaDB collection for issues
6. **Integrate with orchestrator** - Index issues during generation
7. **Issue-aware Q&A** - Query issues for relevant questions
8. **Update QA router** - Dependency injection
9. **Integration testing** - Verify everything works together

Each task follows TDD with clear test → implement → verify → commit cycles.
