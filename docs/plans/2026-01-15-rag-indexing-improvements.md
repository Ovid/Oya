# RAG Indexing Improvements Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Improve RAG retrieval precision through semantic chunking, richer metadata, and Reciprocal Rank Fusion ranking.

**Architecture:** Split wiki pages into section-based chunks with context prefixes. Extract metadata (layer, symbols, imports, entry_points) from existing parsed data. Replace dedup-based result merging with RRF scoring. Update IndexingService and QAService to use new components.

**Tech Stack:** Python 3.11+, pytest, ChromaDB, SQLite FTS5, dataclasses

---

## Task 1: Create Chunk Data Model

**Files:**
- Create: `backend/src/oya/indexing/chunking.py`
- Test: `backend/tests/test_chunking.py`

**Step 1: Write the failing test**

Create `backend/tests/test_chunking.py`:

```python
"""Tests for wiki content chunking."""

import pytest

from oya.indexing.chunking import Chunk, ChunkMetadata


class TestChunkDataModel:
    """Tests for Chunk dataclass."""

    def test_chunk_creation(self):
        """Chunk holds all required fields."""
        metadata = ChunkMetadata(
            path="files/src-auth.md",
            title="src/auth.py",
            type="file",
            section_header="Overview",
            chunk_index=0,
            token_count=150,
            layer="domain",
            symbols=["authenticate", "User"],
            imports=["bcrypt"],
            entry_points=[],
        )

        chunk = Chunk(
            id="wiki_files_src-auth_overview",
            content="[Document: src/auth.py | Section: Overview]\n\nHandles authentication.",
            document_path="files/src-auth.md",
            document_title="src/auth.py",
            section_header="Overview",
            chunk_index=0,
            token_count=150,
            metadata=metadata,
        )

        assert chunk.id == "wiki_files_src-auth_overview"
        assert chunk.section_header == "Overview"
        assert chunk.metadata.layer == "domain"
        assert "authenticate" in chunk.metadata.symbols
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/poecurt/projects/oya/.worktrees/rag-indexing/backend && source .venv/bin/activate && pytest tests/test_chunking.py::TestChunkDataModel::test_chunk_creation -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'oya.indexing.chunking'`

**Step 3: Write minimal implementation**

Create `backend/src/oya/indexing/chunking.py`:

```python
"""Chunking service for wiki content."""

from dataclasses import dataclass, field


@dataclass
class ChunkMetadata:
    """Metadata for a wiki chunk.

    Attributes:
        path: Wiki page path (e.g., "files/src-auth.md").
        title: Document title (e.g., "src/auth.py").
        type: Page type (file, directory, workflow, etc.).
        section_header: H2/H3 header text for this chunk.
        chunk_index: Position in document (0, 1, 2...).
        token_count: Estimated token count.
        layer: Architectural layer (api, domain, infrastructure, etc.).
        symbols: Function/class names in this chunk.
        imports: Import dependencies for the source file.
        entry_points: Entry points defined in this file.
    """

    path: str
    title: str
    type: str
    section_header: str
    chunk_index: int
    token_count: int
    layer: str = ""
    symbols: list[str] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)
    entry_points: list[str] = field(default_factory=list)


@dataclass
class Chunk:
    """A semantic chunk of wiki content.

    Attributes:
        id: Unique identifier (e.g., "wiki_files_src-auth_overview").
        content: Chunk text with context prefix.
        document_path: Source wiki page path.
        document_title: Source document title.
        section_header: Section header for this chunk.
        chunk_index: Position in document.
        token_count: Estimated token count.
        metadata: Full metadata for search/filtering.
    """

    id: str
    content: str
    document_path: str
    document_title: str
    section_header: str
    chunk_index: int
    token_count: int
    metadata: ChunkMetadata
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/poecurt/projects/oya/.worktrees/rag-indexing/backend && source .venv/bin/activate && pytest tests/test_chunking.py::TestChunkDataModel::test_chunk_creation -v`

Expected: PASS

**Step 5: Commit**

```bash
cd /Users/poecurt/projects/oya/.worktrees/rag-indexing && git add backend/src/oya/indexing/chunking.py backend/tests/test_chunking.py && git commit -m "feat(chunking): add Chunk and ChunkMetadata dataclasses"
```

---

## Task 2: Implement Markdown Section Parser

**Files:**
- Modify: `backend/src/oya/indexing/chunking.py`
- Test: `backend/tests/test_chunking.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_chunking.py`:

```python
from oya.indexing.chunking import parse_markdown_sections, Section


class TestMarkdownParsing:
    """Tests for markdown section parsing."""

    def test_parses_h2_sections(self):
        """Splits markdown on H2 headers."""
        content = """# Main Title

Introduction paragraph.

## Overview

This is the overview section.

## Details

This is the details section.
"""
        sections = parse_markdown_sections(content)

        assert len(sections) == 3  # Intro + 2 H2 sections
        assert sections[0].header == ""  # Content before first H2
        assert sections[1].header == "Overview"
        assert sections[2].header == "Details"
        assert "overview section" in sections[1].content.lower()

    def test_parses_h3_sections(self):
        """Splits on H3 headers within H2."""
        content = """## Parent Section

Intro text.

### Child Section

Child content.
"""
        sections = parse_markdown_sections(content)

        # Should have parent intro + child section
        assert len(sections) >= 2
        assert any(s.header == "Child Section" for s in sections)

    def test_handles_no_headers(self):
        """Returns single section when no headers."""
        content = "Just plain text without any headers."

        sections = parse_markdown_sections(content)

        assert len(sections) == 1
        assert sections[0].header == ""
        assert sections[0].content == content
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/poecurt/projects/oya/.worktrees/rag-indexing/backend && source .venv/bin/activate && pytest tests/test_chunking.py::TestMarkdownParsing -v`

Expected: FAIL with `ImportError: cannot import name 'parse_markdown_sections'`

