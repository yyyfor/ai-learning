"""One-shot freshness monitor; schedule externally if desired. No data mutation."""
import json
import os
import httpx


def main():
    headers = {"Authorization": "Bearer " + os.environ["API_TOKEN"]} if os.getenv("API_TOKEN") else {}
    response = httpx.get(os.getenv("API_URL", "http://127.0.0.1:8000") + "/governance/freshness",
                         headers=headers, timeout=15)
    response.raise_for_status()
    stale = [row for row in response.json() if not row["usable"] or row["freshness_score"] < .5]
    print(json.dumps({"needs_review": stale}, indent=2))
    raise SystemExit(1 if stale else 0)


if __name__ == "__main__":
    main()
