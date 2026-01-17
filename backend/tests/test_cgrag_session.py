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
        session.last_accessed = datetime.now() - timedelta(minutes=CGRAG_SESSION_TTL_MINUTES + 1)
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
        from oya.qa.session import SessionStore
        from oya.constants.qa import CGRAG_SESSION_TTL_MINUTES

        store = SessionStore()
        session1 = store.get_or_create(None)

        # Manually expire the session
        session1.last_accessed = datetime.now() - timedelta(minutes=CGRAG_SESSION_TTL_MINUTES + 1)

        session2 = store.get_or_create(session1.id)

        assert session2.id != session1.id

    def test_store_cleanup_expired(self):
        """Cleanup removes expired sessions."""
        from oya.qa.session import SessionStore
        from oya.constants.qa import CGRAG_SESSION_TTL_MINUTES

        store = SessionStore()
        session1 = store.get_or_create(None)
        session2 = store.get_or_create(None)

        # Expire session1
        session1.last_accessed = datetime.now() - timedelta(minutes=CGRAG_SESSION_TTL_MINUTES + 1)

        store.cleanup_expired()

        # session1 should be gone, session2 should remain
        assert store.get_or_create(session1.id).id != session1.id
        assert store.get_or_create(session2.id).id == session2.id
