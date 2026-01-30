"""Tests for dead code detection."""

from oya.generation.deadcode import DeadcodeReport, UnusedSymbol


def test_deadcode_report_structure():
    """DeadcodeReport contains categorized unused symbols."""
    report = DeadcodeReport(
        probably_unused_functions=[
            UnusedSymbol(
                name="old_func",
                file_path="utils/legacy.py",
                line=42,
                symbol_type="function",
            )
        ],
        probably_unused_classes=[],
        possibly_unused_functions=[],
        possibly_unused_classes=[],
        possibly_unused_variables=[],
    )

    assert len(report.probably_unused_functions) == 1
    assert report.probably_unused_functions[0].name == "old_func"


def test_is_excluded_test_functions():
    """Test functions are excluded."""
    from oya.generation.deadcode import is_excluded

    assert is_excluded("test_login") is True
    assert is_excluded("login_test") is True
    assert is_excluded("test_") is True


def test_is_excluded_dunders():
    """Python dunders are excluded."""
    from oya.generation.deadcode import is_excluded

    assert is_excluded("__init__") is True
    assert is_excluded("__str__") is True
    assert is_excluded("__all__") is True


def test_is_excluded_entry_points():
    """Entry point names are excluded."""
    from oya.generation.deadcode import is_excluded

    assert is_excluded("main") is True
    assert is_excluded("app") is True


def test_is_excluded_private():
    """Private symbols (underscore prefix) are excluded."""
    from oya.generation.deadcode import is_excluded

    assert is_excluded("_internal_helper") is True
    assert is_excluded("_cache") is True


def test_is_excluded_normal_names():
    """Normal function names are not excluded."""
    from oya.generation.deadcode import is_excluded

    assert is_excluded("calculate_total") is False
    assert is_excluded("UserService") is False
    assert is_excluded("process_data") is False
