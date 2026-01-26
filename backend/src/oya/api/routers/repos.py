"""Repository management endpoints."""

import logging
import os
import uuid
from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException

from oya.api.deps import (
    get_repo,
    get_db,
    get_settings,
    get_active_repo_paths,
    get_active_repo,
    invalidate_db_cache_for_repo,
)
from oya.api.schemas import (
    JobCreated,
    IndexableItems,
    FileList,
    OyaignoreUpdateRequest,
    OyaignoreUpdateResponse,
    RepoStatus,
    EmbeddingMetadata,
)
from oya.repo.file_filter import FileFilter, extract_directories_from_files
from oya.repo.git_operations import GitSyncError, sync_to_default_branch
from oya.repo.git_repo import GitRepo
from oya.repo.repo_paths import RepoPaths
from oya.db.connection import Database
from oya.db.migrations import run_migrations
from oya.config import Settings
from oya.generation.cleanup import cleanup_stale_content
from oya.generation.orchestrator import GenerationOrchestrator, GenerationProgress
from oya.generation.staging import (
    prepare_staging_directory,
    promote_staging_to_production,
)
from oya.indexing.service import IndexingService
from oya.llm.client import LLMClient
from oya.notes.service import NotesService
from oya.vectorstore.store import VectorStore
from oya.vectorstore.issues import IssuesStore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/repos", tags=["repos"])


@router.get("/status", response_model=RepoStatus)
async def get_repo_status(
    settings: Settings = Depends(get_settings),
) -> RepoStatus:
    """Get status of the currently active repository.

    Returns repository metadata including git info, generation status,
    and embedding configuration.
    """
    repo_record = get_active_repo()

    if repo_record is None:
        raise HTTPException(
            status_code=400,
            detail="No repository is active. Please select a repository first.",
        )

    paths = RepoPaths(settings.data_dir, repo_record.local_path)

    # Note: head_message is not currently supported, would require git log parsing
    head_message = None

    # Check if wiki has been generated (overview.md exists)
    initialized = (paths.wiki_dir / "overview.md").exists()

    # Get embedding metadata if available
    embedding_metadata = None
    has_embedding_info = (
        repo_record.embedding_provider
        and repo_record.embedding_model
        and repo_record.last_generated
    )
    if has_embedding_info:
        # Type narrowing: has_embedding_info ensures these are not None
        assert repo_record.embedding_provider is not None
        assert repo_record.embedding_model is not None
        assert repo_record.last_generated is not None
        embedding_metadata = EmbeddingMetadata(
            provider=repo_record.embedding_provider,
            model=repo_record.embedding_model,
            indexed_at=repo_record.last_generated.isoformat(),
        )

    # Check for embedding mismatch
    embedding_mismatch = False
    if embedding_metadata:
        embedding_mismatch = (
            repo_record.embedding_provider != settings.active_provider
            or repo_record.embedding_model != settings.active_model
        )

    return RepoStatus(
        path=repo_record.local_path,
        head_commit=repo_record.head_commit,
        head_message=head_message,
        branch=repo_record.branch,
        initialized=initialized,
        is_docker=os.environ.get("DOCKER_ENV", "").lower() == "true",
        last_generation=(
            repo_record.last_generated.isoformat() if repo_record.last_generated else None
        ),
        generation_status=repo_record.status,
        embedding_metadata=embedding_metadata,
        current_provider=settings.active_provider,
        current_model=settings.active_model,
        embedding_mismatch=embedding_mismatch,
    )


@router.get("/indexable", response_model=IndexableItems)
async def get_indexable_items(
    paths: RepoPaths = Depends(get_active_repo_paths),
) -> IndexableItems:
    """Get list of directories and files categorized by exclusion reason.

    Returns files in three categories:
    - included: Files that will be indexed
    - excluded_by_oyaignore: Files excluded via .oyaignore (user can re-include)
    - excluded_by_rule: Files excluded via built-in rules (cannot be changed)

    Uses the same FileFilter class as GenerationOrchestrator to ensure
    the preview matches actual generation behavior.
    """
    source_path = paths.source
    if not source_path.exists():
        raise HTTPException(status_code=400, detail=f"Repository source not found: {source_path}")

    try:
        # Use the same FileFilter class as GenerationOrchestrator._run_analysis()
        # Pass the oyaignore path from meta/ directory where the API writes it
        file_filter = FileFilter(source_path, ignore_path=paths.oyaignore)
        categorized = file_filter.get_files_categorized()

        # For included, derive directories from files
        included_dirs = extract_directories_from_files(categorized.included)

        # Combine file-derived directories with explicitly excluded directories
        rule_dirs = list(
            set(extract_directories_from_files(categorized.excluded_by_rule))
            | set(categorized.excluded_dirs_by_rule)
        )
        rule_dirs.sort()

        oyaignore_dirs = list(
            set(extract_directories_from_files(categorized.excluded_by_oyaignore))
            | set(categorized.excluded_dirs_by_oyaignore)
        )
        oyaignore_dirs.sort()

        # Remove root directory ("") from oyaignore and rule dirs since it's always in included
        oyaignore_dirs = [d for d in oyaignore_dirs if d != ""]
        rule_dirs = [d for d in rule_dirs if d != ""]

        return IndexableItems(
            included=FileList(
                directories=included_dirs,
                files=categorized.included,
            ),
            excluded_by_oyaignore=FileList(
                directories=oyaignore_dirs,
                files=categorized.excluded_by_oyaignore,
            ),
            excluded_by_rule=FileList(
                directories=rule_dirs,
                files=categorized.excluded_by_rule,
            ),
        )
    except PermissionError as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to enumerate files: Permission denied - {e}"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to enumerate files: {e}")


