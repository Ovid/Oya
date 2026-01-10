"""Repository management endpoints."""

import os
import uuid
from pathlib import Path
from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException, Query

from oya.api.deps import (
    get_repo,
    get_db,
    get_settings,
    get_workspace_base_path,
    validate_workspace_path,
    _reset_db_instance,
    _reset_vectorstore_instance,
)
from oya.api.schemas import (
    RepoStatus,
    JobCreated,
    WorkspaceSwitch,
    WorkspaceSwitchResponse,
    DirectoryEntry,
    DirectoryListing,
    EmbeddingMetadata,
    IndexableItems,
    OyaignoreUpdateRequest,
    OyaignoreUpdateResponse,
)
from oya.repo.file_filter import FileFilter, extract_directories_from_files
from oya.repo.git_repo import GitRepo
from oya.db.connection import Database
from oya.config import Settings, load_settings
from oya.generation.orchestrator import GenerationProgress
from oya.workspace import initialize_workspace
from oya.indexing.service import IndexingService
from oya.vectorstore.store import VectorStore

router = APIRouter(prefix="/api/repos", tags=["repos"])


def _is_docker_mode() -> bool:
    """Check if running in Docker mode.
    
    Docker mode is detected by the presence of WORKSPACE_DISPLAY_PATH,
    which is set by docker-compose when the host path differs from container path.
    """
    return os.getenv("WORKSPACE_DISPLAY_PATH") is not None


def _get_last_generation(db: Database | None) -> str | None:
    """Get the completed_at timestamp of the most recent completed generation.
    
    Args:
        db: Database connection, or None if not available.
        
    Returns:
        ISO format datetime string of last completed generation, or None.
    """
    if db is None:
        return None
    try:
        result = db.execute(
            """
            SELECT completed_at FROM generations
            WHERE status = 'completed' AND completed_at IS NOT NULL
            ORDER BY completed_at DESC
            LIMIT 1
            """
        ).fetchone()
        return result[0] if result else None
    except Exception:
        return None


def _build_repo_status(
    workspace_path: Path,
    display_path: str | None = None,
    settings: Settings | None = None,
    db: Database | None = None,
) -> RepoStatus:
    """Build RepoStatus for a workspace path.
    
    Args:
        workspace_path: Path to the workspace directory.
        display_path: Optional human-readable path to display (for Docker environments).
        settings: Optional settings for current provider/model info.
        db: Optional database connection for querying last generation.
        
    Returns:
        RepoStatus with git info if available, or uninitialized status.
    """
    # Use display_path if provided, otherwise use workspace_path
    path_to_display = display_path or str(workspace_path)
    is_docker = _is_docker_mode()
    
    # Get embedding metadata if available
    embedding_metadata = None
    embedding_mismatch = False
    current_provider = settings.active_provider if settings else None
    current_model = settings.active_model if settings else None
    last_generation = _get_last_generation(db)
    
    meta_path = workspace_path / ".oyawiki" / "meta"
    if meta_path.exists():
        # Create a temporary indexing service just to read metadata
        try:
            from oya.db.connection import Database
            # We don't need a real vectorstore/db, just the meta_path
            indexing_service = IndexingService(
                vectorstore=None,  # type: ignore
                db=None,  # type: ignore
                wiki_path=workspace_path / ".oyawiki" / "wiki",
                meta_path=meta_path,
            )
            raw_metadata = indexing_service.get_embedding_metadata()
            if raw_metadata:
                embedding_metadata = EmbeddingMetadata(
                    provider=raw_metadata["provider"],
                    model=raw_metadata["model"],
                    indexed_at=raw_metadata["indexed_at"],
                )
                # Check for mismatch
                if settings:
                    embedding_mismatch = (
                        raw_metadata["provider"] != settings.active_provider
                        or raw_metadata["model"] != settings.active_model
                    )
        except Exception:
            pass
    
    try:
        repo = GitRepo(workspace_path)
        head_commit = repo.get_head_commit()
        commit = repo._repo.head.commit
        return RepoStatus(
            path=path_to_display,
            head_commit=head_commit,
            head_message=commit.message.strip() if commit else None,
            branch=repo.get_current_branch(),
            initialized=True,
            is_docker=is_docker,
            last_generation=last_generation,
            embedding_metadata=embedding_metadata,
            current_provider=current_provider,
            current_model=current_model,
            embedding_mismatch=embedding_mismatch,
        )
    except Exception:
        return RepoStatus(
            path=path_to_display,
            head_commit=None,
            head_message=None,
            branch=None,
            initialized=False,
            is_docker=is_docker,
            last_generation=last_generation,
            embedding_metadata=embedding_metadata,
            current_provider=current_provider,
            current_model=current_model,
            embedding_mismatch=embedding_mismatch,
        )


