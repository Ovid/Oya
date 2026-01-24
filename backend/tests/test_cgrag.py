"""Tests for CGRAG core functionality."""

from pathlib import Path
from unittest.mock import AsyncMock

import networkx as nx
import pytest


def _make_test_graph() -> nx.DiGraph:
    """Create a test graph with known structure."""
    G = nx.DiGraph()

    nodes = [
        (
            "auth/handler.py::login",
            {
                "name": "login",
                "type": "function",
                "file_path": "auth/handler.py",
                "line_start": 10,
                "line_end": 30,
            },
        ),
        (
            "auth/verify.py::verify_token",
            {
                "name": "verify_token",
                "type": "function",
                "file_path": "auth/verify.py",
                "line_start": 5,
                "line_end": 25,
            },
        ),
        (
            "db/users.py::get_user",
            {
                "name": "get_user",
                "type": "function",
                "file_path": "db/users.py",
                "line_start": 20,
                "line_end": 40,
            },
        ),
    ]
    for node_id, attrs in nodes:
        G.add_node(node_id, **attrs)

    edges = [
        (
            "auth/handler.py::login",
            "auth/verify.py::verify_token",
            {"type": "calls", "confidence": 0.9, "line": 15},
        ),
        (
            "auth/verify.py::verify_token",
            "db/users.py::get_user",
            {"type": "calls", "confidence": 0.8, "line": 10},
        ),
    ]
    for source, target, attrs in edges:
        G.add_edge(source, target, **attrs)

    return G


class TestIsSpecificGap:
    """Tests for is_specific_gap function."""

    def test_specific_with_path(self):
        """Gap with 'in path' is specific."""
        from oya.qa.cgrag import is_specific_gap

        assert is_specific_gap("verify_token in auth/verify.py")

    def test_specific_with_double_colon(self):
        """Gap with :: is specific."""
        from oya.qa.cgrag import is_specific_gap

        assert is_specific_gap("auth/verify.py::verify_token")

    def test_fuzzy_description(self):
        """Descriptive gap is fuzzy."""
        from oya.qa.cgrag import is_specific_gap

        assert not is_specific_gap("the database connection handler")

    def test_specific_with_function_keyword(self):
        """Gap with 'function X' is specific."""
        from oya.qa.cgrag import is_specific_gap

        assert is_specific_gap("function verify_token")


class TestGraphLookup:
    """Tests for graph_lookup function."""

    def test_lookup_by_name(self):
        """Finds node by function name."""
        from oya.qa.cgrag import graph_lookup

        graph = _make_test_graph()

        result = graph_lookup("verify_token", graph)

        assert result is not None
        assert len(result.nodes) >= 1
        node_names = {n.name for n in result.nodes}
        assert "verify_token" in node_names

    def test_lookup_by_path_and_name(self):
        """Finds node by path::name format."""
        from oya.qa.cgrag import graph_lookup

        graph = _make_test_graph()

        result = graph_lookup("auth/verify.py::verify_token", graph)

        assert result is not None
        node_ids = {n.id for n in result.nodes}
        assert "auth/verify.py::verify_token" in node_ids

    def test_lookup_not_found(self):
        """Returns None for non-existent node."""
        from oya.qa.cgrag import graph_lookup

        graph = _make_test_graph()

        result = graph_lookup("nonexistent_function", graph)

        assert result is None

    def test_lookup_includes_neighborhood(self):
        """Result includes 1-hop neighborhood."""
        from oya.qa.cgrag import graph_lookup

        graph = _make_test_graph()

        result = graph_lookup("verify_token", graph)

        # verify_token connects to login and get_user
        node_names = {n.name for n in result.nodes}
        assert "verify_token" in node_names
        # Should include at least one neighbor
        assert len(node_names) > 1


