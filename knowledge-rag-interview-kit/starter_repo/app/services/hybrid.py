"""Hybrid retrieval: BM25 candidates + dense candidates, fused, then reranked.

Pipeline: query rewrite -> parallel candidate generation -> Reciprocal Rank
Fusion -> reranking -> top_k.

Why the fusion lives here and not in Elasticsearch: the dense side is Qdrant, so
Elasticsearch could not rank it natively even with a subscription, and the
`rrf` / `text_similarity_reranker` retrievers are licensed features. Fusing in
the application layer keeps every tier of Elasticsearch usable, keeps the
ranking logic unit-testable without any server running, and leaves the vector
store replaceable.

Each retriever is isolated: one store being down degrades the ranking to the
other store's results plus a warning, instead of failing the request. Only when
everything requested is unavailable does the caller get an error.
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from app.domain.retrieval import RetrievalFilters, RetrievedChunk
from app.retrieval.fusion import DEFAULT_RRF_K, Ranking, reciprocal_rank_fusion
from app.retrieval.query_rewrite import NoopQueryRewriter
from app.retrieval.rerank import NoopReranker
from app.observability import span

logger = logging.getLogger("knowledge_api")

MODES = ("bm25", "vector", "hybrid")


class RetrievalUnavailableError(RuntimeError):
    """Every retriever the mode asked for failed."""


@dataclass
class HybridRequest:
    query: str
    mode: str = "hybrid"
    top_k: int = 5
    candidate_k: int = 30
    filters: RetrievalFilters = field(default_factory=RetrievalFilters)
    score_threshold: float | None = 0.3
    rerank: bool = False
    rewrite: bool = False


@dataclass
class HybridResult:
    query: str
    mode: str
    variants: list[str]
    hits: list[RetrievedChunk]
    candidates: int = 0
    reranked: bool = False
    warnings: list[str] = field(default_factory=list)
    timings_ms: dict[str, float] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "mode": self.mode,
            "variants": list(self.variants),
            "hits": [hit.as_dict(self.mode) for hit in self.hits],
            "candidates": self.candidates,
            "reranked": self.reranked,
            "warnings": list(self.warnings),
            "timings_ms": {k: round(v, 1) for k, v in self.timings_ms.items()},
        }


class HybridRetrievalService:
    """Owns candidate generation and ranking. Answer generation stays in RagService."""

    def __init__(
        self,
        chunk_index,
        vector_index,
        models,
        reranker=None,
        rewriter=None,
        rrf_k: int = DEFAULT_RRF_K,
        variant_weight: float = 0.5,
        rerank_multiplier: int = 3,
    ) -> None:
        self.chunk_index = chunk_index
        self.vector_index = vector_index
        self.models = models
        self.reranker = reranker or NoopReranker()
        self.rewriter = rewriter or NoopQueryRewriter()
        self.rrf_k = rrf_k
        # Rewritten queries vote at half weight: the user's own words stay
        # authoritative, which protects exact-identifier queries from paraphrase.
        self.variant_weight = variant_weight
        self.rerank_multiplier = rerank_multiplier

    async def retrieve(self, request: HybridRequest) -> HybridResult:
        if request.mode not in MODES:
            raise ValueError(f"mode must be one of {', '.join(MODES)}")

        started = time.perf_counter()
        timings: dict[str, float] = {}
        warnings: list[str] = []

        variants = [request.query]
        if request.rewrite:
            stage = time.perf_counter()
            variants, rewrite_warnings = await self.rewriter.variants(request.query)
            warnings.extend(rewrite_warnings)
            timings["rewrite"] = _elapsed_ms(stage)

        use_bm25 = request.mode in ("bm25", "hybrid")
        use_vector = request.mode in ("vector", "hybrid")

        vectors: list[list[float]] = []
        if use_vector:
            stage = time.perf_counter()
            try:
                # One embed call for every variant keeps the added latency flat.
                vectors = await self.models.embed(variants)
            except Exception as exc:
                logger.warning("embedding_failed type=%s", type(exc).__name__)
                if request.mode == "vector":
                    raise RetrievalUnavailableError("embedding model unavailable") from exc
                warnings.append("embedding unavailable; dense candidates skipped")
                use_vector = False
            timings["embed"] = _elapsed_ms(stage)

        jobs: list[tuple[str, float, Any]] = []
        for index, variant in enumerate(variants):
            weight = 1.0 if index == 0 else self.variant_weight
            if use_bm25:
                jobs.append((f"bm25:{index}", weight, self._bm25(variant, request)))
            if use_vector:
                jobs.append((f"vector:{index}", weight, self._vector(vectors[index], request)))

        if not jobs:
            raise RetrievalUnavailableError(f"no retriever available for mode {request.mode}")

        stage = time.perf_counter()
        outcomes = await asyncio.gather(*(job for _, _, job in jobs), return_exceptions=True)
        timings["retrieve"] = _elapsed_ms(stage)

        payloads: dict[str, dict[str, Any]] = {}
        rankings: list[Ranking] = []
        failed: set[str] = set()
        for (name, weight, _), outcome in zip(jobs, outcomes):
            family = name.split(":", 1)[0]
            if isinstance(outcome, BaseException):
                logger.warning(
                    "retriever_failed name=%s type=%s", name, type(outcome).__name__
                )
                failed.add(family)
                continue
            ids = []
            for payload in outcome:
                chunk_id = payload["chunk_id"]
                ids.append(chunk_id)
                stored = payloads.setdefault(chunk_id, payload)
                score = payload.get("_score")
                if score is not None:
                    key = "_bm25" if family == "bm25" else "_vector"
                    previous = stored.get(key)
                    # Best score across variants: the strongest evidence that
                    # this retriever considered the chunk relevant at all.
                    stored[key] = score if previous is None else max(previous, score)
            rankings.append(Ranking(name=name, ids=ids, weight=weight))

        if not rankings:
            raise RetrievalUnavailableError(
                "all retrievers failed: " + ", ".join(sorted(failed))
            )
        if failed:
            warnings.append(
                f"{', '.join(sorted(failed))} unavailable; ranking used the remaining retrievers"
            )

        stage = time.perf_counter()
        fused = reciprocal_rank_fusion(rankings, k=self.rrf_k, limit=request.candidate_k)
        candidates = [_to_chunk(payloads[hit.id], hit) for hit in fused]
        timings["fuse"] = _elapsed_ms(stage)

        reranked = False
        if request.rerank and candidates and self.reranker.name != "none":
            stage = time.perf_counter()
            pool_size = min(len(candidates), max(request.top_k, request.top_k * self.rerank_multiplier))
            with span("reranker"):
                ordered, rerank_warnings = await self.reranker.rerank(
                    request.query, candidates[:pool_size], request.top_k
                )
            warnings.extend(rerank_warnings)
            reranked = not rerank_warnings
            hits = ordered
            timings["rerank"] = _elapsed_ms(stage)
        else:
            hits = candidates[:request.top_k]

        timings["total"] = _elapsed_ms(started)
        return HybridResult(
            query=request.query,
            mode=request.mode,
            variants=variants,
            hits=hits,
            candidates=len(candidates),
            reranked=reranked,
            warnings=warnings,
            timings_ms=timings,
        )

    async def _bm25(self, variant: str, request: HybridRequest) -> list[dict[str, Any]]:
        return await self.chunk_index.search(variant, request.filters, request.candidate_k)

    async def _vector(self, vector: list[float], request: HybridRequest) -> list[dict[str, Any]]:
        hits = await self.vector_index.query(
            vector, request.candidate_k, request.filters, request.score_threshold
        )
        payloads = []
        for hit in hits:
            payload = dict(hit["payload"])
            # Chunks indexed before Week 4 carry no chunk_id; the Qdrant point id
            # is the same uuid5 the chunk index uses, so fusion still lines up.
            payload["chunk_id"] = payload.get("chunk_id") or str(hit["id"])
            payload["_score"] = float(hit.get("score") or 0.0)
            payloads.append(payload)
        return payloads


def _to_chunk(payload: dict[str, Any], hit) -> RetrievedChunk:
    return RetrievedChunk(
        id=hit.id,
        document_id=str(payload.get("document_id", "")),
        title=str(payload.get("title", "")),
        source=str(payload.get("source", "")),
        page=int(payload.get("page") or 1),
        text=str(payload.get("text", "")),
        fused_score=hit.score,
        ranks=dict(hit.ranks),
        retrievers=hit.retrievers,
        bm25_score=payload.get("_bm25"),
        vector_score=payload.get("_vector"),
    )


def _elapsed_ms(started: float) -> float:
    return (time.perf_counter() - started) * 1000
