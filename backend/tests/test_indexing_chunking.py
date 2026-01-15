"""Tests for wiki content chunking."""

from oya.indexing.chunking import Chunk, ChunkMetadata, parse_markdown_sections


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
