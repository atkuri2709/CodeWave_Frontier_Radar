"""Captures log messages during a pipeline run and persists them to the run_logs table."""

import logging
from datetime import datetime, timezone
from typing import List

from app.db.models import LogEntry


class RunLogCollector(logging.Handler):
    """A logging handler that buffers log records for a specific run_id."""

    def __init__(self, run_id: int, level: int = logging.DEBUG):
        super().__init__(level)
        self.run_id = run_id
        self.entries: List[dict] = []

    def emit(self, record: logging.LogRecord):
        try:
            self.entries.append({
                "run_id": self.run_id,
                "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc),
                "level": record.levelname,
                "logger_name": record.name,
                "message": self.format(record),
            })
        except Exception:
            self.handleError(record)

    def get_orm_entries(self) -> List[LogEntry]:
        return [LogEntry(**e) for e in self.entries]
