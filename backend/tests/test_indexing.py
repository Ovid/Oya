# backend/tests/test_indexing.py
"""Tests for content indexing into vector store and FTS."""

import pytest

from oya.db.connection import Database
from oya.vectorstore.store import VectorStore


class TestContentIndexing:
    """Tests for indexing wiki content into search stores.

    The indexing service should:
    1. Index wiki pages into ChromaDB for semantic search
    2. Index wiki pages into FTS5 for full-text search
    3. Include metadata (path, title, type) for citation extraction
    """

    @pytest.fixture
    def temp_db(self, tmp_path):
        """Create a temporary database with FTS table."""
        db_path = tmp_path / "test.db"
        db = Database(db_path)
        # Create FTS table matching production schema
        db.executescript("""
            CREATE VIRTUAL TABLE IF NOT EXISTS fts_content USING fts5(
                content,
                title,
                path UNINDEXED,
                type UNINDEXED,
                section_header,
                chunk_id UNINDEXED,
                chunk_index UNINDEXED,
                content_rowid UNINDEXED
            );
        """)
        db.commit()
        return db

    @pytest.fixture
    def temp_vectorstore(self, tmp_path):
        """Create a temporary vector store."""
        index_path = tmp_path / "index"
        index_path.mkdir()
        return VectorStore(index_path)

    @pytest.fixture
    def sample_wiki_content(self, tmp_path):
        """Create sample wiki content files."""
        wiki_path = tmp_path / "wiki"
        wiki_path.mkdir()

        # Create overview page
        overview = wiki_path / "overview.md"
        overview.write_text("# Project Overview\n\nThis is a sample project.")

        # Create architecture page
        arch = wiki_path / "architecture.md"
        arch.write_text("# Architecture\n\nThe system uses FastAPI.")

        # Create a file page
        files_dir = wiki_path / "files"
        files_dir.mkdir()
        file_page = files_dir / "src-main-py.md"
        file_page.write_text("# src/main.py\n\nMain entry point for the application.")

        return wiki_path

    @pytest.mark.asyncio
    async def test_index_wiki_pages_to_vectorstore(
        self, temp_vectorstore, temp_db, sample_wiki_content
    ):
        """Wiki pages are indexed into ChromaDB vector store."""
        from oya.indexing.service import IndexingService

        service = IndexingService(
            vectorstore=temp_vectorstore,
            db=temp_db,
            wiki_path=sample_wiki_content,
        )

        # Index all wiki pages
        indexed_count = await service.index_wiki_pages()

        # Should have indexed 3 pages
        assert indexed_count == 3

        # Query should return results
        results = temp_vectorstore.query("FastAPI", n_results=5)
        assert len(results.get("ids", [[]])[0]) > 0

        # Should find architecture page
        docs = results.get("documents", [[]])[0]
        assert any("FastAPI" in doc for doc in docs)

    @pytest.mark.asyncio
    async def test_index_wiki_pages_to_fts(self, temp_vectorstore, temp_db, sample_wiki_content):
        """Wiki pages are indexed into FTS5 for full-text search."""
        from oya.indexing.service import IndexingService

        service = IndexingService(
            vectorstore=temp_vectorstore,
            db=temp_db,
            wiki_path=sample_wiki_content,
        )

        # Index all wiki pages
        await service.index_wiki_pages()

        # Query FTS should return results
        cursor = temp_db.execute(
            "SELECT content, title, path, type FROM fts_content WHERE fts_content MATCH ?",
            ("FastAPI",),
        )
        results = cursor.fetchall()

        assert len(results) > 0
        # Should find architecture page
        assert any("architecture" in r["path"] for r in results)

    @pytest.mark.asyncio
    async def test_index_includes_metadata(self, temp_vectorstore, temp_db, sample_wiki_content):
        """Indexed documents include path, title, and type metadata."""
        from oya.indexing.service import IndexingService

        service = IndexingService(
            vectorstore=temp_vectorstore,
            db=temp_db,
            wiki_path=sample_wiki_content,
        )

        await service.index_wiki_pages()

        # Query vectorstore and check metadata
        results = temp_vectorstore.query("overview", n_results=5)
        metadatas = results.get("metadatas", [[]])[0]

        assert len(metadatas) > 0
        # Should have path, title, type
        overview_meta = next((m for m in metadatas if "overview" in m.get("path", "")), None)
        assert overview_meta is not None
        assert "path" in overview_meta
        assert "title" in overview_meta
        assert "type" in overview_meta

    @pytest.mark.asyncio
    async def test_clear_and_reindex(self, temp_vectorstore, temp_db, sample_wiki_content):
        """Can clear existing index and reindex."""
        from oya.indexing.service import IndexingService

        service = IndexingService(
            vectorstore=temp_vectorstore,
            db=temp_db,
            wiki_path=sample_wiki_content,
        )

        # Index once
        await service.index_wiki_pages()

        # Clear and reindex
        service.clear_index()
        indexed_count = await service.index_wiki_pages()

        # Should still have 3 pages
        assert indexed_count == 3

        # Query should still work
        results = temp_vectorstore.query("project", n_results=5)
        assert len(results.get("ids", [[]])[0]) > 0

    @pytest.mark.asyncio
    async def test_index_extracts_title_from_markdown(
        self, temp_vectorstore, temp_db, sample_wiki_content
    ):
        """Title is extracted from markdown H1 header."""
        from oya.indexing.service import IndexingService

        service = IndexingService(
            vectorstore=temp_vectorstore,
            db=temp_db,
            wiki_path=sample_wiki_content,
        )

        await service.index_wiki_pages()

        # Query and check title
        results = temp_vectorstore.query("overview", n_results=5)
        metadatas = results.get("metadatas", [[]])[0]

        overview_meta = next((m for m in metadatas if "overview" in m.get("path", "")), None)
        assert overview_meta is not None
        assert overview_meta.get("title") == "Project Overview"

    @pytest.mark.asyncio
    async def test_index_determines_page_type(self, temp_vectorstore, temp_db, sample_wiki_content):
        """Page type is determined from path structure."""
        from oya.indexing.service import IndexingService

        service = IndexingService(
            vectorstore=temp_vectorstore,
            db=temp_db,
            wiki_path=sample_wiki_content,
        )

        await service.index_wiki_pages()

        # Query and check types
        results = temp_vectorstore.query("main entry point", n_results=5)
        metadatas = results.get("metadatas", [[]])[0]

        file_meta = next((m for m in metadatas if "src-main-py" in m.get("path", "")), None)
        assert file_meta is not None
        assert file_meta.get("type") == "file"


