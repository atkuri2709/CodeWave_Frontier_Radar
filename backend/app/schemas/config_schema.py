"""Configuration file (YAML) schema for agents and global settings."""

from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class CompetitorDef(BaseModel):
    name: str
    release_urls: List[str] = []
    rss_feeds: List[str] = []
    selectors: Optional[Dict[str, str]] = None
    keywords: List[str] = Field(
        default_factory=lambda: ["release", "changelog", "GA", "beta"]
    )
    domain_rate_limit: Optional[float] = None


class ModelProviderDef(BaseModel):
    name: str
    urls: List[str] = []
    rss_feeds: List[str] = []
    focus: List[str] = Field(
        default_factory=lambda: ["models", "api", "pricing", "safety"]
    )


class ResearchDef(BaseModel):
    arxiv_categories: List[str] = Field(
        default_factory=lambda: ["cs.CL", "cs.LG", "stat.ML"]
    )
    semantic_scholar_queries: List[str] = []
    openreview_venues: List[str] = []
    curated_urls: List[str] = []
    relevance_keywords: List[str] = Field(
        default_factory=lambda: [
            "benchmark",
            "eval",
            "agent",
            "multimodal",
            "safety",
            "alignment",
        ]
    )


class HFBenchmarksDef(BaseModel):
    leaderboards: List[str] = []
    leaderboard_urls: List[str] = (
        []
    )  # Full URLs to fetch (Spaces, dataset viewer, etc.)
    tasks: List[str] = []
    track_new_sota: bool = True


class GlobalConfig(BaseModel):
    run_time: str = "06:30"  # daily run time
    timezone: str = "America/Los_Angeles"
    max_pages_per_domain: int = 50
    default_rate_limit: float = 1.0
    email_recipients: List[str] = []


class AgentsConfig(BaseModel):
    competitors: List[CompetitorDef] = []
    model_providers: List[ModelProviderDef] = []
    research: Optional[ResearchDef] = None
    hf_benchmarks: Optional[HFBenchmarksDef] = None


class RadarConfig(BaseModel):
    """Root config matching config/radar.yaml."""

    global_config: GlobalConfig = Field(default_factory=GlobalConfig, alias="global")
    agents: AgentsConfig = Field(default_factory=AgentsConfig)

    class Config:
        populate_by_name = True


# Alias for agent config passed to agents
AgentConfig = Dict[str, Any]
