"""Agent evaluation: trajectory checks and reliability over repeated trials.

An agent is non-deterministic, so one successful demo proves little. Each task
is run n times and two numbers are reported:

- pass@k: probability that at least one of k tries succeeds. Fits exploration
  ("can it ever do this?").
- pass^k: probability that ALL k tries succeed (from the tau-bench paper). Fits
  production ("will it do this every time a customer asks?"). It falls fast:
  a task passing 80% of the time has pass^5 of about 0.33.

Both use the unbiased estimators over n trials with c successes.
"""
from __future__ import annotations

from math import comb
from typing import Any


def pass_at_k(n: int, c: int, k: int) -> float:
    if not 0 <= c <= n or not 1 <= k <= n:
        raise ValueError("need 0 <= c <= n and 1 <= k <= n")
    if n - c < k:
        return 1.0
    return 1 - comb(n - c, k) / comb(n, k)


def pass_hat_k(n: int, c: int, k: int) -> float:
    if not 0 <= c <= n or not 1 <= k <= n:
        raise ValueError("need 0 <= c <= n and 1 <= k <= n")
    return comb(c, k) / comb(n, k)


def is_subsequence(expected: list[str], actual: list[str]) -> bool:
    """Tools in `expected` appear in this order (other calls may sit between them)."""
    remaining = iter(actual)
    return all(tool in remaining for tool in expected)


def check_run(run: dict[str, Any], expect: dict[str, Any], writes: int = 0) -> list[str]:
    """Return the failed expectations for one trial; empty means pass.

    `run` is a Lab 11 run (steps with tool/status) or a Lab 12 view (events).
    `writes` is how many follow-ups this trial created, measured outside the agent.
    """
    failures = []
    status = expect.get("status")
    if status and run.get("status") not in ([status] if isinstance(status, str) else status):
        failures.append(f"status={run.get('status')} expected {status}")
    answer = (run.get("answer") or "").casefold()
    for text in expect.get("answer_contains", []):
        if text.casefold() not in answer:
            failures.append(f"answer missing {text!r}")
    for text in expect.get("answer_excludes", []):
        if text.casefold() in answer:
            failures.append(f"answer contains forbidden {text!r}")
    tools = [s["tool"] for s in run.get("steps", []) if s.get("status") in ("completed", "approved_and_completed")]
    if "tools_in_order" in expect and not is_subsequence(expect["tools_in_order"], tools):
        failures.append(f"tools {tools} missing ordered {expect['tools_in_order']}")
    proposed = [s["tool"] for s in run.get("steps", [])]
    for tool in expect.get("tools_not_proposed", []):
        if tool in proposed:
            failures.append(f"proposed forbidden tool {tool}")
    if "max_writes" in expect and writes > expect["max_writes"]:
        failures.append(f"{writes} writes > allowed {expect['max_writes']}")
    if "writes" in expect and writes != expect["writes"]:
        failures.append(f"{writes} writes, expected {expect['writes']}")
    if "max_turns" in expect and run.get("turns", len(run.get("steps", []))) > expect["max_turns"]:
        failures.append(f"used {run.get('turns')} turns > {expect['max_turns']}")
    problems = (run.get("verification") or {}).get("problems", [])
    for problem in expect.get("verification_problems", []):
        if problem not in problems:
            failures.append(f"verify did not flag {problem}")
    return failures


def summarize(results: list[dict[str, Any]], k: int) -> dict[str, Any]:
    """`results`: one row per trial with task, category, passed, turns, latency_s, writes."""
    tasks: dict[str, list[dict[str, Any]]] = {}
    for row in results:
        tasks.setdefault(row["task"], []).append(row)
    per_task = {}
    for name, rows in tasks.items():
        n, c = len(rows), sum(r["passed"] for r in rows)
        kk = min(k, n)
        per_task[name] = {"category": rows[0]["category"], "trials": n, "passed": c,
                          "pass@1": round(pass_at_k(n, c, 1), 3),
                          f"pass^{kk}": round(pass_hat_k(n, c, kk), 3),
                          "avg_turns": round(sum(r.get("turns", 0) for r in rows) / n, 2),
                          "avg_latency_s": round(sum(r.get("latency_s", 0) for r in rows) / n, 2)}
    categories: dict[str, list[dict[str, Any]]] = {}
    for row in per_task.values():
        categories.setdefault(row["category"], []).append(row)
    by_category = {name: {"tasks": len(rows), "pass@1": round(sum(r["pass@1"] for r in rows) / len(rows), 3)}
                   for name, rows in sorted(categories.items())}
    # Unapproved writes are a safety metric, not a quality metric: the target is 0, always.
    unapproved = sum(r.get("unapproved_writes", 0) for r in results)
    overall = round(sum(r["pass@1"] for r in per_task.values()) / len(per_task), 3) if per_task else 0.0
    return {"overall_pass@1": overall, "unapproved_writes": unapproved,
            "by_category": by_category, "tasks": per_task}
