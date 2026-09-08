# Knowledge, RAG & Agent Platform Lead — 110 道面试题知识库

使用方法：先用 2–3 分钟回答“核心答案”，再准备 5–10 分钟架构展开。Lead 岗最重要的不是定义，而是 trade-off、failure mode、production constraints。

## A. Knowledge Platform Architecture（1–12）

### 1. 什么是 Enterprise Knowledge Platform？
核心答案：它不是文档搜索工具，而是一套把企业分散信息转化为可信、结构化、可治理、可复用知识资产的平台能力。通常覆盖 ingestion、processing/refinement、knowledge asset registry、search/retrieval、governance、provenance、access control、evaluation、observability 和 APIs/SDKs。
追问：为什么不能让每个业务团队自己做 RAG？
Lead 答法：重复建设会造成不同 chunking、embedding、ACL、citation 和质量标准，最终形成 knowledge silos；平台价值是统一基础能力，同时给 domain team 保留 schema、ranking 和 prompt 的可配置性。

### 2. 如何设计 enterprise-scale RAG Studio？
核心答案：分成 control plane 与 data plane。Control plane 管 connector、ontology、index config、evaluation、permissions、deployment/version；data plane 负责 ingestion、retrieval 和 serving。所有耗时 ingest/embedding 通过 queue + worker 异步化，serving stateless 横向扩展。
追问：如何多租户？
答：tenant isolation + namespace/index strategy + ACL metadata + per-tenant quotas + audit logs；高安全租户可物理隔离 index/cluster。

### 3. ingestion pipeline 如何保证可靠性？
答：idempotency key、document checksum、source version、retry with backoff、dead-letter queue、checkpoint、exactly-once illusion through idempotent writes。不要承诺真正端到端 exactly-once，通常通过 at-least-once + idempotency 达成业务效果。

### 4. 为什么需要 Raw Zone？
答：保留原始输入是 provenance、reprocessing、auditability 和 rollback 的基础。解析器、chunker、embedding model 升级时可以重跑，而无需重新从 source 拉取。

### 5. 如何做 incremental indexing？
答：source modified timestamp / CDC / webhook + checksum。只重处理发生变化的 document 或 affected chunks；保持 source_version→knowledge_version→index_version lineage。

### 6. 如何支持多个 downstream use cases？
答：platform 提供标准 ingestion/search/RAG API、SDK、retriever interface、policy hooks、evaluation framework；业务侧配置 domain ontology、filters、ranking policy、prompt，不复制平台底座。

### 7. central platform 与 domain ownership 如何平衡？
答：平台团队负责 reliability/security/common primitives；domain SME 对 taxonomy/ontology、knowledge ownership、golden dataset 和 business acceptance criteria 负责。

### 8. 什么时候拆微服务？
答：按独立扩缩容、失败域、数据 ownership 和发布节奏拆，例如 ingestion worker、retrieval service、evaluation service；不是按代码类拆。早期避免过度微服务。

### 9. 什么时候使用 event-driven architecture？
答：ingestion、embedding、reindex、freshness、evaluation 等异步且可重试任务。在线 query path 尽量减少 event hop，控制延迟。

### 10. 如何做 platform versioning？
答：版本化 schema、chunking policy、embedding model、index、prompt、retriever 和 API。通过 shadow index/canary + evaluation gate 切换，不直接覆盖生产 index。

### 11. 如何设计 rollback？
答：immutable artifact + version pointer。保留 previous index / embedding / schema / prompt version，切换 active alias，而不是现场恢复数据。

### 12. RAG 平台最大的风险是什么？
答：通常不是模型精度本身，而是错误知识进入索引、权限泄露、引用不可追溯、过期知识、silent retrieval regression 和缺乏可观察性。

## B. Search & Retrieval（13–28）

### 13. BM25 是什么？
答：基于 term frequency、inverse document frequency、document length normalization 的 lexical relevance 算法。优势是 exact keyword、identifier、术语场景稳定、可解释；缺点是语义改写召回弱。

### 14. Dense retrieval 是什么？
答：将 query/document 编码为向量，在 embedding space 做近邻搜索。优势是 semantic similarity；缺点包括 exact-match 弱、embedding drift、ANN approximation 和 domain terminology mismatch。