**Step 3: Write minimal implementation**

Add to `backend/src/oya/indexing/chunking.py`:

```python
import re


@dataclass
class Section:
    """A section of markdown content.

    Attributes:
        header: Section header text (empty for content before first header).
        content: Full section content including header.
        level: Header level (2 for H2, 3 for H3, 0 for no header).
    """

    header: str
    content: str
    level: int = 0


def parse_markdown_sections(content: str) -> list[Section]:
    """Parse markdown into sections based on H2/H3 headers.

    Args:
        content: Markdown content to parse.

    Returns:
        List of Section objects.
    """
    if not content.strip():
        return []

    # Pattern matches ## or ### headers
    header_pattern = re.compile(r"^(#{2,3})\s+(.+)$", re.MULTILINE)

    sections: list[Section] = []
    last_end = 0

    for match in header_pattern.finditer(content):
        # Capture content before this header
        if match.start() > last_end:
            pre_content = content[last_end : match.start()].strip()
            if pre_content:
                # Check if this is content before first header or after a header
                if not sections:
                    sections.append(Section(header="", content=pre_content, level=0))

        # This header starts a new section - we'll capture its content on next iteration
        header_level = len(match.group(1))
        header_text = match.group(2).strip()
        last_end = match.start()

    # Handle remaining content after last header (or all content if no headers)
    if last_end == 0:
        # No headers found
        return [Section(header="", content=content.strip(), level=0)]

    # Now re-process to get sections with their content
    sections = []
    matches = list(header_pattern.finditer(content))

    # Content before first header
    if matches and matches[0].start() > 0:
        pre_content = content[: matches[0].start()].strip()
        if pre_content:
            sections.append(Section(header="", content=pre_content, level=0))

    # Each header and its content
    for i, match in enumerate(matches):
        header_level = len(match.group(1))
        header_text = match.group(2).strip()

        # Content extends to next header or end of document
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        section_content = content[start:end].strip()

        sections.append(Section(header=header_text, content=section_content, level=header_level))

    return sections
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/poecurt/projects/oya/.worktrees/rag-indexing/backend && source .venv/bin/activate && pytest tests/test_chunking.py::TestMarkdownParsing -v`

Expected: PASS

**Step 5: Commit**

```bash
cd /Users/poecurt/projects/oya/.worktrees/rag-indexing && git add backend/src/oya/indexing/chunking.py backend/tests/test_chunking.py && git commit -m "feat(chunking): add markdown section parser"
```

---

## Task 3: Implement ChunkingService

**Files:**
- Modify: `backend/src/oya/indexing/chunking.py`
- Test: `backend/tests/test_chunking.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_chunking.py`:

```python
from oya.indexing.chunking import ChunkingService
from oya.generation.chunking import estimate_tokens


class TestChunkingService:
    """Tests for ChunkingService."""

    def test_creates_chunks_from_sections(self):
        """Creates chunks with context prefix from markdown sections."""
        service = ChunkingService()

        content = """# src/auth.py

## Overview

Handles user authentication.

## Public API

Exports authenticate() function.
"""
        chunks = service.chunk_document(
            content=content,
            document_path="files/src-auth.md",
            document_title="src/auth.py",
            page_type="file",
        )

        assert len(chunks) >= 2
        assert chunks[0].section_header == "Overview"
        assert chunks[1].section_header == "Public API"

        # Check context prefix
        assert "[Document: src/auth.py |" in chunks[0].content
        assert "Section: Overview]" in chunks[0].content

    def test_generates_chunk_ids(self):
        """Generates unique chunk IDs from path and section."""
        service = ChunkingService()

        content = """## Overview

Content here.
"""
        chunks = service.chunk_document(
            content=content,
            document_path="files/src-auth.md",
            document_title="src/auth.py",
            page_type="file",
        )

        assert chunks[0].id == "wiki_files_src-auth_overview"

    def test_splits_oversized_sections(self):
        """Splits sections exceeding max tokens with overlap."""
        service = ChunkingService(max_section_tokens=100, overlap_tokens=20)

        # Create content that exceeds 100 tokens
        long_content = "## Big Section\n\n" + ("This is a test sentence. " * 50)

        chunks = service.chunk_document(
            content=long_content,
            document_path="files/big.md",
            document_title="big.py",
            page_type="file",
        )

        # Should be split into multiple chunks
        assert len(chunks) > 1
        # All chunks should reference same section
        assert all(c.section_header == "Big Section" for c in chunks)
        # Chunk indices should be sequential
        assert [c.chunk_index for c in chunks] == list(range(len(chunks)))
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/poecurt/projects/oya/.worktrees/rag-indexing/backend && source .venv/bin/activate && pytest tests/test_chunking.py::TestChunkingService -v`

Expected: FAIL with `ImportError: cannot import name 'ChunkingService'`

**Step 3: Write minimal implementation**

Add to `backend/src/oya/indexing/chunking.py`:

