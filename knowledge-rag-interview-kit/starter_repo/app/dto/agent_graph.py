from typing import Literal

from pydantic import Field

from app.dto.agent_lab import FollowUpArguments, StrictModel


class AgentGraphStart(StrictModel):
    goal: str = Field(min_length=1, max_length=2000)


class AgentGraphApproval(StrictModel):
    approved: bool


class Proposal(StrictModel):
    """The ONE thing the model decides in the Lab 12 graph.

    Flat and all-required on purpose. Local grammar-constrained decoding
    (Ollama/llama.cpp) fails to build a grammar for nested nullable objects or
    long maxLength bounds, and optional fields are simply skipped by small
    models. Field order is generation order: evidence first, then the answer.
    """

    evidence: list[int] = Field(max_length=5)   # Ids (1, 2, ...) of supporting evidence items.
    answer: str = Field(min_length=1, max_length=1000)
    action: Literal["answer_only", "create_follow_up"]
    follow_up_title: str = Field(max_length=200)
    follow_up_description: str = Field(max_length=1000)

    def to_state(self) -> dict:
        """Graph-state shape: the follow-up exists only when both fields are filled."""
        follow_up = None
        if self.follow_up_title.strip() and self.follow_up_description.strip():
            follow_up = FollowUpArguments(title=self.follow_up_title.strip(),
                                          description=self.follow_up_description.strip()).model_dump()
        return {"action": self.action, "answer": self.answer, "evidence": self.evidence,
                "follow_up": follow_up}