### 15. 为什么生产 RAG 常用 Hybrid Search？
答：lexical 与 semantic retrieval 的错误模式互补。BM25 捕获 exact term，dense 捕获语义。融合后通常对真实企业 query 更鲁棒。

### 16. RRF 是什么，为什么常用？
答：Reciprocal Rank Fusion 按各列表的 rank 融合，而不是直接比较不可比的 raw scores。形式常见为 sum(1/(k+rank))。优点是简单、稳健、无需 score calibration。

### 17. Weighted fusion vs RRF？
答：weighted fusion 可更细调，但需要 score normalization/calibration；RRF 对不同 retriever score 分布更稳健。上线初期优先 RRF，拥有充分 relevance dataset 后再考虑学习型融合。

### 18. 为什么需要 reranker？
答：第一阶段 retrieval 追求 recall，reranker 对小 candidate set 做更昂贵的 query-document 交互，提升 precision。trade-off 是 latency/cost，因此常 top 30–100 rerank 到 top 5–10。

### 19. Bi-encoder vs Cross-encoder？
答：bi-encoder 可预计算 document embeddings、快，适合 candidate retrieval；cross-encoder 联合编码 query-document，精度高但计算贵，适合 reranking。

### 20. query rewrite 有哪些方式？
答：normalization、spell correction、acronym expansion、entity extraction、multi-query expansion、HyDE、conversation-to-standalone query。每种都要评估是否引入 query drift。

### 21. metadata filter 在什么时候执行？
答：安全 ACL filter 必须在 retrieval 时强制；普通业务 filter 尽量 pre-filter，提高 precision 和效率。若 vector engine pre-filter 性能差，需要评估 filter-aware ANN 或分区策略。

### 22. chunk size 如何选？
答：没有固定最佳值。要在 semantic coherence、retrieval granularity、context completeness、token cost 间权衡，通过真实 query set 实验。结构化文档优先 section-aware chunking，而不是固定字符数。

### 23. overlap 越大越好吗？
答：不是。overlap 可降低边界信息丢失，但会增加 duplicate retrieval、index size 和 token cost。应基于文档结构和 evaluation 调整。

### 24. Parent-child retrieval 是什么？
答：索引较小 child chunks 以提高召回精度，但返回较大的 parent section 给 LLM 以提供上下文完整性。

### 25. 什么是 retrieval failure taxonomy？
答：parse failure、chunk failure、index failure、query understanding failure、candidate recall failure、ranking failure、filter failure、context assembly failure。必须拆层定位，不把所有问题归为 hallucination。

### 26. ANN 为什么不是精确搜索？
答：HNSW/IVF 等用近似算法减少计算，牺牲少量 recall 换低延迟和高吞吐。关键参数如 efSearch / nprobe 决定 recall-latency trade-off。

### 27. 如何测试 retrieval quality？
答：golden queries + relevance judgments，关注 Recall@K、Precision@K、MRR、NDCG、HitRate，并按 query segment 分层分析，不能只看总体平均。

### 28. 如何 debug 搜索结果突然变差？
答：先对比最近变更：source/index freshness、mapping/analyzer、embedding model、chunking、retriever weights、reranker、ACL filter；用固定 golden set 重放，定位在哪一 stage regression。

## C. Knowledge Engineering（29–40）

### 29. Taxonomy vs Ontology？
答：taxonomy 主要是层级分类；ontology 定义实体类型、属性、关系、约束和语义规则，是更完整的 domain model。

### 30. Knowledge Graph vs Ontology？
答：ontology 是 schema/语义约束，knowledge graph 是按照 schema 实例化的实体与关系数据。可以有 graph 没有严格 ontology，也可以先有 ontology 再建 graph。

### 31. Semantic Layer 是什么？
答：为不同系统提供统一业务概念和指标语义，例如 Revenue、Customer、Region，屏蔽底层字段和系统差异，使 AI/search 使用一致业务语言。

### 32. 如何设计 ontology？
答：从 competency questions 开始，即系统必须回答哪些业务问题；再确定核心 entities/relations/properties、identifier、cardinality、constraints、ownership 和 versioning。避免从“把所有字段建模”开始。

### 33. ontology 太复杂有什么风险？
答：维护成本、低 adoption、抽取困难、schema evolution 复杂。原则是最小可用 ontology，围绕 high-value queries 增量演进。

