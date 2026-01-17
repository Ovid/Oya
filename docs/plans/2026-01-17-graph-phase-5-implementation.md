# Phase 5: Iterative Retrieval (CGRAG) - Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add iterative retrieval (CGRAG) to Q&A so the LLM can request missing code context across multiple passes, producing more complete answers.

**Architecture:** Always multi-pass with max 3 iterations. LLM identifies gaps via explicit prompt. Session caching preserves context across questions. "Not found" escalation handles stuck states.

**Tech Stack:** Python 3.11+, NetworkX (existing), ChromaDB (existing), Pydantic, pytest

---

## Task 1: Add CGRAG Constants

**Files:**
- Modify: `backend/src/oya/constants/qa.py`

**Step 1: Add the new constants**

Add at the end of `backend/src/oya/constants/qa.py`:

```python
# =============================================================================
# CGRAG - Iterative Retrieval (Phase 5)
# =============================================================================
# CGRAG (Contextually-Guided RAG) allows the LLM to request missing context
# across multiple retrieval passes, producing more complete answers.

CGRAG_MAX_PASSES = 3
CGRAG_SESSION_TTL_MINUTES = 30
CGRAG_SESSION_MAX_NODES = 50
CGRAG_TARGETED_TOP_K = 3
```

**Step 2: Verify the constants are importable**

Run: `cd /Users/poecurt/projects/oya/backend && python -c "from oya.constants.qa import CGRAG_MAX_PASSES, CGRAG_SESSION_TTL_MINUTES; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add backend/src/oya/constants/qa.py
git commit -m "feat(qa): add CGRAG constants for Phase 5"
```

---

## Task 2: Create CGRAGSession Model

**Files:**
- Create: `backend/src/oya/qa/session.py`
- Create: `backend/tests/test_cgrag_session.py`

**Step 1: Write the failing test**

Create `backend/tests/test_cgrag_session.py`:

```python
"""Tests for CGRAG session management."""

from datetime import datetime, timedelta


class TestCGRAGSession:
    """Tests for CGRAGSession class."""

    def test_session_creation(self):
        """Session is created with unique ID and timestamps."""
        from oya.qa.session import CGRAGSession

        session = CGRAGSession()

        assert session.id is not None
        assert len(session.id) > 0
        assert session.created_at is not None
        assert session.last_accessed is not None
        assert len(session.cached_nodes) == 0
        assert len(session.not_found) == 0

    def test_session_add_nodes(self):
        """Nodes can be added to session cache."""
        from oya.qa.session import CGRAGSession
        from oya.graph.models import Node, NodeType

        session = CGRAGSession()
        node = Node(
            id="test.py::func",
            node_type=NodeType.FUNCTION,
            name="func",
            file_path="test.py",
            line_start=1,
            line_end=10,
        )

        session.add_nodes([node])

        assert "test.py::func" in session.cached_nodes
        assert session.cached_nodes["test.py::func"] == node

    def test_session_add_not_found(self):
        """Not-found gaps are tracked."""
        from oya.qa.session import CGRAGSession

        session = CGRAGSession()

        session.add_not_found("missing_function")

        assert "missing_function" in session.not_found

    def test_session_is_expired(self):
        """Session expiration is detected correctly."""
        from oya.qa.session import CGRAGSession
        from oya.constants.qa import CGRAG_SESSION_TTL_MINUTES

        session = CGRAGSession()

        # Fresh session is not expired
        assert not session.is_expired()

        # Manually expire by setting old timestamp
        session.last_accessed = datetime.now() - timedelta(
            minutes=CGRAG_SESSION_TTL_MINUTES + 1
        )
        assert session.is_expired()

    def test_session_touch_updates_timestamp(self):
        """Touch updates last_accessed timestamp."""
        from oya.qa.session import CGRAGSession

        session = CGRAGSession()
        old_time = session.last_accessed

        # Small delay to ensure timestamp changes
        import time
        time.sleep(0.01)

        session.touch()

        assert session.last_accessed > old_time

    def test_session_enforces_max_nodes(self):
        """Session evicts oldest nodes when max reached."""
        from oya.qa.session import CGRAGSession
        from oya.graph.models import Node, NodeType
        from oya.constants.qa import CGRAG_SESSION_MAX_NODES

        session = CGRAGSession()

        # Add more nodes than max
        nodes = [
            Node(
                id=f"file{i}.py::func{i}",
                node_type=NodeType.FUNCTION,
                name=f"func{i}",
                file_path=f"file{i}.py",
                line_start=1,
                line_end=10,
            )
            for i in range(CGRAG_SESSION_MAX_NODES + 10)
        ]

        session.add_nodes(nodes)

        assert len(session.cached_nodes) <= CGRAG_SESSION_MAX_NODES
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/poecurt/projects/oya/backend && pytest tests/test_cgrag_session.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

Create `backend/src/oya/qa/session.py`:

```python
"""CGRAG session management for iterative Q&A retrieval."""

from __future__ import annotations

import uuid
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from oya.constants.qa import CGRAG_SESSION_MAX_NODES, CGRAG_SESSION_TTL_MINUTES
from oya.graph.models import Node, Subgraph


