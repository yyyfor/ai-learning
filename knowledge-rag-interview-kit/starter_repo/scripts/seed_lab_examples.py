"""Create two small, clearly labelled lab documents through the backend API.

Run once with the server ready. Re-running creates another pair (no deletions).
Use --graph when GRAPH_ENABLED=true. Writes an evaluation request with real IDs.
"""
import argparse
import json
import os
from pathlib import Path
import httpx


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api", default="http://127.0.0.1:8000")
    parser.add_argument("--graph", action="store_true")
    parser.add_argument("--output", type=Path, default=Path("eval/lab9-dataset.json"))
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"{args.output} already exists; choose another --output to avoid overwriting it")
    headers = {"Authorization": "Bearer " + os.environ["API_TOKEN"]} if os.getenv("API_TOKEN") else {}
    with httpx.Client(base_url=args.api, timeout=300, headers=headers) as client:
        def call(method, path, body):
            response = client.request(method, path, json=body)
            response.raise_for_status()
            return response.json()
        texts = ["Acme signs Contract C-101. Contract C-101 has counterparty Bluebird. The contract value is 1200 dollars.",
                 "Policy POL-2026-017: Full-time employees receive 20 days of annual leave each year."]
        ids = []
        for i, text in enumerate(texts):
            doc = call("POST", "/documents", {"title": ["Lab contract C-101", "Lab annual leave policy"][i],
                        "content": text, "source": "lab-examples", "tags": ["lab"], "metadata": {"tenant": "local"}})
            identifier = doc["id"]
            ids.append(identifier)
            call("POST", f"/rag/documents/{identifier}/index", {"chunk_size": 800, "overlap": 80})
            call("PUT", f"/governance/documents/{identifier}", {
                "source_uri": f"lab://examples/{identifier}", "source_owner": "Lab author",
                "business_owner": "Learning team", "effective_date": "2026-01-01"})
            for action in ("validate", "approve", "publish"):
                call("POST", f"/governance/documents/{identifier}/transition", {"action": action, "reason": "Lab example reviewed"})
        if args.graph:
            call("PUT", f"/graph/documents/{ids[0]}", {
                "entities": [{"id": "acme", "name": "Acme", "type": "Company"},
                             {"id": "c-101", "name": "Contract C-101", "type": "Contract"},
                             {"id": "bluebird", "name": "Bluebird", "type": "Customer"}],
                "relations": [{"source": "acme", "target": "c-101", "type": "signs", "evidence": "Acme signs Contract C-101."},
                              {"source": "c-101", "target": "bluebird", "type": "hasCounterparty", "evidence": "Contract C-101 has counterparty Bluebird."}]})
        dataset = {"mode": "hybrid", "top_k": 3, "judge": True, "cases": [
            {"query": "Who is the counterparty on contract C-101?", "expected_sources": [ids[0]],
             "expected_facts": ["Bluebird is the counterparty."], "allowed_answer": "Bluebird", "forbidden_answer": ["Contoso"]},
            {"query": "How many days of annual leave do full-time employees receive?", "expected_sources": [ids[1]],
             "expected_facts": ["20 days each year"], "allowed_answer": "20 days", "forbidden_answer": ["30 days"]}]}
        args.output.write_text(json.dumps(dataset, ensure_ascii=False, indent=2))
        print(json.dumps({"document_ids": ids, "dataset": str(args.output)}, indent=2))


if __name__ == "__main__":
    main()
