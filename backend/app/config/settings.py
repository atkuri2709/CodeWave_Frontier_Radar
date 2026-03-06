"""Application settings loaded from environment and config files."""

from functools import lru_cache
from pathlib import Path
from typing import List, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App
    app_name: str = "Frontier AI Radar"
    debug: bool = False
    config_path: Path = Field(
        default=Path("config/radar.yaml"), description="Path to YAML config"
    )

    # Database: local SQLite only (file in backend/data/)
    database_url: str = "sqlite+aiosqlite:///./data/radar.db"

    # Crawling
    verify_ssl: bool = True  # Set False for local dev if you get SSL certificate errors
    default_rate_limit_per_domain: float = 1.0  # requests per second
    max_pages_per_domain: int = 50
    request_timeout_seconds: int = 30
    user_agent: str = "FrontierAIRadar/1.0 (Research; +https://github.com/radar)"

    # LLM / Summarization: try providers in order; on 429 try next
    llm_provider_order: str = "openai,claude,grok,gemini"  # first available key wins
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4o-mini"
    anthropic_api_key: Optional[str] = None
    anthropic_model: str = "claude-3-5-haiku-20241022"
    grok_api_key: Optional[str] = (
        None  # xAI API key (console.x.ai); OpenAI-compatible API
    )
    grok_model: str = "grok-2-1212"  # or grok-beta
    gemini_api_key: Optional[str] = None
    gemini_model: str = "gemini-2.0-flash"
    gemini_rate_limit_delay_seconds: float = (
        5.0  # delay between Gemini calls (free tier ~15 RPM)
    )
    gemini_max_concurrent: int = 1  # avoid 429: one Gemini request at a time
    gemini_429_retry_delays: Optional[List[float]] = (
        None  # if set, overrides exponential backoff for Gemini 429
    )
    summarization_max_tokens: int = 1500
    # Throttle: minimum seconds between any two summarization API calls (reduces 429 when agents run in parallel)
    summarization_delay_seconds: float = 2.0
    # 429 retries: exponential backoff 2^attempt seconds, max attempts (OpenAI/Claude/Gemini)
    summarization_429_max_retries: int = 5
    summarization_429_base_seconds: float = 2.0  # wait base^attempt, capped at 60s
    # Cache: skip LLM call when content unchanged (keyed by content_hash or url+text)
    summary_cache_max_entries: int = 500
    # Run manager: max agents running at once (2 = less concurrent summarization load)
    agent_max_concurrent: int = 2

    # Email — SMTP (primary) or Mailgun (fallback)
    smtp_host: Optional[str] = None
    smtp_port: int = 587
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_from: Optional[str] = None
    email_recipients: List[str] = Field(default_factory=list)

    # Mailgun (used when SMTP fails or isn't configured)
    mailgun_api_key: Optional[str] = None
    mailgun_domain: Optional[str] = None
    mailgun_from: Optional[str] = None

    # Storage (optional S3; local for hackathon)
    storage_backend: str = "local"
    local_storage_path: Path = Field(
        default=Path("storage"), description="Local PDF/digest storage"
    )
    s3_bucket: Optional[str] = None

    # Dashboard (for email links)
    dashboard_base_url: str = "http://localhost:3000"

    # CORS
    cors_origins: List[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "*"]
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
