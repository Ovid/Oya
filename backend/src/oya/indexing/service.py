"""Indexing service for wiki content into vector store and FTS."""

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from oya.db.connection import Database
from oya.vectorstore.store import VectorStore


EMBEDDING_METADATA_FILE = "embedding_metadata.json"


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

    def index_wiki_pages(
        self,
        embedding_provider: str | None = None,
        embedding_model: str | None = None,
    ) -> int:
        """Index all wiki pages into vector store and FTS.
        
        Args:
            embedding_provider: LLM provider used for embeddings (e.g., 'openai').
            embedding_model: Model used for embeddings (e.g., 'text-embedding-3-small').
        
        Returns:
            Number of pages indexed.
        """
        if not self._wiki_path.exists():
            return 0
        
        indexed_count = 0
        ids: list[str] = []
        documents: list[str] = []
        metadatas: list[dict[str, Any]] = []
        
        # Find all markdown files
        for md_file in self._wiki_path.rglob("*.md"):
            content = md_file.read_text(encoding="utf-8")
            rel_path = str(md_file.relative_to(self._wiki_path))
            
            # Extract title from first H1 header
            title = self._extract_title(content, rel_path)
            
            # Determine page type from path
            page_type = self._determine_type(rel_path)
            
            # Prepare for vector store
            doc_id = f"wiki_{rel_path.replace('/', '_').replace('.md', '')}"
            ids.append(doc_id)
            documents.append(content)
            metadatas.append({
                "path": rel_path,
                "title": title,
                "type": page_type,
            })
            
            # Insert into FTS
            self._db.execute(
                "INSERT INTO fts_content (content, title, path, type) VALUES (?, ?, ?, ?)",
                (content, title, rel_path, page_type),
            )
            
            indexed_count += 1
        
        # Commit FTS inserts
        self._db.commit()
        
        # Add to vector store in batch
        if ids:
            self._vectorstore.add_documents(
                ids=ids,
                documents=documents,
                metadatas=metadatas,
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
            return json.loads(metadata_file.read_text(encoding="utf-8"))
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
