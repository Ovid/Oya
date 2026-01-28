"""Source file fetcher for Q&A context."""

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from oya.db.code_index import CodeIndexEntry


class SourceFetcher:
    """Fetches source code snippets for Q&A context."""

    # Approximate chars per token (conservative estimate)
    CHARS_PER_TOKEN = 4

    def __init__(self, repo_root: Path):
        """Initialize the source fetcher.

        Args:
            repo_root: Root directory of the repository
        """
        self.repo_root = Path(repo_root)

    def fetch(
        self,
        file_path: str,
        line_start: int,
        line_end: int,
        budget: int = 500,
    ) -> str:
        """Fetch source code for a specific line range.

        Args:
            file_path: Path to source file (absolute or relative to repo_root)
            line_start: Starting line (1-indexed)
            line_end: Ending line (1-indexed, inclusive)
            budget: Maximum tokens (approximate, uses char estimate)

        Returns:
            Source code with location header, truncated if necessary
        """
        # Resolve path
        path = Path(file_path)
        if not path.is_absolute():
            path = self.repo_root / path

        if not path.exists():
            return f"# File not found: {file_path}"

        # Read file and extract line range
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            return f"# Error reading file: {file_path} ({e})"

        lines = content.splitlines()

        # Convert to 0-indexed for list access
        start_idx = max(0, line_start - 1)
        end_idx = min(len(lines), line_end)

        # Extract the specified lines
        extracted_lines = lines[start_idx:end_idx]
        extracted_content = "\n".join(extracted_lines)

        # Create header with relative path if possible
        display_path = file_path
        if path.is_absolute():
            try:
                display_path = str(path.relative_to(self.repo_root))
            except ValueError:
                display_path = str(path)

        header = f"# {display_path} (lines {line_start}-{line_end})"

        # Calculate max chars from token budget
        max_chars = budget * self.CHARS_PER_TOKEN

        # Check if we need to truncate
        full_output = f"{header}\n{extracted_content}"

        if len(full_output) <= max_chars:
            return full_output

        # Truncate content, preserving header
        header_len = len(header) + 1  # +1 for newline
        available_chars = max_chars - header_len - 20  # Reserve space for truncation message

        if available_chars <= 0:
            return f"{header}\n[Content truncated - budget too small]"

        truncated_content = extracted_content[:available_chars]

        # Try to truncate at a line boundary for cleaner output
        last_newline = truncated_content.rfind("\n")
        if last_newline > available_chars // 2:
            truncated_content = truncated_content[:last_newline]

        return f"{header}\n{truncated_content}\n... [truncated]"

    def fetch_entry(self, entry: "CodeIndexEntry", budget: int = 500) -> str:
        """Convenience method to fetch source from a CodeIndexEntry.

        Args:
            entry: A CodeIndexEntry with file path and line range
            budget: Maximum tokens (approximate)

        Returns:
            Source code with location header, truncated if necessary
        """
        return self.fetch(
            file_path=entry.file_path,
            line_start=entry.line_start,
            line_end=entry.line_end,
            budget=budget,
        )
