"""Structured finding schema matching agent output contract."""

from datetime import datetime
from typing import Any, List, Optional, Dict, Literal

from pydantic import BaseModel, Field, HttpUrl


class FindingCreate(BaseModel):
    """Input for creating a finding (from agents)."""

    title: str = Field(..., max_length=512)

    date_detected: datetime

    source_url: HttpUrl

    publisher: Optional[str] = None

    # allowed categories
    category: Literal["release", "research", "benchmark"] = "release"

    summary_short: str = Field(..., max_length=1024)

    summary_long: Optional[str] = None

    why_it_matters: Optional[str] = None

    evidence: Optional[str] = None

    confidence: float = Field(ge=0, le=1, default=0.8)

    tags: List[str] = Field(default_factory=list)

    entities: List[str] = Field(default_factory=list)

    diff_hash: Optional[str] = None

    agent_id: str

    raw_metadata: Optional[Dict[str, Any]] = None

    # Fields for snapshot / extraction persistence (not stored on findings table)
    source_config_url: Optional[str] = None
    raw_content: Optional[str] = None
    content_type: Optional[str] = None
    extracted_text: Optional[str] = None


class FindingOut(FindingCreate):
    """Finding as returned from API."""

    id: int
    run_id: Optional[int] = None
    impact_score: Optional[float] = None
    is_sota: Optional[bool] = None
    sota_confidence: Optional[float] = None
    created_at: datetime

    class Config:
        from_attributes = True


class FindingSummary(BaseModel):
    """Lightweight finding for lists."""

    id: int
    title: str
    source_url: HttpUrl
    category: str
    summary_short: str
    confidence: float
    agent_id: str
    publisher: Optional[str] = None
    tags: List[str] = []
    entities: List[str] = []
    impact_score: Optional[float] = None
    is_sota: Optional[bool] = None
    sota_confidence: Optional[float] = None
    created_at: datetime
