"""Source (URL / feed) schemas for CRUD."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, HttpUrl


class SourceCreate(BaseModel):
    """Create a source linked to a pipeline."""

    pipeline_id: Optional[int] = None
    url: str
    agent_id: Optional[str] = None  # auto-detected from URL when omitted
    name: Optional[str] = None
    rss_feed: Optional[str] = None
    selectors: Optional[Dict[str, str]] = None
    keywords: List[str] = []
    rate_limit: Optional[float] = None
    include_rules: List[str] = []
    exclude_rules: List[str] = []
    enabled: bool = True
    extra_config: Optional[Dict[str, Any]] = None


class SourceUpdate(BaseModel):
    """Update a source (partial). All fields optional — only provided fields are updated."""

    pipeline_id: Optional[int] = None
    url: Optional[str] = None
    agent_id: Optional[str] = None
    name: Optional[str] = None
    rss_feed: Optional[str] = None
    selectors: Optional[Dict[str, str]] = None
    keywords: Optional[List[str]] = None
    rate_limit: Optional[float] = None
    include_rules: Optional[List[str]] = None
    exclude_rules: Optional[List[str]] = None
    enabled: Optional[bool] = None
    extra_config: Optional[Dict[str, Any]] = None


class SourceOut(BaseModel):
    """Source as returned from API."""

    id: int
    pipeline_id: Optional[int] = None
    url: str
    agent_id: str
    name: Optional[str] = None
    rss_feed: Optional[str] = None
    rate_limit: Optional[float] = None
    include_rules: List[str] = []
    exclude_rules: List[str] = []
    enabled: bool
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True