```python
from oya.generation.chunking import estimate_tokens


class ChunkingService:
    """Service for chunking wiki pages into semantic units.

    Splits markdown documents on H2/H3 headers, adds context prefixes,
    and handles oversized sections with overlap.
    """

    def __init__(
        self,
        max_section_tokens: int = 1000,
        overlap_tokens: int = 100,
        chunk_size_tokens: int = 500,
    ) -> None:
        """Initialize chunking service.

        Args:
            max_section_tokens: Max tokens before splitting a section.
            overlap_tokens: Token overlap when splitting oversized sections.
            chunk_size_tokens: Target chunk size when splitting.
        """
        self._max_section_tokens = max_section_tokens
        self._overlap_tokens = overlap_tokens
        self._chunk_size_tokens = chunk_size_tokens

    def chunk_document(
        self,
        content: str,
        document_path: str,
        document_title: str,
        page_type: str,
        base_metadata: ChunkMetadata | None = None,
    ) -> list[Chunk]:
        """Chunk a wiki document into semantic units.

        Args:
            content: Markdown content.
            document_path: Wiki page path (e.g., "files/src-auth.md").
            document_title: Document title (e.g., "src/auth.py").
            page_type: Page type (file, directory, workflow, etc.).
            base_metadata: Optional base metadata to merge into chunks.

        Returns:
            List of Chunk objects.
        """
        sections = parse_markdown_sections(content)
        chunks: list[Chunk] = []
        chunk_index = 0

        for section in sections:
            section_chunks = self._chunk_section(
                section=section,
                document_path=document_path,
                document_title=document_title,
                page_type=page_type,
                start_index=chunk_index,
                base_metadata=base_metadata,
            )
            chunks.extend(section_chunks)
            chunk_index += len(section_chunks)

        return chunks

    def _chunk_section(
        self,
        section: Section,
        document_path: str,
        document_title: str,
        page_type: str,
        start_index: int,
        base_metadata: ChunkMetadata | None,
    ) -> list[Chunk]:
        """Chunk a single section, splitting if oversized.

        Args:
            section: Section to chunk.
            document_path: Wiki page path.
            document_title: Document title.
            page_type: Page type.
            start_index: Starting chunk index.
            base_metadata: Optional base metadata.

        Returns:
            List of chunks for this section.
        """
        section_tokens = estimate_tokens(section.content)

        if section_tokens <= self._max_section_tokens:
            # Section fits in one chunk
            return [
                self._create_chunk(
                    section=section,
                    content=section.content,
                    document_path=document_path,
                    document_title=document_title,
                    page_type=page_type,
                    chunk_index=start_index,
                    base_metadata=base_metadata,
                )
            ]

        # Split oversized section
        return self._split_section(
            section=section,
            document_path=document_path,
            document_title=document_title,
            page_type=page_type,
            start_index=start_index,
            base_metadata=base_metadata,
        )

    def _split_section(
        self,
        section: Section,
        document_path: str,
        document_title: str,
        page_type: str,
        start_index: int,
        base_metadata: ChunkMetadata | None,
    ) -> list[Chunk]:
        """Split an oversized section into chunks with overlap.

        Args:
            section: Oversized section to split.
            document_path: Wiki page path.
            document_title: Document title.
            page_type: Page type.
            start_index: Starting chunk index.
            base_metadata: Optional base metadata.

        Returns:
            List of chunks.
        """
        chunks: list[Chunk] = []
        text = section.content
        words = text.split()
        chunk_index = start_index

        # Approximate words per token (rough estimate)
        words_per_token = 0.75
        chunk_words = int(self._chunk_size_tokens * words_per_token)
        overlap_words = int(self._overlap_tokens * words_per_token)

        start = 0
        while start < len(words):
            end = min(start + chunk_words, len(words))
            chunk_text = " ".join(words[start:end])

            chunks.append(
                self._create_chunk(
                    section=section,
                    content=chunk_text,
                    document_path=document_path,
                    document_title=document_title,
                    page_type=page_type,
                    chunk_index=chunk_index,
                    base_metadata=base_metadata,
                )
            )

            chunk_index += 1
            start = end - overlap_words if end < len(words) else len(words)

        return chunks

    def _create_chunk(
        self,
        section: Section,
        content: str,
        document_path: str,
        document_title: str,
        page_type: str,
        chunk_index: int,
        base_metadata: ChunkMetadata | None,
    ) -> Chunk:
        """Create a chunk with context prefix.

        Args:
            section: Source section.
            content: Chunk content (may be subset of section).
            document_path: Wiki page path.
            document_title: Document title.
            page_type: Page type.
            chunk_index: Chunk index in document.
            base_metadata: Optional base metadata.

        Returns:
            Chunk object.
        """
        header = section.header or "Introduction"

        # Add context prefix
        prefixed_content = f"[Document: {document_title} | Section: {header}]\n\n{content}"

        # Generate chunk ID
        slug = self._slugify(document_path.replace(".md", ""))
        header_slug = self._slugify(header)
        chunk_id = f"wiki_{slug}_{header_slug}"
        if chunk_index > 0:
            chunk_id += f"_{chunk_index}"

        token_count = estimate_tokens(prefixed_content)

        metadata = ChunkMetadata(
            path=document_path,
            title=document_title,
            type=page_type,
            section_header=header,
            chunk_index=chunk_index,
            token_count=token_count,
            layer=base_metadata.layer if base_metadata else "",
            symbols=base_metadata.symbols if base_metadata else [],
            imports=base_metadata.imports if base_metadata else [],
            entry_points=base_metadata.entry_points if base_metadata else [],
        )

        return Chunk(
            id=chunk_id,
            content=prefixed_content,
            document_path=document_path,
            document_title=document_title,
            section_header=header,
            chunk_index=chunk_index,
            token_count=token_count,
            metadata=metadata,
        )

    def _slugify(self, text: str) -> str:
        """Convert text to URL-friendly slug."""
        slug = text.lower().replace("/", "_").replace(" ", "-")
        slug = re.sub(r"[^a-z0-9_-]", "", slug)
        return slug
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/poecurt/projects/oya/.worktrees/rag-indexing/backend && source .venv/bin/activate && pytest tests/test_chunking.py::TestChunkingService -v`

Expected: PASS

**Step 5: Commit**

```bash
cd /Users/poecurt/projects/oya/.worktrees/rag-indexing && git add backend/src/oya/indexing/chunking.py backend/tests/test_chunking.py && git commit -m "feat(chunking): add ChunkingService with section splitting"
```

---

## Task 4: Create MetadataExtractor

**Files:**
- Create: `backend/src/oya/indexing/metadata.py`
- Test: `backend/tests/test_metadata_extractor.py`

**Step 1: Write the failing test**

Create `backend/tests/test_metadata_extractor.py`:

