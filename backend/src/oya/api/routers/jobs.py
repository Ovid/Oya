"""Job management endpoints."""

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from oya.api.deps import get_db
from oya.db.connection import Database

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


class JobStatus(BaseModel):
    """Job status response."""
    job_id: str
    type: str
    status: str
    started_at: datetime | None = None
    completed_at: datetime | None = None
    current_phase: str | None = None
    total_phases: int | None = None
    error_message: str | None = None


@router.get("", response_model=list[JobStatus])
async def list_jobs(
    db: Database = Depends(get_db),
    limit: int = 20,
) -> list[JobStatus]:
    """List recent generation jobs."""
    cursor = db.execute(
        """
        SELECT id, type, status, started_at, completed_at,
               current_phase, total_phases, error_message
        FROM generations
        ORDER BY started_at DESC
        LIMIT ?
        """,
        (limit,),
    )

    jobs = []
    for row in cursor.fetchall():
        jobs.append(JobStatus(
            job_id=row["id"],
            type=row["type"],
            status=row["status"],
            started_at=_parse_datetime(row["started_at"]),
            completed_at=_parse_datetime(row["completed_at"]),
            current_phase=row["current_phase"],
            total_phases=row["total_phases"],
            error_message=row["error_message"],
        ))

    return jobs


@router.get("/{job_id}", response_model=JobStatus)
async def get_job(
    job_id: str,
    db: Database = Depends(get_db),
) -> JobStatus:
    """Get status of a specific job."""
    cursor = db.execute(
        """
        SELECT id, type, status, started_at, completed_at,
               current_phase, total_phases, error_message
        FROM generations
        WHERE id = ?
        """,
        (job_id,),
    )

    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    return JobStatus(
        job_id=row["id"],
        type=row["type"],
        status=row["status"],
        started_at=_parse_datetime(row["started_at"]),
        completed_at=_parse_datetime(row["completed_at"]),
        current_phase=row["current_phase"],
        total_phases=row["total_phases"],
        error_message=row["error_message"],
    )


def _parse_datetime(value: str | None) -> datetime | None:
    """Parse SQLite datetime string."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace(" ", "T"))
    except ValueError:
        return None
