"""Log entry schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class LogEntryOut(BaseModel):
    id: int
    run_id: int
    timestamp: datetime
    level: str
    logger_name: Optional[str] = None
    message: str

    class Config:
        from_attributes = True