@router.post("/oyaignore", response_model=OyaignoreUpdateResponse)
async def update_oyaignore(
    request: OyaignoreUpdateRequest,
    paths: RepoPaths = Depends(get_active_repo_paths),
) -> OyaignoreUpdateResponse:
    """Add exclusions to and remove patterns from .oyaignore.

    Creates the .oyaignore file if it doesn't exist.
    Processes removals first (before additions).
    Appends new exclusions to the end of the file, preserving existing entries.
    Adds trailing slash to directory patterns.
    Removes duplicate entries.

    In multi-repo mode, .oyaignore is stored in the meta/ directory.
    """
    oyaignore_path = paths.oyaignore

    try:
        # Read existing content, preserving order but tracking for deduplication
        existing_entries_ordered: list[str] = []
        existing_entries_set: set[str] = set()
        comments_and_blanks: list[tuple[int, str]] = []  # (position, content)

        if oyaignore_path.exists():
            existing_content = oyaignore_path.read_text()
            for i, line in enumerate(existing_content.splitlines()):
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    # Preserve comments and blank lines with their position
                    comments_and_blanks.append((len(existing_entries_ordered), line))
                elif stripped not in existing_entries_set:
                    # Only add non-duplicate entries
                    existing_entries_ordered.append(stripped)
                    existing_entries_set.add(stripped)

        # Process removals first (before additions)
        removed: list[str] = []
        if request.removals:
            # Normalize removal patterns for matching
            removal_patterns: set[str] = set()
            for pattern in request.removals:
                # Add both with and without trailing slash for matching
                normalized = pattern.rstrip("/")
                removal_patterns.add(normalized)
                removal_patterns.add(normalized + "/")

            # Remove matching entries
            entries_to_remove: list[str] = []
            for entry in existing_entries_ordered:
                entry_normalized = entry.rstrip("/")
                if entry in removal_patterns or entry_normalized in removal_patterns:
                    entries_to_remove.append(entry)
                    removed.append(entry)

            # Remove from lists
            for entry in entries_to_remove:
                existing_entries_ordered.remove(entry)
                existing_entries_set.discard(entry)

        # Prepare new entries
        added_directories: list[str] = []
        added_files: list[str] = []

        # Collect all directory patterns (both existing and new) for filtering files
        all_dir_patterns: set[str] = set()

        # Process directories (add trailing slash)
        for dir_path in request.directories:
            dir_pattern = dir_path.rstrip("/") + "/"
            all_dir_patterns.add(dir_pattern)
            if dir_pattern not in existing_entries_set:
                existing_entries_ordered.append(dir_pattern)
                existing_entries_set.add(dir_pattern)
                added_directories.append(dir_pattern)

        # Also include existing directory patterns for filtering
        for entry in existing_entries_set:
            if entry.endswith("/"):
                all_dir_patterns.add(entry)

        # Process files - filter out files within excluded directories
        for file_path in request.files:
            if file_path not in existing_entries_set:
                # Check if file is within any excluded directory
                is_within_excluded_dir = False
                for dir_pattern in all_dir_patterns:
                    dir_prefix = dir_pattern.rstrip("/") + "/"
                    if file_path.startswith(dir_prefix):
                        is_within_excluded_dir = True
                        break

                if not is_within_excluded_dir:
                    existing_entries_ordered.append(file_path)
                    existing_entries_set.add(file_path)
                    added_files.append(file_path)

        # Rebuild the file content with comments/blanks in their original positions
        # and deduplicated entries
        final_lines: list[str] = []
        entry_idx = 0
        comment_idx = 0

        while entry_idx < len(existing_entries_ordered) or comment_idx < len(comments_and_blanks):
            # Check if there's a comment/blank that should come before the next entry
            while (
                comment_idx < len(comments_and_blanks)
                and comments_and_blanks[comment_idx][0] <= entry_idx
            ):
                final_lines.append(comments_and_blanks[comment_idx][1])
                comment_idx += 1

            if entry_idx < len(existing_entries_ordered):
                final_lines.append(existing_entries_ordered[entry_idx])
                entry_idx += 1

        # Add any remaining comments/blanks
        while comment_idx < len(comments_and_blanks):
            final_lines.append(comments_and_blanks[comment_idx][1])
            comment_idx += 1

        # Write the deduplicated content
        with oyaignore_path.open("w") as f:
            if final_lines:
                f.write("\n".join(final_lines))
                f.write("\n")

        return OyaignoreUpdateResponse(
            added_directories=added_directories,
            added_files=added_files,
            removed=removed,
            total_added=len(added_directories) + len(added_files),
            total_removed=len(removed),
        )
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=f"Permission denied writing to .oyaignore: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update .oyaignore: {e}")


