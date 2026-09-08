# Knowledge, RAG & Agent Platform Lead 面试知识库 + Hands-on Lab

适用岗位：Knowledge & RAG Platform Engineering Lead / Senior Staff AI Engineer / AI Platform Lead / Knowledge Intelligence Lead / Agent Platform Engineer。

这套资料按岗位真实能力模型组织，不按“框架 API”组织。核心主线：

1. Enterprise Knowledge Platform Architecture
2. Search & Advanced RAG
3. Knowledge Engineering / Taxonomy / Ontology
4. Knowledge Graph / GraphRAG
5. Knowledge Refinement & Entity Resolution
6. Knowledge Governance / Provenance / Lifecycle
7. Evaluation / Observability / SLO / Cost
8. Backend / Distributed Systems / Security
9. Agent Runtime / Tools / State / Orchestration
10. Technical Leadership / Design Review / Delivery

## 建议使用方式

- 新加入项目：先读 [New Joiner Guide](starter_repo/NEW_JOINER_GUIDE.md)，跑通当前实现，再按路线扩展。
- 第一轮：按 `01_roadmap.md` 学习 12 周。
- 第二轮：每周完成 `03_hands_on_labs.md` 对应实验。
- 第三轮：使用 `02_interview_bank.md` 进行自测和 mock interview。
- Agent 零基础先读 `06_agent_learning_guide.md`，再完成 Lab 11–12。
- 最后：用 `05_architecture_cheatsheet.md` 练习白板系统设计。

## 最终目标

能够独立回答并设计：

> Design an enterprise-scale Knowledge, RAG & Agent Platform that supports ingestion, knowledge refinement, hybrid retrieval, GraphRAG, governance, ACL-aware retrieval, reliable tool execution, stateful orchestration, human approval, evaluation, observability, cost controls and reusable APIs/SDKs for multiple downstream teams.

## 核心边界

Knowledge/RAG Platform 负责提供可信、可追溯、有权限控制的知识能力；Agent Runtime 负责基于目标和当前状态选择下一步动作、调用受控工具并完成任务。优先从 deterministic workflow 与 single agent + tools 开始，只有在任务确实能按专业能力拆分时才引入 multi-agent。
