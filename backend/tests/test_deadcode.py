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
