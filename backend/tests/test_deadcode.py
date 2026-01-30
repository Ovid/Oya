"""Tests for dead code detection."""

import json

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


def test_analyze_deadcode_finds_unused_function(tmp_path):
    """analyze_deadcode identifies function with no incoming edges."""
    from oya.generation.deadcode import analyze_deadcode

    # Create graph files
    graph_dir = tmp_path / "graph"
    graph_dir.mkdir()

    nodes = [
        {
            "id": "main.py::main",
            "name": "main",
            "type": "function",
            "file_path": "main.py",
            "line_start": 1,
            "line_end": 10,
            "docstring": None,
            "signature": None,
            "parent": None,
        },
        {
            "id": "utils.py::unused_helper",
            "name": "unused_helper",
            "type": "function",
            "file_path": "utils.py",
            "line_start": 5,
            "line_end": 15,
            "docstring": None,
            "signature": None,
            "parent": None,
        },
        {
            "id": "utils.py::used_helper",
            "name": "used_helper",
            "type": "function",
            "file_path": "utils.py",
            "line_start": 20,
            "line_end": 30,
            "docstring": None,
            "signature": None,
            "parent": None,
        },
    ]

    edges = [
        {
            "source": "main.py::main",
            "target": "utils.py::used_helper",
            "type": "calls",
            "confidence": 0.9,
            "line": 5,
        }
    ]

    (graph_dir / "nodes.json").write_text(json.dumps(nodes))
    (graph_dir / "edges.json").write_text(json.dumps(edges))

    report = analyze_deadcode(graph_dir)

    # unused_helper has no incoming edges, should be flagged
    assert len(report.probably_unused_functions) == 1
    assert report.probably_unused_functions[0].name == "unused_helper"
    assert report.probably_unused_functions[0].file_path == "utils.py"
    assert report.probably_unused_functions[0].line == 5

    # used_helper and main should not be flagged
    # (main is excluded, used_helper has incoming edge)


def test_analyze_deadcode_excludes_test_functions(tmp_path):
    """Test functions are not flagged even without callers."""
    from oya.generation.deadcode import analyze_deadcode

    graph_dir = tmp_path / "graph"
    graph_dir.mkdir()

    nodes = [
        {
            "id": "tests/test_utils.py::test_something",
            "name": "test_something",
            "type": "function",
            "file_path": "tests/test_utils.py",
            "line_start": 1,
            "line_end": 10,
            "docstring": None,
            "signature": None,
            "parent": None,
        },
    ]

    (graph_dir / "nodes.json").write_text(json.dumps(nodes))
    (graph_dir / "edges.json").write_text(json.dumps([]))

    report = analyze_deadcode(graph_dir)

    assert len(report.probably_unused_functions) == 0


def test_analyze_deadcode_low_confidence_to_possibly(tmp_path):
    """Symbols with only low-confidence edges go to 'possibly unused'."""
    from oya.generation.deadcode import analyze_deadcode

    graph_dir = tmp_path / "graph"
    graph_dir.mkdir()

    nodes = [
        {
            "id": "main.py::main",
            "name": "main",  # Excluded as entry point
            "type": "function",
            "file_path": "main.py",
            "line_start": 1,
            "line_end": 10,
            "docstring": None,
            "signature": None,
            "parent": None,
        },
        {
            "id": "b.py::maybe_used",
            "name": "maybe_used",
            "type": "function",
            "file_path": "b.py",
            "line_start": 1,
            "line_end": 10,
            "docstring": None,
            "signature": None,
            "parent": None,
        },
    ]

    edges = [
        {
            "source": "main.py::main",
            "target": "b.py::maybe_used",
            "type": "calls",
            "confidence": 0.5,  # Below threshold
            "line": 5,
        }
    ]

    (graph_dir / "nodes.json").write_text(json.dumps(nodes))
    (graph_dir / "edges.json").write_text(json.dumps(edges))

    report = analyze_deadcode(graph_dir)

    # maybe_used has only low-confidence edge, goes to possibly_unused
    # main is excluded so no probably_unused
    assert len(report.probably_unused_functions) == 0
    assert len(report.possibly_unused_functions) == 1
    assert report.possibly_unused_functions[0].name == "maybe_used"
