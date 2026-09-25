from typing import Any, Literal

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
    # Chunks written to the Elasticsearch chunk index; 0 when Week 4 lexical
    # indexing is not configured.
    lexical_chunks: int = 0


class RetrievalOptions(BaseModel):
    """Options shared by /rag/query and /rag/hybrid."""

    mode: Literal["bm25", "vector", "hybrid"] = "hybrid"
    top_k: int = Field(default=5, ge=1, le=20)
    # Per-retriever candidate depth before fusion. Deeper costs little and is
    # what gives RRF something to agree on; the reranker then cuts it back.
    candidate_k: int = Field(default=30, ge=1, le=200)
    source: str | None = None
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    # Applied to dense candidates only, before fusion. Raise it to cut noise,
    # lower it in hybrid mode so RRF can still see borderline chunks.
    score_threshold: float = Field(default=0.3, ge=-1, le=1)
    # Both cost extra local model calls, so they are opt-in per request.
    rerank: bool = False
    rewrite: bool = False


class RagQueryRequest(RetrievalOptions):
    query: str = Field(min_length=1, max_length=2000)

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
    version: int | None = None
    source_uri: str | None = None
    # The score for the requested mode: rerank score when reranked, otherwise
    # cosine for vector mode, BM25 for bm25 mode, and the RRF score for hybrid.
    score: float
    fused_score: float = 0.0
    bm25_score: float | None = None
    vector_score: float | None = None
    rerank_score: float | None = None
    retrievers: list[str] = Field(default_factory=list)
    ranks: dict[str, int] = Field(default_factory=dict)


class RagQueryResponse(BaseModel):
    query: str
    answer: str
    context: str
    citations: list[Citation]
    model: str
    retrieved_document_ids: list[str] = Field(default_factory=list)
    mode: str = "hybrid"
    variants: list[str] = Field(default_factory=list)
    reranked: bool = False
    warnings: list[str] = Field(default_factory=list)
    timings_ms: dict[str, float] = Field(default_factory=dict)


class HybridQueryRequest(RetrievalOptions):
    """Retrieval without answer generation, for comparison and evaluation."""

    query: str = Field(min_length=1, max_length=2000)

    @field_validator("query")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("query cannot be blank")
        return value.strip()


class HybridHit(BaseModel):
    chunk_id: str
    document_id: str
    title: str
    source: str
    page: int
    text: str
    score: float
    fused_score: float
    bm25_score: float | None = None
    vector_score: float | None = None
    rerank_score: float | None = None
    # Which retriever families found this chunk, and at what rank each placed it.
    retrievers: list[str] = Field(default_factory=list)
    ranks: dict[str, int] = Field(default_factory=dict)


class HybridQueryResponse(BaseModel):
    query: str
    mode: str
    variants: list[str]
    hits: list[HybridHit]
    candidates: int
    reranked: bool
    warnings: list[str] = Field(default_factory=list)
    timings_ms: dict[str, float] = Field(default_factory=dict)
