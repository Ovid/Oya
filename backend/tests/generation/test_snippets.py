"""Tests for call-site snippet extraction."""

import pytest

from oya.generation.snippets import is_test_file, select_best_call_site
from oya.graph.models import CallSite


@pytest.mark.parametrize(
    "file_path",
    [
        "Component.test.tsx",
        "Component.spec.tsx",
        "src/components/Button.test.tsx",
        "src/components/Button.spec.tsx",
    ],
)
def test_is_test_file_detects_tsx_test_files(file_path: str):
    """TSX test files should be detected as test files."""
    assert is_test_file(file_path) is True


def test_select_best_call_site_prefers_external_over_internal():
    """External callers (different file) should be preferred over internal callers (same file)."""
    target_file = "src/mymodule.py"

    internal_caller = CallSite(
        caller_file="src/mymodule.py",  # Same as target
        caller_symbol="internal_func",
        line=50,
        target_symbol="my_function",
    )
    external_caller = CallSite(
        caller_file="src/other.py",  # Different from target
        caller_symbol="external_func",
        line=10,
        target_symbol="my_function",
    )

    best, others = select_best_call_site(
        call_sites=[internal_caller, external_caller],
        file_contents={},
        target_file=target_file,
    )

    assert best == external_caller
    assert internal_caller in others


def test_select_best_call_site_falls_back_to_internal_when_no_external():
    """When only internal callers exist, use them."""
    target_file = "src/mymodule.py"

    internal_caller = CallSite(
        caller_file="src/mymodule.py",
        caller_symbol="helper",
        line=20,
        target_symbol="my_function",
    )

    best, others = select_best_call_site(
        call_sites=[internal_caller],
        file_contents={},
        target_file=target_file,
    )

    assert best == internal_caller
    assert others == []


def test_select_best_call_site_external_production_beats_external_test():
    """Among external callers, production beats test."""
    target_file = "src/mymodule.py"

    external_test = CallSite(
        caller_file="tests/test_mymodule.py",
        caller_symbol="test_func",
        line=10,
        target_symbol="my_function",
    )
    external_prod = CallSite(
        caller_file="src/other.py",
        caller_symbol="use_func",
        line=20,
        target_symbol="my_function",
    )

    best, others = select_best_call_site(
        call_sites=[external_test, external_prod],
        file_contents={},
        target_file=target_file,
    )

    assert best == external_prod
    assert external_test in others


def test_select_best_call_site_without_target_file_maintains_backward_compat():
    """Without target_file, function should work as before (all treated as external)."""
    caller1 = CallSite(
        caller_file="src/a.py",
        caller_symbol="func_a",
        line=10,
        target_symbol="target",
    )
    caller2 = CallSite(
        caller_file="tests/test_a.py",
        caller_symbol="test_func",
        line=20,
        target_symbol="target",
    )

    # Without target_file, production should still beat test
    best, others = select_best_call_site(
        call_sites=[caller2, caller1],
        file_contents={},
    )

    assert best == caller1  # Production beats test
    assert caller2 in others
