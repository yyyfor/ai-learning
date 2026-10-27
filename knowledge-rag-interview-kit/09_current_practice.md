# 当前实践与项目学习地图

资料复核日期：**2026-10-25**。这是基于官方资料和仓库实际代码的学习快照，
不是实时新闻源，也不意味着把所有依赖都升级到了最新版。先跑通、解释取舍，再决定升级。

## 1. 先理解这个项目的六条线

| 学习线 | 当前实现 | 在页面怎么练 | 下一步值得研究的内容 |
|---|---|---|---|
| 文档与检索 | PostgreSQL、ES BM25、Redis、Qdrant、本地 embedding、应用层 RRF/rerank | Documents → Search → RAG answers | 在固定 golden set 上比较候选召回量、重排与延迟 |
| 结构化知识 | Neo4j 图抽取/查询、实体消歧与重复/矛盾检测 API | GraphRAG；refinement 使用 `/docs` | 抽取质量、实体身份、关系证据、图更新 |
| 治理 | 文档版本、负责人、有效期、审批/发布/回滚、引用检查 | Governance | 分清文档存在、已索引、已审批、仍有效 |
| 评估与观测 | 检索/生成评估、baseline、轻量 trace、指标、可选 ACL | Evaluation、Observability | 用真实问题集定位检索失败还是回答失败 |
| Agent | 有界工具循环、审批、LangGraph checkpoint、写入账本、memory、可选 MCP | Agent playground、Durable agent | 恢复后的副作用、证据与权限边界 |
| 本地语音 | AudioWorklet → Whisper → Ollama 摘要 → 文档 → RAG | **Voice notes** | 名称/数字准确率、chunk 延迟、长摘要的信息损失 |

所有交互都经过 FastAPI；浏览器不持有数据库连接。API、DTO、服务、存储适配器按职责分开。

## 2. 当前资料带来的重点

- **Hybrid retrieval**：Elastic 官方推荐 `semantic_text` 路线；Qdrant 也提供组合查询。
  本项目保留 ES BM25 + Qdrant + 应用层 RRF，以便不用云 key 也能学习融合。
  `semantic_text` 仍是独立可选项，不能把“有 dense 检索”与“用了 semantic_text”混为一谈。
  [Elastic](https://www.elastic.co/docs/solutions/search/hybrid-search)、[Qdrant](https://qdrant.tech/documentation/search/hybrid-queries/)。
- **Context engineering**：模型看到的指令、工具、历史、证据应有明确边界。
  本项目用 step budget、证据引用与历史压缩练习这些取舍。
  [LangChain](https://docs.langchain.com/oss/python/langchain/context-engineering)。
- **持久化**：checkpointer 保存 thread 执行状态，store 保存跨 thread 信息。
  本项目另外用业务账本处理重复写入；checkpoint 不等于外部副作用 exactly-once。
  [LangGraph](https://docs.langchain.com/oss/python/langgraph/persistence)。
- **MCP**：协议连接能力，授权仍由应用负责。规范版本和 Python SDK 版本分开记录。
  [2026-07-28 架构说明](https://modelcontextprotocol.io/docs/2026-07-28/learn/architecture)。
- **评估**：faithfulness 关注回答是否有上下文支撑；它不保证来源正确、完整或及时。
  项目用自己的 Lab 9 实现，不把自写指标包装成 Ragas。
  [Ragas](https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/faithfulness/)。
- **观测规范会演进**：OpenTelemetry 的 GenAI 文档入口已经迁移；采用规范前检查当前维护位置。
  本项目仍是轻量 trace，尚未提供 exporter。
  [官方迁移说明](https://opentelemetry.io/docs/specs/semconv/gen-ai/)。
- **本地语音**：CPU int8 Whisper 负责转写；Ollama JSON schema 输出负责结构化摘要。
  页面采集使用 AudioWorklet。模型结构化输出仍需核对事实。
  [faster-whisper](https://github.com/SYSTRAN/faster-whisper)、[Ollama](https://docs.ollama.com/capabilities/structured-outputs)、[MDN](https://developer.mozilla.org/en-US/docs/Web/API/AudioWorklet)。

## 3. 把参考资料变成可查询知识

`starter_repo/knowledge/reference_notes.json` 包含 9 篇原创精读笔记，
覆盖上述主题及 GraphRAG。每篇保存官方来源、reviewed_on、稳定 reference_key 和内容 hash。
它们是学习材料，不是官方原文，也没有自动审批为权威知识。

在 `starter_repo` 执行：

```sh
.venv/bin/python scripts/import_reference_notes.py
```

脚本只调用后端 API。它先分页查询已有文档，按 key/hash 复用相同快照，
再调用 RAG 索引接口。内容变化时创建新快照；不覆盖或删除旧文档。
索引失败后可重跑。`--no-index` 只导入文档；开启认证时通过环境变量 `API_TOKEN` 传 token。

页面练习：

1. 在 **Documents** 找到 source 为 `reference-notes` 的文档，查看 metadata 来源。
2. 在 **Search & query** 搜索 `checkpoint`，source 填 `reference-notes`。
3. 在 **RAG answers** 的 Retrieval options 填同一 source，问
   `How is a checkpoint different from long-term memory?`，核对引用。
4. 到 **Evaluation** 创建问题和 expected source；脚本也生成
   `var/reference-evaluation.json`，可以作为 `/evaluation/run` 的请求体。
5. 在 **Governance** 为需要正式使用的笔记补负责人/有效期并走审核流程。
   严格治理开启时，未发布的笔记可能不能进入回答，这是预期行为。

这份数据不会自动跟随网站更新。更新时重新读来源、修改正文与 review 日期，
重跑导入，再用相同问题比较结果。新版本与旧版本并存时，应明确弃用旧来源的流程。

本次本机运行记录：9 篇已导入并建立 RAG 索引，重复导入复用相同 9 个 ID。
9 道自拟问题的初次 hybrid 检索检查，Recall@5 为 8/9；
`What should a local RAG and voice application observe?` 没有命中预期 observability 来源。
这暴露了宽泛问题与中英混合笔记的检索难点，保留作为后续分析案例。
这是小样本演示数据，不能用来推断通用检索质量。结果在 `var/reference-evaluation-result.json`。

## 4. 一条完整演示路径

读一篇参考笔记 → 用自己的话录制一分钟解释 → 查看转写错误 → 编辑摘要
→ Save to document library → Index for RAG → 用问题检索自己的录音笔记
→ 检查来源和版本 → 比较检索质量 → 让 Agent 提议一个需要确认的 follow-up。

语音指南：[Lab 13](starter_repo/labs/lab13_local_voice.md)。

每一步都回答三个问题：输入是什么，证据在哪里，失败后如何继续。
暂未实现的扩展包括说话人分离、原生逐词流式 ASR、后台长会议作业、完整 OTel exporter、
自动 web crawler 和托管多租户部署。先把当前流程学明白，再逐项扩展。