@dataclass
class CGRAGSession:
    """Session state for CGRAG iterative retrieval.

    Tracks cached context across multiple questions in a conversation,
    enabling follow-up questions to build on previous retrieval work.
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    cached_nodes: OrderedDict[str, Node] = field(default_factory=OrderedDict)
    cached_subgraph: Subgraph | None = None
    not_found: set[str] = field(default_factory=set)
    created_at: datetime = field(default_factory=datetime.now)
    last_accessed: datetime = field(default_factory=datetime.now)

    def add_nodes(self, nodes: list[Node]) -> None:
        """Add nodes to the cache, evicting old ones if needed.

        Args:
            nodes: Nodes to add to the cache.
        """
        for node in nodes:
            # Move to end if already exists (LRU behavior)
            if node.id in self.cached_nodes:
                self.cached_nodes.move_to_end(node.id)
            self.cached_nodes[node.id] = node

        # Evict oldest nodes if over limit
        while len(self.cached_nodes) > CGRAG_SESSION_MAX_NODES:
            self.cached_nodes.popitem(last=False)

    def add_not_found(self, gap: str) -> None:
        """Record a gap that could not be resolved.

        Args:
            gap: The gap identifier that was not found.
        """
        self.not_found.add(gap)

    def is_expired(self) -> bool:
        """Check if the session has expired.

        Returns:
            True if session is older than TTL.
        """
        expiry = self.last_accessed + timedelta(minutes=CGRAG_SESSION_TTL_MINUTES)
        return datetime.now() > expiry

    def touch(self) -> None:
        """Update last_accessed timestamp."""
        self.last_accessed = datetime.now()

    def get_cached_node_ids(self) -> list[str]:
        """Get list of cached node IDs.

        Returns:
            List of node IDs in the cache.
        """
        return list(self.cached_nodes.keys())
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/poecurt/projects/oya/backend && pytest tests/test_cgrag_session.py -v`
Expected: PASS (6 tests)

**Step 5: Commit**

```bash
git add backend/src/oya/qa/session.py backend/tests/test_cgrag_session.py
git commit -m "feat(qa): add CGRAGSession for iterative retrieval state"
```

---

## Task 3: Create SessionStore

**Files:**
- Modify: `backend/src/oya/qa/session.py`
- Modify: `backend/tests/test_cgrag_session.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_cgrag_session.py`:

```python
class TestSessionStore:
    """Tests for SessionStore class."""

    def test_store_get_or_create_new(self):
        """Get with no ID creates new session."""
        from oya.qa.session import SessionStore

        store = SessionStore()

        session = store.get_or_create(None)

        assert session is not None
        assert session.id is not None

    def test_store_get_or_create_existing(self):
        """Get with existing ID returns same session."""
        from oya.qa.session import SessionStore

        store = SessionStore()
        session1 = store.get_or_create(None)

        session2 = store.get_or_create(session1.id)

        assert session2.id == session1.id

    def test_store_get_or_create_expired(self):
        """Get with expired session ID creates new session."""
        from oya.qa.session import SessionStore, CGRAGSession
        from oya.constants.qa import CGRAG_SESSION_TTL_MINUTES
        from datetime import datetime, timedelta

        store = SessionStore()
        session1 = store.get_or_create(None)

        # Manually expire the session
        session1.last_accessed = datetime.now() - timedelta(
            minutes=CGRAG_SESSION_TTL_MINUTES + 1
        )

        session2 = store.get_or_create(session1.id)

        assert session2.id != session1.id

    def test_store_cleanup_expired(self):
        """Cleanup removes expired sessions."""
        from oya.qa.session import SessionStore
        from oya.constants.qa import CGRAG_SESSION_TTL_MINUTES
        from datetime import datetime, timedelta

        store = SessionStore()
        session1 = store.get_or_create(None)
        session2 = store.get_or_create(None)

        # Expire session1
        session1.last_accessed = datetime.now() - timedelta(
            minutes=CGRAG_SESSION_TTL_MINUTES + 1
        )

        store.cleanup_expired()

        # session1 should be gone, session2 should remain
        assert store.get_or_create(session1.id).id != session1.id
        assert store.get_or_create(session2.id).id == session2.id
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/poecurt/projects/oya/backend && pytest tests/test_cgrag_session.py::TestSessionStore -v`
Expected: FAIL with "ImportError"

**Step 3: Write minimal implementation**

Add to `backend/src/oya/qa/session.py`:

```python
class SessionStore:
    """In-memory store for CGRAG sessions.

    Thread-safe store for managing multiple concurrent sessions.
    Sessions are automatically expired based on TTL.
    """

    def __init__(self) -> None:
        """Initialize empty session store."""
        self._sessions: dict[str, CGRAGSession] = {}

    def get_or_create(self, session_id: str | None) -> CGRAGSession:
        """Get existing session or create new one.

        Args:
            session_id: Optional session ID. If None or not found/expired,
                creates a new session.

        Returns:
            The session (existing or newly created).
        """
        if session_id and session_id in self._sessions:
            session = self._sessions[session_id]
            if not session.is_expired():
                session.touch()
                return session
            # Expired - remove and create new
            del self._sessions[session_id]

        # Create new session
        session = CGRAGSession()
        self._sessions[session.id] = session
        return session

    def cleanup_expired(self) -> int:
        """Remove all expired sessions.

        Returns:
            Number of sessions removed.
        """
        expired_ids = [
            sid for sid, session in self._sessions.items() if session.is_expired()
        ]
        for sid in expired_ids:
            del self._sessions[sid]
        return len(expired_ids)
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/poecurt/projects/oya/backend && pytest tests/test_cgrag_session.py::TestSessionStore -v`
Expected: PASS (4 tests)

**Step 5: Commit**

```bash
git add backend/src/oya/qa/session.py backend/tests/test_cgrag_session.py
git commit -m "feat(qa): add SessionStore for managing CGRAG sessions"
```

---

## Task 4: Add Gap Detection Prompt Template

**Files:**
- Modify: `backend/src/oya/generation/prompts.py`
- Create: `backend/tests/test_cgrag_prompts.py`

**Step 1: Write the failing test**

Create `backend/tests/test_cgrag_prompts.py`:

```python
"""Tests for CGRAG prompt templates."""


def test_cgrag_prompt_has_answer_section():
    """CGRAG prompt template includes ANSWER section marker."""
    from oya.generation.prompts import CGRAG_QA_TEMPLATE

    assert "ANSWER:" in CGRAG_QA_TEMPLATE


def test_cgrag_prompt_has_missing_section():
    """CGRAG prompt template includes MISSING section marker."""
    from oya.generation.prompts import CGRAG_QA_TEMPLATE

    assert "MISSING" in CGRAG_QA_TEMPLATE


def test_cgrag_prompt_has_placeholders():
    """CGRAG prompt template has required placeholders."""
    from oya.generation.prompts import CGRAG_QA_TEMPLATE

    assert "{question}" in CGRAG_QA_TEMPLATE
    assert "{context}" in CGRAG_QA_TEMPLATE


def test_format_cgrag_prompt():
    """Format function produces valid prompt string."""
    from oya.generation.prompts import format_cgrag_prompt

    result = format_cgrag_prompt(
        question="How does auth work?",
        context="Some context here",
    )

    assert "How does auth work?" in result
    assert "Some context here" in result
    assert "ANSWER:" in result
    assert "MISSING" in result
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/poecurt/projects/oya/backend && pytest tests/test_cgrag_prompts.py -v`
Expected: FAIL with "ImportError"

**Step 3: Write minimal implementation**

Add to the end of `backend/src/oya/generation/prompts.py`:

```python
# =============================================================================
# CGRAG - Iterative Retrieval (Phase 5)
# =============================================================================

CGRAG_QA_TEMPLATE = """You are answering a question about a codebase. You have been given some context, but it may be incomplete.

