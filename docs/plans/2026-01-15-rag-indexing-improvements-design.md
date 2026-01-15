# RAG Indexing Improvements Design

## Overview

This design improves Oya's Phase 8 indexing to enable better retrieval for Q&A. The current system indexes entire wiki pages as single documents, leading to diluted embeddings and imprecise retrieval. This design introduces semantic chunking, richer metadata, and improved ranking.

## Current State

- Entire wiki pages indexed as single documents
- Query-time truncation (1500 tokens per result, 6000 total)
- Simple deduplication-based merging of semantic + FTS results
- Basic metadata: path, title, type

## Goals

1. Improve retrieval precision through semantic chunking
2. Enable filtering by architectural layer, symbols, imports
3. Better combine semantic and keyword search results
4. Preserve context across chunk boundaries

## Non-Goals (Future Phases)

- Query expansion (synonym/acronym mapping)
- Raw source code indexing (separate from wiki)
- Cross-encoder re-ranking

---

## Architecture

**Current flow:**
```
Wiki Pages → Index whole documents → ChromaDB + FTS → Query → Merge results → LLM
```

**New flow:**
```
Wiki Pages → Chunk by section → Enrich metadata → ChromaDB + FTS
                                                       ↓
User Query → Search both → RRF merge → Return to LLM
```

### New Components

| Component | Location | Purpose |
|-----------|----------|---------|
| ChunkingService | `oya/indexing/chunking.py` | Splits wiki pages into semantic chunks |
| MetadataExtractor | `oya/indexing/metadata.py` | Extracts symbols, imports, layer info from existing parsed data |
| RRFRanker | `oya/qa/ranking.py` | Combines semantic + FTS rankings using Reciprocal Rank Fusion |

### Modified Components

| Component | Changes |
|-----------|---------|
| IndexingService | Orchestrates chunking → metadata → indexing |
| QAService | Uses RRF ranker instead of dedup-based merging |
| FTS schema | Adds chunk-level columns |

---

## Chunking Strategy

### Section-Based Chunking

Pages are split at H2/H3 header boundaries. Each section becomes a chunk.

**Context prefix:** Each chunk includes document context:
```
[Document: src/auth/service.py | Section: Internal Details]

The validation happens in two stages...
```

**Oversized sections:** If a section exceeds 1000 tokens, split into fixed-size chunks (500 tokens) with 100-token overlap.

### Chunk Data Model

```python
@dataclass
class Chunk:
    id: str                    # "wiki_files_src-auth-service_internal-details"
    content: str               # Prefixed section content
    document_path: str         # "files/src-auth-service.md"
    document_title: str        # "src/auth/service.py"
    section_header: str        # "Internal Details"
    chunk_index: int           # Position in document (0, 1, 2...)
    token_count: int           # For context budgeting
    metadata: ChunkMetadata    # Layer, symbols, imports, etc.
```

### Edge Cases

- **No headers**: Treat entire document as one chunk (with size limit)
- **Empty sections**: Skip
- **Nested headers**: Include H3 content with H2 parent, split if too large

### Code Blocks

Code blocks remain inline with their sections. If a code block exceeds ~500 tokens, truncate in chunk but store full code in metadata for display.

---

## Metadata Extraction

### Chunk Metadata Schema

```python
@dataclass
class ChunkMetadata:
    # Essential
    path: str                  # "files/src-auth-service.md"
    title: str                 # "src/auth/service.py"
    type: str                  # "file", "directory", "workflow", etc.
    section_header: str        # "Internal Details"
    chunk_index: int           # Position in document
    token_count: int           # Token count of chunk

    # Architectural
    layer: str                 # "api", "domain", "infrastructure", etc.

    # Code references
    symbols: list[str]         # ["validate_token", "TokenError"]
    imports: list[str]         # ["datetime", "oya.auth.models"]
    entry_points: list[str]    # ["POST /auth/login"]
```

### Extraction Sources

| Field | Source |
|-------|--------|
| path, title, type | Wiki page path (existing logic) |
| section_header, chunk_index | Markdown parsing |
| token_count | Token estimation |
| layer | SynthesisMap.layers (match source file to layer) |
| symbols | analysis["symbols"] filtered to chunk content |
| imports | analysis["file_imports"] for source file |
| entry_points | SynthesisMap.entry_points matched by file |

All code-related metadata comes from existing parsed data (tree-sitter based, language-agnostic). No new parsing or regex required.

---

## Reciprocal Rank Fusion (RRF)

### Current Approach (Problems)

- Run semantic search, run FTS search
- Deduplicate by path
- Sort by type priority, then distance
- A result ranked #1 in semantic but #10 in FTS gets same treatment as #10 in both

### RRF Formula

```
RRF_score(doc) = 1/(k + rank_semantic) + 1/(k + rank_fts)
```