class TestParseGaps:
    """Tests for parse_gaps function."""

    def test_parse_gaps_none(self):
        """NONE in response returns empty list."""
        from oya.qa.cgrag import parse_gaps

        response = """<answer>
The auth system works by...
</answer>

<missing>
NONE
</missing>"""

        gaps = parse_gaps(response)

        assert gaps == []

    def test_parse_gaps_single(self):
        """Single gap is parsed correctly."""
        from oya.qa.cgrag import parse_gaps

        response = """<answer>
The auth system works by...
</answer>

<missing>
- verify_token in auth/verify.py
</missing>"""

        gaps = parse_gaps(response)

        assert len(gaps) == 1
        assert "verify_token" in gaps[0]

    def test_parse_gaps_multiple(self):
        """Multiple gaps are parsed correctly."""
        from oya.qa.cgrag import parse_gaps

        response = """<answer>
The auth system works by...
</answer>

<missing>
- verify_token in auth/verify.py
- UserModel in models/user.py
- the database connection handler
</missing>"""

        gaps = parse_gaps(response)

        assert len(gaps) == 3
        assert "verify_token" in gaps[0]
        assert "UserModel" in gaps[1]
        assert "database connection" in gaps[2]

    def test_parse_gaps_no_section(self):
        """Missing <missing> section returns empty list."""
        from oya.qa.cgrag import parse_gaps

        response = """<answer>
The auth system works by calling various functions.
</answer>"""

        gaps = parse_gaps(response)

        assert gaps == []

    def test_parse_answer(self):
        """Answer is extracted correctly with XML tags."""
        from oya.qa.cgrag import parse_answer

        response = """<answer>
The auth system works by verifying tokens
and checking user permissions.
</answer>

<missing>
NONE
</missing>"""

        answer = parse_answer(response)

        assert "auth system works" in answer
        assert "verifying tokens" in answer
        assert "<missing>" not in answer

    def test_parse_answer_with_missing_word_in_text(self):
        """Answer containing the word 'missing' is not truncated.

        Regression test: the word 'missing' appearing naturally in the answer
        text should not be confused with the <missing> section.
        """
        from oya.qa.cgrag import parse_answer

        response = """<answer>
The dual-write pattern has consistency hazards:
- DB row exists but file missing
- File exists but DB row missing
This leads to data divergence.
</answer>

<missing>
- the actual transaction handling code
</missing>"""

        answer = parse_answer(response)

        # The full answer should be preserved, including text after "missing"
        assert "DB row exists but file missing" in answer
        assert "File exists but DB row missing" in answer
        assert "data divergence" in answer
        # The <missing> section should not be in the answer
        assert "<missing>" not in answer
        assert "transaction handling" not in answer

    def test_parse_answer_legacy_format(self):
        """Parser still handles legacy ANSWER: format for backwards compatibility."""
        from oya.qa.cgrag import parse_answer

        response = """ANSWER:
Legacy format answer.

MISSING (or "NONE" if nothing needed):
NONE"""

        answer = parse_answer(response)

        assert "Legacy format answer" in answer
        assert "MISSING" not in answer


