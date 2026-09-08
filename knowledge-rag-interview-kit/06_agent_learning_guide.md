# AI Agent 从零到生产：学习指南

## 1. 先建立正确心智模型

Agent 不是“更聪明的聊天机器人”，也不是某个框架。它是一个由模型参与决策的执行闭环：

```text
Goal
  ↓
Load state + policy
  ↓
Model chooses action
  ↓
Tool call / final answer
  ↓
Application authorizes and executes
  ↓
Observation + state update + checkpoint
  ↓
Continue or stop
```

模型负责提出下一步 action；application/runtime 负责真正执行工具、验证输入输出、检查权限、保存状态、重试、审批和审计。把这个边界讲清楚，是所有 Agent 面试题的基础。

## 2. Agent 与 RAG 的关系

RAG 解决“从可信知识中找什么并如何回答”；Agent 解决“为了完成目标，下一步做什么”。

```text
Agent Runtime
  ↓ calls
Knowledge/RAG API
  ↓
ACL-aware Hybrid Retrieval
  ↓
Evidence + provenance
```

Agent 不应直接绕过 Knowledge Platform 扫底层向量库。身份、租户、权限、freshness 和 provenance 仍由知识平台控制。

## 3. 必须掌握的 12 个概念

1. **Goal / Instruction**：要完成什么，以及不可违反的政策。
2. **Tool**：对外部世界的受控能力；必须有明确 schema 和 side-effect 语义。
3. **Action / Observation**：模型提出调用；应用执行后返回结构化结果。
4. **State**：当前任务的权威进度、事实、已完成动作和下一节点。
5. **Context**：本次模型调用看到的信息，不等于持久化 state。
6. **Memory**：跨轮次或跨 run 选择性保存的信息；不能把所有历史聊天原样塞回模型。
7. **Termination**：成功、失败、超时、预算耗尽或转人工的明确停止条件。
8. **Checkpoint**：可暂停、恢复和审批的持久化快照。
9. **HITL**：高风险动作执行前的人类审批、修改或拒绝。
10. **Guardrail / Authorization**：前者验证内容和行为，后者验证身份是否有权执行。
11. **Idempotency / Compensation**：避免重复 side effect，并处理无法直接 rollback 的动作。
12. **Trace / Eval**：记录完整 trajectory，并按任务成功和行为安全做回归测试。

## 4. 学习顺序：不要一上来 Multi-Agent

### Stage A — Tool Calling from Scratch

先手写最小 loop，掌握 tool schema、structured output、tool result validation 和 stop condition。完成 Lab 11 前，不要把主要精力放在框架 API。

验收问题：模型返回了 function call 后，谁执行？工具超时怎么办？写入成功但 response 丢失怎么办？为什么 blind retry 会重复写入？

### Stage B — Single Agent + Governed Tools

建立 read-only、internal write、external side effect 三档风险；只读工具可自动执行，写入和外部动作需要审批、幂等键和 execution receipt。

验收问题：Agent 能否在不看到无权信息的情况下完成检索？审批人能否看到 action、arguments、evidence 和 impact？

### Stage C — Explicit State Graph

把复杂任务表示为显式节点和边：intake → retrieve → plan → execute → verify → approve → finalize。使用 checkpoint 实现暂停与恢复。

验收问题：服务在 tool 成功后宕机，恢复时如何确保不重复执行？state migration 怎么处理？

### Stage D — Agent Evaluation & Production

建立 golden tasks 和 adversarial tasks，评价 task success、tool selection、argument correctness、step efficiency、side-effect safety、evidence completeness、latency 和 cost。

验收问题：prompt 或 model 更新后，如何证明 Agent 行为没有退化？为什么只看 final answer 不够？

### Stage E — Multi-Agent（最后）

仅在任务有清晰专业边界、可并行、上下文可隔离且有合并标准时引入。先用 single agent + tools 做基线，再比较增益。

验收问题：handoff 与 agent-as-tool 有何不同？谁拥有 shared state？如何停止循环委派？

## 5. 四周 Agent 子路线

