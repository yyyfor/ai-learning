"""Lab 7: entity resolution, near-duplicate detection and contradiction detection.

Pure functions, no I/O, so every decision can be unit tested and explained.

Embeddings are deliberately NOT used to decide identity: "Apple Inc" and
"Apple Ltd" are semantically close and may be different legal entities.
Identity comes from identifiers first, then names plus context, and anything
uncertain goes to a human review queue instead of being merged silently.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from itertools import combinations

MERGE_THRESHOLD = 0.92
REVIEW_THRESHOLD = 0.75
LEGAL_SUFFIXES = {"inc", "incorporated", "corp", "corporation", "co", "company", "ltd",
                  "limited", "llc", "plc", "gmbh", "ag", "sa", "group", "holdings"}
CJK_SUFFIXES = ("股份有限公司", "有限责任公司", "有限公司", "集团")


@dataclass
class EntityRecord:
    id: str
    name: str
    type: str
    source: str = ""
    identifiers: dict[str, str] = field(default_factory=dict)  # e.g. {"lei": "...", "registration": "..."}
    attributes: dict[str, str] = field(default_factory=dict)   # e.g. {"country": "US", "city": "Boston"}
    authority: int = 0                                          # Higher = more trusted source.


@dataclass
class PairDecision:
    left: str
    right: str
    score: float
    decision: str            # "merge" | "review" | "distinct"
    reasons: list[str]


def normalize_name(name: str) -> str:
    """Case, width, punctuation and legal-form insensitive name key."""
    text = unicodedata.normalize("NFKC", name).casefold().strip()
    for suffix in CJK_SUFFIXES:
        if text.endswith(suffix) and len(text) > len(suffix):
            text = text[: -len(suffix)]
    words = re.findall(r"[\w]+", text)
    kept = [word for word in words if word not in LEGAL_SUFFIXES]
    return " ".join(kept or words)


def name_similarity(left: str, right: str) -> float:
    """Max of character similarity and token overlap, on normalized names."""
    a, b = normalize_name(left), normalize_name(right)
    if not a or not b:
        return 0.0
    ratio = SequenceMatcher(None, a, b).ratio()
    tokens_a, tokens_b = set(a.split()), set(b.split())
    jaccard = len(tokens_a & tokens_b) / len(tokens_a | tokens_b)
    return max(ratio, jaccard)


def compare(left: EntityRecord, right: EntityRecord, aliases: dict[str, str] | None = None) -> PairDecision:
    """Score one pair. Identifiers dominate; names alone never merge different contexts."""
    aliases = aliases or {}
    reasons: list[str] = []
    if left.type != right.type:
        return PairDecision(left.id, right.id, 0.0, "distinct", ["different_type"])
    shared = sorted(left.identifiers.keys() & right.identifiers.keys())
    conflicting = [k for k in shared if left.identifiers[k] != right.identifiers[k]]
    if conflicting:
        # Two different official identifiers of the same kind: different entities.
        return PairDecision(left.id, right.id, 0.0, "distinct", [f"conflicting_{k}" for k in conflicting])
    if shared:
        return PairDecision(left.id, right.id, 1.0, "merge", [f"same_{k}" for k in shared])
    a, b = normalize_name(left.name), normalize_name(right.name)
    if aliases.get(a, a) == aliases.get(b, b) and (a in aliases or b in aliases):
        score = 0.95
        reasons.append("alias_table")
    else:
        score = name_similarity(left.name, right.name)
        reasons.append(f"name_similarity={score:.2f}")
    for attribute in ("country", "city"):
        x, y = left.attributes.get(attribute), right.attributes.get(attribute)
        if x and y:
            if x.casefold() == y.casefold():
                score += 0.03
                reasons.append(f"same_{attribute}")
            else:
                score -= 0.3 if attribute == "country" else 0.1
                reasons.append(f"different_{attribute}")
    score = max(0.0, min(1.0, score))
    decision = "merge" if score >= MERGE_THRESHOLD else "review" if score >= REVIEW_THRESHOLD else "distinct"
    return PairDecision(left.id, right.id, round(score, 3), decision, reasons)


def blocking_keys(record: EntityRecord, aliases: dict[str, str] | None = None) -> set[str]:
    """Only records sharing a key are compared: O(n) buckets instead of O(n^2) pairs.

    Blocking trades recall for speed: a true match with no shared key is never
    compared. That is why aliases get their own key ("IBM" shares no prefix
    with "International Business Machines").
    """
    keys = {f"{record.type}:id:{k}={v}" for k, v in record.identifiers.items()}
    normalized = normalize_name(record.name)
    compact = normalized.replace(" ", "")
    if compact:
        keys.add(f"{record.type}:name:{compact[:3]}")
    if aliases and normalized in aliases:
        keys.add(f"{record.type}:alias:{aliases[normalized]}")
    return keys


def resolve(records: list[EntityRecord], aliases: dict[str, str] | None = None) -> dict:
    """Cluster records into canonical entities; uncertain pairs go to review."""
    by_id = {record.id: record for record in records}
    blocks: dict[str, list[str]] = {}
    for record in records:
        for key in blocking_keys(record, aliases):
            blocks.setdefault(key, []).append(record.id)
    pairs = sorted({tuple(sorted(pair)) for ids in blocks.values() for pair in combinations(ids, 2)})
    parent = {record.id: record.id for record in records}

    def find(item):
        while parent[item] != item:
            parent[item] = parent[parent[item]]
            item = parent[item]
        return item

    def cluster_identifiers(root):
        merged: dict[str, set[str]] = {}
        for member in (i for i in by_id if find(i) == root):
            for key, value in by_id[member].identifiers.items():
                merged.setdefault(key, set()).add(value)
        return merged

    decisions, review = [], []
    # Strongest evidence first, so identifier merges shape clusters before fuzzy ones.
    scored = sorted((compare(by_id[a], by_id[b], aliases) for a, b in pairs), key=lambda d: -d.score)
    for decision in scored:
        if decision.decision == "merge":
            left, right = find(decision.left), find(decision.right)
            if left != right:
                ids_left, ids_right = cluster_identifiers(left), cluster_identifiers(right)
                # Transitivity guard: A~B and B~C must not merge A and C if their ids conflict.
                if any(ids_left[k] != ids_right[k] for k in ids_left.keys() & ids_right.keys()):
                    decision = PairDecision(decision.left, decision.right, decision.score, "review",
                                            decision.reasons + ["cluster_identifier_conflict"])
                else:
                    parent[right] = left
        if decision.decision == "review":
            review.append(decision)
        decisions.append(decision)
    clusters: dict[str, list[EntityRecord]] = {}
    for record in records:
        clusters.setdefault(find(record.id), []).append(record)
    entities = []
    for members in clusters.values():
        # The most authoritative source names the entity; ties go to the smallest id.
        best = sorted(members, key=lambda r: (-r.authority, r.id))[0]
        identifiers: dict[str, str] = {}
        for member in members:
            identifiers.update({k: v for k, v in member.identifiers.items() if k not in identifiers})
        entities.append({"canonical_id": "ENT-" + min(m.id for m in members), "name": best.name,
                         "type": best.type, "members": sorted(m.id for m in members),
                         "aliases": sorted({m.name for m in members} - {best.name}),
                         "identifiers": identifiers})
    entities.sort(key=lambda e: e["canonical_id"])
    return {"entities": entities, "review": [vars(d) for d in review],
            "decisions": [vars(d) for d in decisions], "compared_pairs": len(pairs)}


def shingles(text: str, size: int = 3) -> set[str]:
    """Word n-grams (CJK: character n-grams), the unit of near-duplicate comparison."""
    words = re.findall(r"[\w]+", unicodedata.normalize("NFKC", text).casefold())
    if len(words) <= 2 and any("一" <= ch <= "鿿" for ch in text):
        chars = [ch for ch in text if not ch.isspace()]
        return {"".join(chars[i:i + size]) for i in range(max(1, len(chars) - size + 1))}
    return {" ".join(words[i:i + size]) for i in range(max(1, len(words) - size + 1))}


def near_duplicates(documents: dict[str, str], threshold: float = 0.8) -> list[dict]:
    """Exact Jaccard over shingles. At scale, MinHash + LSH estimates the same number
    without comparing every pair; the decision rule stays the same."""
    sets = {identifier: shingles(text) for identifier, text in documents.items()}
    found = []
    for a, b in combinations(sorted(sets), 2):
        union = sets[a] | sets[b]
        score = len(sets[a] & sets[b]) / len(union) if union else 0.0
        if score >= threshold:
            found.append({"left": a, "right": b, "jaccard": round(score, 3)})
    return found


@dataclass
class Claim:
    entity_id: str
    property: str
    value: str
    source: str
    effective_date: str = ""   # ISO date; later supersedes earlier.
    authority: int = 0


def find_conflicts(claims: list[Claim]) -> list[dict]:
    """Same entity + property with different values. Resolve only when the rule is unambiguous."""
    grouped: dict[tuple[str, str], list[Claim]] = {}
    for claim in claims:
        grouped.setdefault((claim.entity_id, claim.property), []).append(claim)
    conflicts = []
    for (entity, prop), group in sorted(grouped.items()):
        values = {" ".join(c.value.casefold().split()) for c in group}
        if len(values) < 2:
            continue
        ranked = sorted(group, key=lambda c: (c.effective_date, c.authority), reverse=True)
        top = ranked[0]
        key = " ".join(top.value.casefold().split())
        # The best-ranked claim that DISAGREES with the top one decides how clear the win is.
        runner = next(c for c in ranked if " ".join(c.value.casefold().split()) != key)
        if (top.effective_date, top.authority) == (runner.effective_date, runner.authority):
            resolution, winner = "needs_review", None
        elif top.effective_date != runner.effective_date:
            resolution, winner = "latest_effective_date", top.value
        else:
            resolution, winner = "higher_authority", top.value
        conflicts.append({"entity_id": entity, "property": prop, "resolution": resolution,
                          "winner": winner, "claims": [vars(c) for c in ranked]})
    return conflicts
