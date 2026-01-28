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
