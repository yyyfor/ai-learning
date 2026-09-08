# Enterprise Knowledge & RAG Studio — Starter Repo

建议把所有 Lab 合并到这个仓库，而不是建立多个 demo。

## 新人从这里开始

先读 [New Joiner Guide](NEW_JOINER_GUIDE.md)：从启动项目、阅读真实目录结构，
到跟踪文档写入、检索和缓存的完整流程，再通过小练习理解各层职责。
这份指南对应当前实现，包含前端、数据检查页、语义检索开关和后续学习路线。

## 推荐目录

下面是后续 Lab 的目标结构，不代表这些模块已经实现。当前目录和阅读顺序见新人指南。

```text
app/
  api/
  services/
  repositories/
  ingestion/
  refinement/
  retrieval/
  graph/
  governance/
  evaluation/
  observability/
  security/
  agent/
    runtime/
    tools/
    state/
    policy/
    evaluation/
  domain/
  dto/

labs/
  lab01_backend.md
  lab02_bm25.md
  ...

tests/
docker-compose.yml
pyproject.toml
```

## Milestone

M1 Backend API
M2 BM25 baseline
M3 Vector RAG
M4 Hybrid retrieval
M5 Ontology + Graph
M6 GraphRAG
M7 Refinement
M8 Governance
M9 Evaluation
M10 Production readiness
M11 Single Agent + governed tools
M12 Durable Agent + HITL + evaluation

## Week 1–2 已实现

Week 3 也已实现：PDF 解析、recursive/semantic 分块、Ollama 本地 embedding、
Qdrant 向量检索、LLM 回答与页码引用。默认关闭，无需 API key。
启动步骤和完整 API 示例见 [Week 3 实验指南](labs/lab03_vector_rag.md)。

当前 starter repo 已经包含一个最小但完整的 Knowledge Platform API：

- `POST /documents`：将文档元数据写入 PostgreSQL，并将可检索字段写入 Elasticsearch
- `GET /documents`、`GET /documents/{id}`、`DELETE /documents/{id}`：查看和删除文档
- `GET /search` 或 `POST /search`：默认使用 BM25 关键词检索，可选开启 `semantic_text` 混合搜索；支持 metadata 过滤和分页
- `POST /query`：保留原有搜索结果、context 和 citations；Week 3 回答使用 `POST /rag/query`
- `GET /health`：检查 PostgreSQL、Elasticsearch、Redis

代码按下面的边界组织：

```text
main.py          创建应用、启动/关闭连接、注册路由和中间件
api/             按 documents、search、inspectors、health、workspace 拆分路由
api/dependencies.py  从 app.state 获取 KnowledgeService
api/errors.py    将业务异常转换为 HTTP 响应
dto/             Pydantic 请求、响应和 agent 数据传输对象
domain/          内部业务模型：StoredDocument、SearchHit、SearchPage
KnowledgeService 协调一次文档写入、搜索和缓存失效
repositories     PostgreSQL 文档 metadata
retrieval        Elasticsearch mapping、BM25 检索、可选语义检索和过滤
cache            Redis TTL 搜索缓存
```

## 本地运行

先启动仓库已有的 Docker 服务：

```bash
cd knowledge-rag-interview-kit/starter_repo
docker compose up -d postgres redis elasticsearch
```

再安装依赖并启动 API：

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
uvicorn app.main:app --reload
```

如果系统里有多个 Python，请先确认 `python --version` 是 3.10 或更高版本。使用 `python -m pip` 可以确保 pip 和当前虚拟环境使用同一个 Python。

Week 1–2 不会安装后续 Graph、Agent 或测试实验的依赖；需要时再使用 `pip install -e ".[dev,graph,agent]"`。

默认连接 Docker Compose 中的地址：

```text
PostgreSQL: postgresql://rag:rag@localhost:5432/knowledge
Redis:      redis://localhost:6379/0
ES:         http://localhost:9200
```

也可以通过 `DATABASE_URL`、`REDIS_URL`、`ELASTICSEARCH_URL`、`ELASTICSEARCH_INDEX` 和 `ELASTICSEARCH_SEMANTIC_INFERENCE_ID` 覆盖。

`ELASTICSEARCH_SEMANTIC_ENABLED` 默认是 `false`：使用 `knowledge-documents` 索引，
只创建普通文本字段并执行 BM25 查询，不调用推理端点，不需要模型 API key。

需要语义检索时，在启动 API 的终端中开启：

```bash
export ELASTICSEARCH_SEMANTIC_ENABLED=true
uvicorn app.main:app --reload
```

开启后默认使用独立的 `knowledge-documents-hybrid` 索引，添加 `semantic_text` 字段，
并通过 `bool.should` 合并 BM25 和语义检索评分。默认推理端点是 `.elser-2-elasticsearch`，
也可通过 `ELASTICSEARCH_SEMANTIC_INFERENCE_ID` 指定其他已配置的端点。
此模式需要可用的推理端点及相应 Elasticsearch license；仅打开开关不会配置这些服务。

恢复关键词检索：设置 `ELASTICSEARCH_SEMANTIC_ENABLED=false` 并重启 API。
切换模式后，启动过程会从 PostgreSQL 重建当前索引并清除旧搜索缓存。
若设置过 `ELASTICSEARCH_INDEX`，建议先 `unset ELASTICSEARCH_INDEX` 使用各模式默认索引。
指定索引的 mapping 必须与开关一致，否则应用会报错，避免关闭语义检索后仍在写入时触发推理。

打开 `http://127.0.0.1:8000/docs` 可以直接试用 Swagger UI。