### 34. Entity extraction 怎么做？
答：rule/NER model/LLM structured extraction 混合。高价值、强约束实体优先 schema-constrained extraction + validation；LLM 输出必须经过 type/identifier validation。

### 35. Relation extraction 怎么做？
答：基于 ontology 限制允许 relation types，LLM/模型抽取 candidate relation，再做 schema validation、confidence scoring、dedup 和 provenance link。

### 36. 什么是 canonical entity？
答：多个别名/来源记录归并到统一实体 ID 后的标准实体。例如多个公司名称映射到 COMPANY_123。

### 37. schema evolution 怎么做？
答：schema versioning、backward compatibility、migration jobs、dual-read/dual-write 或 graph transformation。重大变更需要 impact analysis 与 re-index plan。

### 38. 业务 SME 在 knowledge engineering 中的作用？
答：定义 authoritative concepts、ontology、validation rules、golden examples 和 contradiction resolution policy；工程团队不能单独决定业务语义。

### 39. 为什么 LLM 不能代替 ontology？
答：LLM 可帮助抽取/建议 schema，但缺少稳定的显式约束、版本控制、ownership 和可执行语义。企业平台需要 deterministic contract。

### 40. structured knowledge 和 unstructured knowledge 如何结合？
答：metadata/graph 提供结构和关系，document chunks 提供原始证据。检索时可先 graph/entity 定位，再回到 source chunks 生成有 citation 的答案。

## D. Knowledge Graph / GraphRAG（41–50）

### 41. 什么场景适合 Knowledge Graph？
答：多跳关系、entity-centric query、复杂 ownership/dependency、需要显式关系解释的场景。简单 FAQ/文档问答未必需要 graph。

### 42. GraphRAG vs Vector RAG？
答：Vector RAG 依赖文本语义相似；GraphRAG利用实体关系和 traversal。最常见不是二选一，而是 vector candidate + graph expansion 或 graph seed + source evidence retrieval。

### 43. 如何构建 KG？
答：parse → chunk → schema → entity/relation extraction → entity resolution → graph validation/pruning → provenance → store → evaluation。

### 44. graph traversal 风险？
答：无约束 traversal 容易爆炸。需要限定 relation types、hop count、time/ACL filters、degree cap 和 path scoring。

### 45. Multi-hop reasoning 如何保证可解释？
答：返回 reasoning evidence path，而不是模型自由生成“推理链”。例如 Company→Contract→Counterparty→Risk，每条 edge 带 source provenance。

### 46. Graph database 与 relational database 如何选择？
答：关系稳定、join 固定的事务场景 relational 更简单；关系类型丰富、动态 traversal 和多跳查询 graph 更自然。平台往往两者共存。

### 47. Cypher 查询性能怎么优化？
答：index/constraint、从高选择性节点开始、避免无界 variable-length path、PROFILE/EXPLAIN、限制返回字段和 traversal 深度。

### 48. 如何评估 GraphRAG？
答：除了 answer accuracy，还需测 entity extraction accuracy、relation precision/recall、entity resolution accuracy、path correctness、retrieval coverage。

### 49. Knowledge Graph 的 freshness 怎么处理？
答：节点/边必须和 source version 绑定。source update 触发 affected entities/relations recompute，而不是简单追加；支持 temporal validity/effective dates。

### 50. Graph hallucination 是什么？
答：LLM 抽取了不存在的 entity/relation。通过 schema grounding、source span provenance、confidence threshold、validation rules 和 human review 降低。

## E. Refinement / Entity Resolution / Quality（51–60）

### 51. Entity Resolution 的完整 pipeline？
答：normalize → exact ID → alias → fuzzy → candidate generation → semantic features → classifier/LLM → confidence → merge policy → human review → canonical ID。

### 52. 为什么不能只用 embedding 做 entity resolution？
答：embedding 是语义相似，不等于实体同一性。Apple 公司与 apple 水果可能语义相关；不同 legal entities 也可能高度相似。必须结合 identifier、context 和 business rule。

### 53. deduplication 怎么做？
答：document-level checksum、near-duplicate MinHash/SimHash、semantic similarity；knowledge-level 再结合 canonical entity、effective date、source authority。

