"""File filtering with default excludes and .oyaignore support."""

import fnmatch
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class CategorizedFiles:
    """Files categorized by exclusion reason."""

    included: list[str] = field(default_factory=list)
    excluded_by_oyaignore: list[str] = field(default_factory=list)
    excluded_by_rule: list[str] = field(default_factory=list)


def extract_directories_from_files(files: list[str]) -> list[str]:
    """Extract unique parent directories from a list of file paths.

    This replicates the logic from GenerationOrchestrator._run_directories
    to ensure consistency between preview and generation.

    Args:
        files: List of file paths.

    Returns:
        Sorted list of unique directory paths, including root ("").
    """
    directories: set[str] = set()
    # Always include root directory
    directories.add("")
    for file_path in files:
        parts = file_path.split("/")
        for i in range(1, len(parts)):
            dir_path = "/".join(parts[:i])
            directories.add(dir_path)
    return sorted(directories)


DEFAULT_EXCLUDES = [
    # Hidden files and directories (dotfiles/dotdirs)
    # This catches .git, .hypothesis, .pytest_cache, .ruff_cache, .env, etc.
    # Note: .oyawiki/notes is explicitly allowed (see ALLOWED_PATHS below)
    ".*",
    # Dependencies
    "node_modules",
    "vendor",
    "venv",
    "__pycache__",
    "*.pyc",
    # Build outputs
    "build",
    "dist",
    "target",
    "out",
    # Oya artifacts (but NOT .oyawiki/notes/ - those are user corrections)
    # These are redundant with ".*" but kept for clarity
    ".oyawiki/wiki",
    ".oyawiki/meta",
    ".oyawiki/index",
    ".oyawiki/cache",
    ".oyawiki/config",
    # Minified/bundled assets
    "*.min.js",
    "*.min.css",
    "*.bundle.js",
    "*.chunk.js",
    "*.map",
    # Lock files (large, not useful for docs)
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "Cargo.lock",
    "poetry.lock",
    "Gemfile.lock",
    "composer.lock",
]

# Paths that are explicitly allowed even if they match DEFAULT_EXCLUDES
# These take precedence over exclusion patterns
ALLOWED_PATHS = [
    ".oyawiki/notes",  # User corrections guide analysis
]