## Knowledge Studio 前端

启动 API 后打开 **http://127.0.0.1:8000/**。前端是 FastAPI 提供的静态
HTML/CSS/JavaScript，无需 npm 安装或单独启动前端服务器。

- **Documents**：分页展示 PostgreSQL 文档，点击标题查看完整内容和 JSON；New document 支持标题、内容、来源、标签和 metadata。
- **Search & query**：通过 `/query` 查询，展示相关度、完整文档入口、context 和 citations；支持来源、标签和 JSON metadata 过滤。
- **Redis cache**：通过 `/inspector/redis` 只读查看 `knowledge:search:*` 缓存，展示值、大小和剩余 TTL。缓存默认 30 秒，查询后及时刷新。大值只显示前 64 KiB，键多时可继续扫描下一批。
- **Elasticsearch**：通过 `/inspector/elasticsearch` 分页显示当前索引的 `_source` 和 mapping；同时提供 Kibana 入口和配置说明，镜像尚未下载时也能直接查看数据。只读检查限于当前应用索引，最多浏览前 10,000 条记录。

浏览器的数据请求只访问同源 FastAPI API；数据库连接和凭据保留在后端。
`/ui/config` 只返回当前索引名和语义检索开关。Redis 检查不会修改值或延长 TTL。
这是无登录的本地开发界面，请用默认 `127.0.0.1` 启动 API。

### 使用 Kibana 查看 Elasticsearch

Compose 已添加与 Elasticsearch 同版本的 Kibana 9.5.2（可选 `tools` profile）：

Kibana 默认从 DaoCloud 的 Elastic 镜像代理拉取。如需官方源，可在下面命令前设置
`export KIBANA_IMAGE=docker.elastic.co/kibana/kibana:9.5.2`。

```bash
docker compose --profile tools up -d kibana
```

首次拉取和启动可能需要几分钟。打开 **http://127.0.0.1:5601/**，进入
**Stack Management → Data Views → Create data view**，索引填写 `knowledge-documents`
（若开启语义检索则为 `knowledge-documents-hybrid`；自定义索引使用 `/ui/config` 返回的名称），
选择不使用时间过滤器，再去 **Discover** 查看文档。

也可在 **Dev Tools** 执行：

```text
GET knowledge-documents/_search
{ "query": { "match_all": {} }, "size": 20 }

GET knowledge-documents/_mapping
```

Kibana 的服务端连接 Compose 内的 Elasticsearch；自定义前端不会直连 Elasticsearch。
Kibana 端口只绑定本机，沿用当前 Elasticsearch 关闭安全认证的本地开发配置。
参考 [Elastic 官方 Docker 配置说明](https://www.elastic.co/docs/deploy-manage/deploy/self-managed/install-kibana-with-docker)。

创建文档：

```bash
curl -X POST http://127.0.0.1:8000/documents \
  -H 'Content-Type: application/json' \
  -d '{"title":"员工报销政策","content":"差旅报销需要在 30 天内提交。","source":"handbook","tags":["finance","policy"],"metadata":{"team":"finance","year":2026}}'
```

关键词搜索和 metadata 过滤：

```bash
curl 'http://127.0.0.1:8000/search?q=报销&source=handbook&metadata=%7B%22team%22%3A%22finance%22%7D'
```

`POST /query` 不调用大模型，保留检索和组装上下文的原有行为；Week 3 的分块、向量检索和大模型回答使用 `/rag/` 下的接口。