```python
"""Tests for metadata extraction."""

import pytest

from oya.indexing.metadata import MetadataExtractor
from oya.generation.summaries import SynthesisMap, LayerInfo, EntryPointInfo


class TestMetadataExtractor:
    """Tests for MetadataExtractor."""

    def test_extracts_layer_from_synthesis_map(self):
        """Maps source file to architectural layer."""
        synthesis_map = SynthesisMap(
            layers={
                "api": LayerInfo(name="api", purpose="HTTP endpoints", files=["src/api/routes.py"]),
                "domain": LayerInfo(name="domain", purpose="Business logic", files=["src/auth/service.py"]),
            },
        )

        extractor = MetadataExtractor(synthesis_map=synthesis_map)
        layer = extractor.get_layer_for_file("src/auth/service.py")

        assert layer == "domain"

    def test_extracts_symbols_from_analysis(self):
        """Gets symbols for source file from analysis data."""
        analysis_symbols = [
            {"name": "authenticate", "type": "function", "file": "src/auth/service.py"},
            {"name": "User", "type": "class", "file": "src/auth/service.py"},
            {"name": "other_func", "type": "function", "file": "src/other.py"},
        ]

        extractor = MetadataExtractor(symbols=analysis_symbols)
        symbols = extractor.get_symbols_for_file("src/auth/service.py")

        assert "authenticate" in symbols
        assert "User" in symbols
        assert "other_func" not in symbols

    def test_filters_symbols_to_chunk_content(self):
        """Only includes symbols that appear in chunk text."""
        analysis_symbols = [
            {"name": "authenticate", "type": "function", "file": "src/auth/service.py"},
            {"name": "User", "type": "class", "file": "src/auth/service.py"},
            {"name": "validate", "type": "function", "file": "src/auth/service.py"},
        ]

        extractor = MetadataExtractor(symbols=analysis_symbols)
        chunk_content = "The authenticate function handles login."
        symbols = extractor.get_symbols_in_content("src/auth/service.py", chunk_content)

        assert "authenticate" in symbols
        assert "User" not in symbols  # Not mentioned in content
        assert "validate" not in symbols

    def test_extracts_imports_from_analysis(self):
        """Gets imports for source file."""
        file_imports = {
            "src/auth/service.py": ["bcrypt", "src/models/user.py"],
            "src/other.py": ["requests"],
        }

        extractor = MetadataExtractor(file_imports=file_imports)
        imports = extractor.get_imports_for_file("src/auth/service.py")

        assert "bcrypt" in imports
        assert "src/models/user.py" in imports
        assert "requests" not in imports

    def test_extracts_entry_points(self):
        """Gets entry points for source file."""
        synthesis_map = SynthesisMap(
            entry_points=[
                EntryPointInfo(name="login", entry_type="api_route", file="src/auth/routes.py", description="/login"),
                EntryPointInfo(name="logout", entry_type="api_route", file="src/auth/routes.py", description="/logout"),
                EntryPointInfo(name="health", entry_type="api_route", file="src/health.py", description="/health"),
            ],
        )

        extractor = MetadataExtractor(synthesis_map=synthesis_map)
        entry_points = extractor.get_entry_points_for_file("src/auth/routes.py")

        assert "POST /login" in entry_points or "login" in entry_points
        assert len(entry_points) == 2
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/poecurt/projects/oya/.worktrees/rag-indexing/backend && source .venv/bin/activate && pytest tests/test_metadata_extractor.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'oya.indexing.metadata'`

**Step 3: Write minimal implementation**

Create `backend/src/oya/indexing/metadata.py`:

```python
"""Metadata extraction for wiki chunks."""

from typing import Any

from oya.generation.summaries import SynthesisMap


class MetadataExtractor:
    """Extracts metadata for wiki chunks from analysis data.

    Uses existing parsed data (SynthesisMap, symbols, imports) to enrich
    chunks with architectural context, code references, and entry points.
    """

    def __init__(
        self,
        synthesis_map: SynthesisMap | None = None,
        symbols: list[dict[str, Any]] | None = None,
        file_imports: dict[str, list[str]] | None = None,
    ) -> None:
        """Initialize metadata extractor.

        Args:
            synthesis_map: SynthesisMap with layers and entry points.
            symbols: List of parsed symbols from analysis.
            file_imports: Mapping of file paths to their imports.
        """
        self._synthesis_map = synthesis_map
        self._symbols = symbols or []
        self._file_imports = file_imports or {}

        # Build file-to-layer index
        self._file_to_layer: dict[str, str] = {}
        if synthesis_map:
            for layer_name, layer_info in synthesis_map.layers.items():
                for file_path in layer_info.files:
                    self._file_to_layer[file_path] = layer_name

        # Build file-to-symbols index
        self._file_to_symbols: dict[str, list[str]] = {}
        for sym in self._symbols:
            file_path = sym.get("file", "")
            name = sym.get("name", "")
            if file_path and name:
                if file_path not in self._file_to_symbols:
                    self._file_to_symbols[file_path] = []
                self._file_to_symbols[file_path].append(name)

    def get_layer_for_file(self, source_file: str) -> str:
        """Get architectural layer for a source file.

        Args:
            source_file: Source file path.

        Returns:
            Layer name or empty string if not found.
        """
        return self._file_to_layer.get(source_file, "")

    def get_symbols_for_file(self, source_file: str) -> list[str]:
        """Get all symbols defined in a source file.

        Args:
            source_file: Source file path.

        Returns:
            List of symbol names.
        """
        return self._file_to_symbols.get(source_file, [])

    def get_symbols_in_content(self, source_file: str, content: str) -> list[str]:
        """Get symbols from a file that appear in the given content.

        Args:
            source_file: Source file path.
            content: Chunk content to search.

        Returns:
            List of symbol names found in content.
        """
        file_symbols = self.get_symbols_for_file(source_file)
        return [sym for sym in file_symbols if sym in content]

    def get_imports_for_file(self, source_file: str) -> list[str]:
        """Get imports for a source file.

        Args:
            source_file: Source file path.

        Returns:
            List of import paths/modules.
        """
        return self._file_imports.get(source_file, [])

    def get_entry_points_for_file(self, source_file: str) -> list[str]:
        """Get entry points defined in a source file.

        Args:
            source_file: Source file path.

        Returns:
            List of entry point descriptions.
        """
        if not self._synthesis_map or not self._synthesis_map.entry_points:
            return []

        entry_points: list[str] = []
        for ep in self._synthesis_map.entry_points:
            if ep.file == source_file:
                # Format as "TYPE description" or just name
                if ep.description:
                    entry_points.append(f"{ep.entry_type.upper()} {ep.description}")
                else:
                    entry_points.append(ep.name)

        return entry_points

    def extract_for_chunk(
        self,
        source_file: str,
        chunk_content: str,
    ) -> dict[str, Any]:
        """Extract all metadata for a chunk.

        Args:
            source_file: Source file path being documented.
            chunk_content: Content of the chunk.

        Returns:
            Dictionary with layer, symbols, imports, entry_points.
        """
        return {
            "layer": self.get_layer_for_file(source_file),
            "symbols": self.get_symbols_in_content(source_file, chunk_content),
            "imports": self.get_imports_for_file(source_file),
            "entry_points": self.get_entry_points_for_file(source_file),
        }
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/poecurt/projects/oya/.worktrees/rag-indexing/backend && source .venv/bin/activate && pytest tests/test_metadata_extractor.py -v`