@router.get("/status", response_model=RepoStatus)
async def get_repo_status(
    settings: Settings = Depends(get_settings),
    db: Database = Depends(get_db),
) -> RepoStatus:
    """Get current repository status."""
    return _build_repo_status(settings.workspace_path, settings.display_path, settings, db)


@router.get("/generation-status")
async def get_generation_status(
    settings: Settings = Depends(get_settings),
) -> dict | None:
    """Check if there's an incomplete wiki build.
    
    Returns information about incomplete build if .oyawiki-building exists.
    This indicates a previous generation was interrupted.
    
    Returns:
        Dict with incomplete build info, or None if no incomplete build.
    """
    from oya.generation.staging import has_incomplete_build
    
    if has_incomplete_build(settings.workspace_path):
        return {
            "status": "incomplete",
            "message": "A previous wiki generation did not complete. The wiki must be generated from scratch.",
        }
    return None


@router.get("/indexable", response_model=IndexableItems)
async def get_indexable_items(
    settings: Settings = Depends(get_settings),
) -> IndexableItems:
    """Get list of directories and files that will be indexed.
    
    Uses the same FileFilter class as GenerationOrchestrator to ensure
    the preview matches actual generation behavior.
    
    Requirements: 2.2, 2.3, 2.4, 7.1, 7.2, 7.3, 7.4, 7.6, 7.7, 7.8
    """
    # Validate workspace path exists and is accessible
    workspace_path = settings.workspace_path
    if not workspace_path.exists():
        raise HTTPException(
            status_code=400,
            detail=f"Repository path is invalid or inaccessible: {workspace_path}"
        )
    
    if not workspace_path.is_dir():
        raise HTTPException(
            status_code=400,
            detail=f"Repository path is not a directory: {workspace_path}"
        )
    
    try:
        # Use the same FileFilter class as GenerationOrchestrator._run_analysis()
        file_filter = FileFilter(settings.workspace_path)
        files = sorted(file_filter.get_files())
        
        # Derive directories using the same logic as GenerationOrchestrator._run_directories()
        directories = extract_directories_from_files(files)
        
        return IndexableItems(
            directories=directories,
            files=files,
            total_directories=len(directories),
            total_files=len(files),
        )
    except PermissionError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to enumerate files: Permission denied - {e}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to enumerate files: {e}"
        )


