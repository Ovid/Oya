"""Call-site snippet extraction for synopsis generation."""

from pathlib import Path

from oya.graph.models import CallSite


def is_test_file(file_path: str) -> bool:
    """Check if a file is a test file.

    Patterns detected:
    - test_*.py, *_test.py, *_spec.py
    - *.test.js, *.spec.js, *.test.ts, *.spec.ts, *.test.tsx, *.spec.tsx
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
    if name.endswith(".test.tsx") or name.endswith(".spec.tsx"):
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
    target_file: str | None = None,
) -> tuple[CallSite | None, list[CallSite]]:
    """Select the best call site for synopsis, return others for reference.

    Selection criteria (in priority order):
    1. External production (caller from different file, not a test)
    2. External test (caller from different file, is a test)
    3. Internal production (caller from same file, not a test)
    4. Internal test (caller from same file, is a test)

    Args:
        call_sites: List of CallSite objects.
        file_contents: Dict mapping file paths to contents (for future heuristics).
        target_file: The file being documented. Used to distinguish internal vs external callers.

    Returns:
        Tuple of (best_site, other_sites) where best_site may be None if no callers.
        other_sites is limited to 5 entries.
    """
    if not call_sites:
        return None, []

    def is_external(site: CallSite) -> bool:
        """Check if caller is from a different file than the target."""
        if target_file is None:
            return True  # If no target specified, treat all as external
        return site.caller_file != target_file

    # Categorize call sites into 4 tiers
    external_production: list[CallSite] = []
    external_test: list[CallSite] = []
    internal_production: list[CallSite] = []
    internal_test: list[CallSite] = []

    for site in call_sites:
        external = is_external(site)
        test = is_test_file(site.caller_file)

        if external and not test:
            external_production.append(site)
        elif external and test:
            external_test.append(site)
        elif not external and not test:
            internal_production.append(site)
        else:
            internal_test.append(site)

    # Sort each tier by file path and line for deterministic selection
    for tier in [external_production, external_test, internal_production, internal_test]:
        tier.sort(key=lambda s: (s.caller_file, s.line))

    # Select best from highest-priority non-empty tier
    best: CallSite | None = None
    for tier in [external_production, external_test, internal_production, internal_test]:
        if tier:
            best = tier[0]
            break

    if best is None:
        return None, []

    # Build others list from all remaining call sites, prefer different files
    all_remaining = [s for s in call_sites if s is not best]
    all_remaining.sort(key=lambda s: (s.caller_file, s.line))

    others: list[CallSite] = []
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
