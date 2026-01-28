# CGRAG: Contextually-Guided Retrieval-Augmented Generation

## Overview

CGRAG is Oya's Q&A retrieval system. It answers questions about codebases by
retrieving relevant context and generating answers with citations.

### The Core Problem

Traditional RAG uses semantic similarity to find relevant documents. This works
well for conceptual questions ("what does the auth module do?") but fails for
debugging and code tracing because:

1. **Semantic gap**: Error symptoms ("readonly database") don't embed near root
   causes ("cached connection invalidated by directory replacement")
2. **Wiki summaries are lossy**: They describe *what* code does but lose the
   *how* - the actual call paths, state mutations, and edge cases needed for
   debugging

### The Solution

CGRAG uses **query-routed retrieval** - different retrieval strategies for
different question types:

| Query Mode | Example | Strategy |
|------------|---------|----------|
| Conceptual | "How does auth work?" | Semantic search over wiki docs |
| Diagnostic | "Why am I getting error X?" | Error anchors → call graph → source |
| Exploratory | "Trace the auth flow" | Entry points → call graph forward → source |
| Analytical | "What are the flaws in X?" | Structure analysis → issues → source |

Additionally, CGRAG uses **iterative gap-filling**: if the LLM identifies
missing context, the system retrieves more and tries again (up to 3 passes).

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                           Q&A Request                               │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      Query Classifier                               │
│  - LLM classification                                               │
│  - Scope extraction (which part of codebase)                        │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                    ┌─────────────┼─────────────┬─────────────┐
                    ▼             ▼             ▼             ▼
              Conceptual    Diagnostic    Exploratory    Analytical
                    │             │             │             │
                    ▼             ▼             ▼             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Mode-Specific Retrieval                          │
│                                                                     │
│  Data Sources:                                                      │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌────────────┐ │
│  │  Wiki Docs   │ │  Code Index  │ │ Issues Store │ │   Source   │ │
│  │  (ChromaDB)  │ │   (SQLite)   │ │  (ChromaDB)  │ │   Files    │ │
│  └──────────────┘ └──────────────┘ └──────────────┘ └────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      CGRAG Loop (max 3 passes)                      │
│                                                                     │
│  ┌─────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────┐  │
│  │ Context │───▶│  LLM Pass   │───▶│ Extract Gaps│───▶│ Resolve │  │
│  └─────────┘    └─────────────┘    └─────────────┘    │  Gaps   │  │
│       ▲                                               └────┬────┘  │
│       │                                                    │       │
│       └────────────────────────────────────────────────────┘       │
│                         (append new context)                        │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      Q&A Response                                   │
│  - Answer text                                                      │
│  - Citations (file paths, line ranges)                              │
│  - Confidence level (high/medium/low)                               │
└─────────────────────────────────────────────────────────────────────┘
```

### Components

| Component | Location | Purpose |
|-----------|----------|---------|
| Query Classifier | `qa/classifier.py` | Detect query mode and scope |
| Code Index | `db/code_index.py` | Structured code metadata |
| Mode Retrieval | `qa/retrieval/` | Per-mode retrieval strategies |
| Gap Resolver | `qa/cgrag.py` | Enhanced gap resolution with direct lookup |
| Session Manager | `qa/session.py` | Cross-question context caching |

---

## Query Classification

The classifier determines which retrieval strategy to use. It runs before any
retrieval happens.

### Classification via LLM

Every query is classified by a lightweight LLM call. This adds ~100-150 tokens
of overhead but provides reliable classification even for nuanced queries.

**System Prompt:**

```
You are a query classifier for a codebase Q&A system. Your job is to determine
the best retrieval strategy for answering the user's question.

## Why This Matters

Different questions need different retrieval approaches:

- CONCEPTUAL questions ("what does X do?") are answered well by high-level
  documentation and wiki summaries.

- DIAGNOSTIC questions ("why is X failing?") require tracing errors back to
  root causes. The symptoms described in the query often have LOW semantic
  similarity to the actual cause. We need to find error sites in code and
  walk the call graph backward to find state mutations or side effects.

- EXPLORATORY questions ("trace the auth flow") require following execution
  paths forward through the codebase. We need to find entry points and walk
  the call graph to show how components connect.

