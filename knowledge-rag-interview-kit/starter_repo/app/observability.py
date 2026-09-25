"""Bounded in-process traces for a local learning app; no prompts or evidence logged."""
import math
import os
import time
from collections import deque
from contextlib import contextmanager
from contextvars import ContextVar
from uuid import uuid4

current_trace = ContextVar("trace", default=None)
traces = deque(maxlen=500)


@contextmanager
def span(name):
    trace = current_trace.get()
    start = time.perf_counter()
    error = None
    try:
        yield
    except BaseException as exc:
        error = type(exc).__name__
        raise
    finally:
        if trace is not None:
            trace["spans"].append({"name": name, "latency_ms": round((time.perf_counter()-start)*1000, 2), "error": error})


def record_usage(body):
    trace = current_trace.get()
    if trace is not None:
        trace["input_tokens"] += int(body.get("prompt_eval_count", 0))
        trace["output_tokens"] += int(body.get("eval_count", 0))


def new_trace():
    return {"id": str(uuid4()), "spans": [], "input_tokens": 0, "output_tokens": 0}


def percentile(values, quantile):
    return sorted(values)[max(0, math.ceil(len(values)*quantile)-1)] if values else None


def summary():
    rows = list(traces)
    latencies = [r["latency_ms"] for r in rows]
    retrieval = [s["latency_ms"] for r in rows for s in r["spans"] if s["name"] == "retrieval"]
    llm = [s["latency_ms"] for r in rows for s in r["spans"] if s["name"] == "llm"]
    errors = sum(r["status"] >= 500 for r in rows)
    availability = 1-errors/len(rows) if rows else None
    input_tokens = sum(r["input_tokens"] for r in rows)
    output_tokens = sum(r["output_tokens"] for r in rows)
    cost = (input_tokens * float(os.getenv("INPUT_COST_PER_MILLION", "0")) +
            output_tokens * float(os.getenv("OUTPUT_COST_PER_MILLION", "0"))) / 1e6
    p95 = percentile(latencies, .95)
    retrieval_p95 = percentile(retrieval, .95)
    queries = [r for r in rows if r["route"] in {"/rag/query", "/graph/query", "/graph/compare"}]
    query_p95 = percentile([r["latency_ms"] for r in queries], .95)
    query_cost = sum(r["input_tokens"] * float(os.getenv("INPUT_COST_PER_MILLION", "0")) +
                     r["output_tokens"] * float(os.getenv("OUTPUT_COST_PER_MILLION", "0")) for r in queries) / 1e6
    return {"window": "last 500 requests; resets on restart", "requests": len(rows),
            "p50_ms": percentile(latencies, .5), "p95_ms": p95,
            "retrieval_p95_ms": retrieval_p95, "llm_p95_ms": percentile(llm, .95),
            "query_p95_ms": query_p95, "estimated_cost_per_query": query_cost/len(queries) if queries else None,
            "error_rate": errors/len(rows) if rows else None,
            "input_tokens": input_tokens, "output_tokens": output_tokens,
            "estimated_cost": cost, "estimated_cost_per_request": cost/len(rows) if rows else None,
            "slo": {"availability_99_9": availability >= .999 if availability is not None else None,
                    "retrieval_under_500ms": retrieval_p95 < 500 if retrieval_p95 is not None else None,
                    "query_under_5s": query_p95 < 5000 if query_p95 is not None else None,
                    "request_under_5s": p95 < 5000 if p95 is not None else None}}
