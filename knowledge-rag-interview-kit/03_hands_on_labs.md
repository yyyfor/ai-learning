# Hands-on Labs

原则：不要做十个互不相关的小 demo。所有实验最终合并成一个 `Enterprise Knowledge & RAG Studio`。

---

## Lab 1 — Production-style FastAPI Knowledge API

### 目标
建立可测试、可扩展的知识平台 API。

### 必做
- FastAPI + Pydantic
- async endpoint
- service / repository 分层
- PostgreSQL metadata
- Redis cache
- pytest
- Docker Compose

### 学习资料
- FastAPI Docs: https://fastapi.tiangolo.com/tutorial/
- SQLAlchemy 2.0 Tutorial: https://docs.sqlalchemy.org/en/20/tutorial/
- Redis Developer Docs: https://redis.io/docs/latest/develop/

### 推荐仓库
- FastAPI: https://github.com/fastapi/fastapi
- Full Stack FastAPI Template: https://github.com/fastapi/full-stack-fastapi-template

### 面试验收
能解释为什么 API layer 不直接写 SQL、什么时候使用 async、如何处理 dependency injection 和 test doubles。

---

## Lab 2 — Elasticsearch BM25 Search

### 目标
建立 lexical retrieval 基线。

### 必做
- index mapping
- analyzer
- BM25
- metadata filter
- pagination
- relevance test set

### 学习资料
- Elasticsearch Search Tutorial: https://www.elastic.co/docs/reference/query-languages/esql/esql-search-tutorial
- Hybrid Search Docs: https://www.elastic.co/docs/solutions/search/hybrid-search

### 推荐仓库
- Elasticsearch Labs: https://github.com/elastic/elasticsearch-labs

### 面试验收
解释 inverted index、BM25、为什么 exact terminology 场景 lexical search 强于 vector search。

---

## Lab 3 — Vector RAG from Scratch

### 目标
不使用 RAG framework，自己搭 retrieval pipeline。

### 必做
- document parsing
- recursive / semantic chunking 对比
- embedding
- vector index
- top-k retrieval
- context assembly
- citation

### 推荐向量库（二选一）
- Qdrant: https://github.com/qdrant/qdrant
- Milvus: https://github.com/milvus-io/milvus

### 学习资料
- Qdrant docs: https://qdrant.tech/documentation/
- Milvus docs: https://milvus.io/docs

### 面试验收
解释 chunk size trade-off、ANN、cosine similarity、vector-only RAG failure modes。

---

## Lab 4 — Hybrid Retrieval + RRF + Reranker

### 目标
实现真正面向生产的 retrieval pipeline。

### 必做
- BM25 candidate set
- dense vector candidate set
- Reciprocal Rank Fusion
- reranker
- query rewrite
- metadata filter
- baseline vs hybrid evaluation

### 学习资料
- Elastic Hybrid Search: https://www.elastic.co/docs/solutions/search/hybrid-search
- Elastic Labs Hybrid Tutorial: https://www.elastic.co/search-labs/tutorials/search-tutorial/semantic-search/hybrid-search
- Haystack Hybrid Retrieval tutorial repo: https://github.com/deepset-ai/haystack-tutorials

### 推荐实验
准备 50 条问题，至少包含：精确 ID、专业名词、语义改写、时间条件、权限过滤。

### 面试验收
能够解释为什么 RRF 通常比直接融合不同 retrieval score 更稳健。

---

## Lab 5 — Taxonomy / Ontology / Semantic Model

### 目标
把“文本库”升级成“知识模型”。

### 必做
设计一个业务 ontology，例如：

Company → owns → Subsidiary
Company → signs → Contract
Contract → hasCounterparty → Customer
Contract → affects → Account
AuditFinding → relatesTo → Risk

定义：entity type、relation type、required properties、canonical identifier、version。

### 学习资料
- W3C OWL Overview: https://www.w3.org/OWL/
- RDF Primer: https://www.w3.org/TR/rdf11-primer/
- Neo4j Graph Academy: https://graphacademy.neo4j.com/

### 面试验收
能清晰解释 taxonomy vs ontology vs knowledge graph vs semantic layer。

---

## Lab 6 — Neo4j Knowledge Graph Builder & GraphRAG

### 目标
实现 entity/relation extraction、graph retrieval 和 multi-hop reasoning。

### 必做
- unstructured docs → entity/relation extraction
- schema grounding
- entity nodes + relations
- Cypher query
- graph traversal
- vector + graph retriever 对比

### 学习资料
- Neo4j GraphRAG docs: https://neo4j.com/docs/neo4j-graphrag-python/current/
- KG Builder: https://neo4j.com/docs/neo4j-graphrag-python/current/user_guide_kg_builder.html
- GraphRAG Python Package 开发者指南: https://neo4j.com/developer/genai-ecosystem/graphrag-python/

### 推荐仓库
- Neo4j GraphRAG Python: https://github.com/neo4j/neo4j-graphrag-python

### 面试验收
解释什么时候使用 graph retrieval、为什么 multi-hop relationship 不是纯 vector search 的强项。

---

## Lab 7 — Entity Resolution / Dedup / Contradiction Detection

### 目标
构建 Knowledge Refinement Pipeline。

### 输入示例
- PwC
- PricewaterhouseCoopers
- PwC China
- 普华永道
- PwC Zhong Tian LLP

### 必做
分层 matcher：
1. normalization
2. exact identifier
3. alias dictionary
4. fuzzy matching
5. embedding similarity
6. LLM classifier
7. confidence score
8. human review threshold

再加入：duplicate knowledge detection、conflicting effective dates、authority ranking。

### 推荐工具/仓库
- RapidFuzz: https://github.com/rapidfuzz/RapidFuzz
- Neo4j GraphRAG entity resolution capabilities: https://github.com/neo4j/neo4j-graphrag-python

