"""Reciprocal Rank Fusion.

Pure functions, no I/O: the ranking logic is unit tested without Elasticsearch,
Qdrant or a model server.

RRF is used instead of adding retriever scores together because those scores are
not comparable. BM25 is unbounded and depends on corpus statistics, cosine
similarity is bounded in [-1, 1], and both distributions shift per query, so any
fixed weighting of raw scores is tuned to the queries it was measured on. RRF
reads only the *rank* each retriever assigned, which is the one thing every
retriever agrees on the meaning of.
"""
from __future__ import annotations

from dataclasses import dataclass, field

DEFAULT_RRF_K = 60


@dataclass(frozen=True)
class Ranking:
    """One retriever's ordered result list for one query variant.

    `name` is "<retriever>" or "<retriever>:<variant index>". Multi-query
    retrieval contributes several rankings per retriever; the retriever family
    before the colon is what provenance reports.
    """

    name: str
    ids: list[str]
    weight: float = 1.0


@dataclass
class FusedHit:
    id: str
    score: float
    ranks: dict[str, int] = field(default_factory=dict)

    @property
    def retrievers(self) -> list[str]:
        return sorted({name.split(":", 1)[0] for name in self.ranks})


def reciprocal_rank_fusion(
    rankings: list[Ranking],
    k: int = DEFAULT_RRF_K,
    limit: int | None = None,
) -> list[FusedHit]:
    """Fuse ranked id lists: score(d) = sum over rankings of weight / (k + rank).

    `k` damps the influence of the very top positions; the usual default of 60
    means rank 1 and rank 2 differ by about 1.6%, so one retriever being
    confident does not overrule agreement between the others.
    """
    if k <= 0:
        raise ValueError("rrf k must be positive")

    scores: dict[str, float] = {}
    ranks: dict[str, dict[str, int]] = {}
    for ranking in rankings:
        if ranking.weight <= 0:
            continue
        seen: set[str] = set()
        for position, identifier in enumerate(ranking.ids, start=1):
            # A retriever returning the same id twice must not vote twice.
            if identifier in seen:
                continue
            seen.add(identifier)
            scores[identifier] = scores.get(identifier, 0.0) + ranking.weight / (k + position)
            ranks.setdefault(identifier, {})[ranking.name] = position

    # Deterministic order: score, then best rank achieved anywhere, then id.
    order = sorted(scores, key=lambda i: (-scores[i], min(ranks[i].values()), i))
    hits = [FusedHit(id=i, score=scores[i], ranks=ranks[i]) for i in order]
    return hits[:limit] if limit is not None else hits
