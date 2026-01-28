# Synopsis Clarity Enhancement Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Ensure call-site synopses show external import + usage patterns rather than internal implementation details.

**Architecture:** Modify `select_best_call_site()` to prefer callers from different files over same-file callers. Update AI synopsis prompts to encourage import statements.

**Tech Stack:** Python, pytest

---

## Task 1: Update `select_best_call_site()` to Prefer External Callers

**Files:**
- Modify: `backend/src/oya/generation/snippets.py:99-157`
- Test: `backend/tests/generation/test_snippets.py`

**Step 1: Write the failing test**

Add to `backend/tests/generation/test_snippets.py`:

```python
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
```

**Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/generation/test_snippets.py -v -k "external"`

Expected: FAIL - `select_best_call_site() got an unexpected keyword argument 'target_file'`

**Step 3: Update function signature and implementation**

In `backend/src/oya/generation/snippets.py`, replace the `select_best_call_site` function:

```python
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
```

**Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/generation/test_snippets.py -v -k "external"`

Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/oya/generation/snippets.py backend/tests/generation/test_snippets.py
git commit -m "$(cat <<'EOF'
feat(snippets): prefer external callers for call-site synopses

External callers (from different files) now take priority over internal
callers (from the same file) when selecting the best call site for a
synopsis. This ensures synopses show import + usage patterns rather than
internal implementation details.

Priority order: external production > external test > internal production > internal test

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Update Orchestrator to Pass Target File

**Files:**
- Modify: `backend/src/oya/generation/orchestrator.py`
- Test: Existing tests should still pass

**Step 1: Find the call site in orchestrator**

The orchestrator calls `select_best_call_site()` around line 425. We need to pass the `file_path` parameter.

**Step 2: Update the call**

In `backend/src/oya/generation/orchestrator.py`, find the call to `select_best_call_site` and add the `target_file` parameter:

```python
best_site, other_sites = select_best_call_site(
    call_sites, file_contents, target_file=file_path
)
```

**Step 3: Run all tests to verify nothing breaks**

Run: `cd backend && pytest tests/generation/ -v`

Expected: All tests pass

**Step 4: Commit**

```bash
git add backend/src/oya/generation/orchestrator.py
git commit -m "$(cat <<'EOF'
feat(orchestrator): pass target file to call-site selection

Enables the call-site selector to distinguish internal vs external
callers by providing the file being documented.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Update AI Synopsis Prompt

**Files:**
- Modify: `backend/src/oya/generation/prompts.py`

**Step 1: Locate the prompt**

`SYNOPSIS_INSTRUCTIONS_WITHOUT_EXTRACTED` is around line 553.

**Step 2: Update the prompt**

Find the text:
```python
- Necessary imports at the top
```

Replace with:
```python
- Include the import statement when it helps clarify what's being used
```

The full updated instruction block should read:
```python
**You MUST generate a caller-perspective code example** showing:
- How to import/use this file's public API
- The most common/important use case
- Include the import statement when it helps clarify what's being used
- 5-15 lines typically, NO setup boilerplate
```

**Step 3: Run tests**

Run: `cd backend && pytest tests/generation/ -v`

Expected: All tests pass

**Step 4: Commit**

```bash
git add backend/src/oya/generation/prompts.py
git commit -m "$(cat <<'EOF'
feat(prompts): guide AI to include imports when helpful

Updated AI synopsis generation prompt to encourage including import
statements when they help clarify what's being used, while leaving
the judgment to the AI for when imports add clarity vs. when they're
redundant.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Add Integration Test

**Files:**
- Test: `backend/tests/generation/test_snippets.py`

**Step 1: Add test for backward compatibility**

```python
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
```

**Step 2: Run tests**

Run: `cd backend && pytest tests/generation/test_snippets.py -v`

Expected: All tests pass

**Step 3: Commit**

```bash
git add backend/tests/generation/test_snippets.py
git commit -m "$(cat <<'EOF'
test(snippets): verify backward compatibility without target_file

Ensures existing code that doesn't pass target_file continues to work,
with all callers treated as external.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

## Verification

After all tasks complete:

1. Run full test suite: `cd backend && pytest -v`
2. Verify deps.py wiki page would now show external usage (manual check)
3. Run mypy: `cd backend && mypy src/oya/generation/snippets.py src/oya/generation/orchestrator.py`