Expected: PASS

**Step 5: Commit**

```bash
cd /Users/poecurt/projects/oya/.worktrees/rag-indexing && git add backend/src/oya/indexing/metadata.py backend/tests/test_metadata_extractor.py && git commit -m "feat(indexing): add MetadataExtractor for chunk enrichment"
```

---

## Task 5: Implement RRF Ranker

**Files:**
- Create: `backend/src/oya/qa/ranking.py`
- Test: `backend/tests/test_ranking.py`

**Step 1: Write the failing test**

Create `backend/tests/test_ranking.py`:

```python
"""Tests for search result ranking."""

import pytest

from oya.qa.ranking import RRFRanker


class TestRRFRanker:
    """Tests for Reciprocal Rank Fusion ranker."""

    def test_combines_rankings_with_rrf(self):
        """Documents in both lists get higher scores."""
        ranker = RRFRanker(k=60)

        semantic_results = [
            {"id": "doc_a", "content": "A"},
            {"id": "doc_b", "content": "B"},
            {"id": "doc_c", "content": "C"},
        ]
        fts_results = [
            {"id": "doc_b", "content": "B"},
            {"id": "doc_a", "content": "A"},
            {"id": "doc_d", "content": "D"},
        ]

        merged = ranker.merge(semantic_results, fts_results)

        # doc_a and doc_b should be top (in both lists)
        top_ids = [r["id"] for r in merged[:2]]
        assert "doc_a" in top_ids
        assert "doc_b" in top_ids

    def test_handles_disjoint_results(self):
        """Works when lists have no overlap."""
        ranker = RRFRanker(k=60)

        semantic_results = [{"id": "doc_a", "content": "A"}]
        fts_results = [{"id": "doc_b", "content": "B"}]

        merged = ranker.merge(semantic_results, fts_results)

        assert len(merged) == 2
        ids = {r["id"] for r in merged}
        assert ids == {"doc_a", "doc_b"}

    def test_handles_empty_lists(self):
        """Works with empty result lists."""
        ranker = RRFRanker(k=60)

        merged = ranker.merge([], [{"id": "doc_a", "content": "A"}])
        assert len(merged) == 1

        merged = ranker.merge([{"id": "doc_a", "content": "A"}], [])
        assert len(merged) == 1

        merged = ranker.merge([], [])
        assert len(merged) == 0

    def test_preserves_document_fields(self):
        """Merged results contain all original fields."""
        ranker = RRFRanker(k=60)

        semantic_results = [
            {"id": "doc_a", "content": "A", "path": "/a", "title": "Doc A", "type": "file"},
        ]
        fts_results = []

        merged = ranker.merge(semantic_results, fts_results)

        assert merged[0]["path"] == "/a"
        assert merged[0]["title"] == "Doc A"
        assert merged[0]["type"] == "file"

    def test_adds_rrf_score(self):
        """Merged results include RRF score."""
        ranker = RRFRanker(k=60)

        semantic_results = [{"id": "doc_a", "content": "A"}]
        fts_results = [{"id": "doc_a", "content": "A"}]

        merged = ranker.merge(semantic_results, fts_results)

        assert "rrf_score" in merged[0]
        assert merged[0]["rrf_score"] > 0
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/poecurt/projects/oya/.worktrees/rag-indexing/backend && source .venv/bin/activate && pytest tests/test_ranking.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'oya.qa.ranking'`

**Step 3: Write minimal implementation**

Create `backend/src/oya/qa/ranking.py`:

```python
"""Search result ranking with Reciprocal Rank Fusion."""

from collections import defaultdict
from typing import Any


class RRFRanker:
    """Combines semantic and full-text search results using RRF.

    Reciprocal Rank Fusion scores documents based on their ranks in
    multiple result lists. Documents appearing in both lists get
    boosted scores.

    RRF_score(doc) = sum(1 / (k + rank_i)) for each list i
    """

    def __init__(self, k: int = 60, missing_rank: int = 1000) -> None:
        """Initialize RRF ranker.

        Args:
            k: Ranking constant (default 60, standard for RRF).
            missing_rank: Rank assigned to documents not in a list.
        """
        self._k = k
        self._missing_rank = missing_rank

    def merge(
        self,
        semantic_results: list[dict[str, Any]],
        fts_results: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Merge semantic and FTS results using RRF scoring.

        Args:
            semantic_results: Results from semantic/vector search.
            fts_results: Results from full-text search.

        Returns:
            Merged results sorted by RRF score (highest first).
        """
        # Build rank maps
        semantic_ranks: dict[str, int] = {}
        for rank, doc in enumerate(semantic_results):
            doc_id = doc.get("id", "")
            if doc_id:
                semantic_ranks[doc_id] = rank

        fts_ranks: dict[str, int] = {}
        for rank, doc in enumerate(fts_results):
            doc_id = doc.get("id", "")
            if doc_id:
                fts_ranks[doc_id] = rank

        # Build document lookup (prefer semantic version, fall back to FTS)
        docs_by_id: dict[str, dict[str, Any]] = {}
        for doc in fts_results:
            doc_id = doc.get("id", "")
            if doc_id:
                docs_by_id[doc_id] = doc
        for doc in semantic_results:
            doc_id = doc.get("id", "")
            if doc_id:
                docs_by_id[doc_id] = doc

        # Calculate RRF scores
        all_ids = set(semantic_ranks.keys()) | set(fts_ranks.keys())
        scores: dict[str, float] = {}

        for doc_id in all_ids:
            sem_rank = semantic_ranks.get(doc_id, self._missing_rank)
            fts_rank = fts_ranks.get(doc_id, self._missing_rank)

            rrf_score = 1 / (self._k + sem_rank + 1) + 1 / (self._k + fts_rank + 1)
            scores[doc_id] = rrf_score

        # Sort by score and build result list
        sorted_ids = sorted(scores.keys(), key=lambda x: -scores[x])

        results: list[dict[str, Any]] = []
        for doc_id in sorted_ids:
            doc = docs_by_id.get(doc_id, {})
            if doc:
                result = dict(doc)
                result["rrf_score"] = scores[doc_id]
                results.append(result)

        return results
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/poecurt/projects/oya/.worktrees/rag-indexing/backend && source .venv/bin/activate && pytest tests/test_ranking.py -v`

Expected: PASS

**Step 5: Commit**

```bash
cd /Users/poecurt/projects/oya/.worktrees/rag-indexing && git add backend/src/oya/qa/ranking.py backend/tests/test_ranking.py && git commit -m "feat(qa): add RRF ranker for hybrid search"
```

---

## Task 6: Update FTS Schema

**Files:**
- Modify: `backend/src/oya/db/migrations.py`
- Test: `backend/tests/test_migrations.py` (if exists, otherwise manual verification)

**Step 1: Check existing migration**

Run: `cd /Users/poecurt/projects/oya/.worktrees/rag-indexing/backend && grep -n "fts_content" src/oya/db/migrations.py`

Review the current FTS table definition.

**Step 2: Update migration to add chunk columns**

Modify the FTS table creation in `backend/src/oya/db/migrations.py`. Find the `CREATE VIRTUAL TABLE fts_content` statement and update it:

```python
# Old
CREATE VIRTUAL TABLE IF NOT EXISTS fts_content USING fts5(
    content,
    title,
    path UNINDEXED,
    type UNINDEXED
);

# New
CREATE VIRTUAL TABLE IF NOT EXISTS fts_content USING fts5(
    content,
    title,
    path UNINDEXED,
    type UNINDEXED,
    section_header,
    chunk_id UNINDEXED,
    chunk_index UNINDEXED
);
```

**Step 3: Run tests to verify no regressions**

Run: `cd /Users/poecurt/projects/oya/.worktrees/rag-indexing/backend && source .venv/bin/activate && pytest tests/ -k "migration or db" -v`

**Step 4: Commit**

```bash
cd /Users/poecurt/projects/oya/.worktrees/rag-indexing && git add backend/src/oya/db/migrations.py && git commit -m "feat(db): add chunk columns to FTS schema"
```

---

## Task 7: Update IndexingService to Use Chunking

**Files:**
- Modify: `backend/src/oya/indexing/service.py`
- Test: `backend/tests/test_indexing.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_indexing.py`:

```python
@pytest.mark.asyncio
async def test_indexes_chunks_not_whole_pages(tmp_path):
    """IndexingService creates chunks from wiki pages."""
    # Setup wiki with a page that has multiple sections
    wiki_path = tmp_path / ".oyawiki"
    wiki_path.mkdir()
    files_dir = wiki_path / "files"
    files_dir.mkdir()

    page_content = """# src/auth.py

## Overview

Handles authentication.

## Public API

Exports authenticate() function.
"""
    (files_dir / "src-auth.md").write_text(page_content)

    # Create mock dependencies
    mock_vectorstore = MagicMock()
    mock_db = MagicMock()
    mock_db.execute = MagicMock()
    mock_db.commit = MagicMock()

    service = IndexingService(
        vectorstore=mock_vectorstore,
        db=mock_db,
        wiki_path=wiki_path,
    )

    count = await service.index_wiki_pages()

    # Should have indexed multiple chunks, not just one page
    add_calls = mock_vectorstore.add_documents.call_args
    ids = add_calls.kwargs.get("ids", add_calls.args[0] if add_calls.args else [])

    assert len(ids) >= 2  # At least 2 sections
    assert any("overview" in id.lower() for id in ids)
    assert any("public" in id.lower() or "api" in id.lower() for id in ids)
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/poecurt/projects/oya/.worktrees/rag-indexing/backend && source .venv/bin/activate && pytest tests/test_indexing.py::test_indexes_chunks_not_whole_pages -v`

Expected: FAIL (currently indexes whole pages)

**Step 3: Update IndexingService implementation**

Modify `backend/src/oya/indexing/service.py` to use ChunkingService:

1. Import ChunkingService and MetadataExtractor
2. Initialize them in `__init__`
3. Update `index_wiki_pages` to:
   - Parse each page with ChunkingService
   - Extract metadata with MetadataExtractor
   - Index chunks instead of whole pages

Key changes to `index_wiki_pages`:

```python
from oya.indexing.chunking import ChunkingService, Chunk
from oya.indexing.metadata import MetadataExtractor

# In __init__, add:
self._chunking_service = ChunkingService()
self._metadata_extractor: MetadataExtractor | None = None

# In index_wiki_pages, add parameter:
async def index_wiki_pages(
    self,
    embedding_provider: str | None = None,
    embedding_model: str | None = None,
    progress_callback: IndexingProgressCallback | None = None,
    synthesis_map: SynthesisMap | None = None,
    analysis_symbols: list[dict] | None = None,
    file_imports: dict[str, list[str]] | None = None,
) -> int:
    # Initialize metadata extractor if we have analysis data
    if synthesis_map or analysis_symbols or file_imports:
        self._metadata_extractor = MetadataExtractor(
            synthesis_map=synthesis_map,
            symbols=analysis_symbols,
            file_imports=file_imports,
        )

    # ... rest of method uses chunking
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/poecurt/projects/oya/.worktrees/rag-indexing/backend && source .venv/bin/activate && pytest tests/test_indexing.py::test_indexes_chunks_not_whole_pages -v`

Expected: PASS

**Step 5: Run full indexing tests**

Run: `cd /Users/poecurt/projects/oya/.worktrees/rag-indexing/backend && source .venv/bin/activate && pytest tests/test_indexing.py -v`

Expected: All tests PASS

**Step 6: Commit**

```bash
cd /Users/poecurt/projects/oya/.worktrees/rag-indexing && git add backend/src/oya/indexing/service.py backend/tests/test_indexing.py && git commit -m "feat(indexing): use ChunkingService for semantic chunking"
```

---

## Task 8: Update QAService to Use RRF Ranker

**Files:**
- Modify: `backend/src/oya/qa/service.py`
- Test: `backend/tests/test_qa_api.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_qa_api.py`:

```python
@pytest.mark.asyncio
async def test_search_uses_rrf_ranking():
    """Search results are ranked using RRF, not simple deduplication."""
    # Setup mocks
    mock_vectorstore = MagicMock()
    mock_vectorstore.query.return_value = {
        "ids": [["chunk_a", "chunk_b", "chunk_c"]],
        "documents": [["Content A", "Content B", "Content C"]],
        "metadatas": [[
            {"path": "a.md", "title": "A", "type": "file"},
            {"path": "b.md", "title": "B", "type": "file"},
            {"path": "c.md", "title": "C", "type": "file"},
        ]],
        "distances": [[0.1, 0.3, 0.5]],
    }

    mock_db = MagicMock()
    # FTS returns chunk_b first, then chunk_a
    mock_db.execute.return_value.fetchall.return_value = [
        {"content": "Content B", "title": "B", "path": "b.md", "type": "file", "score": -10},
        {"content": "Content A", "title": "A", "path": "a.md", "type": "file", "score": -5},
    ]

    mock_llm = AsyncMock()

    service = QAService(vectorstore=mock_vectorstore, db=mock_db, llm=mock_llm)
    results, _, _ = await service.search("test query")

    # With RRF, documents in both lists should rank higher
    # chunk_a: rank 0 in semantic, rank 1 in FTS = high RRF
    # chunk_b: rank 1 in semantic, rank 0 in FTS = high RRF
    # chunk_c: rank 2 in semantic, not in FTS = lower RRF
    top_ids = [r["id"] for r in results[:2]]
    assert "chunk_a" in top_ids or "chunk_b" in top_ids
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/poecurt/projects/oya/.worktrees/rag-indexing/backend && source .venv/bin/activate && pytest tests/test_qa_api.py::test_search_uses_rrf_ranking -v`