## Question
{question}

## Available Context
{context}

## Instructions
1. Answer the question as best you can with the available context
2. If your answer would be MORE COMPLETE with additional code, list what's missing
3. Format your response as:

ANSWER:
[Your answer here]

MISSING (or "NONE" if nothing needed):
- function_name in path/to/file.py
- ClassName in some/module.py
- the file that handles X
"""


def format_cgrag_prompt(question: str, context: str) -> str:
    """Format CGRAG prompt for iterative Q&A.

    Args:
        question: The user's question.
        context: The accumulated context from retrieval passes.

    Returns:
        Formatted prompt string.
    """
    return CGRAG_QA_TEMPLATE.format(question=question, context=context)
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/poecurt/projects/oya/backend && pytest tests/test_cgrag_prompts.py -v`
Expected: PASS (4 tests)

**Step 5: Commit**

```bash
git add backend/src/oya/generation/prompts.py backend/tests/test_cgrag_prompts.py
git commit -m "feat(qa): add CGRAG prompt template for iterative retrieval"
```

---

## Task 5: Add Gap Parsing Function

**Files:**
- Create: `backend/src/oya/qa/cgrag.py`
- Create: `backend/tests/test_cgrag.py`

**Step 1: Write the failing test**

Create `backend/tests/test_cgrag.py`:

```python
"""Tests for CGRAG core functionality."""


class TestParseGaps:
    """Tests for parse_gaps function."""

    def test_parse_gaps_none(self):
        """NONE in response returns empty list."""
        from oya.qa.cgrag import parse_gaps

        response = """ANSWER:
The auth system works by...

MISSING (or "NONE" if nothing needed):
NONE"""

        gaps = parse_gaps(response)

        assert gaps == []

    def test_parse_gaps_single(self):
        """Single gap is parsed correctly."""
        from oya.qa.cgrag import parse_gaps

        response = """ANSWER:
The auth system works by...

MISSING (or "NONE" if nothing needed):
- verify_token in auth/verify.py"""

        gaps = parse_gaps(response)

        assert len(gaps) == 1
        assert "verify_token" in gaps[0]

    def test_parse_gaps_multiple(self):
        """Multiple gaps are parsed correctly."""
        from oya.qa.cgrag import parse_gaps

        response = """ANSWER:
The auth system works by...

