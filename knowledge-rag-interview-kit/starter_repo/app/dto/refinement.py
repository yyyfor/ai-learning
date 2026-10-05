from pydantic import BaseModel, Field


class EntityIn(BaseModel):
    id: str = Field(min_length=1, max_length=200)
    name: str = Field(min_length=1, max_length=500)
    type: str = Field(min_length=1, max_length=100)
    source: str = ""
    identifiers: dict[str, str] = Field(default_factory=dict)
    attributes: dict[str, str] = Field(default_factory=dict)
    authority: int = Field(default=0, ge=0, le=10)


class ResolveRequest(BaseModel):
    records: list[EntityIn] = Field(min_length=1, max_length=2000)
    # Normalized name -> canonical alias key, maintained by domain experts.
    aliases: dict[str, str] = Field(default_factory=dict)


class DuplicatesRequest(BaseModel):
    documents: dict[str, str] = Field(min_length=1, max_length=500)
    threshold: float = Field(default=0.8, ge=0.1, le=1.0)


class ClaimIn(BaseModel):
    entity_id: str
    property: str
    value: str
    source: str
    effective_date: str = ""
    authority: int = Field(default=0, ge=0, le=10)


class ContradictionsRequest(BaseModel):
    claims: list[ClaimIn] = Field(min_length=1, max_length=5000)
