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


def get_top_level_directory(file_path: str) -> str:
    """Extract the top-level directory from a file path.

    Args:
        file_path: Path like "api/routes.py" or "src/api/routes.py"

    Returns:
        Top-level directory name, e.g., "api" or "src"
    """
    parts = file_path.split("/")
    return parts[0] if parts else file_path


def get_component_graph(
    graph: nx.DiGraph,
    min_confidence: float = 0.0,
) -> nx.DiGraph:
    """Aggregate the code graph to directory-level components.

    Args:
        graph: The code graph with file-level nodes.
        min_confidence: Minimum edge confidence to include.

    Returns:
        New graph where nodes are top-level directories and edges
        represent aggregated dependencies between them.
    """
    component_graph = nx.DiGraph()

    # Map each node to its component (top-level directory)
    node_to_component: dict[str, str] = {}
    for node_id, attrs in graph.nodes(data=True):
        file_path = attrs.get("file_path", node_id)
        component = get_top_level_directory(file_path)
        node_to_component[node_id] = component

        # Add component node if not exists
        if not component_graph.has_node(component):
            component_graph.add_node(component)

    # Aggregate edges
    edge_data: dict[tuple[str, str], list[float]] = {}
    for source, target, attrs in graph.edges(data=True):
        confidence = attrs.get("confidence", 0)
        if confidence < min_confidence:
            continue

        src_component = node_to_component.get(source)
        tgt_component = node_to_component.get(target)

        if src_component and tgt_component and src_component != tgt_component:
            key = (src_component, tgt_component)
            if key not in edge_data:
                edge_data[key] = []
            edge_data[key].append(confidence)

    # Add aggregated edges
    for (src, tgt), confidences in edge_data.items():
        component_graph.add_edge(
            src,
            tgt,
            confidence=max(confidences),
            count=len(confidences),
        )

    return component_graph
