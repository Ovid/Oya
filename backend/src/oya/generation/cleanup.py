"""Cleanup module for stale wiki content during regeneration.

During wiki regeneration, some content becomes stale and needs to be deleted:
- Workflows: Always regenerated fresh, so all existing workflows are deleted
- File/directory pages: Orphaned pages for deleted source files
- Notes: Notes attached to files that no longer exist
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path

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
