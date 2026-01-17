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
