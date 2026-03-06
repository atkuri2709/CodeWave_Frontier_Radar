"""Digests API: list, get, download PDF."""

from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.database import get_db
from app.db.models import Digest
from app.schemas.digest import DigestOut

router = APIRouter()


@router.get("/", response_model=List[DigestOut])
async def list_digests(
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Digest).order_by(Digest.id.desc()).limit(limit))
    rows = result.scalars().all()
    return [
        DigestOut(
            id=d.id,
            run_id=d.run_id,
            pdf_path=d.pdf_path,
            executive_summary=d.executive_summary,
            top_finding_ids=d.top_finding_ids or [],
            recipients=d.recipients or [],
            sent_at=d.sent_at,
            created_at=d.created_at,
        )
        for d in rows
    ]


@router.get("/{digest_id}", response_model=DigestOut)
async def get_digest(
    digest_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Digest).where(Digest.id == digest_id))
    d = result.scalar_one_or_none()
    if not d:
        raise HTTPException(status_code=404, detail="Digest not found")
    return DigestOut(
        id=d.id,
        run_id=d.run_id,
        pdf_path=d.pdf_path,
        executive_summary=d.executive_summary,
        top_finding_ids=d.top_finding_ids or [],
        recipients=d.recipients or [],
        sent_at=d.sent_at,
        created_at=d.created_at,
    )


@router.get("/{digest_id}/download")
async def download_digest_pdf(
    digest_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Digest).where(Digest.id == digest_id))
    d = result.scalar_one_or_none()
    if not d or not d.pdf_path:
        raise HTTPException(status_code=404, detail="Digest or PDF not found")
    path = Path(d.pdf_path)
    if not path.is_absolute():
        path = Path.cwd() / path
    # PDF may be under local_storage_path if path was stored as filename only
    if not path.exists():
        storage = Path(get_settings().local_storage_path)
        if not storage.is_absolute():
            storage = Path.cwd() / storage
        path = storage / Path(d.pdf_path).name
    if not path.exists():
        raise HTTPException(status_code=404, detail="PDF file not found on disk")
    return FileResponse(path, filename=path.name, media_type="application/pdf")
