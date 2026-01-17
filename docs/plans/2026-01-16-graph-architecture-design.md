# Graph-Based Code Intelligence for Oya

## Problem Statement

Oya can explain individual files but cannot synthesize cross-cutting answers like "how does auth flow from request to database." Vector search retrieves *related* files but doesn't understand *how they connect*. The LLM receives isolated chunks without the structural relationships that define architecture.

## Solution Overview

Build a code knowledge graph that captures relationships between code entities (functions, classes, files). Use this graph to:
1. **At generation time:** Write architecture documentation that traces real flows
2. **At query time:** Retrieve connected code subgraphs, not isolated chunks

## Phased Roadmap

| Phase | Goal | Checkpoint |
|-------|------|------------|
| 1 | Extract relationships from code with confidence scores | Can answer "what does function X call?" without LLM |
| 2 | Build queryable NetworkX graph | Can visualize module call graphs, trace paths |
| 3 | Generate architecture documentation from graph | Architecture pages accurately explain feature flows |
| 4 | Graph-augmented Q&A retrieval | "How does auth work?" traces actual call flow |
| 5 | Iterative retrieval (CGRAG) | Multi-pass retrieval improves complex query answers |

---

## Phase 1: Extract Relationships (FULLY DESIGNED)

### What We're Extracting

For each code entity, extract outbound references with confidence:

| Reference Type | Example | Confidence Logic |
|---------------|---------|------------------|
| **Import** | `from auth import verify` | High (0.9+) - statically provable |
| **Direct call** | `verify(token)` | High if imported name, Medium if parameter/local |
| **Method call** | `user.save()` | Medium (0.6-0.8) - requires type inference |
| **Inheritance** | `class Admin(User)` | High - statically provable |
| **Instantiation** | `user = User()` | High if class name resolved |

**Confidence levels:**
- **High (0.9+)**: Statically provable from imports and definitions
- **Medium (0.6-0.8)**: Inferred from naming conventions, nearby context
- **Low (0.3-0.5)**: Guessed based on heuristics, multiple candidates exist

**Storage format:**
```python
{
  "source": "auth/handler.py::login",
  "target": "auth/session.py::create_session",
  "type": "calls",
  "confidence": 0.85,
  "evidence": "imported as create_session, called directly"
}
```

### Extraction Strategy

**Two-pass approach:**

*Pass 1 - Build the symbol table:*
- Parse all files, extract all definitions (functions, classes, methods)
- Build a global lookup: `{"User": "models/user.py::User", "verify": "auth/utils.py::verify", ...}`

*Pass 2 - Resolve references:*
- Parse each file again, looking for usages
- For each call/reference, attempt to resolve against the symbol table
- Assign confidence based on resolution certainty

**Resolution heuristics (Python example):**

```python
# High confidence - direct import, direct call
from auth.utils import verify
verify(token)  # → auth/utils.py::verify (0.95)

# Medium confidence - aliased or method call
from auth import utils
utils.verify(token)  # → auth/utils.py::verify (0.75)

# Medium confidence - instance method
user = User()
user.save()  # → models/user.py::User.save (0.7)

# Low confidence - parameter, unknown type
def process(handler):
    handler.run()  # → multiple candidates (0.4)
```

**Out of scope for Phase 1:**
- Dynamic dispatch (`getattr(obj, method_name)()`)
- Decorator-wrapped functions that change signatures
- Monkey-patched methods

### Integration with Existing Parsing

Extend parsers in `backend/src/oya/parsing/` to return references alongside definitions.

**Current output:**
```python
{"definitions": [Function(...), Class(...)]}
```

**New output:**
```python
{
  "definitions": [Function(...), Class(...)],
  "references": [
    Reference(source="login", target="verify", type="calls", confidence=0.9),
    Reference(source="login", target="User", type="instantiates", confidence=0.85),
  ]
}
```

**New module:**
```
parsing/
  resolver.py  # Builds symbol table, resolves cross-file references
```

**Call flow:**
1. Parse all files → get definitions + unresolved references
2. `resolver.py` builds global symbol table from definitions
3. Resolver matches each reference to a definition
4. Output: resolved references with confidence scores

**Storage:**
References persist to `.oyawiki/graph/references.json`

### Phase 1 Checkpoint Criteria

1. Python, TypeScript parsers extract references with confidence
2. Resolver correctly links cross-file references
3. Self-analysis of Oya produces sensible output
4. References persisted to `.oyawiki/graph/`
5. Accuracy benchmark: >80% precision on high-confidence edges, >60% recall overall

---

## Phase 2: Build the Code Graph (FULLY DESIGNED)

### Graph Structure

**Node types:**
```python
{
  "id": "backend/src/oya/api/routers/qa.py::ask_question",
  "type": "function",  # or "class", "file", "module"
  "name": "ask_question",
  "file": "backend/src/oya/api/routers/qa.py",
  "line_start": 45,
  "line_end": 92,
  "docstring": "Handle Q&A queries against the wiki..."
}
```

**Edge types:**
```python
{
  "source": "qa.py::ask_question",
  "target": "vectorstore/search.py::semantic_search",
  "type": "calls",
  "confidence": 0.9
}
```

### Building and Persisting

**Build process:**
```python
# graph/builder.py
def build_graph(parsed_files: list[ParsedFile]) -> nx.DiGraph:
    G = nx.DiGraph()

    # 1. Add all definition nodes
    for file in parsed_files:
        for defn in file.definitions:
            G.add_node(defn.id, **defn.attributes)

    # 2. Add all reference edges
    for file in parsed_files:
        for ref in file.references:
            G.add_edge(
                ref.source,
                ref.target,
                type=ref.type,
                confidence=ref.confidence
            )

    return G
```

