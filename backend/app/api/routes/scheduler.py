"""Scheduler API: CRUD for scheduled jobs + status/trigger."""

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db.models import ScheduledJob
from app.orchestration.scheduler import (
    get_scheduler_status,
    restart_scheduler,
)
from app.schemas.run import ScheduledJobCreate, ScheduledJobOut, ScheduledJobUpdate

router = APIRouter()


@router.get("/", response_model=List[ScheduledJobOut])
async def list_scheduled_jobs(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ScheduledJob).order_by(ScheduledJob.id.desc())
    )
    return result.scalars().all()


@router.post("/", response_model=ScheduledJobOut)
async def create_scheduled_job(
    body: ScheduledJobCreate,
    db: AsyncSession = Depends(get_db),
):
    existing = await db.execute(
        select(ScheduledJob).where(ScheduledJob.scheduler_name == body.scheduler_name)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail=f"Schedule '{body.scheduler_name}' already exists",
        )
    job = ScheduledJob(
        pipeline_name=body.pipeline_name,
        scheduler_name=body.scheduler_name,
        frequency=body.frequency,
        run_time=body.run_time,
        timezone=body.timezone or "UTC",
        start_date=body.start_date,
        end_date=body.end_date,
        start_time=body.start_time,
        end_time=body.end_time,
        interval_minutes=body.interval_minutes,
        enabled=body.enabled,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    restart_scheduler()
    return job


@router.get("/status")
async def scheduler_status():
    return get_scheduler_status()


@router.patch("/{job_id}", response_model=ScheduledJobOut)
async def update_scheduled_job(
    job_id: int,
    body: ScheduledJobUpdate,
    db: AsyncSession = Depends(get_db),
):
    job = await db.get(ScheduledJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Scheduled job not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(job, field, value)
    await db.commit()
    await db.refresh(job)
    restart_scheduler()
    return job


@router.delete("/{job_id}")
async def delete_scheduled_job(
    job_id: int,
    db: AsyncSession = Depends(get_db),
):
    job = await db.get(ScheduledJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Scheduled job not found")
    await db.delete(job)
    await db.commit()
    restart_scheduler()
    return {"ok": True, "deleted": job_id}


@router.post("/restart")
async def do_restart():
    restart_scheduler()
    return get_scheduler_status()