@router.post("/oyaignore", response_model=OyaignoreUpdateResponse)
async def update_oyaignore(
    request: OyaignoreUpdateRequest,
    settings: Settings = Depends(get_settings),
) -> OyaignoreUpdateResponse:
    """Add exclusions to .oyawiki/.oyaignore.
    
    Creates the .oyawiki directory and .oyaignore file if they don't exist.
    Appends new exclusions to the end of the file, preserving existing entries.
    Adds trailing slash to directory patterns.
    Removes duplicate entries.
    
    Requirements: 5.6, 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7, 8.8
    """
    workspace_path = settings.workspace_path
    oyawiki_dir = workspace_path / ".oyawiki"
    oyaignore_path = oyawiki_dir / ".oyaignore"
    
    # Create .oyawiki directory if it doesn't exist
    try:
        oyawiki_dir.mkdir(exist_ok=True)
    except PermissionError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create .oyawiki directory: {e}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create .oyawiki directory: {e}"
        )
    
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
            while comment_idx < len(comments_and_blanks) and comments_and_blanks[comment_idx][0] <= entry_idx:
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
            total_added=len(added_directories) + len(added_files),
        )
    except PermissionError as e:
        raise HTTPException(
            status_code=403,
            detail=f"Permission denied writing to .oyaignore: {e}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update .oyaignore: {e}"
        )