MISSING (or "NONE" if nothing needed):
- verify_token in auth/verify.py
- UserModel in models/user.py
- the database connection handler"""

        gaps = parse_gaps(response)

        assert len(gaps) == 3
        assert "verify_token" in gaps[0]
        assert "UserModel" in gaps[1]
        assert "database connection" in gaps[2]

    def test_parse_gaps_no_section(self):
        """Missing MISSING section returns empty list."""
        from oya.qa.cgrag import parse_gaps

        response = """ANSWER:
The auth system works by calling various functions."""

        gaps = parse_gaps(response)

        assert gaps == []

    def test_parse_answer(self):
        """Answer is extracted correctly."""
        from oya.qa.cgrag import parse_answer

        response = """ANSWER:
The auth system works by verifying tokens
and checking user permissions.

MISSING (or "NONE" if nothing needed):
NONE"""

        answer = parse_answer(response)

        assert "auth system works" in answer
        assert "verifying tokens" in answer
        assert "MISSING" not in answer
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/poecurt/projects/oya/backend && pytest tests/test_cgrag.py::TestParseGaps -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

Create `backend/src/oya/qa/cgrag.py`:

```python
"""CGRAG (Contextually-Guided RAG) core functionality.

Implements iterative retrieval where the LLM identifies gaps in context
and the system fetches missing pieces across multiple passes.
"""

from __future__ import annotations

import re


def parse_gaps(response: str) -> list[str]:
    """Parse gap requests from LLM response.

    Extracts the MISSING section and parses each line as a gap request.

    Args:
        response: Raw LLM response with ANSWER and MISSING sections.

    Returns:
        List of gap descriptions (empty if NONE or no section).
    """
    # Find MISSING section
    match = re.search(r"MISSING[^:]*:\s*(.+?)$", response, re.DOTALL | re.IGNORECASE)
    if not match:
        return []

    missing_section = match.group(1).strip()

    # Check for NONE
    if missing_section.upper().startswith("NONE"):
        return []

    # Parse each line as a gap
    gaps = []
    for line in missing_section.split("\n"):
        line = line.strip().lstrip("-").strip()
        if line and not line.upper().startswith("NONE"):
            gaps.append(line)

    return gaps


def parse_answer(response: str) -> str:
    """Extract answer from LLM response.

    Args:
        response: Raw LLM response with ANSWER section.

    Returns:
        The answer text.
    """
    # Find ANSWER section
    match = re.search(r"ANSWER:\s*(.+?)(?=MISSING|$)", response, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()

    # Fallback: return everything before MISSING
    parts = re.split(r"MISSING", response, flags=re.IGNORECASE)
    return parts[0].strip()
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/poecurt/projects/oya/backend && pytest tests/test_cgrag.py::TestParseGaps -v`
Expected: PASS (5 tests)

**Step 5: Commit**

```bash
git add backend/src/oya/qa/cgrag.py backend/tests/test_cgrag.py
git commit -m "feat(qa): add gap parsing for CGRAG responses"
```

---

## Task 6: Add Targeted Retrieval Function

**Files:**
- Modify: `backend/src/oya/qa/cgrag.py`
- Modify: `backend/tests/test_cgrag.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_cgrag.py`:

```python
import networkx as nx


def _make_test_graph() -> nx.DiGraph:
    """Create a test graph with known structure."""
    G = nx.DiGraph()

    nodes = [
        ("auth/handler.py::login", {"name": "login", "type": "function",
            "file_path": "auth/handler.py", "line_start": 10, "line_end": 30}),
        ("auth/verify.py::verify_token", {"name": "verify_token", "type": "function",
            "file_path": "auth/verify.py", "line_start": 5, "line_end": 25}),
        ("db/users.py::get_user", {"name": "get_user", "type": "function",
            "file_path": "db/users.py", "line_start": 20, "line_end": 40}),
    ]
    for node_id, attrs in nodes:
        G.add_node(node_id, **attrs)

    edges = [
        ("auth/handler.py::login", "auth/verify.py::verify_token",
            {"type": "calls", "confidence": 0.9, "line": 15}),
        ("auth/verify.py::verify_token", "db/users.py::get_user",
            {"type": "calls", "confidence": 0.8, "line": 10}),
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
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/poecurt/projects/oya/backend && pytest tests/test_cgrag.py::TestIsSpecificGap tests/test_cgrag.py::TestGraphLookup -v`
Expected: FAIL with "ImportError"

**Step 3: Write minimal implementation**

Add to `backend/src/oya/qa/cgrag.py`:

```python
import networkx as nx

from oya.graph.models import Subgraph
from oya.graph.query import get_neighborhood


def is_specific_gap(gap: str) -> bool:
    """Check if a gap request is specific (vs fuzzy).

    Specific gaps can be looked up directly in the graph.
    Fuzzy gaps need vector search.

    Args:
        gap: The gap description from LLM.

    Returns:
        True if gap is specific enough for graph lookup.
    """
    gap_lower = gap.lower()

    # Contains path separator patterns
    if "::" in gap or " in " in gap_lower:
        return True

    # Contains type keyword followed by name
    if any(
        keyword in gap_lower
        for keyword in ["function ", "class ", "method ", "def "]
    ):
        return True

    return False


def graph_lookup(
    gap: str,
    graph: nx.DiGraph,
    hops: int = 1,
) -> Subgraph | None:
    """Look up a specific gap in the code graph.

    Searches for nodes matching the gap description and returns
    the matching node plus its immediate neighborhood.

    Args:
        gap: The gap description (e.g., "verify_token in auth/verify.py").
        graph: The code knowledge graph.
        hops: Number of hops to include in neighborhood.

    Returns:
        Subgraph containing matched node and neighbors, or None if not found.
    """
    # Extract the likely node name from the gap
    node_name = _extract_node_name(gap)
    if not node_name:
        return None

    # Search for matching node
    matching_node_id = None
    for node_id in graph.nodes():
        node_data = graph.nodes[node_id]
        name = node_data.get("name", "")

        # Exact match on node ID
        if node_id == gap or node_id.endswith(f"::{node_name}"):
            matching_node_id = node_id
            break

        # Match on name
        if name == node_name:
            matching_node_id = node_id
            break

    if not matching_node_id:
        return None

    # Get neighborhood
    return get_neighborhood(graph, matching_node_id, hops=hops, min_confidence=0.0)


def _extract_node_name(gap: str) -> str | None:
    """Extract the likely node/function name from a gap description.

    Args:
        gap: The gap description.

    Returns:
        The extracted name, or None if can't extract.
    """
    # Handle "path::name" format
    if "::" in gap:
        return gap.split("::")[-1].strip()

    # Handle "name in path" format
    if " in " in gap.lower():
        parts = gap.lower().split(" in ")
        return parts[0].strip()

    # Handle "function name" format
    for keyword in ["function ", "class ", "method ", "def "]:
        if keyword in gap.lower():
            idx = gap.lower().index(keyword) + len(keyword)
            rest = gap[idx:].strip()
            # Take first word
            return rest.split()[0] if rest else None

    # Fallback: first word that looks like an identifier
    words = gap.split()
    for word in words:
        # Skip common words
        if word.lower() in {"the", "a", "an", "in", "for", "to", "of", "that", "which"}:
            continue
        # Check if looks like identifier (starts with letter, contains only word chars)
        if word[0].isalpha() and word.replace("_", "").isalnum():
            return word

    return None
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/poecurt/projects/oya/backend && pytest tests/test_cgrag.py::TestIsSpecificGap tests/test_cgrag.py::TestGraphLookup -v`
Expected: PASS (7 tests)

**Step 5: Commit**

```bash
git add backend/src/oya/qa/cgrag.py backend/tests/test_cgrag.py
git commit -m "feat(qa): add targeted retrieval functions for CGRAG"
```

---

## Task 7: Add CGRAGMetadata Schema

**Files:**
- Modify: `backend/src/oya/qa/schemas.py`
- Create: `backend/tests/test_cgrag_schemas.py`

**Step 1: Write the failing test**

Create `backend/tests/test_cgrag_schemas.py`:

```python
"""Tests for CGRAG schema additions."""


def test_cgrag_metadata_creation():
    """CGRAGMetadata can be created with all fields."""
    from oya.qa.schemas import CGRAGMetadata

    metadata = CGRAGMetadata(
        passes_used=2,
        gaps_identified=["verify_token", "get_user"],
        gaps_resolved=["verify_token"],
        gaps_unresolved=["get_user"],
        session_id="abc-123",
        context_from_cache=True,
    )

    assert metadata.passes_used == 2
    assert len(metadata.gaps_identified) == 2
    assert len(metadata.gaps_resolved) == 1
    assert len(metadata.gaps_unresolved) == 1
    assert metadata.session_id == "abc-123"
    assert metadata.context_from_cache is True


def test_cgrag_metadata_defaults():
    """CGRAGMetadata has sensible defaults."""
    from oya.qa.schemas import CGRAGMetadata

    metadata = CGRAGMetadata(passes_used=1)

    assert metadata.passes_used == 1
    assert metadata.gaps_identified == []
    assert metadata.gaps_resolved == []
    assert metadata.gaps_unresolved == []
    assert metadata.session_id is None
    assert metadata.context_from_cache is False


def test_qa_request_has_session_id():
    """QARequest has optional session_id field."""
    from oya.qa.schemas import QARequest

    # Without session_id
    request = QARequest(question="How does X work?")
    assert request.session_id is None

    # With session_id
    request = QARequest(question="How does X work?", session_id="abc-123")
    assert request.session_id == "abc-123"


def test_qa_response_has_cgrag():
    """QAResponse has optional cgrag field."""
    from oya.qa.schemas import QAResponse, CGRAGMetadata, ConfidenceLevel, SearchQuality

    response = QAResponse(
        answer="The answer",
        citations=[],
        confidence=ConfidenceLevel.HIGH,
        disclaimer="Test",
        search_quality=SearchQuality(
            semantic_searched=True,
            fts_searched=True,
            results_found=5,
            results_used=3,
        ),
        cgrag=CGRAGMetadata(passes_used=2),
    )

    assert response.cgrag is not None
    assert response.cgrag.passes_used == 2
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/poecurt/projects/oya/backend && pytest tests/test_cgrag_schemas.py -v`
Expected: FAIL with "ImportError" for CGRAGMetadata

**Step 3: Write minimal implementation**

Modify `backend/src/oya/qa/schemas.py` to add CGRAGMetadata and update QARequest/QAResponse:

```python
"""Q&A request and response schemas."""

from enum import Enum

from pydantic import BaseModel, Field


class ConfidenceLevel(str, Enum):
    """Confidence level for Q&A answers."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class SearchQuality(BaseModel):
    """Transparency about search execution."""

    semantic_searched: bool = Field(..., description="Did vector search succeed?")
    fts_searched: bool = Field(..., description="Did FTS search succeed?")
    results_found: int = Field(..., description="Total results before dedup")
    results_used: int = Field(..., description="Results after dedup, within token budget")


