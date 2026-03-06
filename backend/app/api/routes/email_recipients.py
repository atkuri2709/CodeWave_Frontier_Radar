"""Email recipients API: get/set list of emails (stored in DB) to receive the digest."""

from typing import List

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db.models import EmailRecipient

router = APIRouter()


@router.get("", response_model=List[str])
async def list_email_recipients(db: AsyncSession = Depends(get_db)):
    """Return the list of email addresses that receive the digest."""
    result = await db.execute(select(EmailRecipient.email).order_by(EmailRecipient.id))
    return [row[0] for row in result.all()]


@router.put("", response_model=List[str])
async def update_email_recipients(
    emails: List[str] = Body(..., embed=False),
    db: AsyncSession = Depends(get_db),
):
    """Replace the list of email addresses (saved to DB). Commits so data persists across requests."""
    cleaned = list(dict.fromkeys(e.strip() for e in emails if e and str(e).strip()))
    try:
        await db.execute(delete(EmailRecipient))
        for email in cleaned:
            db.add(EmailRecipient(email=email))
        await db.commit()
        result = await db.execute(
            select(EmailRecipient.email).order_by(EmailRecipient.id)
        )
        return [row[0] for row in result.all()]
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