@router.post("/init", response_model=JobCreated, status_code=202)
async def init_repo(
    background_tasks: BackgroundTasks,
    repo: GitRepo = Depends(get_repo),
    db: Database = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> JobCreated:
    """Initialize repository and start wiki generation."""
    job_id = str(uuid.uuid4())

    # Record job in database (8 phases: analysis, files, directories, synthesis, architecture, overview, workflows, indexing)
    db.execute(
        """
        INSERT INTO generations (id, type, status, started_at, total_phases)
        VALUES (?, ?, ?, datetime('now'), ?)
        """,
        (job_id, "full", "pending", 8),
    )
    db.commit()

    # Start generation in background
    background_tasks.add_task(_run_generation, job_id, repo, db, settings)

    return JobCreated(job_id=job_id, message="Wiki generation started")


async def _run_generation(
    job_id: str,
    repo: GitRepo,
    db: Database,
    settings: Settings,
) -> None:
    """Run wiki generation in background using staging directory.
    
    Builds wiki in .oyawiki-building, then promotes to .oyawiki on success.
    If generation fails, staging directory is left for debugging.
    """
    from oya.generation.orchestrator import GenerationOrchestrator
    from oya.llm.client import LLMClient
    from oya.indexing.service import IndexingService
    from oya.vectorstore.store import VectorStore
    from oya.generation.staging import prepare_staging_directory, promote_staging_to_production

    # Staging paths - build in .oyawiki-building
    staging_path = settings.staging_path
    staging_wiki_path = staging_path / "wiki"
    staging_meta_path = staging_path / "meta"

    # Phase number mapping for progress tracking (bottom-up approach)
    # Order: Analysis → Files → Directories → Synthesis → Architecture → Overview → Workflows → Indexing
    phase_numbers = {
        "analysis": 1,
        "files": 2,
        "directories": 3,
        "synthesis": 4,
        "architecture": 5,
        "overview": 6,
        "workflows": 7,
        "indexing": 8,
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

    try:
        # Update status to running
        db.execute(
            "UPDATE generations SET status = 'running', current_phase = '0:starting' WHERE id = ?",
            (job_id,),
        )
        db.commit()

        # Prepare staging directory (copies production for incremental, or creates empty)
        prepare_staging_directory(staging_path, settings.oyawiki_path)

        # Create orchestrator to build in staging directory
        llm = LLMClient(
            provider=settings.llm_provider,
            model=settings.llm_model,
            api_key=settings.llm_api_key,
            endpoint=settings.llm_endpoint,
        )
        orchestrator = GenerationOrchestrator(
            llm_client=llm,
            repo=repo,
            db=db,
            wiki_path=staging_wiki_path,
            parallel_limit=settings.parallel_file_limit,
        )

        await orchestrator.run(progress_callback=progress_callback)

        # Index wiki content for Q&A search (in staging)
        db.execute(
            "UPDATE generations SET current_phase = '8:indexing', current_step = 0, total_steps = 0 WHERE id = ?",
            (job_id,),
        )
        db.commit()

        # Use staging chroma path for indexing
        staging_chroma_path = staging_meta_path / "chroma"
        vectorstore = VectorStore(staging_chroma_path)
        indexing_service = IndexingService(
            vectorstore=vectorstore,
            db=db,
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
        )

        # SUCCESS: Promote staging to production
        promote_staging_to_production(staging_path, settings.oyawiki_path)

        # Update status to completed
        db.execute(
            """
            UPDATE generations
            SET status = 'completed', completed_at = datetime('now')
            WHERE id = ?
            """,
            (job_id,),
        )
        db.commit()

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


@router.post("/workspace", response_model=WorkspaceSwitchResponse)
async def switch_workspace(
    request: WorkspaceSwitch,
) -> WorkspaceSwitchResponse:
    """Switch to a different workspace directory.
    
    Validates the path, clears caches, reinitializes database,
    and runs workspace initialization for the new workspace.
    
    Note: In Docker environments, this endpoint may not work as expected
    since paths must exist inside the container.
    
    Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8, 4.11
    """
    # Get base path for validation
    base_path = get_workspace_base_path()
    
    # Validate the requested path
    is_valid, error_msg, resolved_path = validate_workspace_path(request.path, base_path)
    
    if not is_valid:
        if "outside allowed" in error_msg:
            raise HTTPException(status_code=403, detail=error_msg)
        raise HTTPException(status_code=400, detail=error_msg)
    
    # Clear settings cache and update WORKSPACE_PATH environment variable
    os.environ["WORKSPACE_PATH"] = str(resolved_path)
    # Also update display path to match the new workspace
    os.environ["WORKSPACE_DISPLAY_PATH"] = str(resolved_path)
    load_settings.cache_clear()
    get_settings.cache_clear()
    
    # Reset database and vectorstore instances for new workspace
    _reset_db_instance()
    _reset_vectorstore_instance()
    
    # Initialize workspace for the new path
    initialize_workspace(resolved_path)
    
    # Build and return status for the new workspace (display path is the same as resolved path)
    new_settings = get_settings()
    new_db = get_db()
    status = _build_repo_status(resolved_path, str(resolved_path), new_settings, new_db)
    
    return WorkspaceSwitchResponse(
        status=status,
        message=f"Switched to workspace: {resolved_path}"
    )


@router.get("/directories", response_model=DirectoryListing)
async def list_directories(
    path: str = Query(default=None, description="Directory path to list. Defaults to base path."),
) -> DirectoryListing:
    """List directories for the directory picker.
    
    Returns subdirectories of the given path that are within the allowed base path.
    Only directories are returned (not files) to support workspace selection.
    """
    base_path = get_workspace_base_path()
    
    # Default to base path if no path provided
    if path is None:
        target_path = base_path
    else:
        target_path = Path(path).resolve()
    
    # Validate the path is within base path
    try:
        target_path.relative_to(base_path)
    except ValueError:
        raise HTTPException(
            status_code=403,
            detail="Path is outside allowed workspace area"
        )
    
    if not target_path.exists():
        raise HTTPException(status_code=400, detail="Path does not exist")
    
    if not target_path.is_dir():
        raise HTTPException(status_code=400, detail="Path is not a directory")
    
    # Get parent path (if not at base)
    parent = None
    if target_path != base_path:
        parent_path = target_path.parent
        # Only include parent if it's within base path
        try:
            parent_path.relative_to(base_path)
            parent = str(parent_path)
        except ValueError:
            parent = str(base_path)
    
    # List directory entries
    entries: list[DirectoryEntry] = []
    try:
        for entry in sorted(target_path.iterdir(), key=lambda e: e.name.lower()):
            # Skip hidden files/directories
            if entry.name.startswith('.'):
                continue
            
            entries.append(DirectoryEntry(
                name=entry.name,
                path=str(entry),
                is_dir=entry.is_dir(),
            ))
    except PermissionError:
        raise HTTPException(status_code=403, detail="Permission denied")
    
    return DirectoryListing(
        path=str(target_path),
        parent=parent,
        entries=entries,
    )
