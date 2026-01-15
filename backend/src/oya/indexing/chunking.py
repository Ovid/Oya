"""Chunking service for wiki content."""

import re
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
