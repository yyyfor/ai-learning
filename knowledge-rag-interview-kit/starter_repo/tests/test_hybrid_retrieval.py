"""Hybrid retrieval contracts, exercised with fakes.

The repo has no pytest-asyncio, so each test drives the coroutine with
asyncio.run. No Elasticsearch, Qdrant or model server is needed: the ranking
behaviour is the thing under test.
"""
import asyncio

import pytest

from app.domain.retrieval import RetrievalFilters
from app.services.hybrid import (HybridRequest, HybridRetrievalService,
                                 RetrievalUnavailableError)


def run(coroutine):
    return asyncio.run(coroutine)


def chunk(chunk_id, document_id="doc-1", score=1.0, text="text", page=1):
    return {"chunk_id": chunk_id, "document_id": document_id, "title": "Title",
            "source": "pdf", "text": text, "page": page, "_score": score}


class FakeChunkIndex:
    """Lexical side. `results` may be a list or a per-query dict."""

    def __init__(self, results=None, error=None):
        self.results = results if results is not None else []
        self.error = error
        self.calls = []

    async def search(self, query, filters, limit):
        self.calls.append((query, filters, limit))
        if self.error:
            raise self.error
        results = self.results.get(query, []) if isinstance(self.results, dict) else self.results
        return [dict(item) for item in results][:limit]


class FakeVectorIndex:
    def __init__(self, results=None, error=None):
        self.results = results if results is not None else []
        self.error = error
        self.calls = []

    async def query(self, vector, top_k, filters=None, score_threshold=None):
        self.calls.append((tuple(vector), top_k, filters, score_threshold))
        if self.error:
            raise self.error
        return [
            {"id": item["chunk_id"], "score": item.get("_score", 1.0),
             "payload": {key: value for key, value in item.items() if key != "_score"}}
            for item in self.results
        ][:top_k]


class FakeModels:
    embedding_model = "fake-embed"
    chat_model = "fake-chat"

    def __init__(self, error=None):
        self.error = error
        self.embedded = []

    async def embed(self, texts):
        if self.error:
            raise self.error
        self.embedded.append(list(texts))
        return [[float(len(text)), 1.0] for text in texts]


class FakeRewriter:
    name = "fake"

    def __init__(self, extras, warnings=()):
        self.extras = extras
        self.warnings = list(warnings)

    async def variants(self, query):
        return [query, *self.extras], list(self.warnings)


class ReversingReranker:
    name = "reversing"

    async def rerank(self, query, candidates, top_k):
        for position, candidate in enumerate(reversed(candidates)):
            candidate.rerank_score = float(position)
        return list(reversed(candidates))[:top_k], []


class BrokenReranker:
    name = "broken"

    async def rerank(self, query, candidates, top_k):
        return candidates[:top_k], ["reranker unavailable; fusion order kept"]


def build(chunk_index=None, vector_index=None, models=None, **kwargs):
    return HybridRetrievalService(
        chunk_index if chunk_index is not None else FakeChunkIndex(),
        vector_index if vector_index is not None else FakeVectorIndex(),
        models or FakeModels(),
        **kwargs,
    )


def test_a_chunk_both_retrievers_found_ranks_first():
    service = build(
        FakeChunkIndex([chunk("c1", score=9.5), chunk("c2", score=4.0)]),
        FakeVectorIndex([chunk("c2", score=0.81), chunk("c3", score=0.74)]),
    )
    result = run(service.retrieve(HybridRequest(query="q", top_k=3)))
    assert [hit.id for hit in result.hits] == ["c2", "c1", "c3"]
    top = result.hits[0]
    assert top.retrievers == ["bm25", "vector"]
    # Both raw scores are kept for debugging; the ranking used neither directly.
    assert top.bm25_score == 4.0
    assert top.vector_score == 0.81
    assert top.ranks == {"bm25:0": 2, "vector:0": 1}


def test_bm25_mode_never_embeds_or_touches_the_vector_store():
    models, vector = FakeModels(), FakeVectorIndex([chunk("c9")])
    service = build(FakeChunkIndex([chunk("c1")]), vector, models)
    result = run(service.retrieve(HybridRequest(query="q", mode="bm25")))
    assert [hit.id for hit in result.hits] == ["c1"]
    assert models.embedded == []
    assert vector.calls == []


def test_vector_mode_never_touches_the_lexical_index():
    lexical = FakeChunkIndex([chunk("c1")])
    service = build(lexical, FakeVectorIndex([chunk("c9")]))
    result = run(service.retrieve(HybridRequest(query="q", mode="vector")))
    assert [hit.id for hit in result.hits] == ["c9"]
    assert lexical.calls == []


def test_one_store_down_degrades_to_the_other_with_a_warning():
    service = build(
        FakeChunkIndex(error=RuntimeError("elasticsearch down")),
        FakeVectorIndex([chunk("c2")]),
    )
    result = run(service.retrieve(HybridRequest(query="q")))
    assert [hit.id for hit in result.hits] == ["c2"]
    assert any("bm25" in warning for warning in result.warnings)


