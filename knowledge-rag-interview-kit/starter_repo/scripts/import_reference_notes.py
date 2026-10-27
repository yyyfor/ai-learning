"""Import reviewed study notes through the API and index them for local RAG.

Re-running reuses documents with the same key/content hash. Changed notes become
new snapshots; old user documents are never overwritten or deleted.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path

import httpx


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--no-index", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    pack = json.loads((root / "knowledge/reference_notes.json").read_text())
    headers = {"Authorization": f"Bearer {os.environ['API_TOKEN']}"} if os.getenv("API_TOKEN") else {}
    results, failures = [], []
    with httpx.Client(base_url=args.base_url, headers=headers, timeout=180) as client:
        existing = {}
        page = 1
        while True:
            response = client.get("/documents", params={"page": page, "page_size": 100})
            response.raise_for_status()
            batch = response.json()
            for document in batch:
                if document["source"] == "reference-notes":
                    metadata = document["metadata"]
                    existing[(metadata.get("reference_key"), metadata.get("content_sha256"))] = document
            if len(batch) < 100:
                break
            page += 1
        for note in pack["notes"]:
            try:
                content = (f"{note['title']}\nReviewed: {pack['reviewed_on']}\n"
                           f"Original curated study note; not an official source document.\n\n{note['content']}\n\n"
                           + "Sources:\n" + "\n".join(note["sources"]))
                digest = hashlib.sha256(content.encode()).hexdigest()
                key = (note["key"], digest)
                document = existing.get(key)
                reused = document is not None
                if not document:
                    response = client.post("/documents", json={
                        "title": note["title"], "content": content, "source": "reference-notes",
                        "tags": ["knowledge-refresh", *note["tags"]],
                        "metadata": {"reference_key": note["key"], "content_sha256": digest,
                                     "reviewed_on": pack["reviewed_on"], "source_urls": note["sources"],
                                     "kind": "curated-study-note", "review_status": "draft"},
                    })
                    response.raise_for_status()
                    document = response.json()
                result = {"key": note["key"], "id": document["id"], "reused": reused, "indexed": False}
                results.append(result)
                if not args.no_index:
                    response = client.post(f"/rag/documents/{document['id']}/index", json={
                        "strategy": "recursive", "chunk_size": 700, "chunk_overlap": 80})
                    response.raise_for_status()
                    result["indexed"] = True
                print(f"{'Reused' if reused else 'Created'} {note['key']}: {document['id']} · indexed={result['indexed']}", flush=True)
            except httpx.HTTPError as exc:
                detail = exc.response.text[:200] if isinstance(exc, httpx.HTTPStatusError) else str(exc)
                failures.append({"key": note["key"], "error": detail})
                print(f"Failed {note['key']}: {detail}", flush=True)
    target = root / "var/reference-import.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps({"reviewed_on": pack["reviewed_on"], "documents": results, "failures": failures}, indent=2))
    questions = {note["key"]: note["question"] for note in pack["notes"]}
    dataset = {"cases": [{"query": questions[item["key"]], "expected_sources": [item["id"]]}
                         for item in results if item["indexed"]], "mode": "hybrid", "top_k": 5,
               "rerank": False, "rewrite": False, "judge": False}
    (root / "var/reference-evaluation.json").write_text(json.dumps(dataset, indent=2))
    print(f"Manifest: {target}\nEvaluation request: var/reference-evaluation.json")
    if failures:
        raise SystemExit("Some notes could not be imported/indexed. Fix the reported issue and rerun safely.")


if __name__ == "__main__":
    main()
