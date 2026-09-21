import pytest

from app.evaluation.metrics import (aggregate, dedupe, evaluate_query,
                                    ndcg_at_k, precision_at_k, recall_at_k,
                                    reciprocal_rank)

RETRIEVED = ["d1", "d2", "d3", "d4"]
RELEVANT = ["d2", "d4"]


def test_recall_counts_only_the_top_k():
    assert recall_at_k(RETRIEVED, RELEVANT, 4) == 1.0
    assert recall_at_k(RETRIEVED, RELEVANT, 2) == 0.5
    assert recall_at_k(RETRIEVED, RELEVANT, 1) == 0.0


def test_precision_divides_by_k():
    assert precision_at_k(RETRIEVED, RELEVANT, 4) == 0.5
    assert precision_at_k(RETRIEVED, RELEVANT, 2) == 0.5


def test_reciprocal_rank_uses_the_first_relevant_position():
    assert reciprocal_rank(RETRIEVED, RELEVANT) == 0.5
    assert reciprocal_rank(["d4", "d1"], RELEVANT) == 1.0
    assert reciprocal_rank(["d1", "d3"], RELEVANT) == 0.0


def test_ndcg_rewards_relevant_items_placed_higher():
    # gains [0,1,0,1]: DCG = 1/log2(3) + 1/log2(5), IDCG = 1 + 1/log2(3)
    assert ndcg_at_k(RETRIEVED, RELEVANT, 4) == pytest.approx(0.650921, abs=1e-6)
    assert ndcg_at_k(["d2", "d4", "d1"], RELEVANT, 4) == 1.0
    assert ndcg_at_k(RETRIEVED, RELEVANT, 4) < ndcg_at_k(["d2", "d1", "d3", "d4"], RELEVANT, 4)


def test_metrics_are_zero_when_nothing_is_relevant():
    assert recall_at_k(RETRIEVED, [], 4) == 0.0
    assert ndcg_at_k(RETRIEVED, [], 4) == 0.0


def test_dedupe_keeps_first_occurrence():
    # Several chunks of one document must count once at document level.
    assert dedupe(["d1", "d2", "d1", "d3"]) == ["d1", "d2", "d3"]


def test_evaluate_query_deduplicates_before_scoring():
    row = evaluate_query(["d1", "d1", "d2"], ["d2"], k=2)
    assert row["recall@2"] == 1.0
    assert row["mrr"] == 0.5


def test_aggregate_is_a_macro_average():
    assert aggregate([{"recall@10": 1.0}, {"recall@10": 0.0}]) == {"recall@10": 0.5}
    assert aggregate([]) == {}
