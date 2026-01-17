"""Graph analysis utilities for architecture generation."""

import re

import networkx as nx


# Patterns that indicate test files
TEST_PATTERNS = [
    r"^tests?/",  # tests/ or test/ directory
    r"/tests?/",  # tests/ or test/ subdirectory
    r"test_[^/]+\.py$",  # test_*.py files
    r"_test\.py$",  # *_test.py files
    r"\.test\.[jt]sx?$",  # *.test.js, *.test.ts, *.test.tsx
    r"\.spec\.[jt]sx?$",  # *.spec.js, *.spec.ts
    r"__tests__/",  # __tests__/ directory (Jest convention)
]


def is_test_file(file_path: str) -> bool:
    """Check if a file path represents a test file."""
    for pattern in TEST_PATTERNS:
        if re.search(pattern, file_path):
            return True
    return False


def filter_test_nodes(graph: nx.DiGraph) -> nx.DiGraph:
    """Return a copy of the graph with test nodes and their edges removed.

    Args:
        graph: The code graph.

    Returns:
        New graph with test files filtered out.
    """
    filtered = nx.DiGraph()

    # Copy non-test nodes
    for node_id, attrs in graph.nodes(data=True):
        file_path = attrs.get("file_path", node_id)
        if not is_test_file(file_path):
            filtered.add_node(node_id, **attrs)

    # Copy edges between non-test nodes
    for source, target, attrs in graph.edges(data=True):
        if filtered.has_node(source) and filtered.has_node(target):
            filtered.add_edge(source, target, **attrs)

    return filtered
