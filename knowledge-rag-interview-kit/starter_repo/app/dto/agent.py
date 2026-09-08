from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ToolRisk(str, Enum):
    READ_ONLY = "read_only"
    INTERNAL_WRITE = "internal_write"
    EXTERNAL_SIDE_EFFECT = "external_side_effect"


class ToolRequest(BaseModel):
    run_id: str
    tool_name: str
    arguments: dict[str, Any]
    risk: ToolRisk
    idempotency_key: str | None = None


class ApprovalDecision(BaseModel):
    approved: bool
    approver_id: str | None = None
    reason: str | None = None


class AgentRunState(BaseModel):
    run_id: str
    goal: str
    step: int = 0
    max_steps: int = Field(default=8, ge=1, le=50)
    completed_action_keys: set[str] = Field(default_factory=set)
    status: str = "running"
