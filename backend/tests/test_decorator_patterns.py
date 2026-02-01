"""Tests for decorator pattern registry."""

import re

from oya.parsing.decorator_patterns import (
    ENTRY_POINT_PATTERNS,
    REFERENCE_PATTERNS,
    EntryPointPattern,
    ReferencePattern,
)


def test_reference_pattern_dataclass_is_frozen():
    """ReferencePattern is immutable (frozen dataclass)."""
    pattern = ReferencePattern(
        decorator_name=r"^get$",
        object_name=r".*",
        arguments=("response_model",),
    )
    # Attempting to modify should raise
    try:
        pattern.decorator_name = "new"
        assert False, "Should have raised FrozenInstanceError"
    except AttributeError:
        pass  # Expected - frozen dataclass


def test_entry_point_pattern_dataclass_is_frozen():
    """EntryPointPattern is immutable (frozen dataclass)."""
    pattern = EntryPointPattern(
        decorator_name=r"^fixture$",
        object_name=r"^pytest$",
    )
    try:
        pattern.decorator_name = "new"
        assert False, "Should have raised FrozenInstanceError"
    except AttributeError:
        pass  # Expected


def test_python_reference_patterns_exist():
    """Python reference patterns are defined."""
    assert "python" in REFERENCE_PATTERNS
    assert len(REFERENCE_PATTERNS["python"]) > 0


def test_python_entry_point_patterns_exist():
    """Python entry point patterns are defined."""
    assert "python" in ENTRY_POINT_PATTERNS
    assert len(ENTRY_POINT_PATTERNS["python"]) > 0


def test_fastapi_route_pattern_matches():
    """FastAPI route patterns match HTTP methods."""
    patterns = REFERENCE_PATTERNS["python"]
    route_pattern = next(p for p in patterns if "response_model" in p.arguments)

    # Should match HTTP methods
    assert re.match(route_pattern.decorator_name, "get")
    assert re.match(route_pattern.decorator_name, "post")
    assert re.match(route_pattern.decorator_name, "put")
    assert re.match(route_pattern.decorator_name, "patch")
    assert re.match(route_pattern.decorator_name, "delete")

    # Should NOT match non-HTTP methods
    assert not re.match(route_pattern.decorator_name, "route")
    assert not re.match(route_pattern.decorator_name, "depends")


def test_fastapi_entry_point_pattern_matches():
    """FastAPI route handlers are marked as entry points."""
    patterns = ENTRY_POINT_PATTERNS["python"]
    route_patterns = [p for p in patterns if re.match(p.decorator_name, "get")]

    assert len(route_patterns) > 0