- ANALYTICAL questions ("what are the architectural flaws?") require examining
  code structure, dependencies, and known issues. We need structural analysis,
  not just text search.

## Classification Rules

DIAGNOSTIC - Choose when:
  - Query contains error messages, exception types, or stack traces
  - Query describes unexpected behavior ("X happens when it should Y")
  - Query asks WHY something is broken, failing, or not working
  - Query mentions specific error codes or status codes

EXPLORATORY - Choose when:
  - Query asks to trace, follow, or walk through code paths
  - Query asks how components connect or call each other
  - Query asks about execution order or data flow
  - Query wants to understand a sequence of operations

ANALYTICAL - Choose when:
  - Query asks about architecture, structure, or design
  - Query asks about code quality, flaws, or problems
  - Query asks about dependencies, coupling, or cohesion
  - Query asks for assessment or evaluation of code

CONCEPTUAL - Choose when:
  - Query asks what something does or how to use it
  - Query asks for explanation of a feature or module
  - Query is a general question about functionality
  - None of the above categories clearly fit

## Response Format

Respond with a JSON object:
{
  "mode": "DIAGNOSTIC" | "EXPLORATORY" | "ANALYTICAL" | "CONCEPTUAL",
  "reasoning": "<one sentence explaining why>",
  "scope": "<specific part of codebase if mentioned, otherwise null>"
}
```

**User Prompt:**

```
Classify this question: {query}
```

### Example Classifications

| Query | Mode | Reasoning |
|-------|------|-----------|
| "Why am I getting sqlite3.OperationalError: readonly database after regeneration?" | DIAGNOSTIC | Contains exception type and describes unexpected failure |
| "Trace how a request flows from the API endpoint to the database" | EXPLORATORY | Asks to trace execution path through components |
| "What are the architectural problems in the frontend code?" | ANALYTICAL | Asks for structural assessment and flaw detection |
| "How does the authentication system work?" | CONCEPTUAL | General question about functionality |
| "What's wrong with the caching layer?" | ANALYTICAL | Asks about problems/flaws in a component |
| "The auth endpoint returns 401 when it should return 200" | DIAGNOSTIC | Describes unexpected behavior with specific symptoms |

---

## Code Index

The code index stores structured metadata about functions, classes, and methods.
It enables retrieval based on code behavior rather than just semantic similarity.

### What Already Exists

The parsing infrastructure already extracts much of what we need:

| Field | Source | Status |
|-------|--------|--------|
| `symbol_name` | `ParsedSymbol.name` | ✅ Exists |
| `symbol_type` | `ParsedSymbol.symbol_type` | ✅ Exists |
| `line_start/end` | `ParsedSymbol.start_line/end_line` | ✅ Exists |
| `signature` | `ParsedSymbol.signature` | ✅ Exists (Python), ❌ Missing (TS/Java) |
| `docstring` | `ParsedSymbol.docstring` | ✅ Exists (Python), ❌ Missing (TS/Java) |
| `calls` | `Reference` with `ReferenceType.CALLS` | ✅ Exists (Python/TS), ❌ Missing (Java) |
| `called_by` | Computed by inverting `calls` | ⚠️ Needs computation |
| `raises` | Not extracted | ❌ Needs new extraction |
| `mutates` | Not extracted | ❌ Needs new extraction |
| `error_strings` | Not extracted | ❌ Needs new extraction |

### Schema

```sql
CREATE TABLE code_index (
    id INTEGER PRIMARY KEY,
    file_path TEXT NOT NULL,
    symbol_name TEXT NOT NULL,
    symbol_type TEXT NOT NULL,  -- 'function', 'class', 'method'
    line_start INTEGER NOT NULL,
    line_end INTEGER NOT NULL,
    signature TEXT,
    docstring TEXT,             -- First 200 chars
    calls TEXT,                 -- JSON array: ["module.func", "Class.method"]
    called_by TEXT,             -- JSON array: computed after indexing
    raises TEXT,                -- JSON array: ["ValueError", "IOError"]
    mutates TEXT,               -- JSON array: ["_cache", "self.state"]
    error_strings TEXT,         -- JSON array: ["invalid input", "not found"]
    source_hash TEXT NOT NULL,
    UNIQUE(file_path, symbol_name)
);