class Citation(BaseModel):
    """Citation reference in an answer."""

    path: str = Field(..., description="Wiki-relative path of the cited source")
    title: str = Field(..., description="Display title for the citation")
    lines: str | None = Field(None, description="Line range if applicable (e.g., '10-20')")
    url: str = Field(..., description="Frontend route (e.g., '/files/src_main-py')")


class CGRAGMetadata(BaseModel):
    """Metadata about the iterative retrieval process."""

    passes_used: int = Field(..., description="Number of retrieval passes (1-3)")
    gaps_identified: list[str] = Field(
        default_factory=list,
        description="All gaps the LLM requested across passes",
    )
    gaps_resolved: list[str] = Field(
        default_factory=list,
        description="Gaps that were successfully retrieved",
    )
    gaps_unresolved: list[str] = Field(
        default_factory=list,
        description="Gaps that could not be found",
    )
    session_id: str | None = Field(
        None,
        description="Session ID for follow-up questions",
    )
    context_from_cache: bool = Field(
        False,
        description="Whether session cache contributed context",
    )


class QARequest(BaseModel):
    """Request for Q&A endpoint."""

    question: str = Field(..., min_length=1, description="The question to answer")
    use_graph: bool = Field(default=True, description="Whether to use graph expansion")
    session_id: str | None = Field(
        None,
        description="Session ID for CGRAG context continuity",
    )