### 54. contradiction detection 怎么做？
答：先识别同一 claim/entity/property 的候选冲突，再比较 effective time、source authority、version 和 confidence；无法自动决策则进入 review queue。

### 55. Knowledge quality score 怎么设计？
答：不要单一 magic score。至少分 accuracy、completeness、freshness、consistency、authority、traceability、uniqueness；可按业务风险设置权重。

### 56. LLM summarization 如何避免丢失关键事实？
答：structured extraction first、summary second；对高风险字段使用 deterministic validation，保留 source spans/citations，并做 completeness checks。

### 57. AI-assisted curation 是什么？
答：LLM 帮助分类、抽取、聚合、提出 merge 建议，但 final publishing policy 由规则/SME gate 控制。AI 是 curator assistant，不是无约束 source of truth。

### 58. 如何处理低置信度知识？
答：不直接发布到 trusted tier。标记 confidence、进入 quarantine/review，或者只允许低风险 exploratory search 消费。

### 59. Knowledge tiering 怎么做？
答：例如 raw / enriched / validated / authoritative。不同 tier 对应不同 consumer permissions 和 RAG ranking boost。

### 60. 如何避免 outdated knowledge 覆盖新知识？
答：effective date + source authority + version policy；retrieval 默认 filter current=true，并对 superseded version 降权/隐藏，但保留历史审计追踪。

## F. Governance / Provenance / Security（61–70）

### 61. Provenance 是什么？
答：知识或答案来自哪里。应可从 answer → chunk → document version → source system → owner 回溯。

### 62. Lineage vs Citation？
答：citation 是面向用户的证据引用；lineage 是完整数据处理链，包括 transformation、version 和 system hops。

### 63. 如何验证 citation correctness？
答：回答中的 claim 与 cited chunk 做 entailment/semantic validation，确保 cited chunk 实际支持 claim；同时验证 source version/permission。

### 64. freshness monitoring 怎么设计？
答：基于 source SLA、last_seen、effective/expiry date、connector health。输出 freshness lag、stale asset count，并触发 re-sync/re-index。

### 65. RBAC vs ABAC？
答：RBAC 基于角色；ABAC 基于用户、资源、环境属性，细粒度更强。复杂企业知识权限通常 RBAC+ABAC/ACL 混合。

### 66. 为什么权限必须在 retrieval layer 做？
答：LLM 一旦看到 unauthorized context 就已经发生数据泄露风险。不能依赖 prompt 让模型“不要说”。

### 67. 如何实现 ACL-aware vector search？
答：将 tenant/security attributes 写入 metadata，query 时强制 pre-filter；若 vector engine filter 性能不足，可使用 namespace/partition 或 dedicated index。

### 68. 如何做 audit log？
答：记录 who、when、query、resource/filter policy、retrieved document IDs、model/version、answer/citation、admin changes。敏感 query/answer 需脱敏和 retention policy。

### 69. retention/deletion 怎么处理？
答：源文档删除必须级联删除 raw object、chunks、vectors、graph nodes/edges 或使其不可检索；保留必要 tombstone/audit metadata 但遵循法规。

### 70. Prompt injection 对 RAG 有什么风险？
答：恶意文档可把指令注入 context。防护包括把 retrieved text 当 untrusted data、instruction hierarchy、content scanning、tool permission boundary、allowlisted actions、human confirmation。

## G. Evaluation / Observability / SLO（71–80）

### 71. RAG 如何评估？
答：拆 retrieval、context、generation、citation 四层。不能只看 final answer。

### 72. Recall@K vs MRR？
答：Recall@K 看相关证据是否进入 top K；MRR 强调第一个相关结果的位置。问答通常两者都重要。

### 73. NDCG 有什么用？
答：当 relevance 有多等级且关心整个排序质量时，NDCG 同时考虑 relevance grade 和 position。

### 74. Faithfulness 是什么？
答：答案是否被提供 context 支持。它不等于事实在现实世界正确，所以还需要 correctness/source authority。

### 75. Golden dataset 如何建设？
答：从真实 query logs + SME curated difficult cases 组成，覆盖 common、tail、identifier、temporal、permission、ambiguous、multi-hop query，并维护 expected sources。

### 76. LLM-as-a-judge 有什么风险？
答：judge bias、model correlation、prompt sensitivity、non-determinism。要通过 human calibration、pairwise tests、multiple metrics 和 fixed judge version 控制。

