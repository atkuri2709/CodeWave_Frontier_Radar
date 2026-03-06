"""Source (URL / feed) schemas for CRUD."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, HttpUrl


class SourceCreate(BaseModel):
    """Create a source."""

    url: str
    agent_id: str  # competitors | model_providers | research | hf_benchmarks
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
    url: str
    agent_id: str
    name: Optional[str] = None
    rss_feed: Optional[str] = None
    rate_limit: Optional[float] = None
    include_rules: List[str] = []
    exclude_rules: List[str] = []
    enabled: bool
    created_at: Optional[str] = None

    class Config:
        from_attributes = True
