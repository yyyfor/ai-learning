# Lab 4 完整学习指南：Hybrid Retrieval、RRF 与 Reranker

这份指南对应 `03_hands_on_labs.md` 的 **Lab 4**。后面的 roadmap 与 lab 编号并不完全一致；这里始终按 lab 编号。
建议先花 30 分钟理解链路，再花 60–90 分钟跑实验，最后对照代码解释每一步。

## 1. 学完应该能回答什么？

1. 为什么关键词搜索和向量搜索都需要？
2. 为什么不能把 BM25 分数与 cosine 分数直接相加？
3. RRF 是什么，它解决了什么，又没有解决什么？
4. `candidate_k`、`top_k`、reranker 分别在哪一步起作用？
5. 怎么证明 hybrid 更好，而不是凭几次回答的感觉？
6. metadata filter 为什么必须在检索时执行？

前置知识：Lab 1 的 API/service/repository 分层；Lab 2 的 Elasticsearch；Lab 3 的 chunk、embedding、Qdrant。
不需要先学 LangChain。这里故意直接写 Python，让关键步骤可见。

## 2. 先区分三个接口

| 接口 | 检索单位 | 调用生成模型？ | 用途 |
|---|---|---|---|
| `/search` | 整份 document | 否 | Lab 2 文档关键词搜索 |
| `/rag/hybrid` | chunk | 只有开启 rewrite/rerank 才会调用 | 单独观察检索结果、评估排名 |
| `/rag/query` | chunk | 有证据时生成回答 | 最终 RAG 问答 |

Hybrid search 是检索策略；RAG 是“检索证据 + 让模型根据证据回答”的整个流程。
LangChain 是编排工具库，不等于 RAG，也不是实现 RAG 的必要条件。

## 3. 写入链路与查询链路

```text
POST /documents 或 /rag/pdf
  └─ PostgreSQL: 原文、标题、metadata（事实来源）
     └─ POST /rag/documents/{id}/index
         └─ chunk_pages → 同一组 chunk / 同一组 chunk_id
             ├─ Elasticsearch knowledge-chunks: text → BM25
             └─ Ollama embedding → Qdrant: vector → cosine similarity

POST /rag/hybrid
  → 校验请求、计算服务端 ACL/发布状态允许的文档 ID
  → 可选 query rewrite
  → Elasticsearch BM25 ─┐
  → Ollama embed → Qdrant┴→ RRF → 可选 reranker → top_k
  → PostgreSQL 检查文档是否仍然存在

POST /rag/query
  → 相同检索链路 → 组装 context + 引用编号 → Ollama answer
```

只上传 PDF 并不意味着已建立 RAG 索引。必须再执行 index。
`build_record()` 使用 `uuid5(document_id:chunk_position)`，确保两个检索器说的是同一块文本。
若两个库各自生成随机 ID，RRF 会把相同内容当成两个候选，无法正确合并。

这里的 hybrid 是 **应用层 Elasticsearch BM25 + Qdrant dense vectors**，不是 Elasticsearch `semantic_text`。
`ELASTICSEARCH_SEMANTIC_ENABLED=false` 不会关闭这条 hybrid 链路。无需云 API key。

## 4. 用一组例子理解检索差异

假设有三份文档：

- A：`POL-2026-017`，规定全职员工每年有 20 天年假。
- B：休假申请流程，描述如何在系统提交申请。
- C：服务器维护手册，描述系统离线与休眠。

问“POL-2026-017 规定什么？”时，精确 ID 是 BM25 的强项。
问“今年我可以休多少天？”时，向量更可能连接“休多少天”和“年假额度”。
但向量也可能把“休假”和“休眠”混淆。Hybrid 让两种不同信号互相补充，不保证每道题都胜出。

BM25 主要考虑词频、逆文档频率和长度归一化。分数无固定上界，且随查询、语料变化。
本项目向量检索使用 cosine similarity；它衡量向量方向相近程度，不是“答案正确的概率”。
不同分数不在同一标尺，直接相加会让数值较大的检索器主导。

## 5. 手算一次 RRF

公式：`score(d) = Σ weight_i / (k + rank_i(d))`，排名从 1 开始。
本项目默认 `k=60`；这里的 k **不是** top_k。

| 文档 | BM25 排名 | Vector 排名 | RRF 得分 |
|---|---:|---:|---:|
| A | 1 | 2 | 1/61 + 1/62 ≈ 0.032522 |
| B | 2 | 1 | 1/62 + 1/61 ≈ 0.032522 |
| C | 3 | 未出现 | 1/63 ≈ 0.015873 |