class QAResponse(BaseModel):
    """Response from Q&A endpoint."""

    answer: str = Field(..., description="The generated answer")
    citations: list[Citation] = Field(
        default_factory=list,
        description="Citations referenced in the answer",
    )
    confidence: ConfidenceLevel = Field(
        ...,
        description="Confidence level: high, medium, or low",
    )
    disclaimer: str = Field(
        ...,
        description="Disclaimer about AI-generated content",
    )
    search_quality: SearchQuality = Field(
        ...,
        description="Metrics about search execution",
    )
    cgrag: CGRAGMetadata | None = Field(
        None,
        description="CGRAG iteration metadata (if iterative retrieval was used)",
    )
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/poecurt/projects/oya/backend && pytest tests/test_cgrag_schemas.py -v`
Expected: PASS (4 tests)

**Step 5: Commit**

```bash
git add backend/src/oya/qa/schemas.py backend/tests/test_cgrag_schemas.py
git commit -m "feat(qa): add CGRAGMetadata schema and session_id to QARequest"
```

---

## Task 8: Add CGRAG Core Loop

**Files:**
- Modify: `backend/src/oya/qa/cgrag.py`
- Modify: `backend/tests/test_cgrag.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_cgrag.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock


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
        assert "verify_token" in result.gaps_identified

    @pytest.mark.asyncio
    async def test_stops_at_max_passes(self):
        """Stops after max passes even if gaps remain."""
        from oya.qa.cgrag import run_cgrag_loop
        from oya.qa.session import CGRAGSession
        from oya.constants.qa import CGRAG_MAX_PASSES

        mock_llm = AsyncMock()
        # Always report gaps
        mock_llm.generate.return_value = """ANSWER:
Partial answer.

MISSING (or "NONE" if nothing needed):
- some_function"""

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
- nonexistent_function"""

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
        assert "nonexistent_function" in result.gaps_unresolved
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/poecurt/projects/oya/backend && pytest tests/test_cgrag.py::TestCGRAGLoop -v`
Expected: FAIL with "ImportError" for run_cgrag_loop

**Step 3: Write minimal implementation**

Add to `backend/src/oya/qa/cgrag.py`:

```python
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from oya.constants.qa import CGRAG_MAX_PASSES, CGRAG_TARGETED_TOP_K
from oya.generation.prompts import format_cgrag_prompt
from oya.graph.models import Node, Subgraph
from oya.graph.query import get_neighborhood
from oya.qa.session import CGRAGSession

if TYPE_CHECKING:
    from oya.llm.client import LLMClient
    from oya.vectorstore.store import VectorStore


@dataclass
class CGRAGResult:
    """Result from CGRAG iteration loop."""

    answer: str
    passes_used: int
    gaps_identified: list[str] = field(default_factory=list)
    gaps_resolved: list[str] = field(default_factory=list)
    gaps_unresolved: list[str] = field(default_factory=list)
    context_from_cache: bool = False


async def run_cgrag_loop(
    question: str,
    initial_context: str,
    session: CGRAGSession,
    llm: "LLMClient",
    graph: "nx.DiGraph | None",
    vectorstore: "VectorStore | None",
) -> CGRAGResult:
    """Run the CGRAG iteration loop.

    Performs multiple retrieval passes, with the LLM identifying gaps
    in context after each pass until satisfied or max passes reached.

    Args:
        question: The user's question.
        initial_context: Context from initial retrieval (Phase 4 style).
        session: CGRAG session for caching.
        llm: LLM client for generating answers.
        graph: Code graph for targeted lookups (optional).
        vectorstore: Vector store for fuzzy lookups (optional).

    Returns:
        CGRAGResult with answer and iteration metadata.
    """
    context = initial_context
    all_gaps_identified: list[str] = []
    gaps_resolved: list[str] = []
    not_found: set[str] = set(session.not_found)  # Start with session's not_found
    context_from_cache = len(session.cached_nodes) > 0

    answer = ""
    passes_used = 0

    for pass_num in range(1, CGRAG_MAX_PASSES + 1):
        passes_used = pass_num

        # Generate answer + identify gaps
        prompt = format_cgrag_prompt(question=question, context=context)
        response = await llm.generate(prompt=prompt, temperature=0.2)

        answer = parse_answer(response)
        gaps = parse_gaps(response)

        # Track gaps
        for gap in gaps:
            if gap not in all_gaps_identified:
                all_gaps_identified.append(gap)

        # Check termination: no gaps
        if not gaps:
            break

        # Check termination: all gaps already not found
        if all(gap in not_found for gap in gaps):
            break

        # Targeted retrieval for gaps
        new_context_parts: list[str] = []
        for gap in gaps:
            if gap in not_found:
                continue  # Already tried and failed

            retrieved = await _retrieve_for_gap(gap, graph, vectorstore)
            if retrieved:
                new_context_parts.append(retrieved)
                gaps_resolved.append(gap)
                # Add nodes to session cache
                # (In full implementation, would extract nodes from retrieved)
            else:
                not_found.add(gap)
                session.add_not_found(gap)

        # Append new context
        if new_context_parts:
            context = context + "\n\n---\n\n" + "\n\n".join(new_context_parts)

    # Compute unresolved
    gaps_unresolved = [g for g in all_gaps_identified if g in not_found]

    return CGRAGResult(
        answer=answer,
        passes_used=passes_used,
        gaps_identified=all_gaps_identified,
        gaps_resolved=gaps_resolved,
        gaps_unresolved=gaps_unresolved,
        context_from_cache=context_from_cache,
    )


async def _retrieve_for_gap(
    gap: str,
    graph: "nx.DiGraph | None",
    vectorstore: "VectorStore | None",
) -> str | None:
    """Retrieve context for a single gap.

    Tries graph lookup first for specific gaps, falls back to vector search.

    Args:
        gap: The gap description.
        graph: Code graph (optional).
        vectorstore: Vector store (optional).

    Returns:
        Retrieved context string, or None if not found.
    """
    # Try graph lookup for specific gaps
    if graph is not None and is_specific_gap(gap):
        subgraph = graph_lookup(gap, graph)
        if subgraph and subgraph.nodes:
            return _format_subgraph_context(subgraph)

    # Try vector search for fuzzy gaps
    if vectorstore is not None:
        try:
            results = vectorstore.query(query_text=gap, n_results=CGRAG_TARGETED_TOP_K)
            documents = results.get("documents", [[]])[0]
            if documents:
                return "\n\n".join(documents[:CGRAG_TARGETED_TOP_K])
        except Exception:
            pass

    return None


def _format_subgraph_context(subgraph: Subgraph) -> str:
    """Format a subgraph as context text.

    Args:
        subgraph: The subgraph to format.

    Returns:
        Formatted context string.
    """
    parts = []
    for node in subgraph.nodes:
        node_text = f"### {node.file_path}::{node.name} (lines {node.line_start}-{node.line_end})"
        if node.docstring:
            node_text += f"\n> {node.docstring}"
        if node.signature:
            node_text += f"\n```\n{node.signature}\n```"
        parts.append(node_text)
    return "\n\n".join(parts)
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/poecurt/projects/oya/backend && pytest tests/test_cgrag.py::TestCGRAGLoop -v`
Expected: PASS (4 tests)

**Step 5: Commit**

```bash
git add backend/src/oya/qa/cgrag.py backend/tests/test_cgrag.py
git commit -m "feat(qa): add CGRAG core iteration loop"
```

---

## Task 9: Integrate CGRAG into QAService

**Files:**
- Modify: `backend/src/oya/qa/service.py`
- Modify: `backend/tests/test_qa_service.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_qa_service.py`:

```python
class TestQAServiceCGRAG:
    """Tests for CGRAG integration in QAService."""

    @pytest.mark.asyncio
    async def test_qa_returns_cgrag_metadata(self, mock_vectorstore, mock_db, mock_llm):
        """QAResponse includes CGRAG metadata."""
        # Mock LLM to return CGRAG-formatted response
        mock_llm.generate.return_value = """ANSWER:
The system works by doing things.

MISSING (or "NONE" if nothing needed):
NONE"""

        service = QAService(mock_vectorstore, mock_db, mock_llm)
        request = QARequest(question="How does it work?")

        response = await service.ask(request)

        assert response.cgrag is not None
        assert response.cgrag.passes_used >= 1

    @pytest.mark.asyncio
    async def test_qa_uses_session_id(self, mock_vectorstore, mock_db, mock_llm):
        """Session ID is preserved across requests."""
        mock_llm.generate.return_value = """ANSWER:
Answer here.

MISSING (or "NONE" if nothing needed):
NONE"""

        service = QAService(mock_vectorstore, mock_db, mock_llm)

        # First request - no session
        request1 = QARequest(question="First question")
        response1 = await service.ask(request1)
        session_id = response1.cgrag.session_id

        assert session_id is not None

        # Second request - with session
        request2 = QARequest(question="Follow-up", session_id=session_id)
        response2 = await service.ask(request2)

        assert response2.cgrag.session_id == session_id
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/poecurt/projects/oya/backend && pytest tests/test_qa_service.py::TestQAServiceCGRAG -v`
Expected: FAIL (cgrag is None or test infrastructure issues)

**Step 3: Write the implementation**

Modify `backend/src/oya/qa/service.py`:

1. Add imports at the top:

```python
from oya.qa.cgrag import run_cgrag_loop, CGRAGResult
from oya.qa.schemas import CGRAGMetadata
from oya.qa.session import CGRAGSession, SessionStore
```

2. Add session store as class attribute in `__init__`:

```python
# Add to imports at module level
_session_store = SessionStore()
```

3. Modify `_ask_normal` to use CGRAG:

Replace the `_ask_normal` method with a version that uses CGRAG. The key changes are:
- Get or create session from store
- Build initial context (existing logic)
- Call `run_cgrag_loop` instead of single LLM call
- Return response with CGRAGMetadata

The full implementation changes are significant - see the actual code modification below.

**Step 4: Run test to verify it passes**

Run: `cd /Users/poecurt/projects/oya/backend && pytest tests/test_qa_service.py::TestQAServiceCGRAG -v`
Expected: PASS (2 tests)

**Step 5: Commit**

```bash
git add backend/src/oya/qa/service.py backend/tests/test_qa_service.py
git commit -m "feat(qa): integrate CGRAG iteration into QAService"
```

---

## Task 10: Update Q&A Router

**Files:**
- Modify: `backend/src/oya/api/routers/qa.py`

**Step 1: Verify router works with session**

The router should already work since session management is handled inside QAService.
Just verify the endpoint still functions.

**Step 2: Test manually**

Run: `cd /Users/poecurt/projects/oya/backend && python -c "from oya.api.routers.qa import router; print('Router OK')"`
Expected: `Router OK`

**Step 3: Commit if changes needed**

```bash
git add backend/src/oya/api/routers/qa.py
git commit -m "feat(qa): ensure router supports CGRAG session handling"
```

---

## Task 11: Run Full Test Suite

**Files:** None (verification only)

**Step 1: Run all backend tests**

Run: `cd /Users/poecurt/projects/oya/backend && pytest -v`
Expected: All tests pass

**Step 2: Run linting**

Run: `cd /Users/poecurt/projects/oya/backend && ruff check src/ tests/`
Expected: No errors

**Step 3: Run formatting**

Run: `cd /Users/poecurt/projects/oya/backend && ruff format src/ tests/`
Expected: Files formatted

**Step 4: Run type checking**

Run: `cd /Users/poecurt/projects/oya/backend && mypy src/oya`
Expected: No errors

**Step 5: Run make all**

Run: `cd /Users/poecurt/projects/oya && make all`
Expected: All checks pass

**Step 6: Fix any issues and commit**

```bash
git add -A
git commit -m "fix: address lint and test issues from Phase 5 implementation"
```

---

## Task 12: Final Phase 5 Commit

**Step 1: Verify all changes are committed**

Run: `git status`
Expected: Clean working tree

**Step 2: Create summary commit if needed**

```bash
git add -A
git commit -m "feat(qa): complete Phase 5 CGRAG iterative retrieval

- Add CGRAG constants (max passes, session TTL, etc.)
- Create CGRAGSession and SessionStore for state management
- Add gap detection prompt template
- Implement gap parsing and targeted retrieval
- Add CGRAGMetadata schema
- Integrate CGRAG loop into QAService
- Add comprehensive tests"
```

---

## Summary

| Task | Description | Files |
|------|-------------|-------|
| 1 | Add CGRAG constants | `constants/qa.py` |
| 2 | Create CGRAGSession | `qa/session.py` |
| 3 | Create SessionStore | `qa/session.py` |
| 4 | Add gap detection prompt | `generation/prompts.py` |
| 5 | Add gap parsing | `qa/cgrag.py` |
| 6 | Add targeted retrieval | `qa/cgrag.py` |
| 7 | Add CGRAGMetadata schema | `qa/schemas.py` |
| 8 | Add CGRAG core loop | `qa/cgrag.py` |
| 9 | Integrate into QAService | `qa/service.py` |
| 10 | Update Q&A router | `api/routers/qa.py` |
| 11 | Run full test suite | - |
| 12 | Final commit | - |

**Estimated tests:** 25+ new tests across 4 test files
