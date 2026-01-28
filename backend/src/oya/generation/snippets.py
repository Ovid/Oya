"""Call-site snippet extraction for synopsis generation."""

from pathlib import Path


def is_test_file(file_path: str) -> bool:
    """Check if a file is a test file.

    Patterns detected:
    - test_*.py, *_test.py, *_spec.py
    - Paths containing: tests/, test/, spec/, __tests__/
    - Special files: conftest.py, fixtures.py

    Args:
        file_path: Path to the file.

    Returns:
        True if the file appears to be a test file.
    """
    path = Path(file_path)
    name = path.name

    # Check filename patterns
    if name.startswith("test_"):
        return True
    if name.endswith("_test.py") or name.endswith("_spec.py"):
        return True
    if name.endswith(".test.js") or name.endswith(".spec.js"):
        return True
    if name.endswith(".test.ts") or name.endswith(".spec.ts"):
        return True

    # Check special files
    if name in ("conftest.py", "fixtures.py"):
        return True

    # Check directory patterns
    parts = path.parts
    test_dirs = {"tests", "test", "spec", "__tests__"}
    if any(part in test_dirs for part in parts):
        return True

    return False