class TestCGRAGLoop:
    """Tests for the CGRAG iteration loop."""

    @pytest.mark.asyncio
    async def test_single_pass_when_no_gaps(self):
        """Single pass when LLM reports no gaps."""
        from oya.qa.cgrag import run_cgrag_loop
        from oya.qa.session import CGRAGSession

        mock_llm = AsyncMock()
        mock_llm.generate.return_value = """ANSWER:
The auth system validates tokens.

MISSING (or "NONE" if nothing needed):
NONE"""

        session = CGRAGSession()
        initial_context = "Some initial context"

        result = await run_cgrag_loop(
            question="How does auth work?",
            initial_context=initial_context,
            session=session,
            llm=mock_llm,
            graph=None,
            vectorstore=None,
        )

        assert result.passes_used == 1
        assert "auth system validates" in result.answer
        assert len(result.gaps_identified) == 0

    @pytest.mark.asyncio
    async def test_multiple_passes_with_gaps(self):
        """Multiple passes when LLM identifies gaps."""
        from oya.qa.cgrag import run_cgrag_loop
        from oya.qa.session import CGRAGSession

        mock_llm = AsyncMock()
        # First call: identifies gap
        # Second call: no more gaps
        mock_llm.generate.side_effect = [
            """ANSWER:
The auth system calls verify_token.

MISSING (or "NONE" if nothing needed):
- verify_token function""",
            """ANSWER:
The auth system calls verify_token which checks JWT signatures.

MISSING (or "NONE" if nothing needed):
NONE""",
        ]

        # Mock graph with verify_token
        mock_graph = _make_test_graph()

        session = CGRAGSession()

        result = await run_cgrag_loop(
            question="How does auth work?",
            initial_context="Initial context",
            session=session,
            llm=mock_llm,
            graph=mock_graph,
            vectorstore=None,
        )

        assert result.passes_used == 2
        assert "JWT signatures" in result.answer
        assert any("verify_token" in gap for gap in result.gaps_identified)

    @pytest.mark.asyncio
    async def test_stops_at_max_passes(self):
        """Stops after max passes even if gaps remain."""
        from oya.qa.cgrag import run_cgrag_loop
        from oya.qa.session import CGRAGSession

        # Default from CONFIG_SCHEMA: cgrag_max_passes = 3
        CGRAG_MAX_PASSES = 3

        mock_llm = AsyncMock()
        # Report different gaps each time so we don't hit the "already not found" early exit
        mock_llm.generate.side_effect = [
            """ANSWER:
Partial answer.

MISSING (or "NONE" if nothing needed):
- function_one""",
            """ANSWER:
Partial answer.

MISSING (or "NONE" if nothing needed):
- function_two""",
            """ANSWER:
Partial answer.

MISSING (or "NONE" if nothing needed):
- function_three""",
        ]

        session = CGRAGSession()

        result = await run_cgrag_loop(
            question="Complex question",
            initial_context="Initial context",
            session=session,
            llm=mock_llm,
            graph=None,
            vectorstore=None,
        )

        assert result.passes_used == CGRAG_MAX_PASSES
        assert mock_llm.generate.call_count == CGRAG_MAX_PASSES

    @pytest.mark.asyncio
    async def test_stops_when_all_gaps_not_found(self):
        """Stops when all requested gaps were already not found."""
        from oya.qa.cgrag import run_cgrag_loop
        from oya.qa.session import CGRAGSession

        mock_llm = AsyncMock()
        # Always ask for same non-existent thing
        mock_llm.generate.return_value = """ANSWER:
Can't fully answer.

MISSING (or "NONE" if nothing needed):
- missing_function"""

        session = CGRAGSession()

        result = await run_cgrag_loop(
            question="Question about missing code",
            initial_context="Initial context",
            session=session,
            llm=mock_llm,
            graph=None,  # No graph, so nothing found
            vectorstore=None,  # No vectorstore, so nothing found
        )

        # Should stop after 2 passes: first identifies gap, second sees it's still not found
        assert result.passes_used == 2
        assert "missing_function" in result.gaps_unresolved


