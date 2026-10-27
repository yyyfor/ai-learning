"""Small request/response contracts for the local voice lab."""
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class TranscriptSegment(BaseModel):
    start: float
    end: float
    text: str


class TranscriptionResponse(BaseModel):
    text: str
    language: str
    duration_seconds: float
    processing_seconds: float
    segments: list[TranscriptSegment]


class VoiceSummaryRequest(BaseModel):
    transcript: str = Field(min_length=1, max_length=24000)
    language: Literal["auto", "en", "zh"] = "auto"

    @field_validator("transcript")
    @classmethod
    def not_blank(cls, value):
        if not value.strip():
            raise ValueError("Add some transcript text first")
        return value.strip()


class ActionItem(BaseModel):
    task: str
    owner: str | None
    due: str | None
    evidence: str = Field(description="A verbatim transcript quote supporting this explicit task")


class MeetingSummary(BaseModel):
    overview: str
    key_points: list[str]
    decisions: list[str]
    action_items: list[ActionItem]
    open_questions: list[str]


class VoiceSummaryResponse(BaseModel):
    summary: MeetingSummary
    model: str
    parts: int
    warnings: list[str] = Field(default_factory=list)
