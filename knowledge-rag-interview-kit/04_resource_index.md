# 官方资料与推荐仓库索引

## P0 — 必学

### Search / RAG
- Elasticsearch Hybrid Search Docs — https://www.elastic.co/docs/solutions/search/hybrid-search
- Elasticsearch Search Tutorial — https://www.elastic.co/docs/reference/query-languages/esql/esql-search-tutorial
- Elasticsearch Labs — https://github.com/elastic/elasticsearch-labs
- Haystack Tutorials — https://github.com/deepset-ai/haystack-tutorials

### Knowledge Graph / GraphRAG
- Neo4j GraphRAG Docs — https://neo4j.com/docs/neo4j-graphrag-python/current/
- Neo4j Knowledge Graph Builder — https://neo4j.com/docs/neo4j-graphrag-python/current/user_guide_kg_builder.html
- Neo4j GraphRAG Repo — https://github.com/neo4j/neo4j-graphrag-python
- Neo4j Graph Academy — https://graphacademy.neo4j.com/

### Evaluation
- Ragas — https://github.com/explodinggradients/ragas
- DeepEval — https://github.com/confident-ai/deepeval
- Arize Phoenix — https://github.com/Arize-ai/phoenix

### Observability
- OpenTelemetry Python Docs — https://opentelemetry.io/docs/languages/python/
- OpenTelemetry Python Repo — https://github.com/open-telemetry/opentelemetry-python

## P1 — Agent / Orchestration（新增必修）

### 先理解原理
- OpenAI Agents SDK Quickstart — https://developers.openai.com/api/docs/guides/agents/quickstart
- OpenAI Orchestration — https://developers.openai.com/api/docs/guides/agents/orchestration
- OpenAI Guardrails & Human Review — https://developers.openai.com/api/docs/guides/agents/guardrails-approvals
- OpenAI Agent Evals — https://developers.openai.com/api/docs/guides/agent-evals
- Function Calling — https://developers.openai.com/api/docs/guides/function-calling

### 两条实操路线
- OpenAI Agents SDK — https://github.com/openai/openai-agents-python
- LangGraph Overview — https://docs.langchain.com/oss/python/langgraph/overview
- LangGraph Repo — https://github.com/langchain-ai/langgraph
- LangGraph Academy — https://academy.langchain.com/

### Tool interoperability / MCP
- MCP Introduction — https://modelcontextprotocol.io/docs/getting-started/intro
- MCP Python SDK — https://py.sdk.modelcontextprotocol.io/
- MCP Python Repo — https://github.com/modelcontextprotocol/python-sdk

## P1 — 工程底座

### Python / Backend
- FastAPI Tutorial — https://fastapi.tiangolo.com/tutorial/
- FastAPI Repo — https://github.com/fastapi/fastapi
- Full-stack FastAPI Template — https://github.com/fastapi/full-stack-fastapi-template
- SQLAlchemy Tutorial — https://docs.sqlalchemy.org/en/20/tutorial/
- Redis Docs — https://redis.io/docs/latest/develop/

### Vector Database
- Qdrant — https://github.com/qdrant/qdrant
- Milvus — https://github.com/milvus-io/milvus

## P2 — Agent 扩展阅读（不要同时学完）

- PydanticAI Docs — https://ai.pydantic.dev/
- PydanticAI Repo — https://github.com/pydantic/pydantic-ai
- LlamaIndex — https://github.com/run-llama/llama_index
- Microsoft Agent Framework — https://github.com/microsoft/agent-framework
- CrewAI — https://github.com/crewAIInc/crewAI

说明：主线只选 OpenAI Agents SDK 或 LangGraph 之一做深。PydanticAI 适合学习 typed tools/dependencies；其他框架用于理解设计取舍，不建议把时间花在横向背 API。Multi-agent 放在 single-agent baseline 稳定之后。

## Knowledge Modeling

- RDF 1.1 Primer — https://www.w3.org/TR/rdf11-primer/
- OWL — https://www.w3.org/OWL/

## 推荐阅读顺序

1. FastAPI + SQLAlchemy（只需达到工程可用）
2. Elasticsearch BM25
3. Vector RAG from scratch
4. Hybrid Search + RRF + rerank
5. Neo4j / Cypher
6. KG Builder / GraphRAG
7. Entity Resolution / Refinement
8. Governance / Provenance
9. RAG Evaluation
10. OpenTelemetry / SLO
11. Agent execution loop + function calling
12. OpenAI Agents SDK 或 LangGraph（二选一做深）
13. State/checkpoint/HITL/guardrails/evals
14. MCP server/client 小实验