@router.get("/generation-status")
async def get_generation_status(
    paths: RepoPaths = Depends(get_active_repo_paths),
) -> dict | None:
    """Get the current generation status.

    Returns information about any incomplete build in the staging directory.
    Returns null if no incomplete build exists.
    """
    staging_path = paths.meta_dir / ".oyawiki-building"
    if staging_path.exists():
        return {
            "status": "incomplete",
            "message": "An incomplete build was found in the staging directory.",
        }
    return None


@router.post("/init", response_model=JobCreated, status_code=202)
async def init_repo(
    background_tasks: BackgroundTasks,
    repo: GitRepo = Depends(get_repo),
    db: Database = Depends(get_db),
    paths: RepoPaths = Depends(get_active_repo_paths),
    settings: Settings = Depends(get_settings),
) -> JobCreated:
    """Initialize repository and start wiki generation."""
    # Get active repo ID for cache invalidation after promotion
    active_repo = get_active_repo()
    if active_repo is None:
        raise HTTPException(
            status_code=400,
            detail="No repository is active. Please select a repository first.",
        )
    repo_id = active_repo.id

    job_id = str(uuid.uuid4())

    # Record job in database
    # (9 phases: syncing, analysis, files, directories, synthesis, architecture,
    # overview, workflows, indexing)
    db.execute(
        """
        INSERT INTO generations (id, type, status, started_at, total_phases)
        VALUES (?, ?, ?, datetime('now'), ?)
        """,
        (job_id, "full", "pending", 9),
    )
    db.commit()

    # Start generation in background
    background_tasks.add_task(_run_generation, job_id, repo, db, paths, settings, repo_id)

    return JobCreated(job_id=job_id, message="Wiki generation started")


