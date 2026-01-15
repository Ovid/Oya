# File Issue Detection Design

## Goal

Pre-compute potential code issues (bugs, security concerns, design flaws) during file analysis so Q&A can surface systemic patterns without re-analyzing every file.

## Data Model

### FileIssue

New dataclass in `summaries.py`:

```python
@dataclass
class FileIssue:
    file_path: str
    category: str      # "security" | "reliability" | "maintainability"
    severity: str      # "problem" | "suggestion"
    title: str         # Short description
    description: str   # Details + why it matters
    line_range: tuple[int, int] | None  # Optional location
```

### Extended FileSummary

```python
@dataclass
class FileSummary:
    file_path: str
    purpose: str
    layer: str
    key_abstractions: list[str]
    internal_deps: list[str]
    external_deps: list[str]
    issues: list[FileIssue]  # NEW
```

### YAML Schema

File documentation YAML header adds:

```yaml
issues:
  - category: security
    severity: problem
    title: "SQL query built with string concatenation"
    description: "Potential SQL injection vulnerability"
    lines: [45, 47]
```

## Categories and Severities

**Categories:**
- `security` - Injection vulnerabilities, hardcoded secrets, missing auth, unsafe deserialization
- `reliability` - Unhandled errors, race conditions, resource leaks, null pointer risks
- `maintainability` - God classes, circular deps, code duplication, missing abstractions

**Severities:**
- `problem` - Likely bug or security hole that needs attention
- `suggestion` - Improvement opportunity, not urgent

## Prompt Changes

Add to `FILE_TEMPLATE` in `prompts.py`:

```
## Code Analysis

While documenting this file, also identify potential issues:

**Categories:**
- security: Injection vulnerabilities, hardcoded secrets, missing auth, unsafe deserialization
- reliability: Unhandled errors, race conditions, resource leaks, null pointer risks
- maintainability: God classes, circular deps, code duplication, missing abstractions

**Severities:**
- problem: Likely bug or security hole that needs attention
- suggestion: Improvement opportunity, not urgent

Only flag issues you're reasonably confident about. Skip stylistic nitpicks.
```

Extend YAML output schema to include issues array.

## ChromaDB Issues Collection

**Collection name:** `{repo_id}_issues`

**Document structure:**

```python
{
    "id": "{file_path}::{issue_title_slug}",
    "content": f"{title}\n\n{description}",  # For semantic search
    "metadata": {
        "file_path": "backend/src/oya/api/routers.py",
        "category": "security",
        "severity": "problem",
        "title": "SQL query built with string concatenation",
        "line_start": 45,
        "line_end": 47
    }
}
```

**Operations:**
- `add_issues(file_path, issues)` - Add issues for a file
- `delete_issues_for_file(file_path)` - Remove old issues on regeneration
- `query_issues(filters)` - Query by category, severity, file path

## Q&A Integration

When user asks about code quality, bugs, or issues:

1. **Detect issue-related queries** - Keywords: "bugs", "issues", "problems", "security", "code quality", "technical debt", "what's wrong"

2. **Query issues collection first** - Retrieve pre-computed issues instead of re-analyzing

3. **Aggregate for systemic patterns** - Prompt asks LLM to identify patterns:
   ```
   These issues were identified during analysis:
   [list of issues with file paths]

   Identify any systemic patterns across these issues.
   Are there architectural or process problems causing multiple similar issues?
   ```

4. **Fall back to full analysis** - If no relevant issues found, proceed with normal file retrieval

## Implementation Scope

### Files to Modify

| File | Changes |
|------|---------|
| `backend/src/oya/generation/summaries.py` | Add `FileIssue` dataclass, extend `FileSummary`, update parser |
| `backend/src/oya/generation/prompts.py` | Extend `FILE_TEMPLATE` with issue instructions |
| `backend/src/oya/generation/file.py` | Pass issues to indexing after generation |
| `backend/src/oya/vectorstore/` | Add issues collection and query methods |
| `backend/src/oya/api/routers/qa.py` | Detect issue queries, query issues collection, aggregation prompt |
| `backend/src/oya/constants/` | Add issue categories/severities constants |

### New Files

| File | Purpose |
|------|---------|
| `backend/src/oya/vectorstore/issues.py` | Issues collection management |

### No Changes Needed

- Frontend (issues appear in wiki markdown naturally)
- Directory/synthesis generation (issues are file-level)
- Parsing layer (issues come from LLM, not AST)