Expected: FAIL (current implementation doesn't use RRF)

**Step 3: Update QAService to use RRFRanker**

Modify `backend/src/oya/qa/service.py`:

1. Import RRFRanker
2. Initialize in `__init__`
3. Replace dedup-based merging in `search()` with RRF

```python
from oya.qa.ranking import RRFRanker

class QAService:
    def __init__(self, ...):
        ...
        self._ranker = RRFRanker(k=60)

    async def search(self, query: str, limit: int = 10):
        # ... get semantic_results and fts_results ...

        # Replace deduplication with RRF
        merged = self._ranker.merge(semantic_results, fts_results)

        # Sort by type priority, then RRF score
        merged.sort(key=lambda r: (TYPE_PRIORITY.get(r.get("type"), 3), -r.get("rrf_score", 0)))

        return merged[:limit], semantic_ok, fts_ok
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/poecurt/projects/oya/.worktrees/rag-indexing/backend && source .venv/bin/activate && pytest tests/test_qa_api.py::test_search_uses_rrf_ranking -v`

Expected: PASS

**Step 5: Run full QA tests**

Run: `cd /Users/poecurt/projects/oya/.worktrees/rag-indexing/backend && source .venv/bin/activate && pytest tests/test_qa_api.py -v`

Expected: All tests PASS

**Step 6: Commit**

```bash
cd /Users/poecurt/projects/oya/.worktrees/rag-indexing && git add backend/src/oya/qa/service.py backend/tests/test_qa_api.py && git commit -m "feat(qa): use RRF ranker for hybrid search"
```

---

## Task 9: Update Orchestrator to Pass Analysis Data to Indexing

**Files:**
- Modify: `backend/src/oya/api/routers/repos.py`
- Test: Integration test

**Step 1: Find where indexing is called**

Run: `cd /Users/poecurt/projects/oya/.worktrees/rag-indexing/backend && grep -n "index_wiki_pages" src/oya/api/routers/repos.py`

**Step 2: Update to pass synthesis_map and analysis data**

The `_run_generation` function should pass the analysis data to `index_wiki_pages`:

```python
# After synthesis phase completes, pass data to indexing
indexed_count = await indexing_service.index_wiki_pages(
    embedding_provider=provider,
    embedding_model=model,
    progress_callback=progress_callback,
    synthesis_map=synthesis_map,
    analysis_symbols=analysis.get("symbols"),
    file_imports=analysis.get("file_imports"),
)
```

**Step 3: Run integration tests**

Run: `cd /Users/poecurt/projects/oya/.worktrees/rag-indexing/backend && source .venv/bin/activate && pytest tests/test_repos_api.py -v`

**Step 4: Commit**

```bash
cd /Users/poecurt/projects/oya/.worktrees/rag-indexing && git add backend/src/oya/api/routers/repos.py && git commit -m "feat(api): pass analysis data to indexing service"
```

---

## Task 10: End-to-End Integration Test

**Files:**
- Create: `backend/tests/test_rag_integration.py`

**Step 1: Write integration test**

Create `backend/tests/test_rag_integration.py`:

```python
"""End-to-end tests for RAG indexing improvements."""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from oya.indexing.service import IndexingService
from oya.indexing.chunking import ChunkingService
from oya.qa.service import QAService
from oya.generation.summaries import SynthesisMap, LayerInfo, EntryPointInfo


class TestRAGIntegration:
    """Integration tests for chunking → indexing → search flow."""

    @pytest.fixture
    def sample_wiki(self, tmp_path):
        """Create sample wiki with multiple pages."""
        wiki_path = tmp_path / ".oyawiki"
        wiki_path.mkdir()

        # File page with sections
        files_dir = wiki_path / "files"
        files_dir.mkdir()
        (files_dir / "src-auth-service.md").write_text("""# src/auth/service.py

## Overview

The authentication service handles user login and session management.

## Public API

### authenticate(username, password)

Validates credentials and returns a session token.

### logout(token)

Invalidates the given session token.

## Internal Details

Uses bcrypt for password hashing. Sessions stored in Redis.
""")

        # Workflow page
        workflows_dir = wiki_path / "workflows"
        workflows_dir.mkdir()
        (workflows_dir / "user-login.md").write_text("""# User Login Workflow

## Overview

Handles the complete user login flow.

## Entry Points

- POST /auth/login
- POST /auth/logout

## Flow

1. User submits credentials
2. Service validates against database
3. Session token generated and returned
""")

        return wiki_path

    @pytest.fixture
    def synthesis_map(self):
        """Create sample synthesis map."""
        return SynthesisMap(
            layers={
                "api": LayerInfo(name="api", purpose="HTTP endpoints", files=["src/api/routes.py"]),
                "domain": LayerInfo(name="domain", purpose="Business logic", files=["src/auth/service.py"]),
            },
            entry_points=[
                EntryPointInfo(name="login", entry_type="api_route", file="src/api/routes.py", description="/auth/login"),
            ],
        )

    @pytest.mark.asyncio
    async def test_chunking_creates_section_chunks(self, sample_wiki):
        """Wiki pages are chunked by section."""
        service = ChunkingService()

        content = (sample_wiki / "files" / "src-auth-service.md").read_text()
        chunks = service.chunk_document(
            content=content,
            document_path="files/src-auth-service.md",
            document_title="src/auth/service.py",
            page_type="file",
        )

        # Should have multiple chunks
        assert len(chunks) >= 3

        # Check sections are captured
        headers = [c.section_header for c in chunks]
        assert "Overview" in headers
        assert "Public API" in headers
        assert "Internal Details" in headers

        # Check context prefix
        assert all("[Document:" in c.content for c in chunks)

    @pytest.mark.asyncio
    async def test_search_finds_relevant_chunks(self, sample_wiki, synthesis_map, tmp_path):
        """Search returns relevant chunks, not whole pages."""
        # Setup real vector store and DB mocks
        mock_vectorstore = MagicMock()
        mock_db = MagicMock()
        mock_db.execute = MagicMock(return_value=MagicMock(fetchall=MagicMock(return_value=[])))
        mock_db.commit = MagicMock()

        # Index the wiki
        indexing_service = IndexingService(
            vectorstore=mock_vectorstore,
            db=mock_db,
            wiki_path=sample_wiki,
        )

        await indexing_service.index_wiki_pages(synthesis_map=synthesis_map)

        # Verify chunks were indexed
        add_call = mock_vectorstore.add_documents.call_args
        indexed_ids = add_call.kwargs.get("ids", [])

        # Should have multiple chunks per page
        assert len(indexed_ids) >= 4  # At least 2 pages × 2 sections each

        # Chunks should be section-based, not whole pages
        assert any("overview" in id.lower() for id in indexed_ids)
        assert any("public" in id.lower() or "api" in id.lower() for id in indexed_ids)
```

**Step 2: Run integration test**

Run: `cd /Users/poecurt/projects/oya/.worktrees/rag-indexing/backend && source .venv/bin/activate && pytest tests/test_rag_integration.py -v`

Expected: PASS

**Step 3: Run full test suite**

Run: `cd /Users/poecurt/projects/oya/.worktrees/rag-indexing/backend && source .venv/bin/activate && pytest`

Expected: All tests PASS

**Step 4: Commit**

```bash
cd /Users/poecurt/projects/oya/.worktrees/rag-indexing && git add backend/tests/test_rag_integration.py && git commit -m "test(rag): add end-to-end integration tests"
```

---

## Summary

| Task | Description | Files |
|------|-------------|-------|
| 1 | Chunk data model | chunking.py, test_chunking.py |
| 2 | Markdown section parser | chunking.py, test_chunking.py |
| 3 | ChunkingService | chunking.py, test_chunking.py |
| 4 | MetadataExtractor | metadata.py, test_metadata_extractor.py |
| 5 | RRF Ranker | ranking.py, test_ranking.py |
| 6 | FTS schema update | migrations.py |
| 7 | Update IndexingService | service.py, test_indexing.py |
| 8 | Update QAService | service.py, test_qa_api.py |
| 9 | Update orchestrator | repos.py |
| 10 | Integration tests | test_rag_integration.py |

**Total commits:** 10
**Estimated test coverage:** All new code tested via TDD