### 面试验收
解释为什么 entity resolution 不能只依靠 embedding。

---

## Lab 8 — Knowledge Governance & Provenance

### 目标
把知识变成可治理资产。

### Knowledge Asset Metadata
- knowledge_id
- source_uri
- source_owner
- business_owner
- effective_date
- expiry_date
- version
- status
- security_level
- confidence_score
- freshness_score
- parent_version
- provenance_chain

### 必做
- draft → validate → approve → publish → deprecate
- rollback
- freshness monitor
- citation validation
- lineage chain

### 面试验收
回答：两个政策文档冲突时系统如何判断哪个可用？

---

## Lab 9 — RAG Evaluation + Regression Test

### 目标
建立 platform-level evaluation，而不是人工“感觉不错”。

### 必做
建立 golden dataset：
- query
- expected sources
- expected facts
- allowed answer
- forbidden answer

评价：
- Recall@K
- MRR
- NDCG
- answer relevance
- faithfulness
- correctness
- citation accuracy

### 推荐仓库
- Ragas: https://github.com/explodinggradients/ragas
- DeepEval: https://github.com/confident-ai/deepeval
- Arize Phoenix: https://github.com/Arize-ai/phoenix

### 学习资料
- Haystack RAG evaluation tutorials: https://github.com/deepset-ai/haystack-tutorials

### 面试验收
解释 retrieval evaluation 与 generation evaluation 为什么必须拆开。

---

## Lab 10 — Observability / SLO / Security / Cost

### 目标
让系统达到 production readiness。

### 必做
Tracing：
request → retriever → reranker → LLM → tool

Metrics：
- P50/P95 latency
- retrieval latency
- LLM latency
- error rate
- index lag
- freshness lag
- token usage
- cost/query

Security：
- RBAC / ABAC
- document ACL
- retrieval-time permission filter

SLO 示例：
- availability >= 99.9%
- P95 retrieval < 500 ms
- P95 end-to-end query < 5 s
- indexing freshness lag < 10 min

### 学习资料
- OpenTelemetry: https://opentelemetry.io/docs/languages/python/

### 推荐仓库
- OpenTelemetry Python: https://github.com/open-telemetry/opentelemetry-python
- Arize Phoenix: https://github.com/Arize-ai/phoenix

### 面试验收
设计“RAG 回答质量突然下降”的 incident response playbook。

---

## Lab 11 — Agent Fundamentals from Scratch

### 目标
先理解 Agent execution loop，再使用框架。

### 必做
- 定义 goal、state、action、observation、termination condition
- 自己实现 `model → tool call → execute → observation → model` loop
- 用 JSON Schema/Pydantic 定义 3 个工具：Knowledge Search、Calculator、Create Follow-up
- Tool input/output server-side validation
- read-only / write / external-side-effect 风险分级
- max steps、timeout、retry、token/cost budget
- 写入工具使用 idempotency key，并在执行前要求人工批准
- 记录每一步 trace，但不把敏感内容写入普通日志

### 学习资料
- OpenAI Agents SDK Quickstart: https://developers.openai.com/api/docs/guides/agents/quickstart
- OpenAI Function Calling: https://developers.openai.com/api/docs/guides/function-calling
- LangChain Agents concepts: https://docs.langchain.com/oss/python/langchain/agents

### 面试验收
能解释：LLM 只产生结构化 tool call，真正的工具执行发生在 application layer；为什么 deterministic workflow 通常比 Agent 更稳定；如何阻止 Agent 无限循环或重复写入。

---

## Lab 12 — Governed, Durable Agent Runtime

### 目标
构建可暂停、恢复、审批、审计和评估的 Agent，作为受治理 Knowledge Platform 的 consumer。

### 建议场景
Audit Issue Follow-up Agent：读取审计问题和支持文件，检索政策，生成待办；发送或更新外部系统前必须审批。

### 必做
- 显式 state graph：intake → retrieve → plan → execute → verify → approve → finalize
- checkpoint + resume；进程中断后不得重复执行已完成的 side effect
- Knowledge API → ACL Filter → Hybrid Retrieval → Provenance
- human-in-the-loop approval 与 approval expiry
- tool allowlist、least privilege、tenant/identity propagation
- prompt injection 与恶意 tool output 防护
- single agent + tools 基线；再做 handoff 或 agent-as-tool 对比
- MCP client/server 小实验：只暴露 allowlisted tools/resources
- golden tasks：成功率、tool selection、argument correctness、step efficiency、side-effect safety、evidence completeness
- OpenTelemetry/Agent trace：run、span、tool call、latency、token、cost、error、approval

### 学习资料与仓库
- OpenAI orchestration: https://developers.openai.com/api/docs/guides/agents/orchestration
- OpenAI guardrails & human review: https://developers.openai.com/api/docs/guides/agents/guardrails-approvals
- OpenAI Agent Evals: https://developers.openai.com/api/docs/guides/agent-evals
- OpenAI Agents SDK: https://github.com/openai/openai-agents-python
- LangGraph Overview: https://docs.langchain.com/oss/python/langgraph/overview
- LangGraph Repo: https://github.com/langchain-ai/langgraph
- MCP Python SDK: https://py.sdk.modelcontextprotocol.io/
- MCP Python Repo: https://github.com/modelcontextprotocol/python-sdk

### 面试验收
能够设计一次生产事故：Agent 重复创建任务或错误调用高风险工具。回答必须覆盖 containment、trace 定位、idempotency、approval record、state repair、rollback/compensation、regression test 和重新发布。

### 核心边界
Agent 是平台 consumer，不是 Knowledge Platform 本身；受治理的知识、权限与 provenance 仍由 Knowledge/RAG Platform 提供。
