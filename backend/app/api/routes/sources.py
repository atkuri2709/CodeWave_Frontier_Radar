"""Sources CRUD API."""

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db.models import Source
from app.schemas.source import SourceCreate, SourceOut, SourceUpdate
from app.utils.agent_detection import detect_agent

logger = logging.getLogger(__name__)

router = APIRouter()

DEFAULT_KEYWORDS = {
    "competitors": [
        "release",
        "changelog",
        "update",
        "launch",
        "GA",
        "beta",
        "API",
        "model",
        "feature",
        "version",
    ],
    "model_providers": [
        "model",
        "API",
        "pricing",
        "safety",
        "release",
        "benchmark",
        "context",
        "tool use",
        "agents",
    ],
    "research": [
        "benchmark",
        "eval",
        "agent",
        "multimodal",
        "safety",
        "alignment",
        "llm",
        "transformer",
    ],
    "hf_benchmarks": [
        "leaderboard",
        "benchmark",
        "SOTA",
        "evaluation",
        "ranking",
        "model",
    ],
}


@router.post("/", response_model=SourceOut)
async def create_source(
    body: SourceCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a source. Auto-detects agent from URL when agent_id is omitted."""
    cleaned = body.url.strip()
    if not cleaned:
        raise HTTPException(status_code=400, detail="URL is required")
    agent_id = body.agent_id or detect_agent(cleaned)
    keywords = body.keywords if body.keywords else DEFAULT_KEYWORDS.get(agent_id, [])
    s = Source(
        pipeline_id=body.pipeline_id,
        url=cleaned,
        agent_id=agent_id,
        name=body.name,
        rss_feed=body.rss_feed,
        selectors=body.selectors,
        keywords=keywords,
        rate_limit=body.rate_limit,
        include_rules=body.include_rules,
        exclude_rules=body.exclude_rules,
        enabled=body.enabled,
        extra_config=body.extra_config,
    )
    db.add(s)
    await db.flush()
    await db.refresh(s)
    return _source_out(s)


class AgentDetectionResult(BaseModel):
    url: str
    agent_id: str


@router.get("/detect-agent", response_model=AgentDetectionResult)
async def detect_agent_for_url(url: str = Query(..., min_length=1)):
    """Auto-detect the best agent for a given URL."""
    agent_id = detect_agent(url.strip())
    return AgentDetectionResult(url=url.strip(), agent_id=agent_id)


def _source_out(s: Source) -> SourceOut:
    return SourceOut(
        id=s.id,
        pipeline_id=s.pipeline_id,
        url=s.url,
        agent_id=s.agent_id,
        name=s.name,
        rss_feed=s.rss_feed,
        rate_limit=s.rate_limit,
        include_rules=s.include_rules or [],
        exclude_rules=s.exclude_rules or [],
        enabled=s.enabled,
        created_at=s.created_at if s.created_at else None,
    )


@router.get("/", response_model=List[SourceOut])
async def list_sources(
    agent_id: str | None = None,
    pipeline_id: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    q = select(Source)
    if agent_id:
        q = q.where(Source.agent_id == agent_id)
    if pipeline_id is not None:
        q = q.where(Source.pipeline_id == pipeline_id)
    result = await db.execute(q.order_by(Source.id.desc()))
    return [_source_out(s) for s in result.scalars().all()]


@router.get("/{source_id}", response_model=SourceOut)
async def get_source(
    source_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Source).where(Source.id == source_id))
    s = result.scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="Source not found")
    return _source_out(s)


@router.patch("/{source_id}", response_model=SourceOut)
async def update_source(
    source_id: int,
    body: SourceUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Source).where(Source.id == source_id))
    s = result.scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="Source not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(s, field, value)
    await db.flush()
    await db.refresh(s)
    return _source_out(s)


@router.delete("/{source_id}", status_code=204)
async def delete_source(
    source_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Source).where(Source.id == source_id))
    s = result.scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="Source not found")
    await db.delete(s)
    await db.flush()
