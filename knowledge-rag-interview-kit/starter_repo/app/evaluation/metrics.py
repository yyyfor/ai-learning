"""Ranking metrics for retrieval evaluation.

Retrieval is scored separately from generation on purpose: if the right chunk
never reaches the context, no prompt or model change can fix the answer, and a
generation metric would hide which half regressed.

All functions are pure and take an ordered list of retrieved ids plus the set of
relevant ids, so they can be tested against hand-worked examples.
"""
from __future__ import annotations

from math import log2
from typing import Any, Collection, Iterable, Sequence


def dedupe(items: Iterable[str]) -> list[str]:
    """Keep first occurrence only; several chunks can map to one document."""
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered


def recall_at_k(retrieved: Sequence[str], relevant: Collection[str], k: int) -> float:
    """Share of the relevant items that appear in the top k."""
    if not relevant:
        return 0.0
    found = len(set(retrieved[:k]) & set(relevant))
    return found / len(set(relevant))


def precision_at_k(retrieved: Sequence[str], relevant: Collection[str], k: int) -> float:
    if k <= 0:
        return 0.0
    return len(set(retrieved[:k]) & set(relevant)) / k


def reciprocal_rank(retrieved: Sequence[str], relevant: Collection[str]) -> float:
    """1/rank of the first relevant item. Rewards getting one right answer high."""
    relevant_set = set(relevant)
    for position, identifier in enumerate(retrieved, start=1):
        if identifier in relevant_set:
            return 1.0 / position
    return 0.0


def ndcg_at_k(retrieved: Sequence[str], relevant: Collection[str], k: int) -> float:
    """Binary-gain NDCG: unlike recall, it cares where in the top k a hit landed."""
    relevant_set = set(relevant)
    if not relevant_set:
        return 0.0
    gains = [1.0 if identifier in relevant_set else 0.0 for identifier in retrieved[:k]]
    dcg = sum(gain / log2(position + 1) for position, gain in enumerate(gains, start=1))
    ideal_hits = min(len(relevant_set), k)
    idcg = sum(1.0 / log2(position + 1) for position in range(1, ideal_hits + 1))
    return dcg / idcg if idcg else 0.0


def evaluate_query(
    retrieved: Sequence[str], relevant: Collection[str], k: int = 10
) -> dict[str, float]:
    ordered = dedupe(retrieved)
    return {
        f"recall@{k}": recall_at_k(ordered, relevant, k),
        f"precision@{k}": precision_at_k(ordered, relevant, k),
        f"ndcg@{k}": ndcg_at_k(ordered, relevant, k),
        "mrr": reciprocal_rank(ordered, relevant),
    }


def aggregate(rows: Iterable[dict[str, float]]) -> dict[str, float]:
    """Macro average: every query counts the same, regardless of how many
    relevant documents it has, so a few broad queries cannot mask the rest."""
    rows = list(rows)
    if not rows:
        return {}
    keys = rows[0].keys()
    return {key: sum(row[key] for row in rows) / len(rows) for key in keys}


def group_by(rows: Iterable[dict[str, Any]], field: str) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(str(row.get(field) or "uncategorised"), []).append(row)
    return grouped
