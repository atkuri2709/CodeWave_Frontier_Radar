"""Run (pipeline execution) and ScheduledJob schemas."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class RunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RunCreate(BaseModel):
    """Trigger a new run."""

    trigger: str = "manual"
    pipeline_name: Optional[str] = None
    pipeline_description: Optional[str] = None
    config_json: Optional[Dict[str, Any]] = None
    save_config: bool = False
    use_yaml: bool = False


class RunOut(BaseModel):
    """Run as returned from API."""

    id: int
    pipeline_name: Optional[str] = None
    pipeline_description: Optional[str] = None
    status: RunStatus
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    trigger: str = "manual"
    agent_results: Optional[Dict[str, Any]] = None
    findings_count: int = 0
    digest_id: Optional[int] = None
    error_message: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# --------------- Scheduled Jobs ---------------


class ScheduledJobCreate(BaseModel):
    pipeline_name: str = Field(..., min_length=1, max_length=256)
    scheduler_name: str = Field(..., min_length=1, max_length=256)
    frequency: str = Field(
        default="daily", pattern=r"^(daily|weekly|monthly|yearly|interval)$"
    )
    run_time: Optional[str] = Field(default="06:30", pattern=r"^\d{1,2}:\d{2}$")
    timezone: Optional[str] = "UTC"
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    start_time: Optional[str] = Field(default=None, pattern=r"^\d{1,2}:\d{2}$")
    end_time: Optional[str] = Field(default=None, pattern=r"^\d{1,2}:\d{2}$")
    interval_minutes: Optional[int] = Field(default=None, ge=1)
    enabled: bool = True


class ScheduledJobUpdate(BaseModel):
    pipeline_name: Optional[str] = Field(default=None, max_length=256)
    scheduler_name: Optional[str] = Field(default=None, max_length=256)
    frequency: Optional[str] = Field(
        default=None, pattern=r"^(daily|weekly|monthly|yearly|interval)$"
    )
    run_time: Optional[str] = Field(default=None, pattern=r"^\d{1,2}:\d{2}$")
    timezone: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    start_time: Optional[str] = Field(default=None, pattern=r"^\d{1,2}:\d{2}$")
    end_time: Optional[str] = Field(default=None, pattern=r"^\d{1,2}:\d{2}$")
    interval_minutes: Optional[int] = Field(default=None, ge=1)
    enabled: Optional[bool] = None


class ScheduledJobOut(BaseModel):
    id: int
    pipeline_name: str
    scheduler_name: str
    frequency: str
    run_time: Optional[str] = None
    timezone: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    interval_minutes: Optional[int] = None
    enabled: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# --------------- Pipeline Configs ---------------


class PipelineConfigCreate(BaseModel):
    pipeline_name: str = Field(..., min_length=1, max_length=256)
    pipeline_description: Optional[str] = None
    config_json: Optional[Dict[str, Any]] = None
    enabled: bool = True


class PipelineConfigUpdate(BaseModel):
    pipeline_name: Optional[str] = Field(default=None, min_length=1, max_length=256)
    pipeline_description: Optional[str] = None
    config_json: Optional[Dict[str, Any]] = None
    enabled: Optional[bool] = None


class PipelineConfigOut(BaseModel):
    id: int
    pipeline_name: str
    pipeline_description: Optional[str] = None
    config_json: Optional[Dict[str, Any]] = None
    enabled: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
