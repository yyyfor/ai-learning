# Lab 11: Agent Foundations (framework-free)

The first walkthrough (Chinese) is in [labs06_08_09_10_11.md §5](labs06_08_09_10_11.md#5-lab-11不靠框架的-agent). This page covers the whole lab, including the **upgrades** added for agent-engineer interviews: native tool calling, context compaction, approval expiry, crash recovery and the evaluation suite.

Code reading order: [dto/agent_lab.py](../app/dto/agent_lab.py) → [agent/runtime.py](../app/agent/runtime.py) → [agent/memory.py](../app/agent/memory.py) → [repositories/platform.py](../app/repositories/platform.py) → [api/agent.py](../app/api/agent.py) → [tests/test_agent_runtime.py](../tests/test_agent_runtime.py).

## 1. The loop in one picture

```text
goal + (compacted) observations
  -> model proposes action(s)          structured: one JSON action | native_tools: 0..n tool calls
  -> Pydantic validates tool + args    unknown tool / bad args -> invalid_action (still counts as a turn)
  -> read-only? execute -> observation -> next turn
  -> write?     pause: awaiting_approval (idempotency key + expires_at)
                  approve -> ledger check -> create_once -> continue
                  reject  -> rejected, nothing written
stop: finish | max_steps | timeout | budget_exceeded | failed | approval_expired
```

## 2. Step by step

Start the stack (see [New Joiner Guide](../NEW_JOINER_GUIDE.md)), seed data once with `python scripts/seed_lab_examples.py`, then use Swagger at `http://127.0.0.1:8000/docs`.

| # | Do this | Observe | Learn |
|---|---|---|---|
| 1 | `POST /agent/runs` `{"goal":"Calculate (1200 * 0.15) and finish with the result."}` | `steps`: calculate → finish, `answer` 180 | The model proposes; the app executes `calculate` |
| 2 | `GET /agent/tools` | 3 tools with risk levels and schemas | A tool contract = name + description + schema + risk |
| 3 | Goal "Find the dollar value of Contract C-101 and calculate 15 percent of it." **without** `required_tools`, 3 times | Sometimes it skips calculate and guesses | Prompts don't enforce critical steps |
| 4 | Same with `"required_tools":["search_knowledge","calculate"]` | Always search → calculate → finish | Enforce in code: the schema `enum` only allows the next required tool |
| 5 | `{"goal":"...", "max_steps":1}` and `{"token_budget":1000}` | `max_steps`, `budget_exceeded` | Stop conditions are code, not hope |
| 6 | Goal "Create a follow-up titled X with description Y" | `awaiting_approval`, `pending.idempotency_key`, `pending.expires_at`; `GET /agent/followups` unchanged | Writes wait for a human |
| 7 | `POST /agent/runs/{id}/approval {"approved":true}` twice | One follow-up only | Idempotency = hash(run, args) + `ON CONFLICT DO NOTHING` |
| 8 | Repeat 6, then `{"approved":false}` | `rejected`, no write | Rejection is a safe terminal state |
| 9 | `GET /agent/memories` after a Lab 12 run | Episodic memories you own | Memory is per user, with source + expiry |

## 3. The upgrades (what each one teaches)

### 3.1 Native tool calling (`"mode": "native_tools"`)

- **Structured mode** (default) asks for one JSON action and constrains decoding with a JSON Schema. It works with any model, including the local `llama3`.
- **Native mode** sends the tools in the model API's `tools` field ([`tool_definitions()`](../app/agent/runtime.py)). The model returns **zero or more** `tool_calls`, or plain text meaning "done".
- Several calls in one turn each get their own step record with the same `turn`. `max_steps` counts **turns** (model calls), not tool calls.
- If a write appears among parallel calls, the calls after it are dropped (`dropped_calls`), because the plan can't continue until a human approves.
- `required_tools` in native mode **offers only that tool**. The model can't call what it isn't offered.
- Tool definitions count toward the token reservation, because they're sent on every call.

Local `llama3` does **not** support native tools. To try it:

```sh
ollama pull qwen2.5:7b          # or llama3.1:8b; any model whose capabilities include "tools"
OLLAMA_TOOL_MODEL=qwen2.5:7b RAG_ENABLED=true sh scripts/start_local.sh
```

Without a tool-capable model the run ends `failed` with `error: ToolCallingUnsupported`, which is a clear, typed failure.

### 3.2 Context compaction

Each turn used to re-send **all** observations, so cost grew every step. Now [`compact_observations`](../app/agent/memory.py) keeps the newest 4 verbatim and shortens older ones to a one-line summary. The full list stays in durable state; only the prompt sees the compact view. It's deterministic, so it can't invent facts. *Trade-off:* a fact in an old, truncated observation may be lost. That's why the goal and recent evidence stay verbatim.

### 3.3 Approval expiry, with the ledger checked first

`pending.expires_at` defaults to 1 hour (`approval_ttl_seconds`). A late approval returns `approval_expired`, and nothing is written.

The subtle part is the **order of checks** in `approve()`:

1. Look up the idempotency key in the ledger (the `followups` table).
2. If a record exists, an earlier approval already wrote it (and maybe crashed before saving the run). The truth is **done**, not expired.
3. Only if there's no record, check expiry and then write.

Test: `test_ledger_beats_expiry_after_a_crash`.

### 3.4 Crash recovery: `POST /agent/runs/{id}/resume`

If the process dies mid-run, the row stays `running` forever. `resume()` takes the runtime lock, sees `running`, and knows no live loop owns it, since every loop in this process holds that lock. It marks the half-finished step `interrupted` and continues.

| Crash point | What resume does | Why it's safe |
|---|---|---|
| During a model call | Asks the model again | Nothing external happened |
| After a read tool, before saving | Re-runs the read | Reads have no side effects |
| After `create_once`, before saving the run | Run is still `awaiting_approval`; approving again finds the ledger record | Idempotency key |
| Run finished | Returns it unchanged | Finished runs are never re-executed |

## 4. Evaluation

- `python eval/run_agent.py`: the original 5 golden tasks, one run each.
- `python eval/run_agent_suite.py --seed-injection --trials 1` (once), then `python eval/run_agent_suite.py --trials 3 --k 3`: 21 tasks in [eval/agent_tasks.json](../eval/agent_tasks.json), covering tool use, knowledge, workflow, autonomy, approval, stop conditions and **safety** (code injection, indirect prompt injection). It reports pass@1, pass^k per task and category, and `unapproved_writes`, which must always be 0. See [Lab 12 §6](lab12_agent_reliability.md#6-evaluate-it-properly) for how to read it.

## 5. Definition of done

- [ ] All five golden tasks pass, and you can explain every step in the `steps` array.
- [ ] You can show that nothing is written before approval, and a double approval writes once.
- [ ] You can explain why `required_tools` exists, using a run where the model guessed.
- [ ] `pytest -q tests/test_agent_runtime.py` passes, and you can explain each test's name.
- [ ] You can draw the loop above from memory and name every stop condition.
