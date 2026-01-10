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
)
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
    """Run wiki generation in background."""
    from oya.generation.orchestrator import GenerationOrchestrator
    from oya.llm.client import LLMClient
    from oya.indexing.service import IndexingService
    from oya.vectorstore.store import VectorStore

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

        # Create orchestrator and run
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
            wiki_path=settings.wiki_path,
            parallel_limit=settings.parallel_file_limit,
        )

        await orchestrator.run(progress_callback=progress_callback)

        # Index wiki content for Q&A search
        db.execute(
            "UPDATE generations SET current_phase = '8:indexing' WHERE id = ?",
            (job_id,),
        )
        db.commit()

        vectorstore = VectorStore(settings.chroma_path)
        indexing_service = IndexingService(
            vectorstore=vectorstore,
            db=db,
            wiki_path=settings.wiki_path,
            meta_path=settings.oyawiki_path / "meta",
        )
        # Clear old index and reindex with new content
        indexing_service.clear_index()
        indexing_service.index_wiki_pages(
            embedding_provider=settings.active_provider,
            embedding_model=settings.active_model,
        )

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
