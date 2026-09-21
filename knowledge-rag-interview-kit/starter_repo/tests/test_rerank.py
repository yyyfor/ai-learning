import asyncio
import json

from app.domain.retrieval import RetrievedChunk
from app.retrieval.rerank import (CrossEncoderReranker, NoopReranker,
                                  OllamaReranker, build_reranker)


def run(coroutine):
    return asyncio.run(coroutine)


def candidates(*ids):
    return [RetrievedChunk(id=i, document_id="d", title="t", source="pdf",
                           page=1, text=f"text {i}", fused_score=1.0) for i in ids]


class ScriptedModels:
    """Returns canned chat completions; records the prompts it was given."""

    chat_model = "fake-chat"

    def __init__(self, replies):
        self.replies = list(replies)
        self.prompts = []

    async def complete(self, system, user, **kwargs):
        self.prompts.append(user)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


def scores_json(pairs):
    return json.dumps({"scores": [{"id": i, "score": s} for i, s in pairs]})


def test_noop_reranker_keeps_fusion_order():
    hits, warnings = run(NoopReranker().rerank("q", candidates("a", "b"), 2))
    assert [hit.id for hit in hits] == ["a", "b"]
    assert warnings == []


def test_scores_reorder_the_candidates():
    models = ScriptedModels([scores_json([(1, 2), (2, 9)])])
    hits, warnings = run(OllamaReranker(models).rerank("q", candidates("a", "b"), 2))
    assert [hit.id for hit in hits] == ["b", "a"]
    assert hits[0].rerank_score == 9.0
    assert warnings == []


def test_equal_scores_keep_the_retrieval_consensus():
    models = ScriptedModels([scores_json([(1, 5), (2, 5)])])
    hits, _ = run(OllamaReranker(models).rerank("q", candidates("a", "b"), 2))
    assert [hit.id for hit in hits] == ["a", "b"]


def test_scores_are_clamped_to_the_documented_range():
    models = ScriptedModels([scores_json([(1, 99), (2, -5)])])
    hits, _ = run(OllamaReranker(models).rerank("q", candidates("a", "b"), 2))
    assert hits[0].rerank_score == 10.0
    assert hits[1].rerank_score == 0.0


def test_unparsable_output_falls_back_to_fusion_order():
    models = ScriptedModels(["not json at all"])
    hits, warnings = run(OllamaReranker(models).rerank("q", candidates("a", "b"), 2))
    assert [hit.id for hit in hits] == ["a", "b"]
    assert warnings and hits[0].rerank_score is None


def test_a_model_error_never_fails_the_query():
    models = ScriptedModels([RuntimeError("ollama down")])
    hits, warnings = run(OllamaReranker(models).rerank("q", candidates("a", "b"), 2))
    assert [hit.id for hit in hits] == ["a", "b"]
    assert warnings


def test_a_partially_scored_batch_is_discarded_whole():
    # Mixing reranked and fusion-ordered results would make runs unreproducible.
    models = ScriptedModels([scores_json([(1, 8)])])
    hits, warnings = run(OllamaReranker(models).rerank("q", candidates("a", "b"), 2))
    assert [hit.id for hit in hits] == ["a", "b"]
    assert warnings


def test_one_failed_batch_discards_the_whole_request():
    models = ScriptedModels([scores_json([(1, 9)]), RuntimeError("timeout")])
    reranker = OllamaReranker(models, batch_size=1)
    hits, warnings = run(reranker.rerank("q", candidates("a", "b"), 2))
    assert [hit.id for hit in hits] == ["a", "b"]
    assert warnings


def test_passages_are_truncated_before_they_reach_the_model():
    models = ScriptedModels([scores_json([(1, 5)])])
    long_chunk = candidates("a")
    long_chunk[0].text = "x" * 5000
    run(OllamaReranker(models, max_chars=100).rerank("q", long_chunk, 1))
    assert len(models.prompts[0]) < 400


def test_empty_candidate_set_short_circuits():
    models = ScriptedModels([])
    assert run(OllamaReranker(models).rerank("q", [], 5)) == ([], [])


def test_factory_maps_configuration_to_implementations():
    models = ScriptedModels([])
    assert isinstance(build_reranker("none", models), NoopReranker)
    assert isinstance(build_reranker("", models), NoopReranker)
    assert isinstance(build_reranker("ollama", models), OllamaReranker)
    # An unknown value disables reranking rather than breaking startup.
    assert isinstance(build_reranker("nonsense", models), NoopReranker)
    assert CrossEncoderReranker.name == "cross-encoder"
