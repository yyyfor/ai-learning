from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class AssetMetadata(BaseModel):
    source_uri: str = Field(min_length=1, max_length=2000)
    source_owner: str = Field(min_length=1, max_length=200)
    business_owner: str = Field(min_length=1, max_length=200)
    effective_date: date
    expiry_date: date | None = None
    security_level: int = Field(default=0, ge=0, le=3)
    confidence_score: float = Field(default=1, ge=0, le=1)

    @model_validator(mode="after")
    def dates(self):
        if self.expiry_date and self.expiry_date < self.effective_date:
            raise ValueError("expiry_date must not precede effective_date")
        return self


class Transition(BaseModel):
    action: Literal["validate", "approve", "publish", "deprecate"]
    reason: str = Field(min_length=1, max_length=1000)


class Rollback(BaseModel):
    version: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=1000)


class CitationCheck(BaseModel):
    document_id: str
    text: str = Field(min_length=1, max_length=10000)
    version: int | None = None
