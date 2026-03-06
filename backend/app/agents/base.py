"""Shared agent interface: input (run_id, config, since) -> output (findings)."""

from datetime import datetime
from typing import Any, Dict, List

from pydantic import BaseModel

from app.schemas.finding import FindingCreate


class AgentContext(BaseModel):
    run_id: int
    agent_config: Dict[str, Any]
    since_timestamp: datetime | None = None


class AgentResult(BaseModel):
    agent_id: str
    findings: List[FindingCreate] = []
    status: str = "success"  # success | partial | failed
    error_message: str | None = None
    pages_processed: int = 0


class BaseAgent:
    """Base class for all crawler and digest agents."""

    agent_id: str = "base"

    async def run(self, context: AgentContext) -> AgentResult:
        """Override in subclasses. Produce findings from config and since_timestamp."""
        raise NotImplementedError