class TestReadSourceForNodes:
    """Tests for _read_source_for_nodes function."""

    def test_reads_source_file_content(self, tmp_path: Path):
        """Reads actual source file content for nodes."""
        from dataclasses import dataclass

        from oya.qa.cgrag import _read_source_for_nodes

        # Create a test source file
        source_file = tmp_path / "auth" / "handler.py"
        source_file.parent.mkdir(parents=True, exist_ok=True)
        source_file.write_text(
            """# Auth handler module

def login(username: str, password: str) -> dict:
    '''Log in a user.'''
    user = get_user(username)
    if verify_password(user, password):
        return create_token(user)
    raise AuthError("Invalid credentials")

def logout(token: str) -> None:
    '''Log out a user.'''
    invalidate_token(token)
"""
        )

        @dataclass
        class MockNode:
            id: str
            name: str
            file_path: str
            line_start: int
            line_end: int

        nodes = [
            MockNode(
                id="auth/handler.py::login",
                name="login",
                file_path="auth/handler.py",
                line_start=3,
                line_end=9,
            )
        ]

        result = _read_source_for_nodes(nodes, tmp_path)

        assert result is not None
        assert "auth/handler.py" in result
        assert "login" in result
        assert "def login" in result
        assert "username: str" in result
        # Should include syntax highlighting hint
        assert "```python" in result

    def test_returns_none_when_file_not_found(self, tmp_path: Path):
        """Returns None when source file doesn't exist."""
        from dataclasses import dataclass

        from oya.qa.cgrag import _read_source_for_nodes

        @dataclass
        class MockNode:
            id: str
            name: str
            file_path: str
            line_start: int
            line_end: int

        nodes = [
            MockNode(
                id="nonexistent/file.py::func",
                name="func",
                file_path="nonexistent/file.py",
                line_start=1,
                line_end=10,
            )
        ]

        result = _read_source_for_nodes(nodes, tmp_path)

        assert result is None

    def test_deduplicates_files(self, tmp_path: Path):
        """Only reads each file once even with multiple nodes."""
        from dataclasses import dataclass

        from oya.qa.cgrag import _read_source_for_nodes

        # Create a test source file
        source_file = tmp_path / "utils.py"
        source_file.write_text(
            """def func1():
    pass

def func2():
    pass
"""
        )

        @dataclass
        class MockNode:
            id: str
            name: str
            file_path: str
            line_start: int
            line_end: int

        nodes = [
            MockNode(
                id="utils.py::func1",
                name="func1",
                file_path="utils.py",
                line_start=1,
                line_end=2,
            ),
            MockNode(
                id="utils.py::func2",
                name="func2",
                file_path="utils.py",
                line_start=4,
                line_end=5,
            ),
        ]

        result = _read_source_for_nodes(nodes, tmp_path)

        # Should only have one occurrence of the file header
        assert result.count("utils.py") == 1


class TestCGRAGWithSourcePath:
    """Tests for CGRAG loop with source_path parameter."""

    @pytest.mark.asyncio
    async def test_cgrag_uses_source_path_for_gap_retrieval(self, tmp_path: Path):
        """CGRAG reads actual source files when source_path is provided."""
        from oya.qa.cgrag import run_cgrag_loop
        from oya.qa.session import CGRAGSession

        # Create a test source file that matches the graph node
        auth_file = tmp_path / "auth" / "verify.py"
        auth_file.parent.mkdir(parents=True, exist_ok=True)
        auth_file.write_text(
            """# Token verification module

def verify_token(token: str) -> dict:
    '''Verify JWT token and return payload.'''
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return payload
    except jwt.InvalidTokenError:
        raise AuthError("Invalid token")
"""
        )

        mock_llm = AsyncMock()
        # First call: identifies gap about verify_token
        # Second call: answers with the retrieved source context
        mock_llm.generate.side_effect = [
            """<answer>
The auth system verifies tokens but I need more details.
</answer>

<missing>
- verify_token in auth/verify.py
</missing>""",
            """<answer>
The auth system verifies tokens using JWT. The verify_token function decodes
JWT tokens using HS256 algorithm and returns the payload.
</answer>

<missing>
NONE
</missing>""",
        ]

        # Create graph with verify_token node
        mock_graph = _make_test_graph()

        session = CGRAGSession()

        result = await run_cgrag_loop(
            question="How does token verification work?",
            initial_context="Initial context about auth",
            session=session,
            llm=mock_llm,
            graph=mock_graph,
            vectorstore=None,
            source_path=tmp_path,  # Provide source path
        )

        assert result.passes_used == 2
        assert "JWT" in result.answer or "verify" in result.answer
        # The gap should have been resolved
        assert any("verify_token" in gap for gap in result.gaps_resolved)
