"""Indexing service for wiki content into vector store and FTS."""

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Coroutine

from oya.db.connection import Database
from oya.generation.summaries import SynthesisMap
from oya.indexing.chunking import Chunk, ChunkingService, ChunkMetadata
from oya.indexing.metadata import MetadataExtractor
from oya.vectorstore.store import VectorStore


EMBEDDING_METADATA_FILE = "embedding_metadata.json"

# Type alias for progress callback
IndexingProgressCallback = Callable[[int, int, str], Coroutine[Any, Any, None]]


class IndexingService:
    """Service for indexing wiki content into search stores.

    Indexes wiki pages into:
    - ChromaDB for semantic/vector search
    - SQLite FTS5 for full-text keyword search

    Also tracks embedding metadata (provider/model) to detect mismatches.
    """

    def __init__(
        self,
        vectorstore: VectorStore,
        db: Database,
        wiki_path: Path,
        meta_path: Path | None = None,
    ) -> None:
        """Initialize indexing service.

        Args:
            vectorstore: ChromaDB vector store for semantic search.
            db: SQLite database with FTS5 table.
            wiki_path: Path to wiki directory containing markdown files.
            meta_path: Path to metadata directory for storing embedding info.
        """
        self._vectorstore = vectorstore
        self._db = db
        self._wiki_path = Path(wiki_path)
        self._meta_path = Path(meta_path) if meta_path else None
        self._chunking_service = ChunkingService()

    async def index_wiki_pages(
        self,
        embedding_provider: str | None = None,
        embedding_model: str | None = None,
        progress_callback: IndexingProgressCallback | None = None,
        synthesis_map: SynthesisMap | None = None,
        analysis_symbols: list[dict[str, Any]] | None = None,
        file_imports: dict[str, list[str]] | None = None,
    ) -> int:
        """Index all wiki pages into vector store and FTS.

        Args:
            embedding_provider: LLM provider used for embeddings (e.g., 'openai').
            embedding_model: Model used for embeddings (e.g., 'text-embedding-3-small').
            progress_callback: Optional async callback for progress updates (step, total, message).
            synthesis_map: Optional SynthesisMap for enriching chunk metadata with layers.
            analysis_symbols: Optional list of symbol dicts from code analysis.
            file_imports: Optional mapping of file paths to their imports.

        Returns:
            Number of pages indexed.
        """
        if not self._wiki_path.exists():
            return 0

        # First, collect all markdown files to get total count
        md_files = list(self._wiki_path.rglob("*.md"))
        total_files = len(md_files)

        if total_files == 0:
            return 0

        # Initialize metadata extractor if analysis data provided
        metadata_extractor: MetadataExtractor | None = None
        if synthesis_map or analysis_symbols or file_imports:
            metadata_extractor = MetadataExtractor(
                synthesis_map=synthesis_map,
                symbols=analysis_symbols,
                file_imports=file_imports,
            )

        # Emit initial progress
        if progress_callback:
            await progress_callback(0, total_files, f"Indexing pages (0/{total_files})...")

        indexed_count = 0
        all_chunks: list[Chunk] = []

        # Process each markdown file
        for idx, md_file in enumerate(md_files):
            content = md_file.read_text(encoding="utf-8")
            rel_path = str(md_file.relative_to(self._wiki_path))

            # Extract title from first H1 header
            title = self._extract_title(content, rel_path)

            # Determine page type from path
            page_type = self._determine_type(rel_path)

            # Extract source file path from title (for file pages)
            source_file = self._extract_source_file(title, page_type)

            # Get base metadata from analysis data if available
            base_metadata: ChunkMetadata | None = None
            if metadata_extractor and source_file:
                base_metadata = ChunkMetadata(
                    path=rel_path,
                    title=title,
                    type=page_type,
                    section_header="",
                    chunk_index=0,
                    token_count=0,
                    layer=metadata_extractor.get_layer_for_file(source_file),
                    symbols=metadata_extractor.get_symbols_for_file(source_file),
                    imports=metadata_extractor.get_imports_for_file(source_file),
                    entry_points=metadata_extractor.get_entry_points_for_file(source_file),
                )

            # Chunk the document
            chunks = self._chunking_service.chunk_document(
                content=content,
                document_path=rel_path,
                document_title=title,
                page_type=page_type,
                base_metadata=base_metadata,
            )

            # If metadata extractor is available, filter symbols to those in each chunk
            if metadata_extractor and source_file:
                for chunk in chunks:
                    chunk.metadata.symbols = metadata_extractor.get_symbols_in_content(
                        source_file, chunk.content
                    )

            all_chunks.extend(chunks)
            indexed_count += 1

            # Emit progress every 10 files or on last file
            if progress_callback and ((idx + 1) % 10 == 0 or idx == total_files - 1):
                await progress_callback(
                    idx + 1, total_files, f"Indexed {idx + 1}/{total_files} pages..."
                )

        # Insert chunks into FTS
        for chunk in all_chunks:
            self._db.execute(
                """INSERT INTO fts_content
                (content, title, path, type, section_header, chunk_id, chunk_index)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    chunk.content,
                    chunk.metadata.title,
                    chunk.metadata.path,
                    chunk.metadata.type,
                    chunk.metadata.section_header,
                    chunk.id,
                    chunk.metadata.chunk_index,
                ),
            )

        # Commit FTS inserts
        self._db.commit()

        # Add to vector store in batch
        if all_chunks:
            self._vectorstore.add_documents(
                ids=[chunk.id for chunk in all_chunks],
                documents=[chunk.content for chunk in all_chunks],
                metadatas=[
                    {
                        "path": chunk.metadata.path,
                        "title": chunk.metadata.title,
                        "type": chunk.metadata.type,
                        "section_header": chunk.metadata.section_header,
                        "chunk_index": chunk.metadata.chunk_index,
                        "layer": chunk.metadata.layer,
                        "symbols": json.dumps(chunk.metadata.symbols),
                        "imports": json.dumps(chunk.metadata.imports),
                        "entry_points": json.dumps(chunk.metadata.entry_points),
                    }
                    for chunk in all_chunks
                ],
            )

        # Save embedding metadata if provider/model specified
        if embedding_provider and embedding_model and self._meta_path:
            self._save_embedding_metadata(embedding_provider, embedding_model)

        return indexed_count

    def clear_index(self) -> None:
        """Clear all indexed content from vector store and FTS."""
        # Clear vector store
        self._vectorstore.clear()

        # Clear FTS table
        self._db.execute("DELETE FROM fts_content")
        self._db.commit()

        # Remove embedding metadata
        self._remove_embedding_metadata()

    def get_embedding_metadata(self) -> dict[str, Any] | None:
        """Get the embedding metadata from the last indexing.

        Returns:
            Dictionary with 'provider', 'model', and 'indexed_at' keys,
            or None if no metadata exists.
        """
        if not self._meta_path:
            return None

        metadata_file = self._meta_path / EMBEDDING_METADATA_FILE
        if not metadata_file.exists():
            return None

        try:
            data: dict[str, Any] = json.loads(metadata_file.read_text(encoding="utf-8"))
            return data
        except (json.JSONDecodeError, OSError):
            return None

    def _save_embedding_metadata(self, provider: str, model: str) -> None:
        """Save embedding metadata to file.

        Args:
            provider: LLM provider used for embeddings.
            model: Model used for embeddings.
        """
        if not self._meta_path:
            return

        self._meta_path.mkdir(parents=True, exist_ok=True)
        metadata = {
            "provider": provider,
            "model": model,
            "indexed_at": datetime.now(timezone.utc).isoformat(),
        }
        metadata_file = self._meta_path / EMBEDDING_METADATA_FILE
        metadata_file.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    def _remove_embedding_metadata(self) -> None:
        """Remove embedding metadata file."""
        if not self._meta_path:
            return

        metadata_file = self._meta_path / EMBEDDING_METADATA_FILE
        if metadata_file.exists():
            metadata_file.unlink()

    def _extract_title(self, content: str, fallback: str) -> str:
        """Extract title from markdown H1 header.

        Args:
            content: Markdown content.
            fallback: Fallback title if no H1 found.

        Returns:
            Extracted title or fallback.
        """
        match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        if match:
            return match.group(1).strip()
        return fallback.replace(".md", "").replace("-", " ").title()

    def _determine_type(self, rel_path: str) -> str:
        """Determine page type from relative path.

        Args:
            rel_path: Path relative to wiki directory.

        Returns:
            Page type: 'overview', 'architecture', 'workflow', 'directory', 'file', or 'wiki'.
        """
        if rel_path == "overview.md":
            return "overview"
        elif rel_path == "architecture.md":
            return "architecture"
        elif rel_path.startswith("workflows/"):
            return "workflow"
        elif rel_path.startswith("directories/"):
            return "directory"
        elif rel_path.startswith("files/"):
            return "file"
        return "wiki"

    def _extract_source_file(self, title: str, page_type: str) -> str:
        """Extract source file path from wiki page title.

        For file pages, the title is typically the source file path (e.g., "src/auth.py").
        For other page types, returns empty string.

        Args:
            title: Wiki page title.
            page_type: Type of wiki page.

        Returns:
            Source file path or empty string.
        """
        if page_type == "file":
            # Title is typically the source file path for file pages
            return title
        return ""
