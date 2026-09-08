from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.dto.documents import DocumentResponse


class ChunkOptions(BaseModel):
    strategy: Literal["recursive", "semantic"] = "recursive"
    chunk_size: int = Field(default=800, ge=100, le=2000)
    overlap: int = Field(default=80, ge=0, lt=100)
    similarity_threshold: float = Field(default=0.65, ge=-1, le=1)


class ChunkPreviewRequest(ChunkOptions):
    text: str = Field(min_length=1, max_length=100000)


class ChunkResponse(BaseModel):
    text: str
    page: int
    position: int


class IndexResponse(BaseModel):
    document: DocumentResponse
    chunks: int


class RagQueryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=20)
    source: str | None = None
    tags: list[str] = Field(default_factory=list)
    score_threshold: float = Field(default=0.3, ge=-1, le=1)

    @field_validator("query")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("query cannot be blank")
        return value.strip()


class Citation(BaseModel):
    number: int
    document_id: str
    chunk_id: str
    title: str
    source: str
    page: int
    text: str
    score: float


class RagQueryResponse(BaseModel):
    query: str
    answer: str
    context: str
    citations: list[Citation]
    model: str
