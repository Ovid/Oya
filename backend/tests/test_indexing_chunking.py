"""Tests for wiki content chunking."""

from oya.indexing.chunking import (
    Chunk,
    ChunkingService,
    ChunkMetadata,
    parse_markdown_sections,
)


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
