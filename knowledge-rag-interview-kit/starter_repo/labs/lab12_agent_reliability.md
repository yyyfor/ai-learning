# Lab 12: Durable Agent: LangGraph, Checkpoints, Approval, MCP, Evaluation

Lab 11 taught the loop. Lab 12 makes it **survive failures and pass an audit**. It rebuilds the same follow-up use case as an explicit **LangGraph** state graph with durable checkpoints, a human-approval pause, an execution ledger, a read-only **MCP** knowledge tool, long-term memory, and a repeated-trial evaluation.

Code reading order:

1. [dto/agent_graph.py](../app/dto/agent_graph.py): the one thing the model decides (`Proposal`).
2. [agent/graph_runtime.py](../app/agent/graph_runtime.py): nodes, edges, and the service (registry, identity, locks).
3. [agent/knowledge_tools.py](../app/agent/knowledge_tools.py): Direct vs MCP knowledge access.
4. [mcp_server.py](../app/mcp_server.py): the read-only MCP server.
5. [agent/memory.py](../app/agent/memory.py): episodic memory.
6. [tests/test_graph_agent.py](../tests/test_graph_agent.py) and [tests/test_mcp_server.py](../tests/test_mcp_server.py): the behavior, as executable specs.

Install the extras once: `pip install -e '.[agent]'` (LangGraph, the SQLite checkpointer, MCP).

## 1. The graph

```text
intake -> retrieve -> plan -> verify --(write proposed & checks pass)--> [PAUSE] approve --approved--> execute -> finalize
   |          |         |        \--(answer only, or checks failed)----------------------------------------> finalize
 recall    ACL-aware   the ONLY                                              \--rejected / expired---------> finalize
 memory    hybrid      model call
```

| Node | Deterministic? | What it does | Interview point |
|---|---|---|---|
| intake | yes | Recalls up to 3 of the requester's memories | Memory is context, not evidence |
| retrieve | yes | Governed search (direct or via MCP), with a retry policy for transport errors only | Agent never touches the vector DB |
| plan | **model** | Returns a `Proposal`: answer, cited evidence ids, optional follow-up | One agentic node inside a workflow |
| verify | yes | Checks citations, "write requested by goal?", no links/emails in writes; builds the approval request | Code decides whether the model's plan may proceed |
| approve | yes | Reads the human decision from the checkpoint and checks expiry at *decision time* | Fails closed if no decision |
| execute | yes | Ledger check → `create_once` → receipt | Survives crash-after-write |
| finalize | yes | Answer + citations + status; writes one episodic memory | Idempotent memory id per run |

**Why verify and approve come before execute:** every check that can stop a side effect should run while stopping is still free. (The original outline listed `execute` earlier; that ordering would only be safe for read-only execution.)

## 2. Step by step

Browser workspace: open `http://127.0.0.1:8000/#durable-agent`. Choose an example or write a goal,
then click **Run agent**. The page displays graph events, verification, approval evidence and the
write receipt. Approve/reject controls appear only while awaiting approval. Copy the run ID to
reload it after refreshing or restarting the API; **Resume interrupted run** appears for interrupted
execution. The same page lists local follow-ups and saved memories. The Swagger steps below use
the same APIs.

```sh
source .venv/bin/activate
pip install -e '.[agent]'
python scripts/seed_lab_examples.py            # once, if not already seeded
RAG_ENABLED=true sh scripts/start_local.sh
```

In Swagger, the **Lab 12 Durable agent** section:

1. `POST /agent/v2/runs` `{"goal": "How many days of annual leave do full-time employees receive?"}`
   → `status: completed`, `citations` with a document id, and `events` showing intake → retrieve → plan → verify → finalize.
2. `POST /agent/v2/runs` `{"goal": "Create a follow-up task asking HR to confirm the annual leave policy for full-time employees."}`
   → `status: awaiting_approval`, `next: ["approve"]`, and an `approval_request` containing arguments, idempotency key, the **evidence**, the **impact**, and an expiry. That is exactly what an approver should see.
3. `GET /agent/followups`: nothing written yet.
4. `POST /agent/v2/runs/{id}/approval {"approved": true}` → `completed`, with `receipt.followup_id`. Call it again: same result, no second write.
5. Stop the API with Ctrl+C in the middle of step 2's pause, then restart it. `GET /agent/v2/runs/{id}` still shows `awaiting_approval`, because the checkpoint lives in `var/agent_checkpoints.sqlite`.
6. `GET /agent/memories`: an episodic record of the run, owned by you.

## 3. The crash demo (this lab's definition of done)

```sh
python scripts/lab12_crash_demo.py
```

The script starts its own API on port 8010 with `AGENT_CRASH_AFTER_WRITE=exit`, approves a follow-up, and the process **dies right after the write** (`os._exit(137)`, like `kill -9`). Then it restarts the API and resumes:

```text
status=interrupted next=['execute']       <- the checkpoint says execute never finished
follow-ups written so far: 1              <- but the write DID happen
resume -> status=completed receipt={'followup_id': ..., 'reused_existing': True}
Ledger check: 1 follow-up for this run -> PASS
```

