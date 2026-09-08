# Week 3: local Vector RAG, without a framework or API key

The existing `/search` and `/query` remain unchanged. Week 3 uses
`/rag/query`, with local Ollama embeddings + Qdrant cosine vector retrieval
+ a local LLM. Elasticsearch `semantic_text` is independent and stays off.

## Start

From `starter_repo`:

```bash
source .venv/bin/activate
pip install -e .
docker compose up -d postgres redis elasticsearch
docker compose --profile rag up -d qdrant
# Install/start Ollama on your Mac first. Native Ollama can use the Mac GPU.
ollama pull embeddinggemma
ollama pull llama3:latest
RAG_ENABLED=true uvicorn app.main:app --reload
```

If the API is already running, stop that process before restarting it with
the environment variable. Reload/startup still rebuilds the existing Elasticsearch
index and clears the search cache; it does NOT automatically embed documents.
The installed llama3 model can be reused; no paid inference service is used.

| Variable | Default |
| --- | --- |
| RAG_ENABLED | false |
| OLLAMA_URL | http://localhost:11434 |
| OLLAMA_EMBEDDING_MODEL | embeddinggemma |
| OLLAMA_CHAT_MODEL | llama3:latest |
| QDRANT_URL | http://localhost:6333 |

Qdrant uses a Docker volume and a collection name derived from the embedding
model name. Use a new model tag when changing embedding weights, then reindex
the documents you want to search. Never mix different embedding models.

## Try the complete workflow

Open [RAG answers](http://localhost:8000/#rag) in the frontend to upload a PDF,
index it, and ask questions with expandable page citations. You can also open
a document in the library and choose **Use in RAG** to select it for indexing.
The page shows setup instructions when RAG is disabled. The existing Search &
query tab remains retrieval-only. All data access goes through the backend API.
[Swagger UI](http://localhost:8000/docs) and the examples below remain available.

1. Upload a text-based PDF:

```bash
curl -X POST http://localhost:8000/rag/pdf \
  -F 'title=Leave policy' -F 'file=@/absolute/path/policy.pdf'
```

Copy the returned `id`. Upload stores extracted text in PostgreSQL and indexes
the whole document in Elasticsearch. It does not embed yet, and works with RAG
disabled. Page boundaries are preserved as form-feed characters in stored text.
Limits: 10 MiB, 200 pages, 1 million extracted characters. Encrypted PDFs and
PDFs without extractable text are rejected. Scanned PDFs need OCR first.

2. Index that document (or any existing document ID):

```bash
curl -X POST http://localhost:8000/rag/documents/DOCUMENT_ID/index \
  -H 'Content-Type: application/json' \
  -d '{"strategy":"recursive","chunk_size":800,"overlap":80}'
```

This splits text, embeds chunks, and replaces that document's Qdrant points.
Reindexing uses stable chunk IDs; it does not duplicate chunks. PDF ingestion
and vector indexing are deliberately separate: if Ollama is unavailable, the
stored document remains available and the indexing request can be retried.
Existing 100 test documents are not automatically embedded.

3. Ask a question:

```bash
curl -X POST http://localhost:8000/rag/query \
  -H 'Content-Type: application/json' \
  -d '{"query":"How do I request leave?","top_k":5,"score_threshold":0.3}'
```

Response: `answer`, assembled `context`, and `citations` containing document ID,
chunk ID, title, source, page, excerpt, and cosine score. Optional `source` and
`tags` filters are applied during vector retrieval. No evidence means no LLM
call and an explicit insufficient-evidence response. Scores are similarities,
not probabilities; tune the threshold using your own examples.

`GET /rag/status` shows whether RAG is configured; it is not a dependency health
check. Disabled RAG returns 503 for indexing and querying. Missing local models
or unavailable Qdrant/Ollama also return a helpful 503.

## Compare chunking

`POST /rag/chunks/preview` accepts:

```json
{
  "text": "Paste a few paragraphs here.",
  "strategy": "recursive",
  "chunk_size": 800,
  "overlap": 80,
  "similarity_threshold": 0.65
}
```

Run again with `strategy: "semantic"`. Recursive splitting prefers paragraphs,
lines, sentences, then words before falling back to characters. Semantic splitting
embeds sentence units and starts a new chunk when adjacent cosine similarity
falls below the threshold. Both enforce size limits; overlap never crosses pages.
Sizes are characters, not tokens. Semantic splitting costs extra model calls.

## Read the code in this order

1. `app/api/rag.py`: upload, preview, index, query routes.
2. `app/dto/rag.py`, `app/domain/chunks.py`: HTTP contracts vs internal model.
3. `app/ingestion/parsing.py`, `chunking.py`: pages to chunks.
4. `app/retrieval/local_models.py`: plain Ollama embed/chat HTTP calls.
5. `app/retrieval/qdrant_index.py`: vector collection, point writes, top-k query.
6. `app/services/rag.py`: pipeline and evidence assembly.

Qdrant manages the vector index (HNSW/ANN; small datasets may use a scan).
Cosine compares vector direction; ANN trades exactness for speed. Vector-only
retrieval can miss exact IDs and specialized terminology: compare it with
`/search`. BM25 + dense fusion/reranking belongs to Week 4, not this lab.

Context is capped at 6,000 characters, and citations refer only to text actually
sent to the LLM. Prompts treat evidence as untrusted data, but prompting is not a
security boundary or a guarantee of factual accuracy. Inspect answers/citations.
This is intentionally a learning project: no OCR, background jobs, answer cache,
transaction across stores, or production access control. Reindex retries repair
partial vector writes. Deletion removes current-model vectors when RAG is enabled;
query also checks PostgreSQL so deleted documents cannot supply stale evidence.
Other model collections can retain old vectors and require manual maintenance.

API references:
[Ollama embeddings](https://docs.ollama.com/api/embed),
[Ollama chat](https://docs.ollama.com/api/chat),
[Qdrant search](https://qdrant.tech/documentation/search/search/).