未出现的列表贡献 0，不是补一个末尾排名。原查询权重 1，改写查询默认权重 0.5。
RRF 不比较 BM25/cosine 的原始分数，只比较各自排名；因此稳健，但也丢失了分数差距的信息。
例如 BM25 第一名比第二名强很多，RRF 并不知道差距有多大。
查看 `app/retrieval/fusion.py`：去重、排名从 1 开始、相同分数的稳定排序。

## 6. Reranker 和 query rewrite 各负责什么？

**Rewrite** 在检索前生成同义表达，扩大召回。原始问题始终保留。
它可能把精确编号改坏，所以改写票权更低，并且默认关闭。

**Reranker** 在检索后重新判断“问题与候选文本到底有多相关”。
默认实现使用本地 Ollama 为候选打分；可配置其他实现，但首次学习先用 Ollama。
本项目最多重排 `3 * top_k` 个融合后的候选，再返回 top_k。
reranker 无法找回候选池里不存在的正确文档：先看召回，再优化排序。
它也不是事实核验器，不能保证最终模型不产生幻觉。

`rerank=true` 只是请求开启；必须查看响应 `reranked` 和 `warnings`，确认实际执行成功。
失败时系统可能退回原始融合排序，不应该把这种结果算作“reranker 改善了质量”。

## 7. 按调用顺序读代码

| 阅读顺序 | 文件 / 入口 | 重点 |
|---|---|---|
| 1 | `app/dto/rag.py` | 默认参数、请求与响应字段 |
| 2 | `app/api/rag.py` | `/hybrid` 与 `/query` 的区别 |
| 3 | `app/services/rag.py` | 双写索引、context、citations |
| 4 | `app/services/hybrid.py` | 完整检索 orchestration |
| 5 | `app/retrieval/chunk_index.py` | BM25 mapping、filter、top candidates |
| 6 | `app/retrieval/qdrant_index.py` | vector 查询和相同的过滤条件 |
| 7 | `app/retrieval/fusion.py` | 手算结果对照实现 |
| 8 | `app/retrieval/rerank.py` / `query_rewrite.py` | 可选模型调用与降级 |
| 9 | `app/evaluation/metrics.py` / `eval/run_eval.py` | 指标计算与横向比较 |

建议在 VS Code 给 `RagService.retrieve`、`HybridRetrievalService.retrieve`、`reciprocal_rank_fusion` 打断点。
观察 `jobs → outcomes → rankings → fused → candidates → hits`，而不是从头背每一行。

## 8. 启动与首次实验

所有命令在 `starter_repo` 目录执行。若服务已启动，不要再开第二份。

```sh
source .venv/bin/activate
docker compose up -d postgres redis elasticsearch
docker compose --profile rag up -d qdrant
ollama pull embeddinggemma
ollama pull llama3:latest
RAG_ENABLED=true sh scripts/start_local.sh
```

Ollama 应已在本机运行；`ollama list` 可查看模型。
浏览器打开 `http://127.0.0.1:8000/docs`，或用以下 curl。

```sh
curl http://127.0.0.1:8000/rag/status
curl -X POST http://127.0.0.1:8000/documents \
  -H 'Content-Type: application/json' \
  -d '{"title":"POL-2026-017 Annual Leave","content":"Policy POL-2026-017: Full-time employees receive 20 days of annual leave each year. Leave requests require manager approval.","source":"lab4","tags":["hr"],"metadata":{"team":"people"}}'
```

复制返回的 `id`，把下面的 `<DOCUMENT_ID>` 替换掉。保存第二份流程文档与第三份无关文档，再分别 index，结果对比更明显。

```sh
curl -X POST http://127.0.0.1:8000/rag/documents/<DOCUMENT_ID>/index \
  -H 'Content-Type: application/json' \
  -d '{"strategy":"recursive","chunk_size":800,"overlap":80}'

curl -X POST http://127.0.0.1:8000/rag/hybrid \
  -H 'Content-Type: application/json' \
  -d '{"query":"How many days can I take off each year?","mode":"hybrid","source":"lab4","top_k":3,"candidate_k":30,"rerank":false,"rewrite":false}'
```

依次只修改一个变量：

1. mode 改为 `bm25`，记录 document_id、rank、耗时。
2. mode 改为 `vector`，其他参数保持不变。
3. mode 改为 `hybrid`。
4. hybrid + `rerank:true`。
5. hybrid + `rewrite:true`。
6. hybrid + 两个开关都开启。

不要一开始同时换模型、改 chunk size、开 rerank，否则无法判断哪个变化导致结果改善。
最后把 endpoint 改为 `/rag/query`，查看 context、answer 与 citations 是否对应。
本地模型第一次加载可能很慢；可以先用 bm25 验证索引，再测 vector，再测生成。

