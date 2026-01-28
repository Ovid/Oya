"""Call-site snippet extraction for synopsis generation."""

from pathlib import Path

from oya.graph.models import CallSite


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


def select_best_call_site(
    call_sites: list[CallSite],
    file_contents: dict[str, str],
) -> tuple[CallSite | None, list[CallSite]]:
    """Select the best call site for synopsis, return others for reference.

    Selection criteria:
    1. Filter out test files (prefer production code)
    2. If only test files exist, use best test example
    3. Prefer diversity (different files over same file)

    Args:
        call_sites: List of CallSite objects.
        file_contents: Dict mapping file paths to contents (for future heuristics).

    Returns:
        Tuple of (best_site, other_sites) where best_site may be None if no callers.
        other_sites is limited to 5 entries.
    """
    if not call_sites:
        return None, []

    # Separate production and test files
    production = [s for s in call_sites if not is_test_file(s.caller_file)]
    tests = [s for s in call_sites if is_test_file(s.caller_file)]

    # Prefer production code for "best"
    if production:
        production.sort(key=lambda s: (s.caller_file, s.line))
        best = production[0]
    elif tests:
        tests.sort(key=lambda s: (s.caller_file, s.line))
        best = tests[0]
    else:
        return None, []

    # Build others list from all remaining call sites, prefer different files
    all_remaining = [s for s in call_sites if s is not best]
    all_remaining.sort(key=lambda s: (s.caller_file, s.line))

    others = []
    seen_files = {best.caller_file}

    # First pass: prefer sites from different files
    for site in all_remaining:
        if len(others) >= 5:
            break
        if site.caller_file not in seen_files:
            others.append(site)
            seen_files.add(site.caller_file)

    # Fill remaining slots if we have space
    for site in all_remaining:
        if len(others) >= 5:
            break
        if site not in others:
            others.append(site)

    return best, others