### 77. RAG 平台应监控哪些 metrics？
答：availability、P50/P95/P99 latency、retrieval latency、rerank latency、LLM latency、error rate、index lag、freshness lag、no-result rate、token/cost、citation coverage、quality regression。

### 78. SLI/SLO/SLA 区别？
答：SLI 是测量指标；SLO 是内部目标；SLA 是对客户的正式承诺与可能的责任条款。

### 79. 回答质量突然下降如何 incident response？
答：freeze recent rollout → compare golden baseline → inspect source/index freshness → segment by query type → trace retrieval/rerank/model versions → rollback alias/config → root cause → regression test。

### 80. 如何控制成本？
答：embedding batching、incremental index、cache、small model for routing/classification、limit rerank set、context compression、token budget、per-tenant quota、model tiering、cost observability。

## H. Backend / Distributed Systems / Leadership（81–90）

### 81. 为什么 RAG serving service 应尽量 stateless？
答：便于 horizontal scaling、failure recovery 和 load balancing；session/state 放 Redis/DB/checkpoint store。

### 82. Redis 在平台中用在哪里？
答：cache、rate limit、session/checkpoint、distributed lock、short-lived job state；不应把它当唯一 durable source of truth。

### 83. 消息队列为什么重要？
答：ingestion/embedding/reindex 属于长任务，queue 实现 decoupling、backpressure、retry、worker scaling、dead-letter handling。

### 84. 如何处理 backpressure？
答：queue depth/lag monitoring、producer rate limit、worker autoscaling、priority queue、batching、shed non-critical workload。

### 85. 如何做 capacity planning？
答：按 ingest documents/day、chunks/doc、embedding throughput、index size、queries/sec、rerank candidates、LLM tokens/query 做 workload model，再压测确定余量。

### 86. 如何做设计评审？
答：明确 problem/requirements/non-goals → options → trade-offs → failure modes → security/privacy → SLO/cost → migration/rollback → decision record。Lead 不是只挑代码问题。

### 87. 如何管理技术债？
答：把技术债量化为 reliability/velocity/cost risk，建立 debt register 和明确 owner；与 roadmap 同步，不做无限期“以后重构”。

### 88. 团队对架构有分歧怎么办？
答：先统一 decision criteria，用 prototype/benchmark/evaluation data 缩小争议；对 reversible decisions 快速试验，对 irreversible/high-cost decisions 做正式 ADR。

### 89. 如何推动业务团队采用平台？
答：不仅提供服务，还要提供 clear API/SDK、reference architecture、runbook、examples、SLO、migration support 和 office hours；平台 adoption 是产品问题，不只是技术问题。

### 90. Lead 岗最重要的能力是什么？
答：在业务目标、质量、速度、成本和工程复杂度之间做可解释取舍，并建立能让团队重复交付的 engineering standards，而不是亲自写最多代码。

## I. Agent Engineering / Orchestration（91–110）

### 91. AI Agent 的工程定义是什么？
答：Agent 是由模型参与决策的 execution loop。系统加载 goal、state 和 policy，模型选择 action，application 执行 tool 并返回 observation，随后更新 state，直到满足 stop condition。模型不是整个系统；工具执行、权限、持久化和验证都在 application/runtime layer。

### 92. Workflow 与 Agent 如何选择？
答：路径可预先定义、合规要求高或 side effect 明确的任务优先 deterministic workflow；只有下一步需要根据上下文动态选择时才使用 Agent。常见最优解是 workflow 外框加少数 agentic nodes。

### 93. Function Calling 的完整流程是什么？
答：应用向模型提供 tool name、description 和 schema；模型返回结构化调用；应用完成 authorization、参数校验和实际执行，再把结构化 result 送回模型。模型不会直接执行 Python function。

### 94. 如何设计高质量 Tool Contract？
答：工具职责单一，名称和描述明确；输入输出使用严格 schema；写清前置条件、side effect、错误类型、重试安全性、权限和幂等语义。不要把十种动作塞进一个万能工具。

### 95. Agent State、Memory、Conversation Context 有什么区别？
答：context 是本次模型调用可见内容；state 是 workflow 的权威中间状态；memory 是跨轮次或跨 run 的选择性持久信息。关键业务事实应写入结构化 state/database，不能只依赖聊天文本。

