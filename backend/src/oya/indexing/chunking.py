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
