# Dead Code Detection Feature Design

## Overview

Add a "Code Health" wiki page that identifies potentially unused code symbols by analyzing the existing call graph data.

## Data Source

The feature uses existing graph artifacts generated during wiki building:
- `graph/nodes.json` - All code symbols (functions, classes, variables)
- `graph/edges.json` - Call relationships with confidence scores

No new parsing required.

## Analysis Logic

1. Load all nodes from the graph
2. Build a set of "used" node IDs by collecting all edge targets
3. Classify unused nodes into two tiers:
   - **Probably unused**: Zero incoming edges
   - **Possibly unused**: Only incoming edges with confidence < 0.7

### Automatic Exclusions

Symbols matching these patterns are never flagged:
- Test functions (`test_*`, `*_test`)
- Python dunders (`__init__`, `__str__`, `__all__`, etc.)
- Main entry points (`main`, `app`)
- Private symbols (single underscore prefix `_`)

Variables are excluded from "probably unused" and only shown in "possibly unused" due to high false positive rate.

## Page Structure

**Location:** `/wiki/code-health.md` in the generated wiki

**Layout:**
```markdown
# Potential Dead Code

Analysis of code symbols with no detected callers. Review before removing -
some may be entry points, event handlers, or called via reflection.

## Probably Unused

These symbols have no incoming references in the codebase.

### Functions (N)

| Name | File | Line |
|------|------|------|
| [symbol_name](#) | path/to/file.py | 45 |

### Classes (N)

| Name | File | Line |
|------|------|------|

## Possibly Unused

These symbols only have low-confidence references (may be false positives).

### Functions (N)
...

### Variables (N)
...
```

**Links:** Each symbol links to its file page with line anchor, e.g., `/wiki/files/path/to/file.py#L45`

**Empty States:** Categories with zero items show "None detected"

## Backend Implementation

### New Module

`backend/src/oya/generation/deadcode.py`

```python
EXCLUDED_PATTERNS = [
    r"^test_",           # Test functions
    r"_test$",           # Test functions (suffix)
    r"^__.*__$",         # Python dunders
    r"^main$",           # Entry points
    r"^app$",            # FastAPI/Flask app
    r"^_",               # Private by convention
]

CONFIDENCE_THRESHOLD = 0.7

def analyze_deadcode(graph_dir: Path) -> DeadcodeReport:
    """Analyze graph data to find potentially unused symbols."""
    ...
```

### Integration

Called during wiki generation in `orchestrator.py`, after graph is built:

1. Parse files → build nodes
2. Resolve references → build edges
3. Generate wiki pages (overview, architecture, files, etc.)
4. **Analyze deadcode → generate code-health.md**
5. Finalize/promote wiki

### Navigation

Add "Code Health" to wiki sidebar. The frontend already renders whatever the tree contains, so no frontend changes needed.

## Limitations

### Known False Positives

- Callback functions passed to frameworks
- Functions called via `getattr()` or reflection
- Public API intended for external consumers
- Plugin/hook functions discovered at runtime

### Known False Negatives

- Functions only called by other dead functions
- Code behind always-false conditions
- Unreachable branches

### Cross-Language

The graph only tracks calls within parseable files. Cross-language calls (Python calling JavaScript) are not tracked. The page notes this limitation.

## Out of Scope for v1

- "Mark as intentional" feature
- Automatic deletion suggestions
- IDE integration
- Historical tracking
