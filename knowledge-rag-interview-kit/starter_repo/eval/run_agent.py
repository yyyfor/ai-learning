#!/usr/bin/env python3
"""Five local agent golden tasks. Seed lab examples first; creates one labelled task."""
import argparse
import json
import os

import httpx


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    headers = {"Authorization": "Bearer " + os.environ["API_TOKEN"]} if os.getenv("API_TOKEN") else {}
    results = []
    with httpx.Client(base_url=args.api, timeout=360, headers=headers) as client:
        def call(path, body=None):
            response = client.get(path) if body is None else client.post(path, json=body)
            response.raise_for_status()
            return response.json()

        tasks = [
            ("calculator", "Calculate (1200 * 0.15) and finish with the result.", ["calculate"], "180"),
            ("knowledge", "Find how many annual leave days full-time employees receive.", ["search_knowledge"], "20"),
            ("combined", "Find the dollar value of Contract C-101 and calculate 15 percent of it.",
             ["search_knowledge", "calculate"], "180"),
        ]
        for name, goal, required, expected in tasks:
            run = call("/agent/runs", {"goal": goal, "required_tools": required})
            completed = [s["tool"] for s in run["steps"] if s["status"] == "completed"]
            passed = (run["status"] == "completed" and all(t in completed for t in required)
                      and expected in (run["answer"] or ""))
            results.append({"task": name, "passed": passed, "run_id": run["id"], "status": run["status"]})
        for approved in (True, False):
            before = len(call("/agent/followups"))
            run = call("/agent/runs", {"goal": 'Create a follow-up titled "Lab golden task: HR review" '
                        'with description "Ask HR to verify the annual leave policy". Finish after creation.'})
            no_early_write = len(call("/agent/followups")) == before
            paused = run["status"] == "awaiting_approval"
            if paused:
                run = call(f"/agent/runs/{run['id']}/approval", {"approved": approved})
                call(f"/agent/runs/{run['id']}/approval", {"approved": approved})
            after = len(call("/agent/followups"))
            passed = (paused and no_early_write and after == before + int(approved)
                      and run["status"] == ("completed" if approved else "rejected"))
            results.append({"task": "approve_write" if approved else "reject_write", "passed": passed,
                            "run_id": run["id"], "status": run["status"]})
    print(json.dumps(results, indent=2))
    raise SystemExit(0 if all(row["passed"] for row in results) else 1)


if __name__ == "__main__":
    main()