class FileFilter:
    """Filter files based on patterns and size limits."""

    def __init__(
        self,
        repo_path: Path,
        max_file_size_kb: Optional[int] = None,
        extra_excludes: list[str] | None = None,
        ignore_path: Optional[Path] = None,
    ):
        """Initialize file filter.

        Args:
            repo_path: Path to repository root.
            max_file_size_kb: Maximum file size in KB. If None, uses settings or default (500).
            extra_excludes: Additional exclude patterns.
            ignore_path: Path to ignore file. If None, uses repo_path with ignore filename from settings.
        """
        self.repo_path = repo_path

        # Get defaults from settings if available
        ignore_filename = ".oyaignore"  # Default
        default_max_file_size_kb = 500  # Default from CONFIG_SCHEMA
        try:
            from oya.config import ConfigError, load_settings

            settings = load_settings()
            ignore_filename = settings.paths.ignore_file
            default_max_file_size_kb = settings.files.max_file_size_kb
        except (ValueError, OSError, ConfigError):
            # Settings not available (e.g., WORKSPACE_PATH not set in tests)
            pass

        # Get max_file_size_kb from settings if not provided
        if max_file_size_kb is None:
            max_file_size_kb = default_max_file_size_kb
        self.max_file_size_bytes = max_file_size_kb * 1024

        # Build exclude patterns - track oyaignore patterns separately for categorization
        self.default_exclude_patterns = list(DEFAULT_EXCLUDES)
        if extra_excludes:
            self.default_exclude_patterns.extend(extra_excludes)

        # Oyaignore patterns are tracked separately
        self.oyaignore_patterns: list[str] = []

        # Determine ignore file path - always relative to repo_path
        if ignore_path is None:
            ignore_path = repo_path / ignore_filename

        # Load ignore file if exists (in root directory, not .oyawiki)
        if ignore_path.exists():
            for line in ignore_path.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    self.oyaignore_patterns.append(line)

        # Combined patterns for backward compatibility with get_files()
        self.exclude_patterns = self.default_exclude_patterns + self.oyaignore_patterns

    def _is_excluded(self, path: str) -> bool:
        """Check if path matches any exclude pattern.

        Args:
            path: Relative file path.

        Returns:
            True if path should be excluded.
        """
        return self._is_excluded_by_patterns(path, self.exclude_patterns)

    def _is_excluded_by_patterns(self, path: str, patterns: list[str]) -> bool:
        """Check if path matches any of the given exclude patterns.

        Args:
            path: Relative file path.
            patterns: List of patterns to check against.

        Returns:
            True if path matches any pattern.
        """
        # Check if path is in an explicitly allowed location
        for allowed in ALLOWED_PATHS:
            if path.startswith(allowed + "/") or path == allowed:
                return False

        parts = path.split("/")

        for pattern in patterns:
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

    def _is_excluded_by_default_rules(self, path: str) -> bool:
        """Check if path is excluded by DEFAULT_EXCLUDES patterns.

        Args:
            path: Relative file path.

        Returns:
            True if path should be excluded by default rules.
        """
        return self._is_excluded_by_patterns(path, self.default_exclude_patterns)

    def _is_excluded_by_oyaignore(self, path: str) -> bool:
        """Check if path is excluded by .oyaignore patterns.

        Args:
            path: Relative file path.

        Returns:
            True if path should be excluded by oyaignore.
        """
        return self._is_excluded_by_patterns(path, self.oyaignore_patterns)

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

    def _is_minified(self, file_path: Path) -> bool:
        """Check if file appears to be minified based on line length.

        Minified files typically have extremely long lines (often the
        entire file on one line). We sample the first 20 lines and
        check if the average length exceeds the threshold.

        Args:
            file_path: Path to file.

        Returns:
            True if file appears to be minified.
        """
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
            lines = content.split("\n")[:20]  # Sample first 20 lines
            if not lines:
                return False
            avg_length = sum(len(line) for line in lines) / len(lines)
            # Get minified threshold from settings if available
            minified_threshold = 500  # Default
            try:
                from oya.config import ConfigError, load_settings

                settings = load_settings()
                minified_threshold = settings.files.minified_line_length
            except (ValueError, OSError, ConfigError):
                pass  # Settings not available, use default
            return avg_length > minified_threshold
        except Exception:
            return False

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

            # Check minified (only for text files that passed other checks)
            if self._is_minified(file_path):
                continue

            files.append(relative)

        return sorted(files)

    def get_files_categorized(self) -> CategorizedFiles:
        """Get files categorized by exclusion reason.

        Returns files in three categories:
        - included: Files that will be indexed
        - excluded_by_oyaignore: Files excluded via .oyaignore (user can re-include)
        - excluded_by_rule: Files excluded via built-in rules (cannot be changed)

        Note: Files excluded by rule take precedence. A file excluded by both
        default rules AND oyaignore will appear only in excluded_by_rule.

        Returns:
            CategorizedFiles with files in each category.
        """
        result = CategorizedFiles()

        for file_path in self.repo_path.rglob("*"):
            if not file_path.is_file():
                continue

            relative = str(file_path.relative_to(self.repo_path))

            # Check if excluded by default rules first (takes precedence)
            if self._is_excluded_by_default_rules(relative):
                result.excluded_by_rule.append(relative)
                continue

            # Check file properties that are "rule" based exclusions
            # Check size
            try:
                if file_path.stat().st_size > self.max_file_size_bytes:
                    result.excluded_by_rule.append(relative)
                    continue
            except OSError:
                result.excluded_by_rule.append(relative)
                continue

            # Check binary
            if self._is_binary(file_path):
                result.excluded_by_rule.append(relative)
                continue

            # Check minified (only for text files that passed other checks)
            if self._is_minified(file_path):
                result.excluded_by_rule.append(relative)
                continue

            # Check if excluded by oyaignore (user-configurable)
            if self._is_excluded_by_oyaignore(relative):
                result.excluded_by_oyaignore.append(relative)
                continue

            # File is included
            result.included.append(relative)

        # Sort all lists
        result.included.sort()
        result.excluded_by_oyaignore.sort()
        result.excluded_by_rule.sort()

        return result
