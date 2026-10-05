# Beginner Step-by-Step Guide and 16-Week Learning Plan

**Target:** interviews for **RAG / Knowledge Platform Engineer** *and* **AI Agent Engineer**.
**Assumes:** you can write basic Python. Everything else is taught in order.
**Pace:** about 10–12 hours/week (2 hours on weekdays plus a longer weekend session). A compressed 8-week version is in §4.

How the kit fits together:

| File | Use it for |
|---|---|
| **This file** | The route: what to do each week, in which order, and how to check yourself |
| [07_agent_interview_prep_guide.md](07_agent_interview_prep_guide.md) | Interview Q&A in English, glossary, your project story |
| [02_interview_bank.md](02_interview_bank.md) | 110 short Chinese Q&As for extra depth |
| [starter_repo/NEW_JOINER_GUIDE.md](starter_repo/NEW_JOINER_GUIDE.md) | First run and project map |
| `starter_repo/labs/*.md` | Hands-on walkthrough per lab |
| Study site (web page, EN/中文) | Self-quiz with flashcards, the plan and the glossary on one page |

---

## 1. Ground rules

1. **Run before you read.** For every feature, first make it work and watch its output, then read the code that produced it.
2. **One question per file.** Don't read a file "to understand it". Read it to answer one specific question (they're listed per week).
3. **Break things on purpose.** Each week has a "break it" step. Watching a failure teaches more than reading about it.
4. **Say it out loud.** Every week ends with a timed spoken answer (2 minutes). Record it on your phone.
5. **Three outputs a week:** a runnable change or experiment, a one-page note (ADR style: problem, options, decision, trade-offs), and a recorded answer.
6. **When stuck for over 30 minutes:** write down exactly what you expected vs what happened, check §6 troubleshooting, then ask (a colleague or an AI assistant) with that note.

---

## 2. The map (what you're building up to)

```text
Documents ──► parse ──► chunk ──► embed ──► Elasticsearch (words) + Qdrant (vectors) + Neo4j (relations)
                                                        │
Question ──► rewrite ──► BM25 + vector ──► RRF fuse ──► rerank ──► top chunks ──► LLM answer + [1][2] citations
                                                        │
Governance (approved? current?) · ACL (may this user see it?) · Evaluation (is it good?) · Observability (what happened?)
                                                        │
Agent: goal ──► model proposes action ──► app validates + executes ──► observation ──► ... ──► finish
       + tools, budgets, human approval, idempotent writes, checkpoints, memory, MCP, trajectory evaluation
```

**Weeks 1–9 build the knowledge platform. Weeks 10–12 build the agent on top of it. Week 13 covers the model and ecosystem knowledge. Weeks 14–16 turn it all into interview performance.**

---

## 3. The 16-week plan, step by step

Each week lists **Goal → Learn → Do → Break it → Check yourself → Output**. "Check yourself" questions are answered in the 07 guide or the study site.

### Week 0: Setup and prerequisites (≈ 6–10 h)

**Goal:** the project runs on your machine and you know the tools.

**Learn (only as much as needed):**
- HTTP and REST: GET vs POST, status codes, JSON bodies.
- Docker: image vs container, `docker compose up -d`, `docker ps`, `docker logs`.
- Git: `status`, `add`, `commit`, `branch`, `log`.
- SQL: `SELECT … WHERE … ORDER BY`.
- Python: virtual environments, `pip install -e .`, `async`/`await` at the "what it's for" level.

