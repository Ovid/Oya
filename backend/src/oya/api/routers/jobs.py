"""Job management endpoints."""

import asyncio
import json
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
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
    cancelled_at: datetime | None = None
    current_phase: str | None = None
    total_phases: int | None = None
    error_message: str | None = None


class JobCancelled(BaseModel):
    """Job cancellation response."""
    job_id: str
    status: str
    cancelled_at: datetime


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


@router.post("/{job_id}/cancel", response_model=JobCancelled)
async def cancel_job(
    job_id: str,
    db: Database = Depends(get_db),
) -> JobCancelled:
    """Cancel a running job."""
    cursor = db.execute(
        "SELECT id, status FROM generations WHERE id = ?",
        (job_id,),
    )
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    if row["status"] not in ("pending", "running"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel job with status: {row['status']}"
        )

    # Update job status to cancelled
    db.execute(
        """
        UPDATE generations
        SET status = 'cancelled', completed_at = datetime('now')
        WHERE id = ?
        """,
        (job_id,),
    )
    db.commit()

    return JobCancelled(
        job_id=job_id,
        status="cancelled",
        cancelled_at=datetime.now(),
    )


def _parse_datetime(value: str | None) -> datetime | None:
    """Parse SQLite datetime string."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace(" ", "T"))
    except ValueError:
        return None


@router.get("/{job_id}/stream")
async def stream_job_progress(
    job_id: str,
    db: Database = Depends(get_db),
):
    """Stream job progress via SSE."""
    # Verify job exists
    cursor = db.execute("SELECT id, status FROM generations WHERE id = ?", (job_id,))
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    async def event_generator():
        """Generate SSE events for job progress."""
        while True:
            # Get current job status
            cursor = db.execute(
                """
                SELECT id, status, current_phase, total_phases,
                       current_step, total_steps, error_message
                FROM generations WHERE id = ?
                """,
                (job_id,),
            )
            row = cursor.fetchone()

            if not row:
                break

            status = row["status"]

            # Send progress event
            event_data = {
                "job_id": row["id"],
                "status": status,
                "phase": row["current_phase"],
                "total_phases": row["total_phases"],
                "current_step": row["current_step"],
                "total_steps": row["total_steps"],
            }

            if status == "completed":
                yield f"event: complete\ndata: {json.dumps(event_data)}\n\n"
                break
            elif status == "failed":
                event_data["error"] = row["error_message"]
                yield f"event: error\ndata: {json.dumps(event_data)}\n\n"
                break
            elif status == "cancelled":
                yield f"event: cancelled\ndata: {json.dumps(event_data)}\n\n"
                break
            else:
                yield f"event: progress\ndata: {json.dumps(event_data)}\n\n"

            # Poll every 500ms
            await asyncio.sleep(0.5)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
