"""Integration tests for call-site synopsis feature."""

import pytest
import networkx as nx

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

    def test_pipeline_extracts_meaningful_context(self, realistic_graph, file_contents):
        """Pipeline extracts code that shows meaningful usage context."""
        sites = get_call_sites(realistic_graph, "auth/verify.py")
        best, _ = select_best_call_site(sites, file_contents)

        assert best is not None
        snippet = extract_call_snippet(
            best.caller_file,
            best.line,
            file_contents,
        )

        # Should include function definition for context
        assert "def handle_login" in snippet
        # Should include the actual call
        assert "verify_token" in snippet
        # Should include surrounding context showing error handling
        assert "if not user:" in snippet

    def test_format_synopsis_with_multiple_callers(self):
        """format_call_site_synopsis includes references to other callers."""
        snippet = "user = verify_token(token)"
        other_callers = [
            ("service/auth.py", 42),
            ("middleware/check.py", 15),
            ("handler/process.py", 88),
        ]

        formatted = format_call_site_synopsis(
            snippet=snippet,
            caller_file="api/routes.py",
            line=55,
            language="python",
            other_callers=other_callers,
        )

        # Primary caller info
        assert "api/routes.py" in formatted
        assert "line 55" in formatted
        assert "```python" in formatted

        # Other callers should be listed
        assert "service/auth.py:42" in formatted
        assert "middleware/check.py:15" in formatted
        assert "handler/process.py:88" in formatted

    def test_format_synopsis_limits_other_callers(self):
        """format_call_site_synopsis limits the number of other callers shown."""
        snippet = "result = helper()"
        # Create 10 other callers
        other_callers = [(f"file{i}.py", i * 10) for i in range(10)]

        formatted = format_call_site_synopsis(
            snippet=snippet,
            caller_file="main.py",
            line=1,
            language="python",
            other_callers=other_callers,
        )

        # Should mention that there are more callers
        assert "and 5 more" in formatted

    def test_full_pipeline_with_missing_file_contents(self, realistic_graph):
        """Pipeline handles missing file contents gracefully."""
        sites = get_call_sites(realistic_graph, "auth/verify.py")
        best, _ = select_best_call_site(sites, {})  # Empty file_contents

        assert best is not None
        # Extract with empty contents should return empty string
        snippet = extract_call_snippet(
            best.caller_file,
            best.line,
            {},  # No file contents available
        )
        assert snippet == ""

    def test_call_site_includes_caller_symbol(self, realistic_graph):
        """CallSite objects include the caller symbol name."""
        sites = get_call_sites(realistic_graph, "auth/verify.py")

        # Find the production caller
        prod_site = next(s for s in sites if s.caller_file == "api/routes.py")
        assert prod_site.caller_symbol == "handle_login"

        # Find the test caller
        test_site = next(s for s in sites if s.caller_file == "tests/test_auth.py")
        assert test_site.caller_symbol == "test_verify_token"

    def test_call_site_includes_target_symbol(self, realistic_graph):
        """CallSite objects include the target symbol name."""
        sites = get_call_sites(realistic_graph, "auth/verify.py")

        # All sites should target verify_token
        for site in sites:
            assert site.target_symbol == "verify_token"
