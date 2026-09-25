#!/usr/bin/env python3
"""Call Lab 9 API; save an inspectable report and exit nonzero on regression."""
import argparse
import json
import os
from pathlib import Path

import httpx


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path, help="JSON EvaluationRequest: cases, mode, judge, etc.")
    parser.add_argument("--api", default="http://127.0.0.1:8000")
    parser.add_argument("--baseline", help="Previous evaluation id with the same cases/K/judge")
    parser.add_argument("--output", type=Path, default=Path("eval/generation-result.json"))
    args = parser.parse_args()
    body = json.loads(args.dataset.read_text())
    if args.baseline:
        body["baseline_id"] = args.baseline
    headers = {"Authorization": "Bearer " + os.environ["API_TOKEN"]} if os.getenv("API_TOKEN") else {}
    with httpx.Client(timeout=3600, headers=headers) as client:
        response = client.post(args.api + "/evaluation/run", json=body)
        response.raise_for_status()
    result = response.json()
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps({"id": result["id"], "summary": result["summary"], "passed": result["passed"]}, indent=2))
    raise SystemExit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
