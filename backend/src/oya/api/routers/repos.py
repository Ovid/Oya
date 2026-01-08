"""Repository management endpoints."""

import uuid
from fastapi import APIRouter, Depends, BackgroundTasks

from oya.api.deps import get_repo, get_db, get_settings
from oya.api.schemas import RepoStatus, JobCreated
from oya.repo.git_repo import GitRepo
from oya.db.connection import Database
from oya.config import Settings

router = APIRouter(prefix="/api/repos", tags=["repos"])


@router.get("/status", response_model=RepoStatus)
async def get_repo_status(
    settings: Settings = Depends(get_settings),
) -> RepoStatus:
    """Get current repository status."""
    try:
        repo = GitRepo(settings.workspace_path)
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
            path=str(settings.workspace_path),
            head_commit=None,
            head_message=None,
            branch=None,
            initialized=False,
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

    # Record job in database
    db.execute(
        """
        INSERT INTO generations (id, type, status, started_at)
        VALUES (?, ?, ?, datetime('now'))
        """,
        (job_id, "full", "pending"),
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

    try:
        # Update status to running
        db.execute(
            "UPDATE generations SET status = 'running' WHERE id = ?",
            (job_id,),
        )
        db.commit()

        # Create orchestrator and run
        llm = LLMClient()
        orchestrator = GenerationOrchestrator(
            llm_client=llm,
            repo=repo,
            db=db,
            wiki_path=settings.wiki_path,
        )

        await orchestrator.run()

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
