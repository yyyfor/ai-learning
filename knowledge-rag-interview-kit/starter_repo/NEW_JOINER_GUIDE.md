# New Joiner Guide

Updated 2026-10-25. Start with the [current learning map](../09_current_practice.md)
for the whole system, or [Lab 13](labs/lab13_local_voice.md) for local voice notes.
The original `/query` remains retrieval-only; `/rag/query` generates answers.

This is a learning project: a small Knowledge Platform with a browser workspace.
Your first goal is to explain how one document becomes searchable and how a query
becomes context with citations. High-concurrency work and new unit tests are not
needed for this onboarding; use a few owned demo documents and inspect results.

## 1. What exists today

Implemented: FastAPI document create/list/detail/delete, PostgreSQL storage,
Elasticsearch BM25 search with filters and pagination, Redis search caching,
context/citation assembly, a static frontend, health checks, and read-only inspectors.
Optional Elasticsearch `semantic_text` search is also implemented behind a switch.

`POST /query` does **not** call an LLM or generate an answer. It returns retrieved
documents, their scores, a combined `context` string, and `citations`.
The optional RAG pipeline adds PDF parsing, chunking, local embeddings, hybrid
BM25/vector retrieval with RRF, reranking, and LLM answers at `/rag/query`.
GraphRAG, entity refinement, governance, evaluation, optional authentication/ACL,
bounded agents and durable LangGraph execution are implemented. The main UI has
forms for Labs 6/8/9/10/11/12; refinement also has APIs in `/docs`.
Voice notes add local Whisper transcription and Ollama summaries, with explicit
save-to-document and index-for-RAG actions. See each lab for its dependencies and limits.

The [parent roadmap](../01_roadmap.md) and [hands-on labs](../03_hands_on_labs.md)
describe future learning goals as well as the starting backend/search work.
The proposed directory tree in [README](README.md) is a destination, not the
current filesystem. Use `app/agent/runtime.py` and `graph_runtime.py` to study
the implemented agent loops. Optional packages and services must still be installed/enabled.

## 2. First run

Use Docker Compose and Python **3.10 or newer**. Check your interpreter first;
replace `python3` below with an installed supported interpreter if necessary.
If `.venv` already exists, inspect its Python version before reusing it.

Before starting, ensure the configured Elasticsearch index belongs only to this
app. **Every API start or reload clears and rebuilds that index.** Do not point
`ELASTICSEARCH_INDEX` at an index shared with another application or dataset.
Use the default local connections only if those services are your learning environment.

From the directory containing `knowledge-rag-interview-kit`, run:

```bash
cd knowledge-rag-interview-kit/starter_repo
python3 --version
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
docker compose up -d postgres redis elasticsearch
python -m uvicorn app.main:app --reload --host 127.0.0.1
```

Compose starting containers does not guarantee they are ready. If API startup fails,
inspect `docker compose ps` and `docker compose logs --tail=60 postgres redis elasticsearch`,
then retry after resolving the reported problem. Keep one API process for learning.

