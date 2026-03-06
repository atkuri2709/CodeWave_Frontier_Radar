"""SQLAlchemy models for sources, snapshots, extractions, findings, runs, digests."""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, Boolean, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.database import Base


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    url: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    agent_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    rss_feed: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    selectors: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    keywords: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    rate_limit: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    include_rules: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    exclude_rules: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    extra_config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    last_run_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    findings: Mapped[list["Finding"]] = relationship(
        back_populates="source_rel", foreign_keys="Finding.source_id"
    )


class Snapshot(Base):
    __tablename__ = "snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    url: Mapped[str] = mapped_column(String(2048), nullable=False, index=True)
    source_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("sources.id"), nullable=True
    )
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    raw_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)


class Extraction(Base):
    __tablename__ = "extractions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    url: Mapped[str] = mapped_column(String(2048), nullable=False, index=True)
    snapshot_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("snapshots.id"), nullable=True
    )
    title: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    published_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    extracted_metadata: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True
    )  # 'metadata' is reserved by SQLAlchemy
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class PipelineConfig(Base):
    __tablename__ = "pipeline_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pipeline_name: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    pipeline_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    config_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pipeline_name: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    pipeline_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    trigger: Mapped[str] = mapped_column(String(32), default="manual")
    agent_results: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    findings_count: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, default=0
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    findings: Mapped[list["Finding"]] = relationship(back_populates="run")
    digest: Mapped[Optional["Digest"]] = relationship(
        back_populates="run", uselist=False
    )


class ScheduledJob(Base):
    __tablename__ = "scheduled_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pipeline_name: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    scheduler_name: Mapped[str] = mapped_column(
        String(256), nullable=False, unique=True
    )
    frequency: Mapped[str] = mapped_column(String(16), default="daily")
    run_time: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    timezone: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    start_date: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    end_date: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    start_time: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    end_time: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    interval_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Finding(Base):
    __tablename__ = "findings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("runs.id"), nullable=True, index=True
    )
    source_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("sources.id"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    date_detected: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    source_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    publisher: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    category: Mapped[str] = mapped_column(String(64), default="release")
    summary_short: Mapped[str] = mapped_column(String(1024), nullable=False)
    summary_long: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    why_it_matters: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    evidence: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.8)
    tags: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    entities: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    diff_hash: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, index=True
    )
    agent_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    raw_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    impact_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    run: Mapped[Optional["Run"]] = relationship(back_populates="findings")
    source_rel: Mapped[Optional["Source"]] = relationship(
        back_populates="findings", foreign_keys=[source_id]
    )


class Digest(Base):
    __tablename__ = "digests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("runs.id"), nullable=False, unique=True
    )
    pdf_path: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    executive_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    top_finding_ids: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    recipients: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    sent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    run: Mapped["Run"] = relationship(back_populates="digest")


class LogEntry(Base):
    __tablename__ = "run_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("runs.id"), nullable=False, index=True
    )
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    level: Mapped[str] = mapped_column(String(16), nullable=False, default="INFO")
    logger_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)

    run: Mapped["Run"] = relationship()


class EmailRecipient(Base):
    """Email addresses that receive the daily digest (stored in DB)."""

    __tablename__ = "email_recipients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(256), nullable=False, unique=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
