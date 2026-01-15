"""Chunking service for wiki content."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from oya.generation.chunking import estimate_tokens


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
    matches = list(header_pattern.finditer(content))

    # Content before first header
    if matches and matches[0].start() > 0:
        pre_content = content[: matches[0].start()].strip()
        if pre_content:
            sections.append(Section(header="", content=pre_content, level=0))
    elif not matches:
        # No headers found
        return [Section(header="", content=content.strip(), level=0)]

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


class ChunkingService:
    """Service for chunking wiki pages into semantic units.

    Chunks wiki documents by splitting on markdown sections (H2/H3 headers),
    then further splits oversized sections with overlap to maintain context.
    """

    def __init__(
        self,
        max_section_tokens: int = 1000,
        overlap_tokens: int = 100,
        chunk_size_tokens: int = 500,
    ) -> None:
        """Initialize the chunking service.

        Args:
            max_section_tokens: Maximum tokens per section before splitting.
            overlap_tokens: Number of overlapping tokens between chunks.
            chunk_size_tokens: Target size for split chunks.
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
            content: Markdown content to chunk.
            document_path: Wiki page path (e.g., "files/src-auth.md").
            document_title: Document title (e.g., "src/auth.py").
            page_type: Page type (file, directory, workflow, etc.).
            base_metadata: Optional base metadata to extend for each chunk.

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
                start_chunk_index=chunk_index,
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
        start_chunk_index: int,
        base_metadata: ChunkMetadata | None = None,
    ) -> list[Chunk]:
        """Chunk a single section, splitting if oversized.

        Args:
            section: Section to chunk.
            document_path: Wiki page path.
            document_title: Document title.
            page_type: Page type.
            start_chunk_index: Starting chunk index.
            base_metadata: Optional base metadata.

        Returns:
            List of Chunk objects for this section.
        """
        # Get content after header line
        section_content = self._get_section_body(section)

        # Skip sections with empty bodies
        if not section_content.strip():
            return []

        token_count = estimate_tokens(section_content)

        if token_count <= self._max_section_tokens:
            # Section fits in one chunk
            chunk = self._create_chunk(
                section=section,
                content=section_content,
                document_path=document_path,
                document_title=document_title,
                page_type=page_type,
                chunk_index=start_chunk_index,
                base_metadata=base_metadata,
            )
            return [chunk]
        else:
            # Section too large, split with overlap
            return self._split_section(
                section=section,
                content=section_content,
                document_path=document_path,
                document_title=document_title,
                page_type=page_type,
                start_chunk_index=start_chunk_index,
                base_metadata=base_metadata,
            )

    def _split_section(
        self,
        section: Section,
        content: str,
        document_path: str,
        document_title: str,
        page_type: str,
        start_chunk_index: int,
        base_metadata: ChunkMetadata | None = None,
    ) -> list[Chunk]:
        """Split an oversized section into chunks with overlap.

        Args:
            section: Section being split.
            content: Section body content (without header).
            document_path: Wiki page path.
            document_title: Document title.
            page_type: Page type.
            start_chunk_index: Starting chunk index.
            base_metadata: Optional base metadata.

        Returns:
            List of Chunk objects.
        """
        words = content.split()
        chunks: list[Chunk] = []
        chunk_index = start_chunk_index

        # Estimate words per chunk (rough approximation: 0.75 tokens per word)
        # Use max_section_tokens as the target chunk size when splitting
        words_per_chunk = max(1, int(self._max_section_tokens / 0.75))
        overlap_words = int(self._overlap_tokens / 0.75)

        start_word = 0
        while start_word < len(words):
            end_word = min(start_word + words_per_chunk, len(words))
            chunk_words = words[start_word:end_word]
            chunk_content = " ".join(chunk_words)

            chunk = self._create_chunk(
                section=section,
                content=chunk_content,
                document_path=document_path,
                document_title=document_title,
                page_type=page_type,
                chunk_index=chunk_index,
                base_metadata=base_metadata,
            )
            chunks.append(chunk)
            chunk_index += 1

            # Move to next chunk with overlap
            next_start = end_word - overlap_words
            if next_start <= start_word:
                next_start = end_word

            if end_word >= len(words):
                break

            start_word = next_start

        return chunks

    def _create_chunk(
        self,
        section: Section,
        content: str,
        document_path: str,
        document_title: str,
        page_type: str,
        chunk_index: int,
        base_metadata: ChunkMetadata | None = None,
    ) -> Chunk:
        """Create a chunk with context prefix.

        Args:
            section: Source section.
            content: Chunk content (without prefix).
            document_path: Wiki page path.
            document_title: Document title.
            page_type: Page type.
            chunk_index: Position in document.
            base_metadata: Optional base metadata to extend.

        Returns:
            Chunk object.
        """
        header = section.header or "Introduction"
        prefixed_content = f"[Document: {document_title} | Section: {header}]\n\n{content}"
        token_count = estimate_tokens(prefixed_content)

        # Generate chunk ID
        path_slug = self._slugify(document_path.replace(".md", ""))
        header_slug = self._slugify(header)
        chunk_id = f"wiki_{path_slug}_{header_slug}"

        # Create metadata
        if base_metadata:
            metadata = ChunkMetadata(
                path=document_path,
                title=document_title,
                type=page_type,
                section_header=header,
                chunk_index=chunk_index,
                token_count=token_count,
                layer=base_metadata.layer,
                symbols=base_metadata.symbols.copy(),
                imports=base_metadata.imports.copy(),
                entry_points=base_metadata.entry_points.copy(),
            )
        else:
            metadata = ChunkMetadata(
                path=document_path,
                title=document_title,
                type=page_type,
                section_header=header,
                chunk_index=chunk_index,
                token_count=token_count,
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

    def _get_section_body(self, section: Section) -> str:
        """Get section content without the header line.

        Args:
            section: Section to extract body from.

        Returns:
            Section body content.
        """
        content = section.content

        # Remove header line if present (H1, H2, or H3)
        if content.startswith("#"):
            lines = content.split("\n", 1)
            if len(lines) > 1:
                return lines[1].strip()
            return ""

        return content.strip()

    def _slugify(self, text: str) -> str:
        """Convert text to URL-friendly slug.

        Args:
            text: Text to slugify.

        Returns:
            URL-friendly slug.
        """
        slug = text.lower().replace("/", "_").replace(" ", "-")
        slug = re.sub(r"[^a-z0-9_-]", "", slug)
        return slug