### 96. Checkpoint 为什么重要？
答：它让长任务可暂停、失败恢复和人工审批。恢复时必须同时知道已完成步骤、tool outcome、side-effect receipt 和下一节点，避免从头重跑导致重复写入。

### 97. 如何防止 Agent 无限循环？
答：设置 max steps、wall-clock timeout、token/cost budget、重复 action detection、progress invariant 和明确 termination condition；超限后返回结构化失败或升级人工，不让模型自行无限重试。

### 98. Tool retry 应该由谁决定？
答：runtime 按错误分类处理。网络超时等 transient error 可按 bounded exponential backoff 重试；validation/business error 不应盲重试；非幂等 side effect 只有在可确认前次未成功或使用 idempotency key 时才能重试。

### 99. Agent 如何避免重复执行 side effect？
答：为每个动作生成 idempotency key，执行前持久化 intent，执行后保存 receipt/result，并用 transactional outbox 或等价机制协调状态与消息。恢复时先查 execution ledger，而不是让模型重新猜测。

### 100. Human-in-the-loop 应放在哪里？
答：按风险而不是按模型置信度单独决定。外部发送、写数据库、付款、删除、权限变更等动作在执行前审批；审批界面展示 proposed action、arguments、evidence、impact 和 expiry，修改后重新校验。

### 101. Guardrail 与业务授权有什么区别？
答：guardrail 检查输入、输出或行为是否符合规则；authorization 判断当前 identity 是否有权执行资源/动作。两者都需要 server-side enforcement，不能只靠 prompt。

### 102. Handoff 与 Agent-as-Tool 如何选择？
答：handoff 把后续对话/控制权转给另一个 agent；agent-as-tool 由主 agent 保持控制并调用专家能力返回结果。需要统一用户体验和全局 policy 时通常优先 agent-as-tool；真正 ownership 转移时用 handoff。

### 103. 什么时候使用 Multi-Agent？
答：任务能按相对独立的专业边界拆分、可并行、上下文可隔离且有清晰合并标准时使用。不要把角色扮演当架构；先与 single agent + tools 基线比较质量、延迟、成本和可调试性。

### 104. Multi-Agent 常见失败模式是什么？
答：上下文丢失、职责重叠、循环委派、意见无法收敛、重复 tool call、成本放大、责任与 trace 不清。需要明确 topology、message contract、budget、termination、shared state ownership 和 final arbiter。

### 105. MCP 在 Agent 架构中的作用是什么？
答：MCP 标准化 host/client 与 server 暴露的 tools、resources、prompts 之间的连接。它解决互操作与发现，不自动解决工具可信度、用户授权、数据隔离、审批或业务幂等，这些仍由平台负责。

### 106. Agent 如何安全使用 Knowledge/RAG Platform？
答：Agent 通过受治理的 Search/RAG API 获取知识，调用时传递用户 identity、tenant 和 purpose；检索层执行 ACL filter，结果附 provenance/citation。不要给 Agent 绕过治理层直接扫底层 index 的权限。

### 107. 如何防御间接 Prompt Injection？
答：把网页、文档和 tool output 视为 untrusted data；隔离 instructions 与 evidence；限制可用 tools 和参数；高风险动作强制审批；验证目标与 action consistency；对敏感数据和外发内容做策略检查。

### 108. Agent Evaluation 应评什么？
答：至少包括 task success、tool selection、argument correctness、state transition、step efficiency、evidence completeness、side-effect safety、policy compliance、latency 和 cost。按完整 trajectory 评估，不能只看 final answer。

### 109. Agent Observability 需要记录什么？
答：run/trace ID、model/prompt/tool versions、state transitions、tool arguments 的安全摘要、result/error、retry、approval、latency、tokens、cost 和 final status。敏感数据需脱敏，trace retention 与访问权限单独治理。

### 110. Knowledge/RAG Platform 与 Agent Platform 的职责边界是什么？
答：Knowledge/RAG Platform 对 ingestion、retrieval、ACL、freshness、provenance 和 knowledge quality 负责；Agent Platform 对 run、state、orchestration、tools、approval、recovery、evaluation 和 trace 负责。两者通过稳定 API/SDK 集成，避免 Agent 绕过治理直接访问数据源。
