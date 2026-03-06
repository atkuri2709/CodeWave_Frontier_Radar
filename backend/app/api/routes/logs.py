"""Logs API: retrieve run logs."""

from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db.models import LogEntry
from app.schemas.log import LogEntryOut

router = APIRouter()


@router.get("/{run_id}", response_model=List[LogEntryOut])
async def get_run_logs(
    run_id: int,
    level: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Return all log entries for a specific run, ordered chronologically."""
    q = select(LogEntry).where(LogEntry.run_id == run_id)
    if level:
        q = q.where(LogEntry.level == level.upper())
    q = q.order_by(LogEntry.timestamp.asc())
    result = await db.execute(q)
    return result.scalars().all()
