# Lab 12 — Agent Reliability

Build the same use case with OpenAI Agents SDK or LangGraph.

Required nodes: intake → retrieve → plan → execute → verify → approve → finalize.

Add checkpoint/resume, tool allowlist, identity propagation, MCP read-only tool, approval expiry, bounded retry, full trace and golden-trajectory evaluation. Compare single-agent and multi-agent variants on success rate, steps, latency, cost and failure diagnosis.

Definition of done: kill the process after a side effect, resume it, and prove from the execution ledger that the action is not duplicated.
