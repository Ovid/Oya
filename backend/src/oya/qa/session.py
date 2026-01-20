"""CGRAG session management for iterative Q&A retrieval."""

from __future__ import annotations

import uuid
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from oya.config import ConfigError, load_settings
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
        try:
            settings = load_settings()
            max_nodes = settings.ask.cgrag_session_max_nodes
        except (ValueError, OSError, ConfigError):
            # Settings not available (e.g., WORKSPACE_PATH not set in tests)
            max_nodes = 50  # Default from CONFIG_SCHEMA
        while len(self.cached_nodes) > max_nodes:
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
        try:
            settings = load_settings()
            ttl_minutes = settings.ask.cgrag_session_ttl_minutes
        except (ValueError, OSError, ConfigError):
            # Settings not available (e.g., WORKSPACE_PATH not set in tests)
            ttl_minutes = 30  # Default from CONFIG_SCHEMA
        expiry = self.last_accessed + timedelta(minutes=ttl_minutes)
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


class SessionStore:
    """In-memory store for CGRAG sessions.

    Manages multiple concurrent sessions with automatic expiration.
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
        expired_ids = [sid for sid, session in self._sessions.items() if session.is_expired()]
        for sid in expired_ids:
            del self._sessions[sid]
        return len(expired_ids)
