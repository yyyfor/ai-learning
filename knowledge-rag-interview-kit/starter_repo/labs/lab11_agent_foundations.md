# Lab 11 — Agent Foundations

Implemented API and walkthrough: [Labs 6/8/9/10/11 guide](labs06_08_09_10_11.md#5-lab-11不靠框架的-agent).
The framework-free runtime is in `app/agent/runtime.py`; use `/agent/runs` in Swagger.

1. Implement a framework-free agent loop with explicit state and stop conditions.
2. Register three typed tools: `search_knowledge`, `calculate`, `create_follow_up`.
3. Validate arguments and results server-side.
4. Enforce `max_steps`, timeout and cost budget.
5. Require approval and an idempotency key for `create_follow_up`.
6. Add trajectory tests for tool choice, arguments and termination.

Definition of done: the agent completes five golden tasks, never writes without approval, and cannot repeat a successful write after resume.
