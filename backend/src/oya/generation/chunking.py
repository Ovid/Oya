# backend/src/oya/generation/chunking.py
"""Content chunking for wiki generation and embedding."""

from dataclasses import dataclass, field

from oya.config import ConfigError, load_settings
from oya.parsing.models import ParsedSymbol


@dataclass
class Chunk:
    """A chunk of file content for processing.

    Attributes:
        content: The text content of the chunk.
        file_path: Path to the source file.
        start_line: Starting line number (1-indexed).
        end_line: Ending line number (1-indexed).
        symbols: List of symbols contained in this chunk.
        chunk_index: Index of this chunk within the file.
    """

    content: str
    file_path: str
    start_line: int
    end_line: int
    symbols: list[ParsedSymbol] = field(default_factory=list)
    chunk_index: int = 0


def estimate_tokens(text: str) -> int:
    """Estimate token count for text.

    Uses a simple heuristic of ~4 characters per token,
    which is a reasonable approximation for code.

    Args:
        text: Text to estimate tokens for.

    Returns:
        Estimated token count.
    """
    return len(text) // 4


def chunk_file_content(
    content: str,
    file_path: str,
    max_tokens: int | None = None,
    overlap_lines: int | None = None,
) -> list[Chunk]:
    """Split file content into chunks by line count.

    Args:
        content: File content to chunk.
        file_path: Path to the source file.
        max_tokens: Maximum tokens per chunk.
        overlap_lines: Number of lines to overlap between chunks.

    Returns:
        List of Chunk objects.
    """
    if max_tokens is None or overlap_lines is None:
        try:
            settings = load_settings()
            if max_tokens is None:
                max_tokens = settings.generation.chunk_tokens
            if overlap_lines is None:
                overlap_lines = settings.generation.chunk_overlap_lines
        except (ValueError, OSError, ConfigError):
            # Settings not available
            if max_tokens is None:
                max_tokens = 1000  # Default from CONFIG_SCHEMA
            if overlap_lines is None:
                overlap_lines = 5  # Default from CONFIG_SCHEMA

    if not content:
        return []

    lines = content.split("\n")
    total_lines = len(lines)

    # Calculate approximate lines per chunk based on average line length
    avg_chars_per_line = len(content) / max(total_lines, 1)
    chars_per_chunk = max_tokens * 4  # Convert tokens to chars
    lines_per_chunk = max(1, int(chars_per_chunk / max(avg_chars_per_line, 1)))

    chunks: list[Chunk] = []
    chunk_index = 0
    start_idx = 0

    while start_idx < total_lines:
        # Calculate end index for this chunk
        end_idx = min(start_idx + lines_per_chunk, total_lines)

        # Extract lines for this chunk
        chunk_lines = lines[start_idx:end_idx]
        chunk_content = "\n".join(chunk_lines)

        # Verify we're not over the token limit; adjust if needed
        while estimate_tokens(chunk_content) > max_tokens * 1.2 and end_idx > start_idx + 1:
            end_idx -= 1
            chunk_lines = lines[start_idx:end_idx]
            chunk_content = "\n".join(chunk_lines)

        chunk = Chunk(
            content=chunk_content,
            file_path=file_path,
            start_line=start_idx + 1,  # 1-indexed
            end_line=end_idx,  # 1-indexed (last line included)
            symbols=[],
            chunk_index=chunk_index,
        )
        chunks.append(chunk)
        chunk_index += 1

        # Move to next chunk with overlap
        next_start = end_idx - overlap_lines
        if next_start <= start_idx:
            # Ensure we make progress
            next_start = end_idx

        # If we've reached the end, break
        if end_idx >= total_lines:
            break

        start_idx = next_start

    return chunks


def chunk_by_symbols(
    content: str,
    file_path: str,
    symbols: list[ParsedSymbol],
    max_tokens: int | None = None,
) -> list[Chunk]:
    """Split file content by symbol boundaries.

    Groups symbols into chunks that respect code boundaries
    while staying under the token limit.

    Args:
        content: File content to chunk.
        file_path: Path to the source file.
        symbols: List of ParsedSymbol objects with start_line/end_line.
        max_tokens: Maximum tokens per chunk.

    Returns:
        List of Chunk objects with associated symbols.
    """
    if max_tokens is None:
        try:
            settings = load_settings()
            max_tokens = settings.generation.chunk_tokens
        except (ValueError, OSError, ConfigError):
            # Settings not available
            max_tokens = 1000  # Default from CONFIG_SCHEMA

    if not content or not symbols:
        # If no symbols, fall back to line-based chunking
        if content and not symbols:
            return chunk_file_content(content, file_path, max_tokens)
        return []

    lines = content.split("\n")

    # Sort symbols by start_line
    sorted_symbols = sorted(symbols, key=lambda s: s.start_line)

    chunks: list[Chunk] = []
    chunk_index = 0

    current_symbols: list[ParsedSymbol] = []
    current_start_line: int | None = None
    current_content_lines: list[str] = []

    for symbol in sorted_symbols:
        start_line = symbol.start_line
        end_line = symbol.end_line

        # Extract symbol content (convert to 0-indexed for list access)
        symbol_lines = lines[start_line - 1 : end_line]

        # Check if adding this symbol would exceed the token limit
        if current_content_lines:
            combined_content = "\n".join(current_content_lines + symbol_lines)
            combined_tokens = estimate_tokens(combined_content)

            if combined_tokens > max_tokens:
                # Save current chunk and start a new one
                chunk = Chunk(
                    content="\n".join(current_content_lines),
                    file_path=file_path,
                    start_line=current_start_line or 1,
                    end_line=current_start_line + len(current_content_lines) - 1
                    if current_start_line
                    else 1,
                    symbols=current_symbols.copy(),
                    chunk_index=chunk_index,
                )
                chunks.append(chunk)
                chunk_index += 1

                # Reset for new chunk
                current_symbols = []
                current_content_lines = []
                current_start_line = None

        # Add symbol to current chunk
        if current_start_line is None:
            current_start_line = start_line
            current_content_lines = symbol_lines.copy()
        else:
            # Fill gap between previous symbol and this one if needed
            prev_end = current_start_line + len(current_content_lines) - 1
            if start_line > prev_end + 1:
                # Add gap lines
                gap_lines = lines[prev_end : start_line - 1]
                current_content_lines.extend(gap_lines)
            current_content_lines.extend(symbol_lines)

        current_symbols.append(symbol)

    # Don't forget the last chunk
    if current_content_lines and current_symbols:
        chunk = Chunk(
            content="\n".join(current_content_lines),
            file_path=file_path,
            start_line=current_start_line or 1,
            end_line=current_start_line + len(current_content_lines) - 1
            if current_start_line
            else 1,
            symbols=current_symbols.copy(),
            chunk_index=chunk_index,
        )
        chunks.append(chunk)

    return chunks