Open the [workspace](http://127.0.0.1:8000/), [API docs](http://127.0.0.1:8000/docs),
and [health endpoint](http://127.0.0.1:8000/health). No npm install or frontend server
is needed. Health reports `storage`, `search`, and `cache`; inspect the JSON body,
because a degraded result is still an HTTP 200 response.

Defaults are PostgreSQL `postgresql://rag:rag@localhost:5432/knowledge`,
Elasticsearch `http://localhost:9200`, and Redis `redis://localhost:6379/0`.
Overrides are `DATABASE_URL`, `ELASTICSEARCH_URL`, and `REDIS_URL`.
The current Compose file selects PostgreSQL 18, Redis 8, and Elasticsearch 9.5.2;
the Python Elasticsearch client requires `>=9.5,<10`.

## 3. Project map

| File | Why it matters |
| --- | --- |
| [app/main.py](app/main.py) | Creates the app, manages startup/shutdown, registers routers, static files, errors and logging middleware. |
| [app/api/__init__.py](app/api/__init__.py) | Combines the API routers; included once by main.py. |
| [app/api/documents.py](app/api/documents.py) | Document create/list/detail/delete routes. |
| [app/api/search.py](app/api/search.py) | Search and query routes, including GET metadata parsing. |
| [app/api/inspectors.py](app/api/inspectors.py) | Read-only Redis and Elasticsearch inspection routes. |
| [app/api/health.py](app/api/health.py), [workspace.py](app/api/workspace.py) | Health, frontend entry page, and UI configuration routes. |
| [app/api/dependencies.py](app/api/dependencies.py), [errors.py](app/api/errors.py) | Resolve the startup-created service and translate missing documents to HTTP 404. |
| [app/dto/documents.py](app/dto/documents.py), [search.py](app/dto/search.py), [query.py](app/dto/query.py) | Pydantic request validation and response shapes, grouped by API feature. |
| [app/domain/documents.py](app/domain/documents.py), [search.py](app/domain/search.py) | Internal business models: StoredDocument, SearchHit, and SearchPage, including cache serialization. |
| [app/services/knowledge.py](app/services/knowledge.py) | Coordinates writes, retrieval, cache, context, citations, and health. |
| [app/repositories/documents.py](app/repositories/documents.py) | Repository contract, asyncpg SQL, table creation, and mapping database rows to StoredDocument. |
| [app/retrieval/elasticsearch_index.py](app/retrieval/elasticsearch_index.py) | Mapping, BM25/semantic queries, filters, rebuild, index inspector. |
| [app/cache.py](app/cache.py) | Redis keys, 30-second TTL, invalidation, bounded inspection. |
| [app/static/index.html](app/static/index.html) | Workspace panels and forms. |
| [app/static/app.js](app/static/app.js) | Same-origin API calls, rendering, pagination, form handling. |
| [app/static/style.css](app/static/style.css) | Workspace appearance and responsive layout. |
| [docker-compose.yml](docker-compose.yml) | Core services plus optional Kibana, Qdrant and Neo4j. |
| [pyproject.toml](pyproject.toml) | Python requirement, editable package, core and optional dependencies. |
| [app/dto/agent.py](app/dto/agent.py), [policy.py](app/agent/policy.py) | Typed agent state/tool requests and small approval helpers. |
| [app/agent/runtime.py](app/agent/runtime.py), [graph_runtime.py](app/agent/graph_runtime.py) | Bounded agent loop and durable graph, approval and recovery. |
| [app/static/labs.js](app/static/labs.js) | Main-page interactions for Labs 6/8/9/10/11/12. |
| [app/services/voice.py](app/services/voice.py), [voice.js](app/static/voice.js) | Local audio transcription, summaries and the microphone UI. |
| [Lab 11](labs/lab11_agent_foundations.md), [Lab 12](labs/lab12_agent_reliability.md), [Lab 13](labs/lab13_local_voice.md) | Implemented workflows, exercises and explicit limitations. |
| [knowledge/reference_notes.json](knowledge/reference_notes.json) | Reviewed, sourced learning notes; import using `scripts/import_reference_notes.py`. |

## 4. Follow the complete workflow

```mermaid
flowchart TD
    UI[Browser: API calls only] --> API[FastAPI routes]
    API --> S[KnowledgeService]
    S -->|Create: 1. save| PG[(PostgreSQL: source of truth)]
    S -->|Create: 2. index| ES[(Elasticsearch: searchable copy)]
    S -->|Create: 3. invalidate| R[(Redis: 30-second search cache)]
    S -->|Query: lookup| R
    R -->|Hit: cached search page| C[Assemble context and citations]
    R -->|Miss| ES
    ES -->|Search page: cache then assemble| C
    C --> API
```

**Create:** the frontend sends `POST /documents`. Pydantic validates the payload,
strips surrounding whitespace from title/content/source, and cleans/deduplicates tags.
The service adds a UUID and UTC timestamp. PostgreSQL stores the complete document,
including content, tags, and JSON metadata—not just a pointer to external text.
The Elasticsearch adapter indexes the same ID and waits for search refresh.
The service clears the project search cache and the route returns HTTP 201.

If Elasticsearch indexing raises, create attempts to delete the PostgreSQL row.
This is best-effort compensation, not a distributed transaction: either operation
may fail or have an uncertain outcome. A cache-clear failure can also produce an
error after both stores were written. Inspect before retrying; create has no
idempotency key and retrying can create another UUID/document.

**Read/delete:** list and detail read PostgreSQL. Delete removes the PostgreSQL
row first, then the Elasticsearch document, then clears cache. A missing PG row
returns 404. There is no reverse compensation if ES deletion fails; stores can
temporarily disagree. Do not practice deletion on documents you did not create.

**Query/cache miss:** `POST /query` calls `query_documents`, which calls
`search_documents`. The cache key includes query, source, sorted tags, metadata,
page, and page size. Canonical JSON is SHA-256 hashed under `knowledge:search:`.
On a miss, Elasticsearch searches and returns documents from its `_source`;
there is no PostgreSQL lookup to hydrate each search hit. The service caches that
search page for 30 seconds, then builds numbered full-document context and citations.

**Query/cache hit:** the stored search page is reconstructed without searching ES.
Context and citations are assembled again; they are not the cached object itself.
`/search` and `/query` share this path and can share a cache entry for identical
search parameters. Hits do not renew TTL. There is no cache-hit flag in the response;
inspect keys/TTL and read the branch in code instead of guessing from response speed.

**Startup/invalidation:** startup connects PG/Redis/ES, creates the PG table if absent,
ensures a compatible ES mapping, reads *all* PG documents, calls ES `delete_by_query`
with `match_all`, and adds documents sequentially with `refresh="wait_for"`.
It then clears `knowledge:search:*` and makes the service available to routes.
This happens on **every start and reload**, not only when the index is missing.
It can be slow, and a failed rebuild can leave an incomplete index. Restart only
against a dedicated app index. Successful creates/deletes also clear all matching
project cache keys; unrelated Redis keys are outside this invalidation scope.

PG is the source of truth, ES is its rebuildable search copy, and Redis is temporary
search output. Direct PG edits bypass indexing and invalidation; learn through the API.

## 5. Search modes and browser boundaries

Default `ELASTICSEARCH_SEMANTIC_ENABLED=false` uses `knowledge-documents` and BM25.
It searches `title^2` and `content` using a standard analyzer with no stopwords.
Source and metadata filters are exact matches; every requested tag must be present.
Metadata uses ES `flattened` fields with keyword-like values, not typed range queries.
POST requests use `query` and `tags`; GET `/search` uses `q` and repeated `tag` parameters.
Search pagination defaults to 10 results and allows at most 50 per page.

To opt into semantic retrieval, set this in the API terminal before starting it:

```bash
export ELASTICSEARCH_SEMANTIC_ENABLED=true
```

Restart only after confirming the dedicated-index requirement above.
The independent default index becomes `knowledge-documents-hybrid`; content copies
into `semantic_text`. BM25 and semantic matches combine through `bool.should`
scores, **not RRF or a reranker**. This is retrieval, not LLM answer generation.
It requires a usable inference endpoint and a compatible Elasticsearch license.
The default endpoint is `.elser-2-elasticsearch`; override it with
`ELASTICSEARCH_SEMANTIC_INFERENCE_ID` for an already configured endpoint.
The switch alone does not provision these prerequisites. Default BM25 needs no
model API key or inference endpoint.

To return, set `ELASTICSEARCH_SEMANTIC_ENABLED=false` and restart the API.
If you previously set `ELASTICSEARCH_INDEX`, use `unset ELASTICSEARCH_INDEX` to
restore mode-specific defaults. Mapping/mode mismatches fail startup. Separate
indexes avoid that conflict; only the selected index is rebuilt on a given start.

The browser obtains all app data through same-origin FastAPI routes. `/ui/config`
returns the mode and index name, not database credentials. Documents and search
panels use `/documents` and `/query`. Inspectors are read-only and narrowly scoped:
Redis inspection scans project string keys, shows TTL and up to 64 KiB per value,
and does not refresh TTL; ES inspection reads the current index's documents/mapping
without inference. ES inspection allows at most 20 records per page, up to page 500.

Kibana is optional: `docker compose --profile tools up -d kibana` enables the
configured 9.5.2 service. Once available, open [Kibana](http://127.0.0.1:5601/)
and create a data view for the index reported by `/ui/config`, without a time filter.
Kibana's server connects to ES; the custom frontend still calls only FastAPI.
Its presence in Compose or a UI link does not establish that Kibana is running.
The image defaults to DaoCloud's Elastic mirror; `KIBANA_IMAGE` can override it.
If port 5601 is unreachable, check `docker compose --profile tools ps -a` and
`docker compose logs --tail=60 kibana`; an incomplete image pull means no container
exists yet. Finish the pull/start command before troubleshooting the browser.

## 6. A practical reading path

For each layer, ask what goes in, what comes out, and what happens if it fails.
`async`/`await` lets requests yield while waiting for databases. Dependency injection
gives routes the startup-created service. A repository keeps SQL separate from
workflow decisions. BM25 ranks keyword matches; filters narrow the eligible documents.
TTL controls how long cached results survive; invalidation removes them after a change.

1. Open the workspace and `/docs`; identify one create payload and one query result.
2. Read the request/response classes in `app/dto/`, then the matching routes in `app/api/`: follow validation,
   `dependencies.py`, and `errors.py`. See `main.py` for application setup and router registration.
3. Read `KnowledgeService.create_document`, `search_documents`, and `query_documents`.
4. Follow those calls into the PG repository, ES adapter, and cache implementation.
5. Read `lifespan` and `rebuild` together; explain what a code-triggered reload does.
6. Read `app.js`'s `api`, `loadDocuments`, and query/inspector handlers alongside the UI.
7. Revisit parent roadmap Weeks 1–4 and Labs 1–4, then trace governance, evaluation and the real agent runtimes in Labs 11–12.
8. In Voice notes, follow capture → transcription → summary → document → RAG. Compare each model output to its input.

## 7. Five small, safe learning exercises

Use only your own fictional data. Choose a unique source such as
`new-joiner-demo-YOURNAME-YYYYMMDD`; substitute it consistently below and save IDs.
These observations assume your local services are healthy and default BM25 is active.

1. **Create your demo A.** In New document or `/docs`, submit title `Demo cobalt travel`,
   content `Cobalt travel receipts must be submitted within 30 days.`, your unique
   source, tags `["demo","travel"]`, metadata `{"team":"learning","year":2026}`.
   Expect 201, an ID/timestamp, a Documents entry from PG, and the same ID in the ES inspector.

2. **Trace your first query.** POST `/query` with
   `{"query":"cobalt","source":"YOUR_UNIQUE_SOURCE","tags":["demo"]}`.
   Expect demo A, a score, `[1]` context containing its full content, and a citation
   with its ID/title/source. There is no generated answer. Trace the call in the reading path.

3. **Observe expiry.** Immediately refresh Redis inspection and repeat the identical query.
   Expect the same key with decreasing TTL, not a renewed 30 seconds on each hit.
   Wait over 30 seconds without querying, then refresh: the key should disappear.
   Query again: expect a fresh cached page. SCAN may need another batch; other activity
   can invalidate keys, so do not treat an empty first batch as proof of no cache.

4. **Observe filters and invalidation.** Create your demo B with title `Demo cobalt equipment`,
   content `Cobalt equipment requests use the learning desk.`, the same unique source,
   tags `["demo","equipment"]`, and metadata `{"team":"learning","year":2026}`.
   Expect prior project cache entries to be cleared. Query `cobalt` with your source:
   expect both documents; add tags `["demo","travel"]`: expect only A. Add metadata
   `{"team":"unmatched-demo-team"}`: expect no hits and empty context/citations.

5. **Practice validation without changing data.** Submit a demo document with a blank
   title using `/docs`; expect 422 and no new document. Try GET `/search` with `q=cobalt`
   and metadata `[]`; expect 400 because metadata must be a JSON object. Compare
   schema validation with `parse_metadata` in `app/api/search.py`. Keep your labelled examples for later labs.

## 8. Troubleshooting and current limits

- Wrong interpreter/import errors: check `python --version`, `python -m pip --version`,
  and your working directory. Activate the intended venv; use `python -m uvicorn`.
- Connection refused/startup errors: check Docker readiness, port conflicts, connection
  overrides, image-pull errors, and ES/client major-version compatibility before retrying.
- Semantic/license/mapping errors: inspect configuration; use default BM25 while learning
  if inference prerequisites are unavailable. Do not repair by wiping data or shared indexes.
- Stale/empty cache: TTL is only 30 seconds; writes/reloads clear it, and pagination or
  filter changes create different keys. Inspector previews may be truncated.
- Missing results: compare PG detail with ES inspection, then check exact source/tags/metadata.
  After a write error, inspect both stores before retrying; partial success is possible.

This remains a local learning app. Authentication/ACL and strict governance are opt-in;
evaluation is implemented, but no distributed write transaction or durable indexing queue
is provided. Redis failures can fail searches; startup rebuilds the document index serially.
Qdrant and Neo4j have named volumes; core stores still need an explicit backup strategy.
Core service ports are published and ES security is disabled in this development setup.
The lightweight traces are not a full OpenTelemetry deployment. Voice recordings live
in page memory until downloaded, and automatic transcription/summary can be wrong.

## 9. Keep this guide useful

- When routes or schemas change, update payloads, validation notes, and expected observations.
- When storage/retrieval/cache changes, recheck ordering, failure behavior, TTL, and rebuild scope.
- When configuration changes, update first-run commands, versions, index defaults, and prerequisites.
- When a lab becomes real code, update the project map and implemented/scaffold distinction.
- Recheck frontend/inspector boundaries and links; label runtime observations with their actual date.
