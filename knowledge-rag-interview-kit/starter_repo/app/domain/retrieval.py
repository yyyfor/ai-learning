"""Shared retrieval vocabulary.

Week 4 has two candidate generators (BM25 in Elasticsearch, dense vectors in
Qdrant). They only fuse cleanly if they speak about the same unit with the same
identifier, so both stores write the *same* chunk id and both accept the same
filters. These types are the contract between them.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class RetrievalFilters:
    """Metadata restrictions applied inside every retriever.

    Filters are applied by each store during candidate generation, never after
    fusion: post-filtering silently shrinks top_k and, for permission filters,
    would mean the model briefly saw evidence the caller may not read.
    """

    source: str | None = None
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    # Server-computed ACL/lifecycle allowlist. None = unrestricted; [] = deny all.
    document_ids: list[str] | None = None

    def cache_key(self) -> str:
        parts = [self.source or "", ",".join(sorted(self.tags))]
        parts.extend(f"{key}={self.metadata[key]!r}" for key in sorted(self.metadata))
        return "|".join(parts)


@dataclass(frozen=True)
class ChunkRecord:
    """One indexed chunk, written to the vector store and the BM25 index alike."""

    id: str
    document_id: str
    title: str
    source: str
    tags: list[str]
    metadata: dict[str, Any]
    text: str
    page: int
    position: int
    created_at: str

    def as_payload(self) -> dict[str, Any]:
        return {
            "chunk_id": self.id,
            "document_id": self.document_id,
            "title": self.title,
            "source": self.source,
            "tags": list(self.tags),
            "metadata": dict(self.metadata),
            "text": self.text,
            "page": self.page,
            "position": self.position,
            "created_at": self.created_at,
        }


@dataclass
class RetrievedChunk:
    """A candidate surviving fusion, carrying where it came from.

    Provenance is kept per hit because "which retriever found this" is the first
    question asked when hybrid retrieval regresses, and it cannot be
    reconstructed after the fact.
    """

    id: str
    document_id: str
    title: str
    source: str
    page: int
    text: str
    fused_score: float = 0.0
    ranks: dict[str, int] = field(default_factory=dict)
    retrievers: list[str] = field(default_factory=list)
    bm25_score: float | None = None
    vector_score: float | None = None
    rerank_score: float | None = None

    def primary_score(self, mode: str) -> float:
        """The score a caller should read for this retrieval mode."""
        if self.rerank_score is not None:
            return self.rerank_score
        if mode == "vector" and self.vector_score is not None:
            return self.vector_score
        if mode == "bm25" and self.bm25_score is not None:
            return self.bm25_score
        return self.fused_score

    def as_dict(self, mode: str = "hybrid") -> dict[str, Any]:
        return {
            "chunk_id": self.id,
            "document_id": self.document_id,
            "title": self.title,
            "source": self.source,
            "page": self.page,
            "text": self.text,
            "score": round(self.primary_score(mode), 6),
            "fused_score": round(self.fused_score, 6),
            "bm25_score": self.bm25_score,
            "vector_score": self.vector_score,
            "rerank_score": self.rerank_score,
            "retrievers": list(self.retrievers),
            "ranks": dict(self.ranks),
        }
