# Enterprise Knowledge & RAG Platform — 白板架构 Cheat Sheet

```text
Sources
  |-- Files / Wiki / DB / API / Email / SaaS
  v
Ingestion Gateway
  |-- connector auth
  |-- incremental sync / CDC
  |-- idempotency
  |-- checksum
  v
Raw Object Store
  v
Processing / Refinement Pipeline
  |-- parse / OCR
  |-- normalize
  |-- chunk
  |-- classify
  |-- metadata enrichment
  |-- entity/relation extraction
  |-- entity resolution
  |-- dedup / contradiction detection
  v
Knowledge Asset Registry
  |-- owner
  |-- version
  |-- effective date
  |-- ACL
  |-- provenance
  |-- freshness
  v
Storage
  |-- PostgreSQL metadata
  |-- object store
  |-- Elasticsearch lexical index
  |-- vector index
  |-- Neo4j knowledge graph
  v
Retrieval Service
  |-- query understanding
  |-- metadata/ACL filters
  |-- BM25
  |-- dense/sparse vector
  |-- graph retrieval
  |-- RRF/fusion
  |-- reranker
  |-- context builder
  v
RAG Service
  |-- prompt policy
  |-- citation/provenance
  |-- answer validation
  |-- guardrails
  v
Agent Runtime
  |-- goal / instruction / policy
  |-- state / checkpoint / resume
  |-- planner / router / termination
  |-- tool registry / MCP client
  |-- tool input-output validation
  |-- idempotency / retry / compensation
  |-- human approval / escalation
  v
Consumption Layer
  |-- REST/gRPC
  |-- SDK
  |-- RAG Studio
  |-- Agent Studio / workflow templates
  v
Platform Controls
  |-- evaluation
  |-- OpenTelemetry
  |-- SLO/SLA
  |-- rate limit
  |-- cost controls
  |-- security/audit log
```

## 设计时必须主动讲的 15 个 Trade-offs

1. lexical vs semantic retrieval
2. vector-only vs hybrid retrieval
3. pre-filter vs post-filter ACL
4. chunk size vs retrieval precision/context completeness
5. sync vs async ingestion
6. relational store vs graph store
7. generic ontology vs domain-specific ontology
8. deterministic pipeline vs LLM-driven refinement
9. online reranking quality vs latency/cost
10. centralized platform vs domain team flexibility
11. deterministic workflow vs dynamic agent
12. single agent + tools vs multi-agent
13. synchronous run vs background/durable execution
14. short-term context vs durable state/long-term memory
15. autonomous tool use vs approval-gated side effects

## Agent 执行闭环

```text
Goal
  v
Load state + policy
  v
Model chooses action
  |-- final answer -> verify -> finish
  |-- tool call -> authorize -> execute -> validate result
                                      |
                                      v
                              update state/checkpoint
                                      |
                                      +----> next step
```

每次 run 必须定义：allowed tools、identity/tenant、step/time/token/cost budgets、approval boundary、idempotency strategy、stop condition、trace 和 failure handling。

## Lead-level 结束语模板

“我不会把 RAG Platform 定义成一个 vector database + LLM wrapper。平台需要同时解决知识生命周期、检索质量、权限隔离、来源可追溯、质量评估和生产可靠性。架构设计的核心是让 downstream use-case teams 通过稳定 API/SDK 消费受治理的 knowledge capability，而不需要重复建设 ingestion、retrieval、governance 和 observability。”