class TestEmbeddingMetadata:
    """Tests for embedding model metadata tracking."""

    @pytest.fixture
    def temp_db(self, tmp_path):
        """Create a temporary database with FTS table."""
        db_path = tmp_path / "test.db"
        db = Database(db_path)
        # Create FTS table matching production schema
        db.executescript("""
            CREATE VIRTUAL TABLE IF NOT EXISTS fts_content USING fts5(
                content,
                title,
                path UNINDEXED,
                type UNINDEXED,
                section_header,
                chunk_id UNINDEXED,
                chunk_index UNINDEXED,
                content_rowid UNINDEXED
            );
        """)
        db.commit()
        return db

    @pytest.fixture
    def temp_vectorstore(self, tmp_path):
        """Create a temporary vector store."""
        index_path = tmp_path / "index"
        index_path.mkdir()
        return VectorStore(index_path)

    @pytest.fixture
    def sample_wiki_content(self, tmp_path):
        """Create sample wiki content files."""
        wiki_path = tmp_path / "wiki"
        wiki_path.mkdir()
        overview = wiki_path / "overview.md"
        overview.write_text("# Project Overview\n\nThis is a sample project.")
        return wiki_path

    @pytest.mark.asyncio
    async def test_indexing_saves_embedding_metadata(
        self, temp_vectorstore, temp_db, sample_wiki_content, tmp_path
    ):
        """Indexing saves the provider and model used for embeddings."""
        from oya.indexing.service import IndexingService

        meta_path = tmp_path / "meta"
        meta_path.mkdir()

        service = IndexingService(
            vectorstore=temp_vectorstore,
            db=temp_db,
            wiki_path=sample_wiki_content,
            meta_path=meta_path,
        )

        # Index with specific provider/model
        await service.index_wiki_pages(
            embedding_provider="openai",
            embedding_model="text-embedding-3-small",
        )

        # Metadata should be saved
        metadata = service.get_embedding_metadata()
        assert metadata is not None
        assert metadata["provider"] == "openai"
        assert metadata["model"] == "text-embedding-3-small"

    def test_get_embedding_metadata_returns_none_when_not_indexed(
        self, temp_vectorstore, temp_db, tmp_path
    ):
        """Returns None when no indexing has been done."""
        from oya.indexing.service import IndexingService

        wiki_path = tmp_path / "wiki"
        wiki_path.mkdir()
        meta_path = tmp_path / "meta"
        meta_path.mkdir()

        service = IndexingService(
            vectorstore=temp_vectorstore,
            db=temp_db,
            wiki_path=wiki_path,
            meta_path=meta_path,
        )

        metadata = service.get_embedding_metadata()
        assert metadata is None

    @pytest.mark.asyncio
    async def test_clear_index_removes_embedding_metadata(
        self, temp_vectorstore, temp_db, sample_wiki_content, tmp_path
    ):
        """Clearing the index also removes embedding metadata."""
        from oya.indexing.service import IndexingService

        meta_path = tmp_path / "meta"
        meta_path.mkdir()

        service = IndexingService(
            vectorstore=temp_vectorstore,
            db=temp_db,
            wiki_path=sample_wiki_content,
            meta_path=meta_path,
        )

        await service.index_wiki_pages(
            embedding_provider="openai",
            embedding_model="text-embedding-3-small",
        )
        assert service.get_embedding_metadata() is not None

        service.clear_index()
        assert service.get_embedding_metadata() is None


