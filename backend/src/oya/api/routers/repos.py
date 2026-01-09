"""Repository management endpoints."""

import os
import uuid
from pathlib import Path
from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException

from oya.api.deps import (
    get_repo,
    get_db,
    get_settings,
    get_workspace_base_path,
    validate_workspace_path,
    _reset_db_instance,
    _reset_vectorstore_instance,
)
from oya.api.schemas import RepoStatus, JobCreated, WorkspaceSwitch, WorkspaceSwitchResponse
from oya.repo.git_repo import GitRepo
from oya.db.connection import Database
from oya.config import Settings, load_settings
from oya.generation.orchestrator import GenerationProgress
from oya.workspace import initialize_workspace

router = APIRouter(prefix="/api/repos", tags=["repos"])


def _build_repo_status(workspace_path: Path) -> RepoStatus:
    """Build RepoStatus for a workspace path.
    
    Args:
        workspace_path: Path to the workspace directory.
        
    Returns:
        RepoStatus with git info if available, or uninitialized status.
    """
    try:
        repo = GitRepo(workspace_path)
        head_commit = repo.get_head_commit()
        commit = repo._repo.head.commit
        return RepoStatus(
            path=str(repo.path),
            head_commit=head_commit,
            head_message=commit.message.strip() if commit else None,
            branch=repo.get_current_branch(),
            initialized=True,
        )
    except Exception:
        return RepoStatus(
            path=str(workspace_path),
            head_commit=None,
            head_message=None,
            branch=None,
            initialized=False,
        )


@router.get("/status", response_model=RepoStatus)
async def get_repo_status(
    settings: Settings = Depends(get_settings),
) -> RepoStatus:
    """Get current repository status."""
    return _build_repo_status(settings.workspace_path)


@router.post("/init", response_model=JobCreated, status_code=202)
async def init_repo(
    background_tasks: BackgroundTasks,
    repo: GitRepo = Depends(get_repo),
    db: Database = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> JobCreated:
    """Initialize repository and start wiki generation."""
    job_id = str(uuid.uuid4())

    # Record job in database (7 phases: analysis, files, directories, synthesis, architecture, overview, workflows)
    db.execute(
        """
        INSERT INTO generations (id, type, status, started_at, total_phases)
        VALUES (?, ?, ?, datetime('now'), ?)
        """,
        (job_id, "full", "pending", 7),
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

    # Phase number mapping for progress tracking (bottom-up approach)
    # Order: Analysis → Files → Directories → Synthesis → Architecture → Overview → Workflows
    phase_numbers = {
        "analysis": 1,
        "files": 2,
        "directories": 3,
        "synthesis": 4,
        "architecture": 5,
        "overview": 6,
        "workflows": 7,
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
    load_settings.cache_clear()
    get_settings.cache_clear()
    
    # Reset database and vectorstore instances for new workspace
    _reset_db_instance()
    _reset_vectorstore_instance()
    
    # Initialize workspace for the new path
    initialize_workspace(resolved_path)
    
    # Build and return status for the new workspace
    status = _build_repo_status(resolved_path)
    
    return WorkspaceSwitchResponse(
        status=status,
        message=f"Switched to workspace: {resolved_path}"
    )
