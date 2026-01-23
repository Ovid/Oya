# Architectural Flaw Detection Design

## Problem

Claude Code tends to introduce certain architectural flaws:
1. **In-function imports** - Imports inside functions instead of at module top
2. **Code duplication** - Implementing functionality that already exists
3. **God objects** - Classes with too many responsibilities

These flaws accumulate technical debt and make the codebase harder to maintain.

## Solution: Hybrid Approach

Combine automated tooling (for mechanical checks) with enhanced prompting (for judgment calls).

## Current State

**Already configured:**
- Ruff with `PLC0415` rule for import placement (pyproject.toml:55)
- ESLint with React rules for frontend

**Gaps:**
| Flaw | Detection Today | Gap |
|------|-----------------|-----|
| In-function imports (Python) | Ruff rule exists | No pre-commit hook enforcing it |
| In-function imports (TS) | None | No ESLint rule configured |
| Code duplication | None | No detection tooling |
| God objects | None | No complexity limits |
| Missing reuse opportunities | None | Requires judgment (prompting) |

## Tooling Layer

### Pre-commit Hooks

New file `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: local
    hooks:
      - id: ruff-check
        name: ruff (lint)
        entry: ruff check --fix
        language: system
        types: [python]
        files: ^backend/

      - id: eslint
        name: eslint
        entry: npm run lint --prefix frontend
        language: system
        types: [typescript, tsx]
        files: ^frontend/
```

### Pylint for God Objects

Add pylint to dev dependencies with configuration for complexity warnings:

```toml
# pyproject.toml additions
[tool.pylint.design]
max-attributes = 10
max-public-methods = 15
```

Configure as **warnings**, not errors. These thresholds trigger review, not automatic failure.

### jscpd for Duplicate Detection

New file `.jscpd.json`:

```json
{
  "threshold": 0,
  "reporters": ["console"],
  "ignore": ["**/node_modules/**", "**/.venv/**", "**/dist/**"],
  "minLines": 5,
  "minTokens": 50
}
```

Run as warning in pre-commit, not blocker.

## Prompting Layer

### CLAUDE.md Additions

```markdown
## Architectural Discipline

Before implementing new functionality:
1. Search for existing utilities/helpers that do similar things
2. Check if the pattern exists elsewhere in the codebase
3. If implementing something common (date formatting, error handling,
   API calls, validation), assume it already exists and search first

When modifying files:
- Imports go at module top, not inside functions
- If a class exceeds ~10 attributes or ~15 methods, consider splitting

## Before Implementing New Functionality

When about to write something that feels "general purpose":
- Utility functions (formatting, parsing, validation)
- API/HTTP helpers
- Error handling patterns
- Data transformation logic
- UI components (buttons, modals, form elements)

**Stop and search first:**
1. Grep for similar function names or keywords
2. Check obvious locations (utils/, helpers/, common/, shared/)
3. Look at how similar features were implemented elsewhere in the codebase

If found: reuse or extend. If close but not quite: refactor existing rather than duplicate.
```

### Code-Reviewer Agent Enhancements

Add to existing `code-reviewer.md`:

```markdown
## Architectural Checks

### Import Placement
Flag any imports inside functions/methods. These should be at module top unless there's a specific circular import issue being avoided.

### God Object Detection

If a class exceeds 10 attributes or 15 public methods, evaluate cohesion:
- Do all attributes/methods serve ONE clear responsibility?
- Would you struggle to describe the class's purpose in one sentence?
- Are there subsets of methods that only use subsets of attributes?

**Legitimate large classes:** data containers, facades, protocol implementations, test fixtures
**Actual god objects:** multiple unrelated responsibilities crammed together

Flag as issue only if incoherent, not merely large.

### Duplication Review

If jscpd flags duplication, evaluate:
- Is this test code? (Often acceptable)
- Is this the second occurrence? (Wait for third before abstracting)
- Would abstracting create a confusing helper with too many parameters?

Flag as issue only if: 3+ occurrences AND abstraction would be cleaner than repetition.

### Missing Reuse
New helpers that should use existing infrastructure. Check if similar utilities already exist in utils/, helpers/, common/, shared/.
```

## Key Principles

1. **Hard limits are triggers for review**, not automatic violations
2. **Tooling catches mechanical issues**; prompting handles judgment
3. **Warnings over errors** - create awareness without blocking legitimate patterns
4. **Always-present CLAUDE.md rules** beat skills that require invocation

## Implementation Steps

1. Create `.pre-commit-config.yaml` with ruff and eslint hooks
2. Add pylint to dev dependencies with complexity warnings
3. Create `.jscpd.json` configuration
4. Update CLAUDE.md with architectural discipline section
5. Update code-reviewer agent with architectural checks
6. Run `pre-commit install` to activate hooks
