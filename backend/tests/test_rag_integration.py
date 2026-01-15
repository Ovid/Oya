"""End-to-end tests for RAG indexing improvements."""

import pytest

from oya.db.connection import Database
from oya.indexing.service import IndexingService
from oya.indexing.chunking import ChunkingService
from oya.generation.summaries import SynthesisMap, LayerInfo, EntryPointInfo
from oya.vectorstore.store import VectorStore


@pytest.fixture
def temp_db(tmp_path):
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
def temp_vectorstore(tmp_path):
    """Create a temporary vector store."""
    index_path = tmp_path / "index"
    index_path.mkdir()
    return VectorStore(index_path)


class TestRAGIntegration:
    """Integration tests for chunking -> indexing -> search flow."""

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
                "api": LayerInfo(
                    name="api", purpose="HTTP endpoints", files=["src/api/routes.py"]
                ),
                "domain": LayerInfo(
                    name="domain", purpose="Business logic", files=["src/auth/service.py"]
                ),
            },
            entry_points=[
                EntryPointInfo(
                    name="login",
                    entry_type="api_route",
                    file="src/api/routes.py",
                    description="/auth/login",
                ),
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

        # Should have multiple chunks (H2 and H3 headers create sections)
        assert len(chunks) >= 3

        # Check sections are captured (including H3 sub-sections)
        headers = [c.section_header for c in chunks]
        assert "Overview" in headers
        # H3 subsections under Public API are also captured
        assert "authenticate(username, password)" in headers or "Public API" in headers
        assert "Internal Details" in headers

        # Check context prefix is added to all chunks
        assert all("[Document:" in c.content for c in chunks)

    @pytest.mark.asyncio
    async def test_indexing_stores_chunks_with_metadata(
        self, sample_wiki, synthesis_map, temp_db, temp_vectorstore
    ):
        """IndexingService stores chunks with full metadata."""
        indexing_service = IndexingService(
            vectorstore=temp_vectorstore,
            db=temp_db,
            wiki_path=sample_wiki,
        )

        await indexing_service.index_wiki_pages(synthesis_map=synthesis_map)

        # Query the vector store to see what was indexed
        results = temp_vectorstore.query("authentication", n_results=20)
        indexed_ids = results.get("ids", [[]])[0]

        # Should have multiple chunks (at least 2 pages with 2+ sections each)
        assert len(indexed_ids) >= 4

        # Chunks should be section-based, not whole pages
        assert any("overview" in id.lower() for id in indexed_ids)

    @pytest.mark.asyncio
    async def test_full_pipeline_chunking_to_search(
        self, sample_wiki, temp_db, temp_vectorstore
    ):
        """Test full pipeline from wiki content to searchable chunks."""
        # Index the wiki
        indexing_service = IndexingService(
            vectorstore=temp_vectorstore,
            db=temp_db,
            wiki_path=sample_wiki,
        )

        indexed_count = await indexing_service.index_wiki_pages()
        assert indexed_count == 2  # Two wiki pages

        # Search for specific content - should find relevant section
        results = temp_vectorstore.query("bcrypt password hashing", n_results=5)
        docs = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]

        # Should find the Internal Details section
        assert len(docs) > 0
        assert any("bcrypt" in doc.lower() for doc in docs)

        # Metadata should include section information
        assert any(m.get("section_header") == "Internal Details" for m in metadatas)

    @pytest.mark.asyncio
    async def test_fts_search_finds_chunked_content(
        self, sample_wiki, temp_db, temp_vectorstore
    ):
        """FTS search returns results from chunked content."""
        indexing_service = IndexingService(
            vectorstore=temp_vectorstore,
            db=temp_db,
            wiki_path=sample_wiki,
        )

        await indexing_service.index_wiki_pages()

        # Query FTS
        cursor = temp_db.execute(
            "SELECT content, title, path, type, section_header, chunk_id "
            "FROM fts_content WHERE fts_content MATCH ?",
            ("credentials",),
        )
        results = cursor.fetchall()

        assert len(results) > 0
        # Should find content mentioning credentials
        assert any("credentials" in r["content"].lower() for r in results)
        # Should have section headers
        assert any(r["section_header"] for r in results)


class TestGenerationResultFlow:
    """Tests for GenerationResult data flow from orchestrator to indexing."""

    def test_generation_result_contains_analysis_data(self):
        """GenerationResult contains synthesis_map and analysis data."""
        from oya.generation.orchestrator import GenerationResult

        result = GenerationResult(
            job_id="test-job",
            synthesis_map=SynthesisMap(layers={}),
            analysis_symbols=[
                {"name": "test_func", "type": "function", "file": "test.py"}
            ],
            file_imports={"test.py": ["os", "sys"]},
        )

        assert result.job_id == "test-job"
        assert result.synthesis_map is not None
        assert len(result.analysis_symbols) == 1
        assert "test.py" in result.file_imports

    def test_synthesis_map_provides_layer_info(self):
        """SynthesisMap provides layer information for metadata enrichment."""
        synthesis_map = SynthesisMap(
            layers={
                "api": LayerInfo(
                    name="api",
                    purpose="HTTP endpoints",
                    files=["src/api/routes.py", "src/api/handlers.py"],
                ),
                "domain": LayerInfo(
                    name="domain",
                    purpose="Business logic",
                    files=["src/auth/service.py"],
                ),
            },
            entry_points=[
                EntryPointInfo(
                    name="main",
                    entry_type="cli_command",
                    file="src/main.py",
                    description="Application entry point",
                ),
            ],
        )

        # Check layer lookup works
        api_files = synthesis_map.layers["api"].files
        assert "src/api/routes.py" in api_files
        assert "src/api/handlers.py" in api_files

        domain_files = synthesis_map.layers["domain"].files
        assert "src/auth/service.py" in domain_files

        # Check entry points
        assert len(synthesis_map.entry_points) == 1
        assert synthesis_map.entry_points[0].name == "main"


class TestMetadataEnrichment:
    """Tests for metadata enrichment during indexing."""

    @pytest.mark.asyncio
    async def test_indexing_enriches_metadata_from_synthesis_map(
        self, temp_db, temp_vectorstore, tmp_path
    ):
        """Indexing enriches chunks with layer info from synthesis map."""
        # Create wiki with a file page
        wiki_path = tmp_path / ".oyawiki"
        wiki_path.mkdir()
        files_dir = wiki_path / "files"
        files_dir.mkdir()
        (files_dir / "src-auth-service-py.md").write_text("""# src/auth/service.py

## Overview

Authentication service implementation.
""")

        # Create synthesis map with layer info
        synthesis_map = SynthesisMap(
            layers={
                "domain": LayerInfo(
                    name="domain",
                    purpose="Business logic",
                    files=["src/auth/service.py"],
                ),
            },
        )

        indexing_service = IndexingService(
            vectorstore=temp_vectorstore,
            db=temp_db,
            wiki_path=wiki_path,
        )

        await indexing_service.index_wiki_pages(synthesis_map=synthesis_map)

        # Query and check metadata includes layer
        results = temp_vectorstore.query("authentication", n_results=5)
        metadatas = results.get("metadatas", [[]])[0]

        # Should have at least one result
        assert len(metadatas) > 0
        # Layer should be populated from synthesis map
        assert any(m.get("layer") == "domain" for m in metadatas)