CREATE INDEX idx_code_index_file ON code_index(file_path);
CREATE INDEX idx_code_index_symbol ON code_index(symbol_name);
```

### New Extraction Required

Add to Python parser (`python_parser.py`):

```python
def _extract_raises(self, node: ast.FunctionDef) -> list[str]:
    """Extract exception types from raise statements."""
    raises = []
    for child in ast.walk(node):
        if isinstance(child, ast.Raise) and child.exc:
            if isinstance(child.exc, ast.Call):
                # raise ValueError("msg")
                if isinstance(child.exc.func, ast.Name):
                    raises.append(child.exc.func.id)
            elif isinstance(child.exc, ast.Name):
                # raise e (re-raise)
                raises.append(child.exc.id)
    return list(set(raises))

def _extract_error_strings(self, node: ast.FunctionDef) -> list[str]:
    """Extract string literals from raise statements and logging calls."""
    strings = []
    for child in ast.walk(node):
        if isinstance(child, ast.Raise) and child.exc:
            if isinstance(child.exc, ast.Call) and child.exc.args:
                for arg in child.exc.args:
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        strings.append(arg.value[:100])  # Truncate
        # Also check logging calls: logger.error("...")
        if isinstance(child, ast.Call):
            if _is_logging_call(child):
                for arg in child.args:
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        strings.append(arg.value[:100])
    return strings

def _extract_mutates(self, node: ast.FunctionDef, module_level_names: set[str]) -> list[str]:
    """Extract assignments to module-level state or self attributes."""
    mutates = []
    for child in ast.walk(node):
        if isinstance(child, ast.Assign):
            for target in child.targets:
                if isinstance(target, ast.Name) and target.id in module_level_names:
                    mutates.append(target.id)
                elif isinstance(target, ast.Subscript):
                    if isinstance(target.value, ast.Name) and target.value.id in module_level_names:
                        mutates.append(target.value.id)
        elif isinstance(child, ast.Attribute) and isinstance(child.ctx, ast.Store):
            if isinstance(child.value, ast.Name) and child.value.id == "self":
                mutates.append(f"self.{child.attr}")
    return list(set(mutates))