**Persistence to `.oyawiki/graph/`:**
```
.oyawiki/
  graph/
    nodes.json      # All node definitions
    edges.json      # All edges with confidence
    metadata.json   # Build timestamp, file count, stats
```

JSON format chosen for: human-readability, git diffability, partial loading.

**Incremental updates:** Deferred optimization. Start with full rebuild each generation.

### Query Interface

```python
# graph/query.py

def get_calls(node_id: str, min_confidence: float = 0.5) -> list[Node]:
    """What does this function call?"""

def get_callers(node_id: str, min_confidence: float = 0.5) -> list[Node]:
    """What calls this function?"""

def get_neighborhood(node_id: str, hops: int = 2, min_confidence: float = 0.5) -> Subgraph:
    """Get all nodes within N hops of this node."""

def trace_flow(start: str, end: str, min_confidence: float = 0.5) -> list[Path]:
    """Find paths between two nodes (e.g., request handler → database)."""

def get_subgraph_by_path(path_pattern: str) -> Subgraph:
    """Get all nodes in files matching pattern (e.g., 'auth/*')."""

def get_entry_points() -> list[Node]:
    """Find nodes with high in-degree (many callers) - likely important."""

def get_leaf_nodes() -> list[Node]:
    """Find nodes with no outbound calls - endpoints like DB, external APIs."""
```

**Subgraph result:**
```python
@dataclass
class Subgraph:
    nodes: list[Node]
    edges: list[Edge]

    def to_context(self) -> str:
        """Format as text for LLM consumption."""

    def to_mermaid(self) -> str:
        """Generate deterministic Mermaid diagram."""
```

The `to_mermaid()` method generates diagrams from the graph, not LLM imagination.

### Phase 2 Checkpoint Criteria

1. Graph builds successfully from Phase 1 output
2. Graph persists to `.oyawiki/graph/` as JSON
3. Query interface works for forward/backward/multi-hop traversal
4. Self-analysis of Oya produces accurate, verifiable graph
5. Mermaid diagrams are deterministic and correct

---

## ⚠️ STOP AFTER PHASE 2 - DESIGN SESSION REQUIRED ⚠️

**Phases 3-5 have NOT been fully designed.**

When you complete Phase 2:
1. Stop and evaluate: Is the graph accurate enough? Are queries useful?
2. Start a new brainstorming session to design Phase 3 in detail
3. Tell Claude: "Read the graph architecture design doc and let's design Phase 3"

**Do not proceed to implementation of Phase 3 without a full design session.**

---

## Phase 3: Generate Architecture Documentation (KEY DECISIONS ONLY)

*Goal:* During wiki generation, use the graph to identify architectural patterns and generate pages that trace cross-cutting flows.

**Key decisions to make when designing:**

- **What pages to generate?**
  - Options: one "Architecture Overview" page, separate pages per subsystem, flow-specific pages ("How Authentication Works")

- **How to identify subsystems?**
  - Options: directory-based grouping, graph clustering (Leiden algorithm), manual configuration, hybrid

- **How to detect "important" entry points?**
  - High fan-in (many callers)? Route handlers? Decorated functions?

- **How much LLM involvement?**
  - Graph provides structure, but how much prose generation? Just annotations, or full narrative synthesis?

- **How to handle low-confidence edges?**
  - Omit from docs? Include with caveats? Use LLM to disambiguate?

---

## Phase 4: Graph-Augmented Q&A Retrieval (KEY DECISIONS ONLY)

*Goal:* Combine vector search (semantic relevance) with graph traversal (structural connections). Present connected code, not isolated chunks.

**Key decisions to make when designing:**

- **Retrieval strategy?**
  - Vector-first then expand via graph? Graph-first then rank by vector similarity? Parallel and merge?

- **How many hops?**
  - Fixed depth (always 2 hops)? Dynamic based on query complexity? User-configurable?

- **Confidence threshold for Q&A?**
  - Should low-confidence edges be followed during retrieval, or only high-confidence?

- **Context budget?**
  - Graph can return a lot of code. How to prioritize what fits in context window?

- **How to present the subgraph to the LLM?**
  - Flat code dump? Structured with relationship annotations? Include the Mermaid diagram?

---

## Phase 5: Iterative Retrieval / CGRAG (KEY DECISIONS ONLY)

*Goal:* Multi-pass retrieval where the LLM identifies gaps ("I see `verify_user` called but don't have its definition") and the system fetches missing pieces.

**Key decisions to make when designing:**

- **How many iterations?**
  - Fixed (2 passes)? Until LLM says "sufficient"? Cost/latency budget?

- **Gap detection method?**
  - Explicit LLM prompt ("what's missing?")? Parse for unresolved references? Both?

- **What triggers CGRAG vs single-pass?**
  - Always multi-pass? Only for complex queries? User toggle?

- **How to avoid loops?**
  - If LLM keeps asking for more, when to stop?

- **Caching?**
  - If same references are requested often, pre-fetch popular paths?

---

## Key Design Decisions Made

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Relationship accuracy approach | Probabilistic with confidence scores | Balance coverage and honesty about uncertainty |
| Graph storage | NetworkX with JSON persistence | Simple, no external dependencies, git-friendly |
| Diagram generation | Deterministic from graph | Avoids "handwavy" LLM-generated diagrams |
| Incremental updates | Deferred | Start simple with full rebuild |
| Stack Graphs integration | Deferred | Evaluate after seeing Phase 1-2 accuracy |

---

## References

- Original analysis document: `docs/notes/improving-oya.md`
- Tree-sitter documentation: https://tree-sitter.github.io/
- NetworkX documentation: https://networkx.org/
- Stack Graphs (for future consideration): https://github.blog/open-source/introducing-stack-graphs/