## 9. 如何读返回结果

- `hits[].chunk_id`：融合的共同身份。
- `bm25_score` / `vector_score`：原始信号；未被该检索器找到时可能为空。
- `ranks`：例如 `bm25:0=2` 指原始问题在 BM25 结果里排第二。
- `retrievers`：该候选来自哪个检索器家族。
- `fused_score`：RRF 分数，不能解释为置信概率。
- `rerank_score`：可选重排分数；和 fused_score 也不是相同量纲。
- `variants`：原问题与改写后的问题。
- `timings_ms`：rewrite/embed/retrieve/fuse/rerank/total，便于找到慢的阶段。
- `warnings`：部分依赖失败或模型重排降级，不要忽略。

`candidate_k` 是每个检索器/改写的候选深度，同时限制融合池；`top_k` 是最终返回数量。
`score_threshold` 只作用于 dense cosine，不会过滤 BM25，也不是 RRF threshold。
`context` 当前最多 6000 **字符**，不是 6000 token；因此返回候选不一定全部进入上下文。

## 10. Metadata、权限与生命周期

尝试在请求中加 `"metadata":{"team":"people"}` 或 `"tags":["hr"]`。
两个检索库都要执行同一套过滤。只在 top_k 后过滤，可能剩下 0 条，即使第 6 条是合法好结果。

用户提交的 metadata filter 只是业务筛选，**不能作为身份认证**。
Lab 10 通过 bearer identity 计算 tenant/ACL/security_level 允许的文档 ID，再交给每个检索器。
Lab 8 开启 `GOVERNANCE_ENABLED=true` 后，未登记、未发布、过期或尚未生效的文档不会参与检索。
先关着这两个可选开关理解 Lab 4，再逐步开启并观察结果变化。

## 11. 做一套有意义的评估

复制 `eval/golden_set.example.json` 为你自己的 `eval/golden_set.json`，把占位 ID 换成实际文档 ID。
扩展到 30–50 道题：精确 ID、术语、语义改写、日期/metadata 条件、权限条件。
Lab 4 harness 的日期条件是 metadata 精确匹配，不是自然语言日期解析。
权限实验应另用真实 bearer 身份调用 API，不能只把 `metadata.team` 当权限测试。

```sh
python eval/run_eval.py --golden eval/golden_set.json \
  --modes bm25,vector,hybrid,hybrid+rerank,hybrid+rewrite \
  --k 5 --top-k 5 --candidate-k 30 --json eval/lab4-result.json
```

- Recall@K：应找到的文档有多少真的找到了？
- MRR：第一个正确结果是否足够靠前？
- NDCG@K：整个前 K 排名的质量如何？
- 延迟：质量提升是否值得增加的等待？

例：应该找到 A、B，实际前 3 是 C、A、D，则 Recall@3=1/2，MRR=1/2。
本项目按文档 ID 去重后评估，不是严格的 chunk-level relevance。
只看总均值会掩盖精确 ID 题退步；还要看 category breakdown。
生成质量使用 Lab 9 独立评估：检索正确但回答错误，是不同的问题。

## 12. 常见故障定位

| 现象 | 先检查 |
|---|---|
| 创建成功但 RAG 找不到 | 是否执行 `/rag/documents/{id}/index` |
| BM25 有结果、vector 没结果 | Ollama embedding、Qdrant、score_threshold、模型对应 collection |
| vector 有、BM25 没有 | knowledge-chunks 是否已写入；旧文档需重新 index |
| 返回 503 | `/rag/status`、Ollama、Qdrant/ES 是否运行 |
| hybrid 有 warning | 看哪个检索器失败；不要把降级结果误当完整 hybrid |
| rerank 很慢 | 本地模型加载、候选数量、CPU/GPU；先关闭确认基线 |
| 开治理后没有结果 | 文档必须走 draft→validate→approve→publish，且日期有效 |
| 修改 embedding 模型后没结果 | 新模型使用不同 collection，必须重新嵌入所有目标文档 |

双写 ES/Qdrant 没有跨库事务。索引过程中失败可能只写好一个库；重试同一 index 请求修复。
当前定位是本地可理解实现，不是已经具备生产级原子索引切换的产品。

## 13. 学习验收

不看代码，画出两条检索路径；手算三条文档的 RRF；解释 rewrite 与 rerank 的不同位置。
再用自己的 10 道题找一个 BM25 胜出、一个 vector 胜出、一个 hybrid 仍失败的例子。
如果能说清失败是 parsing/chunking、candidate recall、ranking、context 还是 generation 导致，Lab 4 就真正理解了。
