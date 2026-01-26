"""Cleanup module for stale wiki content during regeneration.

During wiki regeneration, some content becomes stale and needs to be deleted:
- Workflows: Always regenerated fresh, so all existing workflows are deleted
- File/directory pages: Orphaned pages for deleted source files
- Notes: Notes attached to files that no longer exist
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path

from oya.generation.frontmatter import parse_frontmatter

logger = logging.getLogger(__name__)


@dataclass
class CleanupResult:
    """Summary of cleanup operations performed.

    Tracks counts of deleted items during the cleanup phase of regeneration.
    """

    workflows_deleted: int = field(default=0)
    files_deleted: int = field(default=0)
    directories_deleted: int = field(default=0)
    notes_deleted: int = field(default=0)


def delete_all_workflows(workflows_dir: Path) -> int:
    """Delete all workflow markdown files in the workflows directory.

    Workflows span multiple source files and should always be regenerated fresh
    rather than incrementally updated. This function removes all existing workflow
    files before new ones are generated.

    Args:
        workflows_dir: Path to the workflows directory in the wiki.

    Returns:
        Number of workflow files deleted.
    """
    if not workflows_dir.exists():
        return 0

    count = 0
    for md_file in workflows_dir.glob("*.md"):
        logger.info(f"Deleting workflow: {md_file.name}")
        md_file.unlink()
        count += 1

    return count


def delete_orphaned_pages(
    pages_dir: Path,
    source_dir: Path,
    is_file: bool,
) -> list[str]:
    """Delete wiki pages whose source files/directories no longer exist.

    Args:
        pages_dir: Path to wiki/files or wiki/directories
        source_dir: Path to source repository
        is_file: True if checking files, False if checking directories

    Returns:
        List of deleted source paths
    """
    if not pages_dir.exists():
        return []

    deleted = []
    for md_file in pages_dir.glob("*.md"):
        content = md_file.read_text(encoding="utf-8")
        meta, _ = parse_frontmatter(content)

        # No frontmatter = treat as orphaned
        if meta is None:
            logger.info(f"Deleting page without frontmatter: {md_file.name}")
            md_file.unlink()
            deleted.append(f"(no frontmatter: {md_file.name})")
            continue

        source_path = meta.get("source")
        if not source_path:
            logger.info(f"Deleting page without source: {md_file.name}")
            md_file.unlink()
            deleted.append(f"(no source: {md_file.name})")
            continue

        # Check if source exists
        full_source = source_dir / source_path
        source_exists = full_source.is_file() if is_file else full_source.is_dir()

        if not source_exists:
            logger.info(f"Deleting orphaned page: {source_path}")
            md_file.unlink()
            deleted.append(source_path)

    return deleted