def test_every_store_down_is_an_error():
    service = build(
        FakeChunkIndex(error=RuntimeError("es down")),
        FakeVectorIndex(error=RuntimeError("qdrant down")),
    )
    with pytest.raises(RetrievalUnavailableError):
        run(service.retrieve(HybridRequest(query="q")))


def test_embedding_failure_is_fatal_only_when_vectors_are_the_whole_mode():
    models = FakeModels(error=RuntimeError("ollama down"))
    hybrid = build(FakeChunkIndex([chunk("c1")]), FakeVectorIndex(), models)
    result = run(hybrid.retrieve(HybridRequest(query="q", mode="hybrid")))
    assert [hit.id for hit in result.hits] == ["c1"]
    assert any("embedding" in warning for warning in result.warnings)

    vector_only = build(FakeChunkIndex(), FakeVectorIndex(), FakeModels(error=RuntimeError("down")))
    with pytest.raises(RetrievalUnavailableError):
        run(vector_only.retrieve(HybridRequest(query="q", mode="vector")))


def test_rewritten_queries_vote_at_a_lower_weight_than_the_users_words():
    # The rewrite prefers c9; the original prefers c1. The user's words win.
    lexical = FakeChunkIndex({"q": [chunk("c1")], "rewritten": [chunk("c9")]})
    service = build(lexical, FakeVectorIndex(), rewriter=FakeRewriter(["rewritten"]))
    result = run(service.retrieve(HybridRequest(query="q", mode="bm25", rewrite=True)))
    assert result.variants == ["q", "rewritten"]
    assert [hit.id for hit in result.hits] == ["c1", "c9"]
    assert [call[0] for call in lexical.calls] == ["q", "rewritten"]


def test_one_embed_call_covers_every_variant():
    models = FakeModels()
    service = build(FakeChunkIndex(), FakeVectorIndex([chunk("c1")]), models,
                    rewriter=FakeRewriter(["a", "b"]))
    run(service.retrieve(HybridRequest(query="q", mode="vector", rewrite=True)))
    assert models.embedded == [["q", "a", "b"]]


def test_reranker_reorders_and_records_its_scores():
    service = build(
        FakeChunkIndex([chunk("c1"), chunk("c2")]),
        FakeVectorIndex(),
        reranker=ReversingReranker(),
    )
    result = run(service.retrieve(HybridRequest(query="q", mode="bm25", rerank=True, top_k=2)))
    assert [hit.id for hit in result.hits] == ["c2", "c1"]
    assert result.reranked is True
    assert result.hits[0].rerank_score is not None


def test_failed_reranking_keeps_fusion_order_instead_of_failing():
    service = build(
        FakeChunkIndex([chunk("c1"), chunk("c2")]),
        FakeVectorIndex(),
        reranker=BrokenReranker(),
    )
    result = run(service.retrieve(HybridRequest(query="q", mode="bm25", rerank=True, top_k=2)))
    assert [hit.id for hit in result.hits] == ["c1", "c2"]
    assert result.reranked is False
    assert result.warnings


def test_rerank_false_leaves_the_reranker_unused():
    service = build(FakeChunkIndex([chunk("c1"), chunk("c2")]), FakeVectorIndex(),
                    reranker=ReversingReranker())
    result = run(service.retrieve(HybridRequest(query="q", mode="bm25", rerank=False, top_k=2)))
    assert [hit.id for hit in result.hits] == ["c1", "c2"]
    assert result.reranked is False


def test_filters_and_depth_reach_both_retrievers():
    lexical, vector = FakeChunkIndex([chunk("c1")]), FakeVectorIndex([chunk("c2")])
    service = build(lexical, vector)
    filters = RetrievalFilters(source="pdf", tags=["hr"], metadata={"team": "risk"})
    run(service.retrieve(HybridRequest(
        query="q", filters=filters, candidate_k=7, score_threshold=0.42)))
    assert lexical.calls[0][1] is filters and lexical.calls[0][2] == 7
    assert vector.calls[0][2] is filters and vector.calls[0][3] == 0.42
    assert vector.calls[0][1] == 7


def test_top_k_cuts_the_response_while_candidates_report_the_fused_depth():
    service = build(
        FakeChunkIndex([chunk("c1"), chunk("c2"), chunk("c3")]),
        FakeVectorIndex(),
    )
    result = run(service.retrieve(HybridRequest(query="q", mode="bm25", top_k=2)))
    assert len(result.hits) == 2
    assert result.candidates == 3
    assert result.timings_ms["total"] >= 0


def test_unknown_mode_is_rejected():
    with pytest.raises(ValueError):
        run(build().retrieve(HybridRequest(query="q", mode="magic")))
