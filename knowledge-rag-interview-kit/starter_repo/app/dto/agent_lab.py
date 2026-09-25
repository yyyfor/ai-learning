from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SearchArguments(StrictModel):
    query: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=3, ge=1, le=5)


class CalculateArguments(StrictModel):
    expression: str = Field(min_length=1, max_length=200)


class FollowUpArguments(StrictModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=2000)


class ToolResult(StrictModel):
    tool: Literal["search_knowledge", "calculate", "create_follow_up"]
    data: dict[str, Any]


class SearchHit(StrictModel):
    document_id: str
    text: str


class SearchResult(StrictModel):
    hits: list[SearchHit]


class CalculationResult(StrictModel):
    value: float = Field(allow_inf_nan=False)


class FollowUpResult(FollowUpArguments):
    id: str
    run_id: str
    owner: str
    tenant: str
    approved_by: str


class AgentAction(StrictModel):
    tool: Literal["search_knowledge", "calculate", "create_follow_up", "finish"]
    arguments: dict[str, Any] = Field(default_factory=dict)
    answer: str = Field(default="", max_length=5000)


class AgentStart(StrictModel):
    goal: str = Field(min_length=1, max_length=2000)
    max_steps: int = Field(default=6, ge=1, le=12)
    timeout_seconds: int = Field(default=120, ge=5, le=300)
    token_budget: int = Field(default=50000, ge=1000, le=100000)
    cost_budget: float = Field(default=1, gt=0, le=20)
    retries: int = Field(default=1, ge=0, le=1)
    # Optional deterministic prerequisites for tasks that must use evidence/tools.
    required_tools: list[Literal["search_knowledge", "calculate"]] = Field(default_factory=list, max_length=2)


class AgentApproval(StrictModel):
    approved: bool
