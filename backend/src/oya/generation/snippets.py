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


def extract_call_snippet(
    file_path: str,
    call_line: int,
    file_contents: dict[str, str],
    context_before: int = 10,
    context_after: int = 10,
) -> str:
    """Extract code context around a call site.

    Args:
        file_path: Path to the file containing the call.
        call_line: Line number of the call (1-indexed).
        file_contents: Dict mapping file paths to their contents.
        context_before: Maximum lines to include before the call.
        context_after: Maximum lines to include after the call.

    Returns:
        Code snippet as string, or empty string if file not found.
    """
    content = file_contents.get(file_path)
    if not content:
        return ""

    lines = content.split("\n")
    total_lines = len(lines)

    # Convert to 0-indexed
    call_idx = call_line - 1

    # Handle out of bounds
    if call_idx < 0 or call_idx >= total_lines:
        # Return last few lines if line is beyond file
        if call_idx >= total_lines and total_lines > 0:
            start = max(0, total_lines - context_after)
            return "\n".join(lines[start:])
        return ""

    # Calculate window
    start = max(0, call_idx - context_before)
    end = min(total_lines, call_idx + context_after + 1)

    # Expand upward to find function/class definition if within range
    for i in range(call_idx, max(start - 1, -1), -1):
        line = lines[i].lstrip()
        if line.startswith("def ") or line.startswith("class ") or line.startswith("async def "):
            start = i
            break

    return "\n".join(lines[start:end])
