# Knowledge, RAG & Agent Platform — 电脑端学习中心

电脑端版本保留完整深度，适合系统学习、写代码、做白板设计和模拟面试。建议使用支持 Markdown 目录与多窗口的编辑器打开本目录，并同时打开 `starter_repo`。

## 推荐打开顺序

1. `knowledge-rag-interview-kit/README.md`：理解整体能力地图。
2. `knowledge-rag-interview-kit/01_roadmap.md`：按 12 周安排学习。
3. `knowledge-rag-interview-kit/06_agent_learning_guide.md`：Agent 零基础先读。
4. `knowledge-rag-interview-kit/03_hands_on_labs.md`：边学边完成 12 个实验。
5. `knowledge-rag-interview-kit/02_interview_bank.md`：使用 110 道题自测。
6. `knowledge-rag-interview-kit/05_architecture_cheatsheet.md`：练习白板系统设计。
7. `knowledge-rag-interview-kit/04_resource_index.md`：只在需要时打开外部资料。

## 电脑端工作区建议

左侧打开 Roadmap 或 Hands-on Lab；中间打开代码和终端；右侧打开 Interview Bank 或 Architecture Cheat Sheet。每完成一个 Lab，就写一页 ADR，说明问题、方案、替代方案、trade-offs、failure modes、security、SLO、cost 和 rollback。

## 每周标准节奏

周一到周三学习概念并做最小实验；周四完成可运行版本；周五补测试、trace 和文档；周末用 Interview Bank 做 30–40 分钟白板回答，并把不会的问题加入下周计划。

## 三个强制输出

每周至少形成：一个可运行的 commit、一个可展示的 architecture decision、一次带计时的口头回答。只收藏资料但没有工程输出，不算完成。

## 最终演示路径

```text
Document ingestion
→ Hybrid RAG
→ Knowledge graph
→ Governance + ACL
→ Agent with tools
→ Approval + checkpoint
→ Evaluation + trace
```

最终要能展示：为什么不是 vector-only；Agent 为什么不能绕过 Knowledge API；高风险工具如何审批；服务中断后如何恢复且不重复 side effect；模型或 prompt 更新后如何做 regression test。
