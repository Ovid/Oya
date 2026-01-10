"""Indexing service for wiki content into vector store and FTS."""

import re
from pathlib import Path
from typing import Any

from oya.db.connection import Database
from oya.vectorstore.store import VectorStore


class IndexingService:
    """Service for indexing wiki content into search stores.
    
    Indexes wiki pages into:
    - ChromaDB for semantic/vector search
    - SQLite FTS5 for full-text keyword search
    """

    def __init__(
        self,
        vectorstore: VectorStore,
        db: Database,
        wiki_path: Path,
    ) -> None:
        """Initialize indexing service.
        
        Args:
            vectorstore: ChromaDB vector store for semantic search.
            db: SQLite database with FTS5 table.
            wiki_path: Path to wiki directory containing markdown files.
        """
        self._vectorstore = vectorstore
        self._db = db
        self._wiki_path = Path(wiki_path)

    def index_wiki_pages(self) -> int:
        """Index all wiki pages into vector store and FTS.
        
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
        
        return indexed_count

    def clear_index(self) -> None:
        """Clear all indexed content from vector store and FTS."""
        # Clear vector store
        self._vectorstore.clear()
        
        # Clear FTS table
        self._db.execute("DELETE FROM fts_content")
        self._db.commit()

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
