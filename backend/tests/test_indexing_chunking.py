"""Tests for wiki content chunking."""

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