**Do:**
1. Follow [NEW_JOINER_GUIDE §2 First run](starter_repo/NEW_JOINER_GUIDE.md#2-first-run).
2. `cd starter_repo && source .venv/bin/activate && pip install -e '.[dev,graph,agent]'`
3. `docker compose up -d postgres redis elasticsearch && docker compose --profile rag up -d qdrant`
4. Install Ollama and run `ollama pull llama3 && ollama pull embeddinggemma`.
5. `pytest -q`. All tests should pass.
6. `RAG_ENABLED=true sh scripts/start_local.sh`, then open `http://127.0.0.1:8000/` and `http://127.0.0.1:8000/docs`.

**Check yourself:** Which Docker service stores document metadata? Which does keyword search? Which stores vectors?
**Output:** a screenshot of Swagger and passing tests; a note listing the five services and what each one does.

---

### Phase 1: Backend and search foundations

#### Week 1: The Knowledge API (Lab 1) (≈ 10 h)

**Goal:** understand how a request flows through a layered API.

**Learn:** FastAPI routes, Pydantic models (validation), dependency injection, service/repository layering, async I/O, Redis caching with a TTL.

**Do:**
1. In Swagger: `POST /documents` → `GET /documents/{id}` → `DELETE /documents/{id}`.
2. Trace one request through code: [app/main.py](starter_repo/app/main.py) → `app/api/documents.py` → `app/services/knowledge.py` → `app/repositories/documents.py`.
3. Read [app/cache.py](starter_repo/app/cache.py): when is the cache cleared?

**Break it:** send a document with an empty title. Which layer rejects it, and with what status code?
**Check yourself:** Why doesn't the API layer write SQL directly? What does `async` buy you here? Why is the cache invalidated on writes?
**Output:** a sequence diagram of `POST /documents` (boxes and arrows on paper is fine).

#### Week 2: BM25 keyword search (Lab 2) (≈ 10 h)

**Goal:** understand lexical retrieval and why it's still essential.

**Learn:** inverted index, tokenization and analyzers, BM25 (term frequency, inverse document frequency, length normalization), filters, pagination.

**Do:**
1. Seed data (`python scripts/seed_lab_examples.py`), then `GET /search?q=annual leave`.
2. Search `C-101` vs `contract one hundred one`. Why does one work and not the other?
3. Read `app/retrieval/elasticsearch_index.py`: find the mapping and the query.

**Break it:** search a synonym the documents don't contain ("vacation"). This is BM25's blind spot.
**Check yourself:** When does BM25 beat vector search? What does IDF reward?
**Output:** a 5-query table (query, top result, correct?), which becomes your first mini golden set.

---

### Phase 2: RAG core

#### Week 3: Embeddings, chunking and vector RAG (Lab 3) (≈ 12 h)

**Goal:** build intuition for embeddings and the basic RAG pipeline.

**Learn:** what an embedding is, cosine similarity, ANN/HNSW (approximate), chunk size and overlap, recursive vs semantic chunking, grounding and citations.

**Do:** follow [labs/lab03_vector_rag.md](starter_repo/labs/lab03_vector_rag.md): upload a PDF, preview chunks with different sizes, index, then `POST /rag/query`.
**Read:** [app/ingestion/chunking.py](starter_repo/app/ingestion/chunking.py) (question: what does overlap cost?), then `app/services/rag.py` (question: where do citation numbers come from?).

**Break it:** set chunk_size to 100, then to 3000. Ask the same question and compare answers and citations.
**Check yourself:** Why must query and documents use the same embedding model? Why does RAG reduce hallucination but not eliminate it?
**Output:** a chunk-size comparison with your conclusion.

#### Week 4: Hybrid retrieval, RRF, reranking, evaluation (Lab 4) (≈ 12 h)

**Goal:** the core of every production RAG system.

**Learn:** why hybrid; RRF (hand-compute it); bi-encoder vs cross-encoder; query rewriting; Recall@K, MRR, NDCG.

**Do:** follow [labs/lab04_hybrid_retrieval.md](starter_repo/labs/lab04_hybrid_retrieval.md). Call `POST /rag/hybrid` with `mode` = `bm25`, `vector` and `hybrid`, and with `rerank` on and off. Run `python eval/run_eval.py --modes bm25,vector,hybrid,hybrid+rerank --k 10`.
**Read:** [app/retrieval/fusion.py](starter_repo/app/retrieval/fusion.py), [app/evaluation/metrics.py](starter_repo/app/evaluation/metrics.py), [app/services/hybrid.py](starter_repo/app/services/hybrid.py).

**Break it:** stop Qdrant (`docker compose stop qdrant`) and run a hybrid query. You get a warning, not an error. Start it again.
**Check yourself:** compute RRF for doc A (rank 1 BM25, rank 3 vector) vs doc B (rank 2 BM25 only). Answer: A ≈ 0.0323 > B ≈ 0.0161.
**Output:** a metrics table for the three modes, plus a 2-minute recorded answer to "Why hybrid search?"

---

### Phase 3: Knowledge engineering

#### Week 5: Ontology and knowledge modelling (Lab 5) (≈ 8 h)

**Goal:** turn "a pile of text" into "a model of the business".

**Learn:** taxonomy vs ontology vs knowledge graph vs semantic layer; competency questions; canonical identifiers.

**Do:** read the minimal ontology in [app/dto/graph.py](starter_repo/app/dto/graph.py). Write 5 competency questions ("Which customers are affected by contracts Acme signed?") and check that the ontology can answer them.
**Check yourself:** Why start from competency questions instead of "model every field"?
**Output:** your ontology diagram, extended with one new entity type and one new relation, plus a justification.

#### Week 6: Knowledge graph and GraphRAG (Lab 6) (≈ 10 h)

**Goal:** multi-hop questions with explainable paths.

**Do:** follow [labs06_08_09_10_11.md §1](starter_repo/labs/labs06_08_09_10_11.md): start Neo4j, extract entities and relations, review, write to the graph, then compare vector vs graph on a two-hop question.
**Break it:** ask a question needing three hops. What does traversal need (hop limits, relation filters)?
**Check yourself:** GraphRAG vs vector RAG: when is each better? Why must every edge carry its source text?
**Output:** a two-hop example showing the evidence path.

#### Week 7: Entity resolution, duplicates, contradictions (Lab 7) (≈ 8 h)

**Do:** follow [labs/lab07_entity_resolution.md](starter_repo/labs/lab07_entity_resolution.md). Run the Swagger examples and the exercises.
**Read:** [app/refinement/entity_resolution.py](starter_repo/app/refinement/entity_resolution.py) and its tests.
**Break it:** lower `MERGE_THRESHOLD` to 0.8 and find the wrong merge.
**Check yourself:** Why not use embeddings for identity? What is blocking, and what does it cost? What is the transitivity guard for?
**Output:** a 2-minute answer to "Design entity resolution for 10 million company records."

---

### Phase 4: Trust, quality and operations

#### Week 8: Governance, provenance, lifecycle (Lab 8) (≈ 8 h)

**Do:** [labs06_08_09_10_11.md §2](starter_repo/labs/labs06_08_09_10_11.md): register metadata, move a document through draft → validated → approved → published, then deprecate it and roll back. Turn on `GOVERNANCE_ENABLED=true` and confirm that unpublished documents are never retrieved.
**Check yourself:** provenance vs lineage vs citation; why snapshots are immutable; how deletion must cascade.
**Output:** a diagram of the lifecycle with who may perform each transition.

#### Week 9: Evaluation, observability, security (Labs 9–10) (≈ 12 h)

**Do:** [labs06_08_09_10_11.md §3–4](starter_repo/labs/labs06_08_09_10_11.md): run generation evaluation with a baseline, check `/observability/summary`, and turn on `SECURITY_ENABLED` with two identities to prove ACL filtering.
**Read:** [app/security.py](starter_repo/app/security.py), [app/services/evaluation.py](starter_repo/app/services/evaluation.py), [app/observability.py](starter_repo/app/observability.py).
**Break it:** as a low-clearance user, try to retrieve a restricted document through `/rag/query` *and* through the agent. Both must fail.
**Check yourself:** Why must ACL be enforced before the LLM sees text? What are the risks of LLM-as-judge? SLI vs SLO vs SLA?
**Output:** a one-page "RAG quality dropped: incident runbook", based on Bank #79.

---

### Phase 5: Agents

#### Week 10: The agent loop from scratch (Lab 11) (≈ 12 h)

**Goal:** understand exactly what an "agent" is before using any framework.

**Do:** follow [labs/lab11_agent_foundations.md](starter_repo/labs/lab11_agent_foundations.md), steps 1–9 of its table.
**Read:** [app/agent/runtime.py](starter_repo/app/agent/runtime.py) top to bottom, then [tests/test_agent_runtime.py](starter_repo/tests/test_agent_runtime.py). Every test name is a behavior you should be able to explain.
**Break it:** run the combined task 5 times without `required_tools` and count the wrong answers. That's your war story.
**Check yourself:** Who executes a tool call? What are all the stop conditions? How is a double approval prevented?
**Output:** a drawing of the loop from memory and a 2-minute answer to "What is an AI agent?"

#### Week 11: Tools, memory, context, reliability (Lab 11 upgrades) (≈ 10 h)

**Learn:** function calling vs structured output; parallel tool calls; context engineering; memory types (semantic, episodic, procedural); approval expiry; crash recovery; idempotency.
**Do:**
1. Read [app/agent/memory.py](starter_repo/app/agent/memory.py) and its tests.
2. Optional (downloads ~4–5 GB): `ollama pull qwen2.5:7b`, restart with `OLLAMA_TOOL_MODEL=qwen2.5:7b`, and run a `"mode":"native_tools"` task. Compare it with structured mode.
3. Read `approve()` and explain why the ledger is checked *before* expiry.

**Break it:** kill the API while a run is `running` (Ctrl+C during a slow model call), restart, and `POST /agent/runs/{id}/resume`.
**Output:** the crash-point table from Lab 11 §3.4 in your own words.

#### Week 12: Durable agent, MCP, evaluation (Lab 12) (≈ 14 h)

**Do:** follow [labs/lab12_agent_reliability.md](starter_repo/labs/lab12_agent_reliability.md) fully:
1. The v2 run flow in Swagger, including approval.
2. `python scripts/lab12_crash_demo.py`, which must print PASS.
3. Run the MCP server and connect it to Claude Code (or another MCP client).
4. `python eval/run_agent_suite.py --seed-injection --trials 1` once, then `--trials 3`.

**Read:** [app/agent/graph_runtime.py](starter_repo/app/agent/graph_runtime.py), [app/mcp_server.py](starter_repo/app/mcp_server.py), [app/evaluation/agent_metrics.py](starter_repo/app/evaluation/agent_metrics.py).
**Check yourself:** checkpoint vs memory vs ledger; why verify/approve precede execute; why nodes run as the requester; what MCP doesn't solve; pass@k vs pass^k.
**Output:** the suite report, plus a one-page ADR on "single agent vs multi-agent for this use case" using your numbers.

---

### Phase 6: Model and ecosystem knowledge

#### Week 13: LLM fundamentals and the ecosystem (≈ 10 h)

This is what the repo can't teach by running it. Study it from the 07 guide §6 and the study site's **Models & ecosystem** questions.

| Day | Topic | Resource (pick one) |
|---|---|---|
| 1 | Transformers, attention, tokens | Jay Alammar, *The Illustrated Transformer*; Karpathy, *Intro to LLMs* |
| 2 | Training pipeline: pretraining → SFT → RLHF/DPO → RL for reasoning | Karpathy, *Deep Dive into LLMs like ChatGPT* |
| 3 | Fine-tuning, LoRA/QLoRA, distillation; when *not* to fine-tune | Hugging Face PEFT docs |
| 4 | Inference: KV cache, batching, quantization, speculative decoding, TTFT; prompt caching | vLLM docs; your provider's prompt-caching docs |
| 5 | Reasoning models, frameworks (LangGraph, OpenAI Agents SDK, Claude Agent SDK), protocols (MCP, A2A) | Anthropic *Building Effective Agents*; MCP docs |
| 6 | Benchmarks (SWE-bench, τ-bench, GAIA, BFCL…) and security frameworks (OWASP LLM Top 10, NIST AI RMF, MITRE ATLAS) | OWASP GenAI site; τ-bench paper |

**Output:** answer every question in the **Models & ecosystem** section out loud, and re-study any answer that runs over 2 minutes or includes "basically".

---

### Phase 7: Interview performance

#### Week 14: Your story and system design (≈ 10 h)

1. Memorize and record the **2-minute pitch** (07 guide §4.1). Then do a 5-minute version.
2. Practice two whiteboard designs, 40 minutes each, using the template (07 guide §5-H):
   - An enterprise knowledge assistant agent (your repo at scale).
   - A customer-support agent that issues refunds.
3. For each, list 5 failure modes and how you'd detect them.

#### Week 15: Mock interviews (≈ 10 h)

- 3 mock sessions of 60 minutes each: 15 min project deep-dive, 25 min system design, 20 min rapid-fire questions from the study site (use **Shuffle** and **Starred only**).
- Live coding from memory: the agent loop (J1), RRF (J2), Recall@K/MRR (J3), retry with backoff (J4).
- After each mock, write down the three weakest answers and redo them the next day.

#### Week 16: Polish (≈ 6–8 h)

- Re-run all tests and demos so everything works if they ask for a live demo.
- Final pass through the glossary; every term should take under 20 seconds to explain.
- Prepare questions to ask the interviewer (07 guide §8).
- Rest the day before.

---

## 4. Compressed 8-week version (about 15–20 h/week)

| Week | Covers |
|---|---|
| 1 | Week 0 + Weeks 1–2 (setup, API, BM25) |
| 2 | Weeks 3–4 (RAG core, hybrid, evaluation) |
| 3 | Weeks 5–7 (ontology, graph, entity resolution): skim ontology, do Labs 6–7 |
| 4 | Weeks 8–9 (governance, evaluation, security) |
| 5 | Weeks 10–11 (agent loop, tools, memory, reliability) |
| 6 | Week 12 (Lab 12, MCP, evaluation suite) |
| 7 | Week 13 (models & ecosystem) + pitch |
| 8 | Weeks 14–16 (design practice, mocks, polish) |

If you have **2 weeks**: Weeks 3, 4, 10, 12 and 13, plus the pitch and the ★ questions only.

---

## 5. Daily routine (on a 2-hour weekday)

| Minutes | Activity |
|---|---|
| 0–10 | Flashcards: 10 random questions on the study site; say each answer before revealing |
| 10–70 | The week's "Do" step: run, observe, read the one file, answer its question |
| 70–100 | "Break it" or an exercise; write down what you saw |
| 100–120 | Write 5 lines in your weekly note; record one 2-minute answer |

---

## 6. Troubleshooting (the problems beginners hit most)

| Symptom | Likely cause | Fix |
|---|---|---|
| `Connection refused` on 8000 | API not started, or started in another terminal | `sh scripts/start_local.sh`; check the control page on 8001 |
| API starts slowly | First start syncs Elasticsearch indexes | Wait; watch the log |
| `/rag/*` or `/agent/*` returns 503 | `RAG_ENABLED` not set, or Ollama not running | `RAG_ENABLED=true sh scripts/start_local.sh`; `ollama list` |
| `/agent/v2/*` returns 503 | Agent extras not installed | `pip install -e '.[agent]'` |
| Agent run `failed` with `ToolCallingUnsupported` | `native_tools` with a model without tool support | Use structured mode or set `OLLAMA_TOOL_MODEL` to a tool-capable model |
| `failed to parse grammar` from Ollama | A JSON Schema the local grammar can't compile (nested nullable objects, very long `maxLength`) | Flatten the schema; see `app/dto/agent_graph.py` |
| Answers are wrong but retrieval metrics are fine | A generation or citation problem, not retrieval | Compare Recall@K with citation accuracy (Lab 9) |
| A small model gives a different tool path each time | Non-determinism plus a weak model | Use `required_tools`, evaluate with repeated trials, or use a stronger model |
| Tests fail after `git pull` | New dependencies | `pip install -e '.[dev,graph,agent]'` |

---

## 7. Self-assessment checklist (you're ready when all are ✅)

**Knowledge platform**
- [ ] I can draw the ingestion and query pipelines and name one design choice per stage.
- [ ] I can hand-compute RRF and Recall@K / MRR / NDCG.
- [ ] I can explain hybrid search, reranking, chunking trade-offs and query rewriting with examples from my repo.
- [ ] I can explain ontology vs graph, GraphRAG vs vector RAG, and entity resolution with a transitivity guard.
- [ ] I can explain governance lifecycle, provenance, ACL-at-retrieval, and how to debug a quality drop.

**Agent engineering**
- [ ] I can write a minimal agent loop from memory, with validation, stop conditions and a pending write.
- [ ] I can explain function calling vs structured output, and state vs context vs memory.
- [ ] I can explain idempotency, the execution ledger, checkpoints and crash recovery with my demo.
- [ ] I can explain prompt injection (direct and indirect), the lethal trifecta, and my layered defenses.
- [ ] I can explain MCP (and what it doesn't solve), A2A, and when multi-agent is justified.
- [ ] I can read my evaluation report: pass@1, pass^k, unapproved writes.

**Models & ecosystem**
- [ ] I can answer every "Models & ecosystem" question in under 2 minutes.

**Delivery**
- [ ] 2-minute pitch recorded; 2 system designs practiced; 3 mocks done.
