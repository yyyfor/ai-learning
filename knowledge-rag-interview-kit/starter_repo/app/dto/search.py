from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.dto.documents import DocumentResponse


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    source: str | None = None
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=10, ge=1, le=50)

    @field_validator("query")
    @classmethod
    def query_cannot_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("query cannot be blank")
        return value


class SearchResult(BaseModel):
    document: DocumentResponse
    score: float


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]
    total: int
    page: int
    page_size: int