class TestIndexingIntegration:
    """Tests for indexing integration with generation pipeline."""

    @pytest.fixture
    def temp_db(self, tmp_path):
        """Create a temporary database with FTS table."""
        db_path = tmp_path / "test.db"
        db = Database(db_path)
        # Create FTS table matching production schema
        db.executescript("""
            CREATE VIRTUAL TABLE IF NOT EXISTS fts_content USING fts5(
                content,
                title,
                path UNINDEXED,
                type UNINDEXED,
                section_header,
                chunk_id UNINDEXED,
                chunk_index UNINDEXED,
                content_rowid UNINDEXED
            );
        """)
        db.commit()
        return db

    @pytest.fixture
    def temp_vectorstore(self, tmp_path):
        """Create a temporary vector store."""
        index_path = tmp_path / "index"
        index_path.mkdir()
        return VectorStore(index_path)

    @pytest.mark.asyncio
    async def test_run_indexing_after_generation(self, temp_vectorstore, temp_db, tmp_path):
        """Indexing runs after wiki generation completes."""
        from oya.indexing.service import IndexingService

        # Create wiki content as if generation just completed
        wiki_path = tmp_path / "wiki"
        wiki_path.mkdir()

        overview = wiki_path / "overview.md"
        overview.write_text("# My Project\n\nThis is a test project.")

        # Run indexing
        service = IndexingService(
            vectorstore=temp_vectorstore,
            db=temp_db,
            wiki_path=wiki_path,
        )
        indexed = await service.index_wiki_pages()

        assert indexed == 1

        # Verify Q&A can now find content
        results = temp_vectorstore.query("test project", n_results=5)
        assert len(results.get("ids", [[]])[0]) > 0

    @pytest.mark.asyncio
    async def test_reindex_clears_old_content(self, temp_vectorstore, temp_db, tmp_path):
        """Reindexing clears old content before adding new."""
        from oya.indexing.service import IndexingService

        wiki_path = tmp_path / "wiki"
        wiki_path.mkdir()

        # First generation
        overview = wiki_path / "overview.md"
        overview.write_text("# Old Content\n\nThis is old.")

        service = IndexingService(
            vectorstore=temp_vectorstore,
            db=temp_db,
            wiki_path=wiki_path,
        )
        await service.index_wiki_pages()

        # Simulate regeneration with new content
        overview.write_text("# New Content\n\nThis is new.")

        # Clear and reindex
        service.clear_index()
        await service.index_wiki_pages()

        # Should find new content
        results = temp_vectorstore.query("new content", n_results=5)
        docs = results.get("documents", [[]])[0]
        assert any("new" in doc.lower() for doc in docs)

        # Should NOT find old content (it was cleared)
        results = temp_vectorstore.query("old content", n_results=5)
        docs = results.get("documents", [[]])[0]
        # The old content should not be in the results
        assert not any("old" in doc.lower() and "new" not in doc.lower() for doc in docs)


