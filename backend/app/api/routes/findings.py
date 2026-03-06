"""Findings API: list, filter by multiple dimensions, search, get by id."""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db.models import Finding
from app.schemas.finding import FindingOut, FindingSummary

router = APIRouter()


@router.get("/", response_model=List[FindingSummary])
async def list_findings(
    run_id: Optional[int] = Query(None, description="Filter by run ID"),
    agent_id: Optional[str] = Query(
        None,
        description="Filter by agent (competitors, model_providers, research, hf_benchmarks)",
    ),
    category: Optional[str] = Query(
        None, description="Filter by category (release, research, benchmark)"
    ),
    publisher: Optional[str] = Query(
        None, description="Filter by publisher name (case-insensitive partial match)"
    ),
    tag: Optional[str] = Query(None, description="Filter findings containing this tag"),
    entity: Optional[str] = Query(
        None, description="Filter findings mentioning this entity"
    ),
    search: Optional[str] = Query(
        None, description="Search in title, summary, and why_it_matters"
    ),
    min_confidence: Optional[float] = Query(
        None, ge=0, le=1, description="Minimum confidence score"
    ),
    created_after: Optional[datetime] = Query(
        None, description="Return findings created on or after this ISO datetime"
    ),
    created_before: Optional[datetime] = Query(
        None, description="Return findings created before this ISO datetime"
    ),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    q = select(Finding)

    if run_id is not None:
        q = q.where(Finding.run_id == run_id)
    if agent_id:
        q = q.where(Finding.agent_id == agent_id)
    if category:
        q = q.where(Finding.category == category)
    if publisher:
        q = q.where(Finding.publisher.ilike(f"%{publisher}%"))
    if min_confidence is not None:
        q = q.where(Finding.confidence >= min_confidence)
    if created_after is not None:
        q = q.where(Finding.created_at >= created_after)
    if created_before is not None:
        q = q.where(Finding.created_at < created_before)
    if search:
        pattern = f"%{search}%"
        q = q.where(
            or_(
                Finding.title.ilike(pattern),
                Finding.summary_short.ilike(pattern),
                Finding.why_it_matters.ilike(pattern),
            )
        )
    if tag:
        q = q.where(Finding.tags.contains(tag))
    if entity:
        q = q.where(Finding.entities.contains(entity))

    q = (
        q.order_by(Finding.impact_score.desc().nullslast(), Finding.created_at.desc())
        .offset(offset)
        .limit(limit)
    )

    result = await db.execute(q)
    rows = result.scalars().all()
    return [
        FindingSummary(
            id=f.id,
            title=f.title,
            source_url=f.source_url,
            category=f.category,
            summary_short=f.summary_short,
            confidence=f.confidence,
            agent_id=f.agent_id,
            publisher=f.publisher,
            tags=f.tags or [],
            entities=f.entities or [],
            impact_score=f.impact_score,
            created_at=f.created_at or f.date_detected,
        )
        for f in rows
    ]


@router.get("/{finding_id}", response_model=FindingOut)
async def get_finding(
    finding_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Finding).where(Finding.id == finding_id))
    f = result.scalar_one_or_none()
    if not f:
        raise HTTPException(status_code=404, detail="Finding not found")
    return FindingOut(
        id=f.id,
        run_id=f.run_id,
        title=f.title,
        date_detected=f.date_detected,
        source_url=f.source_url,
        publisher=f.publisher,
        category=f.category,
        summary_short=f.summary_short,
        summary_long=f.summary_long,
        why_it_matters=f.why_it_matters,
        evidence=f.evidence,
        confidence=f.confidence,
        tags=f.tags or [],
        entities=f.entities or [],
        diff_hash=f.diff_hash,
        agent_id=f.agent_id,
        raw_metadata=f.raw_metadata,
        impact_score=f.impact_score,
        created_at=f.created_at,
    )
