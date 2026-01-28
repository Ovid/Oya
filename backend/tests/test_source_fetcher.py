"""Tests for SourceFetcher class."""

import tempfile
from pathlib import Path

import pytest

from oya.qa.source_fetcher import SourceFetcher
from oya.db.code_index import CodeIndexEntry


@pytest.fixture
def temp_repo():
    """Create a temporary repository with test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)

        # Create a Python file with line numbers for testing
        source_file = repo_root / "src" / "example.py"
        source_file.parent.mkdir(parents=True, exist_ok=True)

        # Write 20 lines of code (line numbers 1-20)
        lines = [
            "# Line 1: Header comment",
            "import os",
            "",
            "def hello_world():",
            '    """Say hello."""',
            '    print("Hello, World!")',
            "",
            "",
            "def add(a, b):",
            '    """Add two numbers."""',
            "    return a + b",
            "",
            "",
            "class Calculator:",
            '    """A simple calculator."""',
            "",
            "    def multiply(self, a, b):",
            "        return a * b",
            "",
            "# Line 20: Footer comment",
        ]
        source_file.write_text("\n".join(lines))

        yield repo_root


class TestSourceFetcherFetchFunctionSource:
    """Tests for fetching specific line ranges from source files."""

    def test_fetch_function_source(self, temp_repo):
        """Verify specific line range is fetched correctly."""
        fetcher = SourceFetcher(temp_repo)

        # Fetch the hello_world function (lines 4-6)
        result = fetcher.fetch("src/example.py", line_start=4, line_end=6)

        # Should include a header with file path and line range
        assert "src/example.py" in result
        assert "4-6" in result or "4:6" in result or ("4" in result and "6" in result)

        # Should include the function code
        assert "def hello_world():" in result
        assert '"""Say hello."""' in result
        assert 'print("Hello, World!")' in result

        # Should NOT include lines outside the range
        assert "import os" not in result
        assert "def add" not in result

    def test_fetch_with_absolute_path(self, temp_repo):
        """Fetch works with absolute paths."""
        fetcher = SourceFetcher(temp_repo)

        absolute_path = temp_repo / "src" / "example.py"
        result = fetcher.fetch(str(absolute_path), line_start=1, line_end=2)

        assert "Header comment" in result
        assert "import os" in result

    def test_fetch_file_not_found(self, temp_repo):
        """Returns error message when file not found."""
        fetcher = SourceFetcher(temp_repo)

        result = fetcher.fetch("nonexistent.py", line_start=1, line_end=10)

        assert "not found" in result.lower() or "error" in result.lower()
        assert "nonexistent.py" in result

    def test_fetch_single_line(self, temp_repo):
        """Can fetch a single line."""
        fetcher = SourceFetcher(temp_repo)

        result = fetcher.fetch("src/example.py", line_start=4, line_end=4)

        assert "def hello_world():" in result

    def test_fetch_line_range_at_end_of_file(self, temp_repo):
        """Handles line range extending to end of file."""
        fetcher = SourceFetcher(temp_repo)

        # Lines 17-20 (last 4 lines)
        result = fetcher.fetch("src/example.py", line_start=17, line_end=20)

        assert "def multiply" in result
        assert "Footer comment" in result


class TestSourceFetcherTruncation:
    """Tests for budget-based truncation."""

    def test_fetch_truncates_when_over_budget(self, temp_repo):
        """Verify truncation works when content exceeds budget."""
        fetcher = SourceFetcher(temp_repo)

        # Small budget (e.g., 10 tokens ~= 40 chars)
        # Fetching many lines should trigger truncation
        result = fetcher.fetch("src/example.py", line_start=1, line_end=20, budget=10)

        # Should include truncation indicator
        assert "truncated" in result.lower() or "..." in result

        # Should be much shorter than full content
        # Full content would be ~500+ chars, truncated should be much less
        assert len(result) < 200

    def test_fetch_no_truncation_within_budget(self, temp_repo):
        """Content within budget is not truncated."""
        fetcher = SourceFetcher(temp_repo)

        # Large budget should not trigger truncation
        result = fetcher.fetch("src/example.py", line_start=4, line_end=6, budget=500)

        # Should NOT have truncation indicator
        assert "truncated" not in result.lower()

        # Should have full content
        assert "def hello_world():" in result
        assert "print(" in result


class TestSourceFetcherFetchEntry:
    """Tests for fetch_entry convenience method."""

    def test_fetch_entry_uses_entry_fields(self, temp_repo):
        """fetch_entry extracts path and lines from CodeIndexEntry."""
        fetcher = SourceFetcher(temp_repo)

        entry = CodeIndexEntry(
            id=1,
            file_path="src/example.py",
            symbol_name="hello_world",
            symbol_type="function",
            line_start=4,
            line_end=6,
            signature="def hello_world():",
            docstring="Say hello.",
            calls=[],
            called_by=[],
            raises=[],
            mutates=[],
            error_strings=[],
            source_hash="abc123",
        )

        result = fetcher.fetch_entry(entry, budget=500)

        assert "def hello_world():" in result
        assert '"""Say hello."""' in result

    def test_fetch_entry_respects_budget(self, temp_repo):
        """fetch_entry passes budget to fetch."""
        fetcher = SourceFetcher(temp_repo)

        # Entry spanning many lines
        entry = CodeIndexEntry(
            id=1,
            file_path="src/example.py",
            symbol_name="Calculator",
            symbol_type="class",
            line_start=1,
            line_end=20,
            signature="class Calculator:",
            docstring="A simple calculator.",
            calls=[],
            called_by=[],
            raises=[],
            mutates=[],
            error_strings=[],
            source_hash="def456",
        )

        result = fetcher.fetch_entry(entry, budget=10)

        # Should be truncated due to small budget
        assert "truncated" in result.lower() or "..." in result