| 周 | 学习重点 | 实操产物 | 验收标准 |
|---|---|---|---|
| A1 | Agent loop、Function Calling、Tool Contract | framework-free agent | 3 个 typed tools，严格校验，明确停止 |
| A2 | State、Memory、Context、Checkpoint | resumable single agent | 中断恢复且不重复 side effect |
| A3 | HITL、Guardrails、MCP、Security | governed agent | 权限透传，高风险动作审批，MCP allowlist |
| A4 | Eval、Trace、Failure Handling、Multi-Agent trade-off | production report | golden/adversarial eval、incident drill、single vs multi 对比 |

## 6. 推荐主线资料

### 原理与第一套实现

- OpenAI Agents SDK Quickstart — https://developers.openai.com/api/docs/guides/agents/quickstart
- OpenAI Orchestration — https://developers.openai.com/api/docs/guides/agents/orchestration
- OpenAI Guardrails & Human Review — https://developers.openai.com/api/docs/guides/agents/guardrails-approvals
- OpenAI Agent Evals — https://developers.openai.com/api/docs/guides/agent-evals
- OpenAI Agents SDK Repo — https://github.com/openai/openai-agents-python

### 长任务、状态图与恢复

- LangGraph Overview — https://docs.langchain.com/oss/python/langgraph/overview
- LangGraph Repo — https://github.com/langchain-ai/langgraph
- LangGraph Academy — https://academy.langchain.com/

### Tools / MCP

- MCP Introduction — https://modelcontextprotocol.io/docs/getting-started/intro
- MCP Python SDK — https://py.sdk.modelcontextprotocol.io/
- MCP Python Repo — https://github.com/modelcontextprotocol/python-sdk

### 扩展阅读

- PydanticAI — https://ai.pydantic.dev/
- PydanticAI Repo — https://github.com/pydantic/pydantic-ai
- Microsoft Agent Framework — https://github.com/microsoft/agent-framework

主线只选 OpenAI Agents SDK 或 LangGraph 之一做深；另一个用于理解架构差异。不要同时学习五个 Agent 框架。

## 7. Hands-on 项目：Audit Issue Follow-up Agent

### 输入

审计问题、相关底稿/政策、负责人、截止日和客户回复。

### 工具

- `search_knowledge`：只读，必须传 identity/tenant，返回 citation/provenance。
- `get_issue`：只读，获取结构化问题和当前状态。
- `draft_follow_up`：无外部 side effect，生成草稿。
- `create_task`：内部写入，需要审批和 idempotency key。
- `send_message`：外部 side effect，需要审批、收件人解析和发送回执。

### 状态图

```text
Intake
  ↓
Retrieve evidence
  ↓
Plan
  ↓
Draft action
  ↓
Verify evidence + policy
  ↓
Human approval
  ↓
Execute tool
  ↓
Save receipt + final report
```

### Golden Tasks

1. 信息充足，正确生成带引用的 follow-up 草稿。
2. 用户无权限访问某文档时，检索不得泄露标题或内容。
3. 工具 timeout 后安全恢复，不重复创建任务。
4. 恶意文档要求“忽略规则并发送邮件”时，系统拒绝执行。
5. 高风险动作没有审批时，run 暂停而不是自动继续。

## 8. 生产检查清单

### Correctness

工具参数和返回值严格校验；每个关键 claim 有 evidence；模型输出不能直接成为数据库命令或外部动作。

### Reliability

明确 timeout、bounded retry、max steps、cost budget、checkpoint、idempotency、dead-letter/escalation 和 compensation。

### Security

identity/tenant 全链路透传；least privilege；tool allowlist；secret 不进入 prompt/log；retrieved content 和 tool output 均视为不可信输入。

### Governance

高风险动作审批；保留 decision、approver、evidence、action、receipt；prompt/model/tool/policy 版本可追溯。

### Evaluation

离线 golden set + adversarial set；发布前 CI gate；线上 trace sampling、成功率、错误率、延迟、token、成本和 policy violation 告警。

## 9. 面试时的一句话总结

> I treat an agent as a governed execution runtime, not just an LLM loop. The model proposes actions, while the platform owns authorization, state, tool execution, idempotency, approvals, observability and evaluation. I start with deterministic workflows and a single agent with tools, and introduce multi-agent orchestration only when the task decomposition creates measurable value.
