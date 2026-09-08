# 12 周 Roadmap

## Week 1 — Python Backend & Platform API

目标：补齐工程底座，不把时间浪费在纯语法。

学习：FastAPI、Pydantic、asyncio、SQLAlchemy、dependency injection、pytest、API design、error handling、structured logging。

实操：建立 Knowledge Platform API，完成 `/documents`、`/search`、`/query`、`/health`。

面试输出：解释 async I/O、API/service/repository 分层、dependency injection、unit vs integration test。

## Week 2 — Storage / Search Fundamentals

目标：掌握 PostgreSQL / Redis / Elasticsearch 在知识平台中的职责边界。

学习：B+Tree、事务、MVCC、Redis TTL/cache、Elasticsearch inverted index、BM25、mapping、filter、aggregation。

实操：同一份文档写入 metadata store + search index；实现关键词检索与 metadata filtering。

## Week 3 — Basic RAG

目标：自己从零搭建 RAG，不依赖 LangChain 封装。

学习：parsing、chunking、embedding、ANN、top-k、context assembly、citation。

实操：PDF → chunks → embeddings → vector retrieval → LLM answer + citations。

## Week 4 — Advanced Retrieval

目标：从 vector-only RAG 升级为 production retrieval。

学习：BM25、dense retrieval、sparse retrieval、hybrid search、RRF、weighted fusion、reranker、query rewrite、metadata filter。

实操：实现 BM25 + dense + RRF + reranker；用 30–50 个 query 做对比评估。

## Week 5 — Knowledge Engineering

目标：理解 Taxonomy、Ontology、Semantic Layer，而不是把所有信息当文本块。

学习：entity、relation、taxonomy、ontology、schema、canonical entity、business concept model。

实操：为一个企业/审计知识域设计 ontology，并把文档中的实体与关系抽取为结构化数据。

## Week 6 — Knowledge Graph & GraphRAG

目标：理解什么时候 graph 比 vector retrieval 更合适。

学习：property graph、Cypher、graph traversal、multi-hop retrieval、community/entity-centric GraphRAG、vector+graph retrieval。

实操：Neo4j 构建 Company–Contract–Customer–Risk–Finding graph；完成 multi-hop query。

## Week 7 — Knowledge Refinement

目标：把 raw information 处理成可信知识资产。

学习：normalization、classification、dedup、entity resolution、contradiction detection、summarization、metadata enrichment。

实操：设计 refinement pipeline，输出 canonical knowledge asset。

## Week 8 — Governance / Provenance / Lifecycle

目标：实现企业级知识治理。

学习：ownership、versioning、effective date、approval、freshness、deprecation、rollback、retention、lineage、citation validation。

实操：Knowledge Asset Registry + version lifecycle + freshness job + provenance chain。

## Week 9 — Evaluation / Observability / Security

目标：能够把系统带到 production。

学习：Recall@K、MRR、NDCG、faithfulness、answer correctness、golden dataset、OpenTelemetry、SLI/SLO/SLA、RBAC/ABAC、ACL-aware retrieval、cost controls。

实操：RAG eval pipeline + traces/metrics + access-control filtered retrieval。

## Week 10 — Agent Fundamentals & Tool Calling

目标：真正理解 Agent execution loop，而不是只会调用框架 API。

学习：goal、instruction、state、action、observation、termination；function calling、structured output、tool schema、tool result validation、memory、context engineering、workflow vs agent。

实操：先不用 Agent framework，实现一个 single-agent loop；接入只读 Knowledge Search Tool、计算工具和一个需要审批的写入工具；增加 max steps、timeout、token/cost budget 和明确 stop condition。

面试输出：解释 Tool Calling 的执行边界、什么时候不用 Agent、如何防止循环和重复执行。

## Week 11 — Reliable Agent Orchestration

目标：让 Agent 从 demo 变成可恢复、可审计、可评估的系统。

学习：state graph、checkpoint、durable execution、human-in-the-loop、handoff、agent-as-tool、MCP、idempotency、retry、compensation、guardrails、approval policy、agent evaluation、trace。

实操：用 OpenAI Agents SDK 或 LangGraph 实现可暂停/恢复的 audit issue follow-up agent；低风险只读工具自动执行，高风险写入工具必须审批；保存完整 trace 和 artifact/evidence。

面试输出：解释 single agent vs multi-agent、handoff vs agent-as-tool、checkpoint vs memory，以及如何处理“工具成功但 Agent 认为失败”的状态不一致。

## Week 12 — Lead-level System Design & Mock Interview

目标：从“会实现”升级成“会做技术取舍和领导平台建设”。

练习 6 个白板题：

1. Enterprise Knowledge & RAG Platform
2. Global multi-tenant RAG Studio
3. Knowledge freshness & governance platform
4. High-scale ingestion and indexing pipeline
5. Retrieval quality incident response
6. Governed enterprise Agent Runtime

输出：每个题 30–40 分钟完整设计，必须覆盖 trade-offs、failure modes、SLO、cost、security、migration、approval boundary、rollback 和 evaluation。
