"""Sources CRUD API."""

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db.models import Source
from app.schemas.source import SourceCreate, SourceOut, SourceUpdate

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
    """Create a source. The url field accepts comma-separated URLs stored together."""
    cleaned = ", ".join(u.strip() for u in body.url.split(",") if u.strip())
    if not cleaned:
        raise HTTPException(status_code=400, detail="At least one URL is required")
    keywords = (
        body.keywords if body.keywords else DEFAULT_KEYWORDS.get(body.agent_id, [])
    )
    s = Source(
        url=cleaned,
        agent_id=body.agent_id,
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


def _source_out(s: Source) -> SourceOut:
    return SourceOut(
        id=s.id,
        url=s.url,
        agent_id=s.agent_id,
        name=s.name,
        rss_feed=s.rss_feed,
        rate_limit=s.rate_limit,
        include_rules=s.include_rules or [],
        exclude_rules=s.exclude_rules or [],
        enabled=s.enabled,
        created_at=s.created_at.isoformat() if s.created_at else None,
    )


@router.get("/", response_model=List[SourceOut])
async def list_sources(
    agent_id: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    q = select(Source)
    if agent_id:
        q = q.where(Source.agent_id == agent_id)
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
    if body.name is not None:
        s.name = body.name
    if body.rss_feed is not None:
        s.rss_feed = body.rss_feed
    if body.selectors is not None:
        s.selectors = body.selectors
    if body.keywords is not None:
        s.keywords = body.keywords
    if body.rate_limit is not None:
        s.rate_limit = body.rate_limit
    if body.include_rules is not None:
        s.include_rules = body.include_rules
    if body.exclude_rules is not None:
        s.exclude_rules = body.exclude_rules
    if body.enabled is not None:
        s.enabled = body.enabled
    if body.extra_config is not None:
        s.extra_config = body.extra_config
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
