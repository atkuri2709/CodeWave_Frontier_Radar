"""Pipeline Configs API: saved JSON/YAML pipeline configurations."""

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.database import get_db
from app.db.models import PipelineConfig
from app.schemas.run import PipelineConfigCreate, PipelineConfigOut, PipelineConfigUpdate

router = APIRouter()


@router.get("/", response_model=List[PipelineConfigOut])
async def list_pipeline_configs(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(PipelineConfig).order_by(PipelineConfig.id.desc()))
    return result.scalars().all()


@router.post("/", response_model=PipelineConfigOut)
async def create_pipeline_config(
    body: PipelineConfigCreate,
    db: AsyncSession = Depends(get_db),
):
    pc = PipelineConfig(
        pipeline_name=body.pipeline_name,
        pipeline_description=body.pipeline_description,
        config_json=body.config_json,
        enabled=body.enabled,
    )
    db.add(pc)
    await db.flush()
    await db.refresh(pc)
    return pc


@router.get("/{config_id}", response_model=PipelineConfigOut)
async def get_pipeline_config(
    config_id: int,
    db: AsyncSession = Depends(get_db),
):
    pc = await db.get(PipelineConfig, config_id)
    if not pc:
        raise HTTPException(status_code=404, detail="Pipeline config not found")
    return pc


@router.patch("/{config_id}", response_model=PipelineConfigOut)
async def update_pipeline_config(
    config_id: int,
    body: PipelineConfigUpdate,
    db: AsyncSession = Depends(get_db),
):
    pc = await db.get(PipelineConfig, config_id)
    if not pc:
        raise HTTPException(status_code=404, detail="Pipeline config not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(pc, field, value)
    await db.flush()
    await db.refresh(pc)
    return pc


@router.delete("/{config_id}")
async def delete_pipeline_config(
    config_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(PipelineConfig)
        .options(selectinload(PipelineConfig.sources))
        .where(PipelineConfig.id == config_id)
    )
    pc = result.scalar_one_or_none()
    if not pc:
        raise HTTPException(status_code=404, detail="Pipeline config not found")
    await db.delete(pc)
    await db.flush()
    return {"ok": True, "deleted": config_id}