async def _run_generation(
    job_id: str,
    repo: GitRepo,
    db: Database,
    paths: RepoPaths,
    settings: Settings,
    repo_id: int,
) -> None:
    """Run wiki generation in background using staging directory.

    Builds wiki in .oyawiki-building, then promotes to .oyawiki on success.
    If generation fails, staging directory is left for debugging.

    Args:
        job_id: Unique job identifier.
        repo: GitRepo instance for the source repository.
        db: Database connection for job tracking.
        paths: RepoPaths for the active repo.
        settings: Application settings.
        repo_id: The ID of the active repo (for cache invalidation after promotion).
    """
    # Staging paths - build in .oyawiki-building (in meta directory)
    staging_path = paths.meta / ".oyawiki-building"
    staging_wiki_path = staging_path / "wiki"
    staging_meta_path = staging_path / "meta"
    production_path = paths.oyawiki

    # Phase number mapping for progress tracking (bottom-up approach)
    # Order: Syncing → Analysis → Files → Directories → Synthesis → Architecture →
    # Overview → Workflows → Indexing
    phase_numbers = {
        "syncing": 1,
        "analysis": 2,
        "files": 3,
        "directories": 4,
        "synthesis": 5,
        "architecture": 6,
        "overview": 7,
        "workflows": 8,
        "indexing": 9,
    }

    async def progress_callback(progress: GenerationProgress) -> None:
        """Update database with current progress."""
        phase_name = progress.phase.value
        phase_num = phase_numbers.get(phase_name, 0)
        db.execute(
            """
            UPDATE generations
            SET current_phase = ?, status = 'running',
                current_step = ?, total_steps = ?
            WHERE id = ?
            """,
            (f"{phase_num}:{phase_name}", progress.step, progress.total_steps, job_id),
        )
        db.commit()

    # Create staging database connection (separate from job tracking db)
    # This db is used by orchestrator for wiki_pages and survives promotion
    staging_db: Database | None = None

    try:
        # Sync repository to default branch before generation
        db.execute(
            "UPDATE generations SET status = 'running', current_phase = '0:syncing' WHERE id = ?",
            (job_id,),
        )
        db.commit()

        try:
            sync_to_default_branch(paths.source)
        except GitSyncError as e:
            db.execute(
                "UPDATE generations SET status = 'failed', error_message = ? WHERE id = ?",
                (e.message, job_id),
            )
            db.commit()
            return

        # Update status to starting (after sync)
        db.execute(
            "UPDATE generations SET current_phase = '0:starting' WHERE id = ?",
            (job_id,),
        )
        db.commit()

        # Prepare staging directory (copies production for incremental, or creates empty)
        prepare_staging_directory(staging_path, production_path)

        # Create staging database connection for orchestrator
        # This ensures wiki_pages data survives the staging → production promotion
        staging_db_path = staging_meta_path / "oya.db"
        staging_db = Database(staging_db_path)
        # Run migrations on staging db to ensure schema is up to date
        run_migrations(staging_db)

        # Cleanup stale content before generation
        try:
            # Create notes service for cleanup
            notes_service = NotesService(
                notes_path=staging_path / "notes",
                db=staging_db,
            )

            cleanup_result = cleanup_stale_content(
                wiki_path=staging_wiki_path,
                source_path=paths.source,
                notes_service=notes_service,
                oyaignore_path=paths.oyaignore,
            )
            logger.info(
                f"Cleanup complete: {cleanup_result.workflows_deleted} workflows, "
                f"{cleanup_result.files_deleted} files, "
                f"{cleanup_result.directories_deleted} directories, "
                f"{cleanup_result.notes_deleted} notes deleted"
            )
        except Exception as e:
            logger.warning(f"Cleanup failed (continuing with generation): {e}")

        # Create orchestrator to build in staging directory
        log_path = paths.oya_logs / "llm-queries.jsonl"
        llm = LLMClient(
            provider=settings.llm_provider,
            model=settings.llm_model,
            api_key=settings.llm_api_key,
            endpoint=settings.llm_endpoint,
            log_path=log_path,
        )
        issues_store = IssuesStore(staging_meta_path / "vectorstore")
        orchestrator = GenerationOrchestrator(
            llm_client=llm,
            repo=repo,
            db=staging_db,  # Use staging db for wiki_pages
            wiki_path=staging_wiki_path,
            parallel_limit=settings.parallel_file_limit,
            issues_store=issues_store,
            ignore_path=paths.oyaignore,
        )

        generation_result = await orchestrator.run(progress_callback=progress_callback)

        # Index wiki content for Q&A search (in staging)
        db.execute(
            """UPDATE generations
            SET current_phase = '9:indexing', current_step = 0, total_steps = 0
            WHERE id = ?""",
            (job_id,),
        )
        db.commit()

        # Use staging chroma path for indexing
        staging_chroma_path = staging_meta_path / "chroma"
        vectorstore = VectorStore(staging_chroma_path)
        indexing_service = IndexingService(
            vectorstore=vectorstore,
            db=staging_db,  # Use staging db for FTS content
            wiki_path=staging_wiki_path,
            meta_path=staging_meta_path,
        )

        # Progress callback for indexing
        async def indexing_progress_callback(step: int, total: int, message: str) -> None:
            db.execute(
                """
                UPDATE generations
                SET current_step = ?, total_steps = ?
                WHERE id = ?
                """,
                (step, total, job_id),
            )
            db.commit()

        # Clear old index and reindex with new content
        indexing_service.clear_index()
        await indexing_service.index_wiki_pages(
            embedding_provider=settings.active_provider,
            embedding_model=settings.active_model,
            progress_callback=indexing_progress_callback,
            synthesis_map=generation_result.synthesis_map,
            analysis_symbols=generation_result.analysis_symbols,
            file_imports=generation_result.file_imports,
        )

        # Compute whether any changes were made
        changes_made = (
            generation_result.files_regenerated or generation_result.directories_regenerated
        )

        # Update status to completed BEFORE promoting staging
        # (promotion deletes .oyawiki which contains the database file)
        db.execute(
            """
            UPDATE generations
            SET status = 'completed', completed_at = datetime('now'), changes_made = ?
            WHERE id = ?
            """,
            (changes_made, job_id),
        )
        db.commit()

        # Close staging db before promotion (releases file handle)
        staging_db.close()
        staging_db = None

        # SUCCESS: Promote staging to production
        promote_staging_to_production(staging_path, production_path)

        # CRITICAL: Invalidate cached database connection for this repo.
        # The promotion replaced the .oyawiki directory (including the DB file),
        # so any cached connection is now stale and will cause "readonly database"
        # errors on subsequent writes.
        invalidate_db_cache_for_repo(repo_id)

    except Exception as e:
        # FAILURE: Leave staging directory for debugging
        # Update status to failed
        db.execute(
            """
            UPDATE generations
            SET status = 'failed', error_message = ?, completed_at = datetime('now')
            WHERE id = ?
            """,
            (str(e), job_id),
        )
        db.commit()
    finally:
        # Ensure staging db is closed
        if staging_db is not None:
            staging_db.close()
