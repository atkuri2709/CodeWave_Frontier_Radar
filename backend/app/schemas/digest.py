"""Digest (PDF report) schemas."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class DigestOut(BaseModel):
    """Digest as returned from API."""

    id: int
    run_id: int
    pdf_path: Optional[str] = None
    executive_summary: Optional[str] = None
    top_finding_ids: List[int] = []
    recipients: List[str] = []
    sent_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True