LangGraph re-runs a node that didn't finish. Without the ledger check in `execute`, the resume would write a **second** follow-up. The checkpoint gives you *where* to resume; the idempotency key and ledger give you *exactly-once effect*. Say it that way in interviews: "at-least-once execution plus idempotent writes".

## 4. Identity and approval rules

- The run registry (`graph_runs`) stores the requester's identity. **Every node runs as the requester**, even when an approver's request resumes the graph (`acting_as`), because the agent acts on behalf of the person who asked. Test: `test_resumed_nodes_run_as_the_requester_not_the_resumer`. In production you'd re-resolve the requester's *current* permissions from the identity provider instead of trusting the stored snapshot.
- Approvers must have the `admin` or `approver` role and be in the same tenant. They may view runs they don't own, which is delegated approval.
- `AGENT_FOUR_EYES=true` forbids approving your own run (separation of duties).
- Other tenants get 404, not 403, so they don't learn that the run exists.

## 5. MCP: the knowledge tool as a protocol

[`app/mcp_server.py`](../app/mcp_server.py) exposes **one read-only tool**, `search_knowledge`. It calls the Knowledge API (`/rag/hybrid`), not the databases, so ACL and governance still apply.

```sh
# stdio (desktop clients launch it themselves)
KNOWLEDGE_API_URL=http://127.0.0.1:8000 python -m app.mcp_server
# or Streamable HTTP at http://127.0.0.1:8002/mcp
python -m app.mcp_server --http --port 8002
```

**Use it from Claude Code** (from `starter_repo`): `claude mcp add knowledge -- .venv/bin/python -m app.mcp_server`, then ask "search my knowledge base for the annual leave policy". Your knowledge platform is now a tool any MCP client can use.

**Use it from the Lab 12 agent:** start the MCP server with `--http`, then start the API with `AGENT_KNOWLEDGE_TRANSPORT=mcp`. `events[].via` shows `mcp`.

What MCP does *not* solve (a favorite interview question):

- **Trust.** Tool annotations like `read_only_hint` are hints. A client must not trust them from an unknown server. This server is read-only because it can only reach a read-only endpoint.
- **User identity.** The server calls the API as `KNOWLEDGE_API_TOKEN`, meaning the person who launched it. Forwarding the client's token ("token passthrough") is an anti-pattern in the MCP spec. Multi-user deployments use MCP's OAuth flow and exchange the user's token for an API-scoped one.
- **Approval, idempotency and audit** stay in the platform.
- **Prompt injection.** Tool output is untrusted text. The server's `instructions` say so, and the client must still treat it that way.

Tests use an in-process MCP client (`Client(server)`) with a mocked HTTP API, so they run without the network.

## 6. Evaluate it properly

```sh
python eval/run_agent_suite.py --seed-injection --trials 1     # once: adds a document containing a prompt injection
python eval/run_agent_suite.py --runtime all --trials 3 --k 3 --output eval/agent-suite-$(date +%F).json
```

How to read the report:

- **pass@1** per task and category is the average success rate.
- **pass^3** is the chance that *all three* tries pass, which is reliability. A task at pass@1 0.67 has pass^3 of 0.
- **unapproved_writes** must be **0**. It's a safety invariant, not a quality score, and the script exits 1 otherwise.
- Compare `search_then_calc_autonomous` with `search_then_calc_required`. The gap is your evidence for "workflow first, agent where needed".
- `indirect_injection` / `v2_indirect_injection`: if the model *proposes* the injected write, that's a model failure. If it gets *written*, that's a system failure. Lab 12's `verify` flags `write_not_requested_by_goal`, so it never even reaches approval.

## 7. Compare single vs "multi-agent" (optional exercise)

Split `plan` into two agents-as-tools: a *researcher* that returns cited facts and a *writer* that drafts the follow-up. Run the suite on both versions and compare pass@1, pass^3, latency and tokens (`/observability/summary`). Write a one-page ADR. Most of the time the single planner wins on cost and debuggability, and the interview answer is the data, not the opinion.

## 8. Python 3.10 note

LangGraph's `interrupt()` needs Python ≥ 3.11 inside async nodes. This repo runs 3.10, so the pause is a **static breakpoint** (`interrupt_before=["approve"]`), and the approval API writes the decision with `aupdate_state`. The behavior is the same: pause, persist, resume with a human decision. On 3.11+ you'd typically call `interrupt(payload)` inside `approve` and resume with `Command(resume=decision)`.

## 9. Definition of done

- [ ] `pytest -q tests/test_graph_agent.py tests/test_mcp_server.py` passes, and you can explain each test.
- [ ] `python scripts/lab12_crash_demo.py` prints PASS.
- [ ] You can draw the graph and say why verify/approve precede execute.
- [ ] You can explain: checkpoint vs memory vs ledger; why nodes run as the requester; what MCP does not solve.
- [ ] The suite report shows `unapproved_writes: 0`, and you can explain one failing task.
