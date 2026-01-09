"""File filtering with default excludes and .oyaignore support."""

import fnmatch
from pathlib import Path


DEFAULT_EXCLUDES = [
    # Version control
    ".git",
    ".hg",
    ".svn",
    # Dependencies
    "node_modules",
    "vendor",
    ".venv",
    "venv",
    "__pycache__",
    "*.pyc",
    # Build outputs
    "build",
    "dist",
    "target",
    "out",
    ".next",
    ".nuxt",
    # IDE
    ".idea",
    ".vscode",
    "*.swp",
    # OS
    ".DS_Store",
    "Thumbs.db",
    # Oya artifacts (but NOT .oyawiki/notes/ - those are user corrections)
    ".oyawiki/wiki",
    ".oyawiki/meta",
    ".oyawiki/index",
    ".oyawiki/cache",
    ".oyawiki/config",
]


class FileFilter:
    """Filter files based on patterns and size limits."""

    def __init__(
        self,
        repo_path: Path,
        max_file_size_kb: int = 500,
        extra_excludes: list[str] | None = None,
    ):
        """Initialize file filter.

        Args:
            repo_path: Path to repository root.
            max_file_size_kb: Maximum file size in KB.
            extra_excludes: Additional exclude patterns.
        """
        self.repo_path = repo_path
        self.max_file_size_bytes = max_file_size_kb * 1024

        # Build exclude patterns
        self.exclude_patterns = list(DEFAULT_EXCLUDES)
        if extra_excludes:
            self.exclude_patterns.extend(extra_excludes)

        # Load .oyaignore if exists (now in .oyawiki/.oyaignore)
        oyaignore = repo_path / ".oyawiki" / ".oyaignore"
        if oyaignore.exists():
            for line in oyaignore.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    self.exclude_patterns.append(line)

    def _is_excluded(self, path: str) -> bool:
        """Check if path matches any exclude pattern.

        Args:
            path: Relative file path.

        Returns:
            True if path should be excluded.
        """
        parts = path.split("/")

        for pattern in self.exclude_patterns:
            # Handle directory patterns (trailing slash means directory)
            # e.g., "docs/" should match any path starting with "docs/"
            if pattern.endswith("/"):
                dir_pattern = pattern.rstrip("/")
                # Check if any path component matches the directory pattern
                for part in parts:
                    if fnmatch.fnmatch(part, dir_pattern):
                        return True
            # Handle path patterns containing "/" (e.g., ".oyawiki/wiki")
            # These should match as path prefixes
            elif "/" in pattern:
                # Check if path starts with the pattern (as a directory prefix)
                if path.startswith(pattern + "/") or path == pattern:
                    return True
                # Also support glob patterns in path-based excludes
                if fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(path, pattern + "/*"):
                    return True
            else:
                # Check each path component
                for part in parts:
                    if fnmatch.fnmatch(part, pattern):
                        return True
                # Check full path
                if fnmatch.fnmatch(path, pattern):
                    return True

        return False

    def _is_binary(self, file_path: Path) -> bool:
        """Check if file appears to be binary.

        Args:
            file_path: Path to file.

        Returns:
            True if file appears to be binary.
        """
        try:
            with open(file_path, "rb") as f:
                chunk = f.read(1024)
                return b"\x00" in chunk
        except Exception:
            return True

    def get_files(self) -> list[str]:
        """Get list of files to process.

        Returns:
            List of relative file paths.
        """
        files = []

        for file_path in self.repo_path.rglob("*"):
            if not file_path.is_file():
                continue

            relative = str(file_path.relative_to(self.repo_path))

            # Check exclusions
            if self._is_excluded(relative):
                continue

            # Check size
            try:
                if file_path.stat().st_size > self.max_file_size_bytes:
                    continue
            except OSError:
                continue

            # Check binary
            if self._is_binary(file_path):
                continue

            files.append(relative)

        return sorted(files)
