"""Cleanup module for stale wiki content during regeneration.

During wiki regeneration, some content becomes stale and needs to be deleted:
- Workflows: Always regenerated fresh, so all existing workflows are deleted
- File/directory pages: Orphaned pages for deleted source files OR excluded sources
- Notes: Notes attached to files that no longer exist
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from oya.generation.frontmatter import parse_frontmatter
from oya.notes.schemas import NoteScope
from oya.repo.file_filter import FileFilter

if TYPE_CHECKING:
    from oya.notes.service import NotesService

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
    file_filter: FileFilter | None = None,
) -> list[str]:
    """Delete wiki pages whose source files/directories no longer exist or are excluded.

    A page is deleted if:
    - Its source file/directory no longer exists in the repository, OR
    - Its source is excluded by .oyaignore or default exclusion rules

    Args:
        pages_dir: Path to wiki/files or wiki/directories
        source_dir: Path to source repository
        is_file: True if checking files, False if checking directories
        file_filter: Optional FileFilter to check exclusions. If provided, pages
            for excluded sources will also be deleted.

    Returns:
        List of deleted source paths
    """
    if not pages_dir.exists():
        return []

    deleted = []
    for md_file in pages_dir.glob("*.md"):
        content = md_file.read_text(encoding="utf-8")
        meta, _ = parse_frontmatter(content)

        # No frontmatter = skip (backwards compatibility with pre-frontmatter pages)
        # These pages will get frontmatter when regenerated
        if meta is None:
            logger.debug(f"Skipping page without frontmatter: {md_file.name}")
            continue

        source_path = meta.get("source")
        if not source_path:
            # Page has frontmatter but no source field - skip for safety
            logger.debug(f"Skipping page without source field: {md_file.name}")
            continue

        # Check if source exists
        full_source = source_dir / source_path
        source_exists = full_source.is_file() if is_file else full_source.is_dir()

        # Check if source is excluded (even if it exists)
        source_excluded = False
        if file_filter and source_exists:
            # Use the appropriate exclusion check based on type
            if is_file:
                source_excluded = file_filter._is_excluded(source_path)
            else:
                # For directories, check if it matches exclusion patterns
                source_excluded = file_filter._is_directory_excluded_by_oyaignore(
                    source_path
                ) or file_filter._is_directory_excluded_by_default_rules(source_path)

        if not source_exists:
            logger.info(f"Deleting orphaned page (source deleted): {source_path}")
            md_file.unlink()
            deleted.append(source_path)
        elif source_excluded:
            logger.info(f"Deleting page for excluded source: {source_path}")
            md_file.unlink()
            deleted.append(source_path)

    return deleted


def delete_orphaned_notes(
    notes_service: "NotesService",
    source_dir: Path,
) -> int:
    """Delete notes whose target files/directories no longer exist.

    Args:
        notes_service: NotesService instance
        source_dir: Path to source repository

    Returns:
        Number of notes deleted
    """
    deleted_count = 0

    # Get all notes
    all_notes = notes_service.list()

    for note in all_notes:
        # Skip general and workflow notes (not tied to specific source paths)
        if note.scope in (NoteScope.GENERAL, NoteScope.WORKFLOW):
            continue

        # Check if source exists
        full_path = source_dir / note.target

        if note.scope == NoteScope.FILE:
            exists = full_path.is_file()
        elif note.scope == NoteScope.DIRECTORY:
            exists = full_path.is_dir()
        else:
            continue

        if not exists:
            logger.info(f"Deleting orphaned note: {note.scope.value}/{note.target}")
            notes_service.delete(note.scope, note.target)
            deleted_count += 1

    return deleted_count


def cleanup_stale_content(
    wiki_path: Path,
    source_path: Path,
    notes_service: "NotesService | None" = None,
    oyaignore_path: Path | None = None,
) -> CleanupResult:
    """Remove stale wiki pages and notes.

    This function should be called during the syncing phase, after git sync
    completes and before generation starts.

    Args:
        wiki_path: Path to wiki directory (.oyawiki/wiki)
        source_path: Path to source repository
        notes_service: Optional NotesService for notes cleanup
        oyaignore_path: Optional path to .oyaignore file. If provided, pages for
            excluded sources will also be deleted.

    Returns:
        CleanupResult with counts of deleted items
    """
    result = CleanupResult()

    # Create FileFilter if oyaignore path provided (for exclusion checking)
    file_filter = None
    if oyaignore_path:
        file_filter = FileFilter(
            repo_path=source_path,
            ignore_path=oyaignore_path,
        )

    # Step 1: Delete all workflows (they'll be regenerated)
    workflows_dir = wiki_path / "workflows"
    result.workflows_deleted = delete_all_workflows(workflows_dir)
    logger.info(f"Deleted {result.workflows_deleted} workflow pages")

    # Step 2: Delete orphaned file pages (and pages for excluded sources)
    files_dir = wiki_path / "files"
    deleted_files = delete_orphaned_pages(
        files_dir, source_path, is_file=True, file_filter=file_filter
    )
    result.files_deleted = len(deleted_files)
    logger.info(f"Deleted {result.files_deleted} orphaned/excluded file pages")

    # Step 3: Delete orphaned directory pages (and pages for excluded sources)
    dirs_dir = wiki_path / "directories"
    deleted_dirs = delete_orphaned_pages(
        dirs_dir, source_path, is_file=False, file_filter=file_filter
    )
    result.directories_deleted = len(deleted_dirs)
    logger.info(f"Deleted {result.directories_deleted} orphaned/excluded directory pages")

    # Step 4: Delete orphaned notes
    if notes_service:
        result.notes_deleted = delete_orphaned_notes(notes_service, source_path)
        logger.info(f"Deleted {result.notes_deleted} orphaned notes")

    return result
