"""Tests for base parser pattern matching helpers."""

from oya.parsing.base import BaseParser
from oya.parsing.decorator_patterns import EntryPointPattern, ReferencePattern


class ConcreteParser(BaseParser):
    """Minimal concrete parser for testing base class methods."""

    @property
    def supported_extensions(self) -> list[str]:
        return [".test"]

    @property
    def language_name(self) -> str:
        return "python"  # Use python to get real patterns

    def parse(self, file_path, content):
        raise NotImplementedError


def test_get_reference_patterns_returns_python_patterns():
    """_get_reference_patterns returns patterns for parser's language."""
    parser = ConcreteParser()
    patterns = parser._get_reference_patterns()

    assert len(patterns) > 0
    assert all(isinstance(p, ReferencePattern) for p in patterns)


def test_get_entry_point_patterns_returns_python_patterns():
    """_get_entry_point_patterns returns patterns for parser's language."""
    parser = ConcreteParser()
    patterns = parser._get_entry_point_patterns()

    assert len(patterns) > 0
    assert all(isinstance(p, EntryPointPattern) for p in patterns)


def test_matches_decorator_pattern_simple_match():
    """_matches_decorator_pattern returns True for matching decorator."""
    parser = ConcreteParser()
    pattern = ReferencePattern(
        decorator_name=r"^get$",
        object_name=r".*",
        arguments=("response_model",),
    )

    assert parser._matches_decorator_pattern("get", "router", pattern) is True
    assert parser._matches_decorator_pattern("get", "app", pattern) is True


def test_matches_decorator_pattern_name_mismatch():
    """_matches_decorator_pattern returns False for wrong decorator name."""
    parser = ConcreteParser()
    pattern = ReferencePattern(
        decorator_name=r"^get$",
        object_name=r".*",
        arguments=("response_model",),
    )

    assert parser._matches_decorator_pattern("post", "router", pattern) is False
    assert parser._matches_decorator_pattern("route", "app", pattern) is False


def test_matches_decorator_pattern_object_mismatch():
    """_matches_decorator_pattern returns False for wrong object name."""
    parser = ConcreteParser()
    pattern = ReferencePattern(
        decorator_name=r"^fixture$",
        object_name=r"^pytest$",  # Only matches pytest
        arguments=(),
    )

    assert parser._matches_decorator_pattern("fixture", "pytest", pattern) is True
    assert parser._matches_decorator_pattern("fixture", "other", pattern) is False


def test_matches_decorator_pattern_none_object_for_bare_decorator():
    """_matches_decorator_pattern handles bare decorators (no object)."""
    parser = ConcreteParser()
    pattern = EntryPointPattern(
        decorator_name=r"^fixture$",
        object_name=None,  # Bare decorator
    )

    # None pattern matches any object_name (including None)
    assert parser._matches_decorator_pattern("fixture", None, pattern) is True
    assert parser._matches_decorator_pattern("fixture", "pytest", pattern) is True


def test_matches_decorator_pattern_requires_object_when_specified():
    """_matches_decorator_pattern requires object when pattern specifies one."""
    parser = ConcreteParser()
    pattern = ReferencePattern(
        decorator_name=r"^get$",
        object_name=r"^router$",  # Must be 'router'
        arguments=("response_model",),
    )

    # Object must match when pattern specifies one
    assert parser._matches_decorator_pattern("get", "router", pattern) is True
    assert parser._matches_decorator_pattern("get", None, pattern) is False