```

Similar extraction needed for TypeScript and Java parsers.

### Building the Index

During wiki generation, after parsing completes:

```python
def build_code_index(db: Database, parsed_files: list[ParsedFile], graph: nx.DiGraph):
    # 1. Clear existing entries for files being regenerated
    for pf in parsed_files:
        db.execute("DELETE FROM code_index WHERE file_path = ?", (pf.path,))

    # 2. Insert symbols with their metadata
    for pf in parsed_files:
        source_hash = compute_content_hash(pf.raw_content)
        for symbol in pf.symbols:
            if symbol.symbol_type not in (SymbolType.FUNCTION, SymbolType.METHOD, SymbolType.CLASS):
                continue

            # Get calls from graph edges
            node_id = f"{pf.path}::{symbol.name}"
            calls = [edge[1] for edge in graph.out_edges(node_id)
                     if graph.edges[edge].get("type") == "CALLS"]

            db.execute("""
                INSERT INTO code_index
                (file_path, symbol_name, symbol_type, line_start, line_end,
                 signature, docstring, calls, raises, mutates, error_strings, source_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                pf.path, symbol.name, symbol.symbol_type.value,
                symbol.start_line, symbol.end_line,
                symbol.signature, (symbol.docstring or "")[:200],
                json.dumps(calls),
                json.dumps(symbol.metadata.get("raises", [])),
                json.dumps(symbol.metadata.get("mutates", [])),
                json.dumps(symbol.metadata.get("error_strings", [])),
                source_hash
            ))

    # 3. Compute called_by by inverting calls
    compute_called_by(db)
```

### Incremental Updates

The code index hooks into existing wiki generation change detection:

1. **File changed** (source_hash differs): Delete and rebuild all entries for
   that file
2. **File deleted**: Delete all entries for that file
3. **File added**: Create entries for all symbols in the file
4. **After all files processed**: Recompute `called_by` for affected symbols

This runs during the Files Phase of wiki generation, using the same
`source_hash` that `wiki_pages` uses.

### Querying the Index

**Find functions that can raise a specific exception:**
```sql
SELECT * FROM code_index
WHERE EXISTS (
    SELECT 1 FROM json_each(raises) WHERE value = 'ValueError'
)
```

**Find functions that mutate a specific cache:**
```sql
SELECT * FROM code_index
WHERE EXISTS (
    SELECT 1 FROM json_each(mutates) WHERE value = '_db_instances'
)
```

**Get callers of a function (walk backward):**
```sql
SELECT * FROM code_index
WHERE EXISTS (
    SELECT 1 FROM json_each(calls) WHERE value = 'target_function'
)
```

**Get callees of a function (walk forward):**
```sql
SELECT c2.* FROM code_index c1
JOIN json_each(c1.calls) AS callees
JOIN code_index c2 ON c2.symbol_name = callees.value
WHERE c1.symbol_name = 'source_function'
```

---

## Mode-Specific Retrieval

Each query mode uses a tailored retrieval strategy optimized for that type of
question.

### Conceptual Mode

**Purpose:** Answer "what does X do?" and "how do I use X?" questions.

**Strategy:** Semantic search over wiki documentation (unchanged from current
system).

```
1. Hybrid search (semantic + FTS) over wiki docs
2. Rank by RRF (Reciprocal Rank Fusion)
3. Return top-k results
```

**Context budget:** ~4000 tokens wiki docs

---

### Diagnostic Mode

**Purpose:** Debug errors, trace failures back to root causes.

**Strategy:** Use error anchors to find relevant code, then walk the call graph
backward to find state mutations that could cause the issue.

```
1. EXTRACT ERROR ANCHORS
   - Parse exception types: /\b(\w+Error|\w+Exception)\b/
   - Parse error messages: quoted strings, specific phrases
   - Parse stack traces: file:line:function patterns

2. SEARCH CODE INDEX
   Query 1: Find functions that raise these exceptions
     SELECT * FROM code_index WHERE EXISTS (
       SELECT 1 FROM json_each(raises) WHERE value IN ({exception_types})
     )

   Query 2: Find functions with matching error strings
     SELECT * FROM code_index WHERE EXISTS (
       SELECT 1 FROM json_each(error_strings)
       WHERE value LIKE '%{error_fragment}%'
     )

   Query 3: If stack trace present, direct lookup by file:function
     SELECT * FROM code_index
     WHERE file_path = ? AND symbol_name = ?

3. WALK CALL GRAPH BACKWARD (2-3 hops)
   For each error site found:
     - Get callers via called_by field
     - Prioritize callers that have non-empty mutates field
     - These are candidates for "state that got corrupted"

4. FETCH SOURCE SNIPPETS
   For top 5-8 functions in the chain:
     - Read actual source using line_start/line_end
     - Include the error site + callers with state mutations

5. SUPPLEMENT WITH WIKI CONTEXT
   - Retrieve wiki docs for files involved
   - Provides high-level "what this module does" context
```

**Context budget:** ~2000 tokens source + ~1000 tokens wiki

---

### Exploratory Mode

**Purpose:** Trace execution flows, show how code paths connect.

**Strategy:** Find entry points matching the query subject, walk the call graph
forward to show the execution flow.

```
1. IDENTIFY ENTRY POINTS
   - Extract subject from query: "trace auth flow" → "auth"
   - Search code_index for matching symbols:
     SELECT * FROM code_index
     WHERE symbol_name LIKE '%{subject}%'
        OR docstring LIKE '%{subject}%'
   - Prioritize by symbol_type: routes > functions > methods
   - Prioritize public APIs (no underscore prefix)

2. WALK CALL GRAPH FORWARD (3-4 hops)
   For each entry point:
     - Get callees via calls field
     - Build execution tree showing the flow
     - Stop at leaf functions or external calls

3. GENERATE FLOW REPRESENTATION
   Create structured output:
     endpoint()
       → validate_input()
       → service.process()
           → repository.save()
               → db.execute()

4. FETCH KEY SOURCE SNIPPETS
   Select pivotal functions (entry, major branches, terminus):
     - Read source for 3-5 key functions
     - Show enough code to understand the flow

5. MINIMAL WIKI CONTEXT
   - Brief description of each module involved
```

**Context budget:** ~2500 tokens source + ~500 tokens wiki

---

### Analytical Mode

**Purpose:** Assess architecture, find structural problems, evaluate code
quality.

**Strategy:** Analyze code structure and dependencies, combine with pre-computed
issues.

```
1. IDENTIFY SCOPE
   - Parse target from query: "frontend flaws" → filter file_path LIKE 'frontend/%'
   - If no scope specified, analyze entire codebase

2. COMPUTE STRUCTURAL METRICS
   From code_index:
     - Dependency fan-in: COUNT of called_by entries per function
     - Dependency fan-out: COUNT of calls entries per function
     - Module coupling: cross-module call density

   Flag potential issues:
     - God functions: fan-out > 15 calls
     - Hotspots: fan-in > 20 callers
     - Circular dependencies: A calls B calls A

3. QUERY ISSUES STORE
   Retrieve pre-computed issues for scope:
     - Filter by severity (high, medium)
     - Group by category (security, performance, maintainability)

4. FETCH REPRESENTATIVE SOURCE
   For flagged problem areas:
     - Read source for functions with structural issues
     - Read source for files with most issues

5. BUILD DEPENDENCY OVERVIEW
   Generate mermaid diagram of module dependencies:
     ```mermaid
     graph LR
       api --> service
       service --> repository
       repository --> db
     ```
```

**Context budget:** ~2000 tokens source + ~1000 tokens wiki/issues

---

## Gap Resolution

CGRAG uses iterative retrieval: if the LLM identifies missing context, the
system retrieves more and tries again. The key improvement is **mode-aware gap
resolution** that uses direct lookup instead of semantic search when possible.

### The CGRAG Loop

```
┌─────────────────────────────────────────────────────────┐
│                    CGRAG Loop                           │
│                                                         │
│  Pass 1:                                                │
│    Context (from mode-specific retrieval)               │
│         ↓                                               │
│    LLM generates answer + identifies gaps               │
│         ↓                                               │
│    Parse <missing> section from response                │
│         ↓                                               │
│    Resolve gaps (mode-aware)                            │
│         ↓                                               │
│    Append new context                                   │
│                                                         │
│  Pass 2-3: Repeat until no new gaps or max passes       │
└─────────────────────────────────────────────────────────┘
```

### Gap Extraction

The LLM is prompted to identify missing context in a `<missing>` section:

```xml
<answer>
The error occurs because... however, I need more context to identify the root
cause.
</answer>

<missing>
- The implementation of get_db() in backend/src/oya/api/deps.py
- How promote_staging_to_production() handles the database file
- What invalidates the _db_instances cache
</missing>
```

### Mode-Aware Gap Resolution

```python
def resolve_gaps(gaps: list[str], mode: QueryMode, code_index: CodeIndex) -> list[Context]:
    results = []

    for gap in gaps:
        # 1. Try to extract explicit file/function references
        file_match = re.search(r'([\w/]+\.py|\.ts|\.java|\.go)', gap)
        func_match = re.search(r'\b([\w_]+)\(\)', gap)
        func_in_file = re.search(r'(\w+)\s+in\s+([\w/\.]+)', gap)

        if func_in_file:
            # "get_db in deps.py" → direct lookup
            result = code_index.lookup(
                symbol_name=func_in_file.group(1),
                file_pattern=func_in_file.group(2)
            )
            if result:
                results.append(fetch_source(result))
                continue

        if file_match:
            # Explicit file path → fetch all symbols from that file
            result = code_index.lookup_file(file_match.group(1))
            if result:
                results.append(fetch_source(result))
                continue

        if func_match:
            # Function name only → search code_index
            result = code_index.lookup(symbol_name=func_match.group(1))
            if result:
                results.append(fetch_source(result))
                continue

        # 2. Mode-specific fallback
        if mode == QueryMode.DIAGNOSTIC:
            # Look for error-related terms
            error_match = re.search(r'(error|exception|fail|invalid)', gap, re.I)
            if error_match:
                result = code_index.search_error_patterns(gap)
                if result:
                    results.append(fetch_source(result))
                    continue

        # 3. Fall back to semantic search (original behavior)
        results.extend(semantic_search(gap, top_k=3))

    return results
```

### Source Fetching

When a gap resolves to a code_index entry, fetch actual source:

```python
def fetch_source(entry: CodeIndexEntry) -> Context:
    """Read source code for a code index entry."""

    # Read the specific line range
    source_lines = read_file_lines(
        entry.file_path,
        entry.line_start,
        entry.line_end
    )

    # Format with location header
    content = f"# {entry.file_path}:{entry.line_start}-{entry.line_end}\n"
    content += f"# {entry.signature}\n\n"
    content += "\n".join(source_lines)

    return Context(
        content=content,
        source="code_index",
        path=entry.file_path,
        line_range=(entry.line_start, entry.line_end)
    )
```

### Token Budget Per Gap

To prevent context explosion across multiple passes:

```python
GAP_RESOLUTION_BUDGET = {
    "per_gap": 500,      # Max tokens per resolved gap
    "per_pass": 1500,    # Max tokens added per CGRAG pass
    "total": 3000,       # Max tokens from all gap resolution
}
```

If a source snippet exceeds `per_gap`, truncate to the most relevant portion
(function signature + first N lines).

### Unresolvable Gaps

Some gaps cannot be resolved (external libraries, missing files). Track these
to avoid repeated failed lookups:

```python
class CGRAGSession:
    unresolvable_gaps: set[str]  # Gaps that failed lookup

    def resolve_gap(self, gap: str) -> Context | None:
        # Normalize gap description
        normalized = normalize_gap(gap)

        if normalized in self.unresolvable_gaps:
            return None  # Don't retry

        result = attempt_resolution(gap)

        if result is None:
            self.unresolvable_gaps.add(normalized)

        return result
```

### Stop Conditions

The CGRAG loop terminates when:

1. **No new gaps:** LLM doesn't request more context
2. **All gaps unresolvable:** Every gap already attempted and failed
3. **Max passes reached:** Default 3 passes
4. **Budget exhausted:** Total context exceeds limit

---

## Context Budget Management

Careful token budgeting prevents context window overflow while maximizing
useful information.

### Overall Budget

```
Total context budget: 6000 tokens (configurable)

Allocation by phase:
┌─────────────────────────────────────────────────────────┐
│ Initial Retrieval          │ 3000-4000 tokens          │
│ Gap Resolution (all passes)│ 1500-2500 tokens          │
│ System prompt + query      │ ~500 tokens               │
└─────────────────────────────────────────────────────────┘
```

### Budget by Query Mode

| Mode | Wiki Docs | Source Code | Issues | Total |
|------|-----------|-------------|--------|-------|
| Conceptual | 4000 | 0 | 0 | ~4000 |
| Diagnostic | 1000 | 2000 | 0 | ~3000 |
| Exploratory | 500 | 2500 | 0 | ~3000 |
| Analytical | 500 | 1500 | 1000 | ~3000 |

Non-conceptual modes reserve more headroom for gap resolution.

### Token Counting

Use tiktoken for accurate counts:

```python
import tiktoken

encoder = tiktoken.encoding_for_model("gpt-4")  # Compatible with Claude

def count_tokens(text: str) -> int:
    return len(encoder.encode(text))

def truncate_to_budget(text: str, budget: int) -> str:
    tokens = encoder.encode(text)
    if len(tokens) <= budget:
        return text
    return encoder.decode(tokens[:budget])
```

### Source Code Truncation

When a function exceeds its token budget, truncate intelligently:

```python
def truncate_source(source: str, budget: int, entry: CodeIndexEntry) -> str:
    """Truncate source while preserving key information."""

    tokens = count_tokens(source)
    if tokens <= budget:
        return source

    lines = source.split("\n")

    # Always include:
    # 1. Signature (first line)
    # 2. Docstring (if present)
    # 3. First N lines of body
    # 4. Truncation marker

    result_lines = []
    remaining_budget = budget - 20  # Reserve for truncation marker

    for i, line in enumerate(lines):
        line_tokens = count_tokens(line + "\n")
        if remaining_budget - line_tokens < 0:
            result_lines.append(f"    # ... truncated ({len(lines) - i} more lines)")
            break
        result_lines.append(line)
        remaining_budget -= line_tokens

    return "\n".join(result_lines)
```

### Prioritization When Over Budget

If retrieved content exceeds budget, prioritize by relevance:

**For Diagnostic Mode:**
```
Priority 1: Error site (where exception is raised)
Priority 2: Functions with state mutations (mutates non-empty)
Priority 3: Direct callers of error site
Priority 4: Wiki context for involved files
```

**For Exploratory Mode:**
```
Priority 1: Entry point function
Priority 2: Terminal functions (end of call chain)
Priority 3: Branch points (functions with multiple callees)
Priority 4: Intermediate functions
```

**For Analytical Mode:**
```
Priority 1: Functions with structural issues (high fan-in/out)
Priority 2: Pre-computed issues (high severity first)
Priority 3: Dependency diagram
Priority 4: Representative source samples
```

### Gap Resolution Budget

Spread across CGRAG passes:

```python
GAP_BUDGET = {
    "pass_1": 1000,  # More generous first pass
    "pass_2": 750,
    "pass_3": 500,   # Tighter in later passes
}

def get_gap_budget(pass_number: int) -> int:
    return GAP_BUDGET.get(f"pass_{pass_number}", 500)
```

### Monitoring and Logging

Track budget usage for debugging and tuning:

```python
@dataclass
class BudgetUsage:
    initial_retrieval: int
    gap_resolution: list[int]  # Per pass
    total_used: int
    budget_limit: int

    def log(self):
        logger.info(f"Context budget: {self.total_used}/{self.budget_limit} tokens")
        logger.info(f"  Initial: {self.initial_retrieval}")
        for i, gap_tokens in enumerate(self.gap_resolution):
            logger.info(f"  Pass {i+1} gaps: {gap_tokens}")
```

---

## Configuration

All CGRAG settings are configurable via `backend/src/oya/config.py`.

### Settings Schema

```python
"cgrag": {
    # Query Classification
    "classification_model": "haiku",  # Fast model for classification

    # CGRAG Loop
    "max_passes": 3,
    "stop_on_no_new_context": True,

    # Context Budgets (tokens)
    "total_context_budget": 6000,
    "initial_retrieval_budget": 4000,
    "gap_resolution_budget": 2000,
    "per_gap_budget": 500,

    # Mode-Specific Budgets
    "mode_budgets": {
        "conceptual": {"wiki": 4000, "source": 0, "issues": 0},
        "diagnostic": {"wiki": 1000, "source": 2000, "issues": 0},
        "exploratory": {"wiki": 500, "source": 2500, "issues": 0},
        "analytical": {"wiki": 500, "source": 1500, "issues": 1000},
    },

    # Call Graph Traversal
    "max_call_graph_hops": 3,
    "max_callers_per_hop": 5,
    "max_callees_per_hop": 8,
    "prioritize_mutating_functions": True,

    # Source Fetching
    "max_source_lines_per_function": 100,
    "truncate_long_functions": True,
    "include_signature_in_truncation": True,

    # Code Index
    "index_during_generation": True,
    "extract_raises": True,
    "extract_error_strings": True,
    "extract_mutates": True,
    "docstring_max_length": 200,

    # Session Management
    "session_ttl_minutes": 30,
    "session_max_cached_sources": 50,

    # Confidence Thresholds
    "high_confidence_threshold": 0.3,
    "medium_confidence_threshold": 0.6,
}
```

### Environment Variables

Override settings via environment:

```bash
# Adjust budgets for larger/smaller context windows
CGRAG_TOTAL_CONTEXT_BUDGET=8000
CGRAG_MAX_PASSES=4

# Disable expensive features for faster responses
CGRAG_EXTRACT_MUTATES=false
CGRAG_MAX_CALL_GRAPH_HOPS=2
```

### Per-Request Overrides

API requests can override settings:

```json
POST /api/qa/ask
{
    "question": "Why is the database readonly?",
    "options": {
        "mode": "diagnostic",
        "max_passes": 2,
        "include_source": true
    }
}
```

### Feature Flags

Disable specific features for debugging or performance:

| Flag | Default | Effect |
|------|---------|--------|
| `use_code_index` | true | Enable code index queries |
| `use_call_graph` | true | Enable call graph traversal |
| `use_source_fetching` | true | Fetch actual source code |
| `use_mode_routing` | true | Route by query mode |
| `use_gap_resolution` | true | Enable CGRAG iteration |

When disabled, falls back to conceptual mode (wiki-only semantic search).

### Logging

Control CGRAG logging verbosity:

```python
"logging": {
    "cgrag_level": "INFO",  # DEBUG for detailed traces
    "log_classification": True,
    "log_retrieval_queries": True,
    "log_gap_resolution": True,
    "log_budget_usage": True,
}
```

Debug output example:

```
[CGRAG] Query classified as DIAGNOSTIC (confidence: 0.92)
[CGRAG] Scope: backend/src/oya/api/
[CGRAG] Initial retrieval: 2847 tokens (wiki: 823, source: 2024)
[CGRAG] Pass 1: LLM identified 2 gaps
[CGRAG]   Gap 1: "get_db in deps.py" → resolved via code_index (324 tokens)
[CGRAG]   Gap 2: "staging promotion" → resolved via semantic search (412 tokens)
[CGRAG] Pass 2: No new gaps identified
[CGRAG] Total context: 3583/6000 tokens
```

---

## Implementation Guide

### Implementation Order

Build the system incrementally, with each phase adding value:

**Phase 1: Code Index Foundation**
1. Add `code_index` table schema (`db/migrations.py`)
2. Extend Python parser to extract `raises`, `error_strings`, `mutates`
3. Build code index during wiki generation (`generation/orchestrator.py`)
4. Add `called_by` computation after indexing

**Phase 2: Query Classification**
1. Create `qa/classifier.py` with LLM classification
2. Add classification call to `qa/service.py` before retrieval
3. Log classification results for validation

**Phase 3: Mode-Specific Retrieval**
1. Create `qa/retrieval/` directory with per-mode modules
2. Implement diagnostic retrieval (highest value)
3. Implement exploratory retrieval
4. Implement analytical retrieval
5. Route queries to appropriate retriever

**Phase 4: Enhanced Gap Resolution**
1. Add file/function extraction to `qa/cgrag.py`
2. Implement direct code_index lookup for gaps
3. Add source fetching for resolved gaps
4. Update prompts per mode

**Phase 5: Budget Management**
1. Add token counting throughout pipeline
2. Implement truncation strategies
3. Add budget logging and monitoring

### Testing Strategy

**Unit Tests:**
```python
# Test query classification
def test_classifies_error_query_as_diagnostic():
    result = classify("Why am I getting ValueError?")
    assert result.mode == QueryMode.DIAGNOSTIC

def test_classifies_trace_query_as_exploratory():
    result = classify("Trace the auth flow")
    assert result.mode == QueryMode.EXPLORATORY

# Test code index queries
def test_finds_functions_by_exception():
    results = code_index.search_raises("ValueError")
    assert any(r.symbol_name == "validate_input" for r in results)

# Test gap resolution
def test_resolves_explicit_file_reference():
    context = resolve_gap("get_db in deps.py")
    assert context is not None
    assert "deps.py" in context.path
```

**Integration Tests:**
```python
# Test full diagnostic flow
def test_diagnostic_mode_finds_root_cause():
    response = qa_service.ask(
        "Why am I getting sqlite3.OperationalError: readonly database?"
    )
    # Should find deps.py caching and staging.py promotion
    assert "deps.py" in response.citations or "staging.py" in response.citations

# Test exploratory flow
def test_exploratory_mode_traces_flow():
    response = qa_service.ask("Trace the wiki generation flow")
    # Should include orchestrator and multiple pipeline stages
    assert "orchestrator" in response.answer.lower()
```

**Evaluation Dataset:**

Create a test set of questions with known answers:

| Question | Expected Mode | Key Files That Should Be Retrieved |
|----------|---------------|-----------------------------------|
| "Why readonly database after regen?" | DIAGNOSTIC | deps.py, staging.py |
| "Trace request from API to database" | EXPLORATORY | routers/*.py, service.py |
| "What are the architectural issues?" | ANALYTICAL | (issues from IssuesStore) |
| "How does auth work?" | CONCEPTUAL | auth/*.py wiki docs |

Run periodically to catch regressions.

### Rollout Strategy

1. **Shadow mode:** Run new system in parallel, log results, don't serve
2. **A/B testing:** Route 10% of queries to new system, compare satisfaction
3. **Gradual rollout:** Increase percentage as confidence grows
4. **Full rollout:** Switch default, keep fallback flag

### Monitoring

Track these metrics post-launch:

| Metric | Target | Alert Threshold |
|--------|--------|-----------------|
| Classification accuracy | >90% | <80% |
| Gap resolution success rate | >70% | <50% |
| Avg tokens used | <4000 | >5500 |
| Avg latency (ms) | <3000 | >5000 |
| User satisfaction (if tracked) | >4.0/5 | <3.5/5 |
