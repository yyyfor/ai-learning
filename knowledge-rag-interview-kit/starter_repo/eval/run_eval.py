#!/usr/bin/env python3
"""Baseline vs hybrid retrieval evaluation.

Runs every golden query through /rag/hybrid once per mode and reports
Recall@k, Precision@k, NDCG@k and MRR, overall and per query category.
Retrieval only: no answers are generated, so a run costs no generation time
and measures the one thing a fusion change can affect.

    python eval/run_eval.py --golden eval/golden_set.json
    python eval/run_eval.py --modes bm25,vector,hybrid,hybrid+rerank --k 10
    python eval/run_eval.py --json eval/results.json

A mode is a base mode (bm25, vector, hybrid) optionally followed by +rerank
and/or +rewrite, for example "hybrid+rewrite+rerank".

Relevance is judged at document level: a query is answered correctly if a chunk
from an expected document is retrieved. Chunk-level judgements are stricter but
need re-labelling whenever chunk_size changes.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.evaluation.metrics import aggregate, dedupe, evaluate_query, group_by  # noqa: E402

BASE_MODES = ("bm25", "vector", "hybrid")


def parse_mode(spec: str) -> dict:
    parts = [part.strip().lower() for part in spec.split("+") if part.strip()]
    if not parts or parts[0] not in BASE_MODES:
        raise SystemExit(f"unknown mode {spec!r}; base mode must be one of {BASE_MODES}")
    unknown = set(parts[1:]) - {"rerank", "rewrite"}
    if unknown:
        raise SystemExit(f"unknown mode flags in {spec!r}: {', '.join(sorted(unknown))}")
    return {
        "label": spec,
        "mode": parts[0],
        "rerank": "rerank" in parts[1:],
        "rewrite": "rewrite" in parts[1:],
    }


def load_golden(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    queries = data["queries"] if isinstance(data, dict) else data
    problems = []
    for index, entry in enumerate(queries):
        if not entry.get("query"):
            problems.append(f"entry {index} has no query")
        expected = entry.get("expected_document_ids") or []
        if not expected:
            problems.append(f"entry {index} ({entry.get('query', '')[:40]}) has no expected_document_ids")
        if any(str(value).startswith("REPLACE_WITH") for value in expected):
            problems.append(f"entry {index} still holds a placeholder document id")
    if problems:
        raise SystemExit(
            "golden set is not ready:\n  - " + "\n  - ".join(problems)
            + "\n\nFill in the ids of documents you have indexed (GET /documents lists them)."
        )
    return queries


def run_mode(client: httpx.Client, api: str, config: dict, golden: list[dict],
             k: int, top_k: int, candidate_k: int) -> tuple[list[dict], list[str]]:
    rows, warnings = [], []
    for entry in golden:
        filters = entry.get("filters") or {}
        payload = {
            "query": entry["query"],
            "mode": config["mode"],
            "top_k": max(top_k, k),
            "candidate_k": candidate_k,
            "rerank": config["rerank"],
            "rewrite": config["rewrite"],
            "source": filters.get("source"),
            "tags": filters.get("tags", []),
            "metadata": filters.get("metadata", {}),
        }
        if "score_threshold" in entry:
            payload["score_threshold"] = entry["score_threshold"]
        started = time.perf_counter()
        response = client.post(f"{api}/rag/hybrid", json=payload)
        elapsed_ms = (time.perf_counter() - started) * 1000
        if response.status_code != 200:
            raise SystemExit(f"{api}/rag/hybrid returned {response.status_code}: {response.text[:300]}")
        body = response.json()
        warnings.extend(body.get("warnings") or [])
        documents = dedupe(hit["document_id"] for hit in body["hits"])
        row = evaluate_query(documents, entry["expected_document_ids"], k=k)
        row["latency_ms"] = elapsed_ms
        row["category"] = entry.get("category", "uncategorised")
        row["query"] = entry["query"]
        rows.append(row)
    return rows, warnings


def metric_keys(k: int) -> list[str]:
    return [f"recall@{k}", f"precision@{k}", f"ndcg@{k}", "mrr"]


def print_table(title: str, header: list[str], rows: list[list[str]]) -> None:
    widths = [max(len(header[i]), *(len(row[i]) for row in rows)) for i in range(len(header))]
    print(f"\n{title}")
    print("  ".join(name.ljust(widths[i]) for i, name in enumerate(header)))
    print("  ".join("-" * widths[i] for i in range(len(header))))
    for row in rows:
        print("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--api", default="http://localhost:8000")
    parser.add_argument("--golden", default="eval/golden_set.json", type=Path)
    parser.add_argument("--modes", default="bm25,vector,hybrid,hybrid+rerank")
    parser.add_argument("--k", type=int, default=10, help="cut-off the metrics are computed at")
    parser.add_argument("--top-k", type=int, default=10, help="hits requested per query")
    parser.add_argument("--candidate-k", type=int, default=30, help="candidates per retriever before fusion")
    parser.add_argument("--timeout", type=float, default=300.0)
    parser.add_argument("--json", dest="json_out", type=Path, default=None)
    args = parser.parse_args()

    golden = load_golden(args.golden)
    configs = [parse_mode(spec) for spec in args.modes.split(",") if spec.strip()]
    keys = metric_keys(args.k)
    results, per_mode_rows = {}, {}

    with httpx.Client(timeout=args.timeout) as client:
        try:
            status = client.get(f"{args.api}/rag/status").json()
        except Exception as exc:
            raise SystemExit(f"cannot reach {args.api}: {exc}")
        if not status.get("enabled"):
            raise SystemExit("RAG is disabled on the API. Start it with RAG_ENABLED=true.")
        print(f"reranker={status.get('reranker')} rrf_k={status.get('rrf_k')} "
              f"chunk_index={status.get('lexical_chunk_index')}")
        print(f"{len(golden)} golden queries, metrics at k={args.k}")

        for config in configs:
            print(f"running {config['label']} ...", flush=True)
            rows, warnings = run_mode(client, args.api, config, golden,
                                      args.k, args.top_k, args.candidate_k)
            per_mode_rows[config["label"]] = rows
            results[config["label"]] = aggregate([{key: row[key] for key in keys} for row in rows])
            results[config["label"]]["p50_latency_ms"] = statistics.median(
                row["latency_ms"] for row in rows)
            for warning in sorted(set(warnings)):
                print(f"  warning: {warning}")

    print_table(
        f"Overall (macro average over {len(golden)} queries)",
        ["mode", *keys, "p50 ms"],
        [[label, *(f"{results[label][key]:.3f}" for key in keys),
          f"{results[label]['p50_latency_ms']:.0f}"] for label in results],
    )

    categories = sorted({row["category"] for rows in per_mode_rows.values() for row in rows})
    primary = keys[0]
    category_rows = []
    for label, rows in per_mode_rows.items():
        grouped = group_by(rows, "category")
        cells = [label]
        for category in categories:
            group = grouped.get(category)
            if not group:
                cells.append("-")
                continue
            score = aggregate([{primary: row[primary]} for row in group])[primary]
            cells.append(f"{score:.3f}")
        category_rows.append(cells)
    # Category breakdown is where hybrid earns its keep: it usually wins on
    # paraphrase while BM25 alone stays ahead on exact identifiers.
    print_table(f"{primary} by category", ["mode", *categories], category_rows)

    if args.json_out:
        args.json_out.write_text(json.dumps(
            {"k": args.k, "summary": results,
             "per_query": {label: rows for label, rows in per_mode_rows.items()}},
            indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nwrote {args.json_out}")


if __name__ == "__main__":
    main()
