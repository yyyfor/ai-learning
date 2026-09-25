from typing import Literal
from pydantic import BaseModel, Field


class GoldenCase(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    expected_sources: list[str] = Field(min_length=1)
    expected_facts: list[str] = Field(default_factory=list)
    allowed_answer: str = ""
    forbidden_answer: list[str] = Field(default_factory=list)


class EvaluationRequest(BaseModel):
    cases: list[GoldenCase] = Field(min_length=1, max_length=50)
    mode: Literal["bm25", "vector", "hybrid"] = "hybrid"
    top_k: int = Field(default=5, ge=1, le=20)
    rerank: bool = False
    rewrite: bool = False
    judge: bool = True
    baseline_id: str | None = None
    max_drop: float = Field(default=0.05, ge=0, le=1)


class AnswerJudgment(BaseModel):
    answer_relevance: float = Field(ge=0, le=1)
    faithfulness: float = Field(ge=0, le=1)
    correctness: float = Field(ge=0, le=1)
