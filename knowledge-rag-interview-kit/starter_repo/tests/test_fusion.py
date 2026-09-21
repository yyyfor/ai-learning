from app.retrieval.fusion import Ranking, reciprocal_rank_fusion

import pytest


def ids(hits):
    return [hit.id for hit in hits]


def test_agreement_between_retrievers_outranks_a_single_strong_vote():
    # "b" is second for both retrievers; "a" is first for one and absent from
    # the other. Two mid votes beat one top vote: that is the point of RRF.
    fused = reciprocal_rank_fusion([
        Ranking("bm25", ["a", "b", "c"]),
        Ranking("vector", ["d", "b", "e"]),
    ])
    assert ids(fused)[0] == "b"


def test_score_is_the_sum_of_reciprocal_ranks():
    fused = reciprocal_rank_fusion([
        Ranking("bm25", ["a"]),
        Ranking("vector", ["a"]),
    ], k=60)
    assert fused[0].score == pytest.approx(2 / 61)
    assert fused[0].ranks == {"bm25": 1, "vector": 1}
    assert fused[0].retrievers == ["bm25", "vector"]


def test_variant_rankings_collapse_to_their_retriever_family():
    fused = reciprocal_rank_fusion([
        Ranking("bm25:0", ["a"]),
        Ranking("bm25:1", ["a"]),
    ])
    assert fused[0].retrievers == ["bm25"]
    assert fused[0].ranks == {"bm25:0": 1, "bm25:1": 1}


def test_weight_scales_a_ranking_contribution():
    full = reciprocal_rank_fusion([Ranking("bm25", ["a"], weight=1.0)])
    half = reciprocal_rank_fusion([Ranking("bm25", ["a"], weight=0.5)])
    assert half[0].score == pytest.approx(full[0].score / 2)


def test_zero_weight_ranking_is_ignored_entirely():
    fused = reciprocal_rank_fusion([
        Ranking("bm25", ["a"], weight=0),
        Ranking("vector", ["b"]),
    ])
    assert ids(fused) == ["b"]


def test_a_retriever_cannot_vote_twice_for_the_same_id():
    fused = reciprocal_rank_fusion([Ranking("bm25", ["a", "a", "b"])], k=60)
    scores = {hit.id: hit.score for hit in fused}
    assert scores["a"] == pytest.approx(1 / 61)
    # The duplicate still occupies its slot, so "b" keeps list position 3.
    assert scores["b"] == pytest.approx(1 / 63)


def test_ties_break_deterministically_by_best_rank_then_id():
    fused = reciprocal_rank_fusion([
        Ranking("bm25", ["b", "a"]),
        Ranking("vector", ["a", "b"]),
    ])
    # Identical scores; both reach rank 1, so the id decides. Stable output
    # matters: evaluation runs must be reproducible.
    assert ids(fused) == ["a", "b"]


def test_limit_truncates_after_fusion():
    fused = reciprocal_rank_fusion([Ranking("bm25", ["a", "b", "c"])], limit=2)
    assert ids(fused) == ["a", "b"]


def test_k_must_be_positive():
    with pytest.raises(ValueError):
        reciprocal_rank_fusion([Ranking("bm25", ["a"])], k=0)


def test_no_rankings_yields_no_hits():
    assert reciprocal_rank_fusion([]) == []
