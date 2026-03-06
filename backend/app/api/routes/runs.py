"""Runs API: trigger run, list runs, get run by id."""

from typing import List

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.database import get_db
from app.db.models import PipelineConfig, Run
from app.orchestration.run_manager import RunManager
from app.schemas.run import RunCreate, RunOut, RunStatus

router = APIRouter()


def _run_to_out(r: Run) -> RunOut:
    return RunOut(
        id=r.id,
        pipeline_name=r.pipeline_name,
        pipeline_description=getattr(r, "pipeline_description", None),
        status=RunStatus(r.status),
        started_at=r.started_at,
        finished_at=r.finished_at,
        trigger=r.trigger,
        agent_results=r.agent_results,
        findings_count=getattr(r, "findings_count", None) or 0,
        digest_id=r.digest.id if r.digest else None,
        error_message=r.error_message,
        created_at=r.created_at,
    )


@router.post("/", response_model=RunOut)
async def trigger_run(
    background_tasks: BackgroundTasks,
    body: RunCreate = RunCreate(trigger="manual"),
    db: AsyncSession = Depends(get_db),
):
    """Trigger a manual run. Returns run record (status pending/running). Pipeline runs in background."""
    if body.save_config and body.pipeline_name and body.config_json:
        existing = await db.execute(
            select(PipelineConfig).where(PipelineConfig.pipeline_name == body.pipeline_name)
        )
        pc = existing.scalar_one_or_none()
        if pc:
            pc.config_json = body.config_json
            pc.pipeline_description = body.pipeline_description
        else:
            pc = PipelineConfig(
                pipeline_name=body.pipeline_name,
                pipeline_description=body.pipeline_description,
                config_json=body.config_json,
            )
            db.add(pc)
        await db.flush()

    manager = RunManager()
    run_id, config = await manager.start_run(
        trigger=body.trigger,
        pipeline_name=body.pipeline_name,
        pipeline_description=body.pipeline_description,
        config_override=body.config_json,
        use_yaml=body.use_yaml,
    )
    background_tasks.add_task(manager._execute_run, run_id, config)
    result = await db.execute(
        select(Run).options(selectinload(Run.digest)).where(Run.id == run_id)
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return _run_to_out(run)


@router.get("/", response_model=List[RunOut])
async def list_runs(
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """List recent runs."""
    result = await db.execute(
        select(Run)
        .options(selectinload(Run.digest))
        .order_by(Run.id.desc())
        .limit(limit)
    )
    runs = result.scalars().all()
    return [_run_to_out(r) for r in runs]


@router.get("/pipeline-names", response_model=List[str])
async def list_pipeline_names(db: AsyncSession = Depends(get_db)):
    """Return distinct pipeline names that have been used in past runs."""
    result = await db.execute(
        select(Run.pipeline_name)
        .where(Run.pipeline_name.isnot(None))
        .distinct()
        .order_by(Run.pipeline_name)
    )
    return [row[0] for row in result.all() if row[0]]


@router.get("/{run_id}", response_model=RunOut)
async def get_run(
    run_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get run by id."""
    result = await db.execute(
        select(Run).options(selectinload(Run.digest)).where(Run.id == run_id)
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return _run_to_out(run)