Where `k = 60` (standard constant preventing top ranks from dominating).

### Example

| Document | Semantic Rank | FTS Rank | RRF Score |
|----------|---------------|----------|-----------|
| chunk_A  | 1             | 3        | 1/61 + 1/63 = 0.032 |
| chunk_B  | 5             | 1        | 1/65 + 1/61 = 0.031 |
| chunk_C  | 2             | 8        | 1/62 + 1/68 = 0.031 |

Documents appearing in both searches get boosted. Missing ranks treated as large number (1000).

### Implementation

```python
def rrf_merge(semantic_results, fts_results, k=60, missing_rank=1000):
    scores = defaultdict(float)

    semantic_ranks = {doc.id: rank for rank, doc in enumerate(semantic_results)}
    fts_ranks = {doc.id: rank for rank, doc in enumerate(fts_results)}

    all_ids = set(semantic_ranks.keys()) | set(fts_ranks.keys())

    for doc_id in all_ids:
        sem_rank = semantic_ranks.get(doc_id, missing_rank)
        fts_rank = fts_ranks.get(doc_id, missing_rank)
        scores[doc_id] = 1/(k + sem_rank + 1) + 1/(k + fts_rank + 1)

    return sorted(scores.items(), key=lambda x: -x[1])
```

---

## Storage Schema

### ChromaDB

Changes from one document per wiki page to one document per chunk:

```python
vectorstore.add_documents(
    ids=["wiki_files_src-auth_chunk0", "wiki_files_src-auth_chunk1", ...],
    documents=["[Document: src/auth.py | Section: Overview]\n...", ...],
    metadatas=[{
        "path": "files/src-auth.md",
        "title": "src/auth.py",
        "type": "file",
        "section_header": "Overview",
        "chunk_index": 0,
        "layer": "domain",
        "symbols": '["authenticate", "User"]',  # JSON string
        "imports": '["bcrypt", "oya.models"]',
        "entry_points": '[]',
    }, ...]
)
```

### SQLite FTS5

```sql
-- New schema
CREATE VIRTUAL TABLE fts_content USING fts5(
    content,
    title,
    path UNINDEXED,
    type UNINDEXED,
    section_header,
    chunk_id UNINDEXED,
    chunk_index UNINDEXED
);
```

### Migration

Drop and recreate index on upgrade. Indexing is idempotent - reindex rebuilds everything from wiki content.

---

## Data Flow

### Indexing Flow

```
1. Load SynthesisMap and analysis data (symbols, file_imports)
2. For each wiki markdown file:
   a. Parse markdown → extract sections
   b. For each section:
      - Create chunk with context prefix
      - If section > 1000 tokens, split with overlap
   c. Extract metadata for each chunk:
      - Map file path → layer, symbols, imports, entry_points
      - Filter symbols to those appearing in chunk content
   d. Collect chunks for batch insert
3. Batch insert all chunks into ChromaDB
4. Batch insert all chunks into FTS5
5. Save embedding metadata
```

### Query Flow

```
1. Receive user query
2. Run semantic search → get ranked chunk results
3. Run FTS search → get ranked chunk results
4. Apply RRF to merge rankings
5. Deduplicate by chunk_id
6. Return top N chunks with full metadata
```

### Context Building

```
1. Receive RRF-ranked chunks
2. For each chunk (up to token budget):
   - Include: type, path, section_header
   - Include: chunk content (already has context prefix)
3. Optionally group consecutive chunks from same document
```

---

## Testing

### Unit Tests

| Component | Test Cases |
|-----------|------------|
| ChunkingService | Splits on H2/H3; handles no headers; splits oversized sections with overlap; adds context prefix |
| MetadataExtractor | Maps file to layer; extracts symbols from analysis; filters to chunk content |
| RRFRanker | Correct scoring formula; handles missing ranks; maintains order |

### Integration Tests

- Index sample wiki → verify chunk count matches expected sections
- Query for specific symbol → verify chunk containing it ranks highly
- Query with term in FTS but not semantic → verify RRF surfaces it

---

## Migration Strategy

1. Database migration adds new FTS columns (backward compatible)
2. On first reindex after upgrade:
   - Clear existing index (already happens)
   - Reindex with new chunking logic
3. No user action required beyond normal regeneration
4. Embedding metadata tracks version to detect old indexes

**Rollback:** Revert code and reindex. Wiki content unchanged, only index structure differs.

---

## Future Enhancements

### Query Expansion (Phase 2)
- Synonym/acronym mapping for common terms
- Optional LLM-based expansion for "deep search" mode

### Raw Code Indexing (Phase 3)
- Index source files directly (not just wiki)
- Code-aware chunking by function/class
- Enables "find the actual implementation" searches