class TestChunkBasedIndexing:
    """Tests for chunk-based indexing using ChunkingService."""

    @pytest.fixture
    def temp_db(self, tmp_path):
        """Create a temporary database with FTS table."""
        db_path = tmp_path / "test.db"
        db = Database(db_path)
        # Create FTS table matching production schema
        db.executescript("""
            CREATE VIRTUAL TABLE IF NOT EXISTS fts_content USING fts5(
                content,
                title,
                path UNINDEXED,
                type UNINDEXED,
                section_header,
                chunk_id UNINDEXED,
                chunk_index UNINDEXED,
                content_rowid UNINDEXED
            );
        """)
        db.commit()
        return db

    @pytest.fixture
    def temp_vectorstore(self, tmp_path):
        """Create a temporary vector store."""
        index_path = tmp_path / "index"
        index_path.mkdir()
        return VectorStore(index_path)

    @pytest.mark.asyncio
    async def test_indexes_chunks_not_whole_pages(self, temp_vectorstore, temp_db, tmp_path):
        """IndexingService creates chunks from wiki pages."""
        from oya.indexing.service import IndexingService

        # Setup wiki with a page that has multiple sections
        wiki_path = tmp_path / ".oyawiki"
        wiki_path.mkdir()
        files_dir = wiki_path / "files"
        files_dir.mkdir()

        page_content = """# src/auth.py

## Overview

Handles user authentication.

## Public API

Exports authenticate() function.
"""
        (files_dir / "src-auth.md").write_text(page_content)

        service = IndexingService(
            vectorstore=temp_vectorstore,
            db=temp_db,
            wiki_path=wiki_path,
        )

        await service.index_wiki_pages()

        # Should have indexed multiple chunks, not just one page
        # Query the vector store to get the indexed documents
        results = temp_vectorstore.query("authenticate", n_results=10)
        ids = results.get("ids", [[]])[0]

        # Should have at least 2 chunks (Overview and Public API sections)
        assert len(ids) >= 2
        # IDs should contain section names
        assert any("overview" in id.lower() for id in ids)
        assert any("public" in id.lower() or "api" in id.lower() for id in ids)

    @pytest.mark.asyncio
    async def test_chunks_include_metadata(self, temp_vectorstore, temp_db, tmp_path):
        """Indexed chunks include section headers and chunk IDs."""
        from oya.indexing.service import IndexingService

        wiki_path = tmp_path / ".oyawiki"
        wiki_path.mkdir()
        files_dir = wiki_path / "files"
        files_dir.mkdir()

        page_content = """# src/main.py

## Overview

Main entry point.

## Dependencies

Uses FastAPI and uvicorn.
"""
        (files_dir / "src-main.md").write_text(page_content)

        service = IndexingService(
            vectorstore=temp_vectorstore,
            db=temp_db,
            wiki_path=wiki_path,
        )

        await service.index_wiki_pages()

        # Query vectorstore and check metadata
        results = temp_vectorstore.query("main entry", n_results=10)
        metadatas = results.get("metadatas", [[]])[0]

        # Should have section_header in metadata
        assert len(metadatas) > 0
        assert any(m.get("section_header") == "Overview" for m in metadatas)

    @pytest.mark.asyncio
    async def test_fts_indexes_chunks_with_section_headers(
        self, temp_vectorstore, temp_db, tmp_path
    ):
        """FTS index includes section headers and chunk metadata."""
        from oya.indexing.service import IndexingService

        wiki_path = tmp_path / ".oyawiki"
        wiki_path.mkdir()
        files_dir = wiki_path / "files"
        files_dir.mkdir()

        page_content = """# src/db.py

## Overview

Database connection handling.

## Connection Pool

Manages connection pooling.
"""
        (files_dir / "src-db.md").write_text(page_content)

        service = IndexingService(
            vectorstore=temp_vectorstore,
            db=temp_db,
            wiki_path=wiki_path,
        )

        await service.index_wiki_pages()

        # Query FTS and check for section headers
        cursor = temp_db.execute(
            "SELECT content, title, path, type, section_header, chunk_id, chunk_index "
            "FROM fts_content WHERE fts_content MATCH ?",
            ("connection",),
        )
        results = cursor.fetchall()

        assert len(results) > 0
        # Should have section_header populated
        assert any(r["section_header"] for r in results)
        # Should have chunk_id populated
        assert any(r["chunk_id"] for r in results)
