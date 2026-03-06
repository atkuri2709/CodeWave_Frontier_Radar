"""Analytics API: SOTA Watch and Entity Heatmap endpoints."""

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.services.analytics_service import get_entity_heatmap, get_sota_findings

router = APIRouter()


@router.get("/sota-watch")
async def sota_watch(
    limit: int = Query(20, ge=1, le=100, description="Max SOTA findings to return"),
    db: AsyncSession = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Return the most recent findings that claim state-of-the-art results."""
    return await get_sota_findings(db, limit=limit)


@router.get("/entity-heatmap")
async def entity_heatmap(
    days: int = Query(7, ge=1, le=90, description="Look-back window in days"),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Return entity-vs-topic frequency matrix for the heatmap visualization."""
    return await get_entity_heatmap(db, days=days)
