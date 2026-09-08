from typing import Any

from pydantic import BaseModel, Field, field_validator


class DocumentCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1)
    source: str = Field(default="manual", min_length=1, max_length=200)
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("title", "content", "source")
    @classmethod
    def value_cannot_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("value cannot be blank")
        return value

    @field_validator("tags")
    @classmethod
    def tags_cannot_be_blank(cls, tags: list[str]) -> list[str]:
        cleaned_tags = [tag.strip() for tag in tags]
        if any(not tag for tag in cleaned_tags):
            raise ValueError("tags cannot contain blank values")
        return sorted(set(cleaned_tags))


class DocumentResponse(BaseModel):
    id: str
    title: str
    content: str
    source: str
    tags: list[str]
    metadata: dict[str, Any]
    created_at: str
