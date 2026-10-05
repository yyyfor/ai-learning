"""Lab 11 runtime: trajectory, approval, idempotency, expiry, recovery, native tools."""
import asyncio
from types import SimpleNamespace

from fakes import FakeStore, ScriptedModels

from app.agent.runtime import AgentRuntime
from app.dto.agent_lab import AgentApproval, AgentStart


def run(coroutine):
    return asyncio.run(coroutine)


class FakeRag:
    def __init__(self, models, hits=("Contract C-101 value is 1200 dollars.",)):
        self.models = models
        self.hits = hits

    async def retrieve(self, request):
        return SimpleNamespace(hits=[SimpleNamespace(document_id=f"doc-{i}", text=text)
                                     for i, text in enumerate(self.hits)])


def runtime(replies=(), tool_replies=()):
    models = ScriptedModels(replies, tool_replies)
    store = FakeStore()
    return AgentRuntime(store, FakeRag(models)), store, models


FOLLOW_UP = {"tool": "create_follow_up", "arguments": {"title": "Check policy", "description": "Ask HR"}}


def test_search_then_calculate_then_finish():
    agent, _, _ = runtime([
        {"tool": "search_knowledge", "arguments": {"query": "C-101 value"}},
        {"tool": "calculate", "arguments": {"expression": "1200 * 0.15"}},
        {"tool": "finish", "answer": "15% is 180"},
    ])
    result = run(agent.start(AgentStart(goal="15% of C-101", required_tools=["search_knowledge", "calculate"])))
    assert result["status"] == "completed"
    assert [s["tool"] for s in result["steps"]] == ["search_knowledge", "calculate", "finish"]
    assert result["observations"][1]["data"]["value"] == 180


def test_required_tool_cannot_be_skipped():
    agent, _, _ = runtime([{"tool": "finish", "answer": "guess: 180"}] * 2)
    result = run(agent.start(AgentStart(goal="15% of C-101", required_tools=["calculate"], max_steps=2)))
    assert result["status"] == "max_steps"
    assert all(step["status"] == "invalid_action" for step in result["steps"])


def test_code_in_calculator_is_rejected_not_executed():
    agent, _, _ = runtime([
        {"tool": "calculate", "arguments": {"expression": "__import__('os').system('ls')"}},
        {"tool": "finish", "answer": "Refused: not arithmetic"},
    ])
    result = run(agent.start(AgentStart(goal="run it")))
    assert result["steps"][0]["status"] == "invalid_action"
    assert result["status"] == "completed"


def test_write_waits_for_approval_and_double_approval_writes_once():
    agent, store, _ = runtime([FOLLOW_UP, {"tool": "finish", "answer": "Created"}])
    paused = run(agent.start(AgentStart(goal="create a follow-up")))
    assert paused["status"] == "awaiting_approval" and store.count("followups") == 0
    done = run(agent.approve(paused["id"], AgentApproval(approved=True)))
    again = run(agent.approve(paused["id"], AgentApproval(approved=True)))
    assert done["status"] == again["status"] == "completed"
    assert store.count("followups") == 1


def test_rejection_writes_nothing():
    agent, store, _ = runtime([FOLLOW_UP])
    paused = run(agent.start(AgentStart(goal="create a follow-up")))
    result = run(agent.approve(paused["id"], AgentApproval(approved=False)))
    assert result["status"] == "rejected" and store.count("followups") == 0


def test_expired_approval_is_refused():
    agent, store, _ = runtime([FOLLOW_UP])
    paused = run(agent.start(AgentStart(goal="create a follow-up")))
    stored = run(store.get("agent_runs", paused["id"]))
    stored["pending"]["expires_at"] = "2000-01-01T00:00:00+00:00"
    run(store.put("agent_runs", paused["id"], stored))
    result = run(agent.approve(paused["id"], AgentApproval(approved=True)))
    assert result["status"] == "approval_expired" and store.count("followups") == 0


def test_ledger_beats_expiry_after_a_crash():
    """A previous approval wrote the record, then the process died before saving the run."""
    agent, store, _ = runtime([FOLLOW_UP, {"tool": "finish", "answer": "Created"}])
    paused = run(agent.start(AgentStart(goal="create a follow-up")))
    stored = run(store.get("agent_runs", paused["id"]))
    key = stored["pending"]["idempotency_key"]
    run(store.create_once("followups", key, {"id": key, "run_id": paused["id"], "owner": "local",
                                             "tenant": "local", "approved_by": "local",
                                             "title": "Check policy", "description": "Ask HR"}))
    stored["pending"]["expires_at"] = "2000-01-01T00:00:00+00:00"
    run(store.put("agent_runs", paused["id"], stored))
    result = run(agent.approve(paused["id"], AgentApproval(approved=True)))
    assert result["status"] == "completed" and store.count("followups") == 1


def test_resume_recovers_a_run_orphaned_by_a_crash():
    agent, store, _ = runtime([{"tool": "finish", "answer": "180"}])
    orphan = {"id": "r1", "owner": "local", "tenant": "local", "goal": "g", "status": "running",
              "config": AgentStart(goal="g").model_dump(), "steps": [{"step": 1, "turn": 1, "tool": None, "status": "planning"}],
              "observations": [], "tokens_reserved": 0, "estimated_cost": 0, "elapsed_seconds": 0,
              "pending": None, "answer": None, "turns": 1}
    run(store.put("agent_runs", "r1", orphan))
    result = run(agent.resume("r1"))
    assert result["status"] == "completed" and result["recoveries"] == 1
    assert result["steps"][0]["status"] == "interrupted"
    assert run(agent.resume("r1"))["recoveries"] == 1  # Finished runs are never re-executed.


def test_native_tools_parallel_calls_then_text_answer():
    agent, _, models = runtime(tool_replies=[
        {"content": "", "tool_calls": [
            {"name": "search_knowledge", "arguments": {"query": "C-101"}},
            {"name": "calculate", "arguments": {"expression": "1200*0.15"}}]},
        {"content": "It is 180.", "tool_calls": []},
    ])
    result = run(agent.start(AgentStart(goal="15% of C-101", mode="native_tools")))
    assert result["status"] == "completed" and result["answer"] == "It is 180."
    assert [s["turn"] for s in result["steps"]] == [1, 1, 2]
    assert result["turns"] == 2


def test_native_required_tool_is_the_only_tool_offered():
    agent, _, models = runtime(tool_replies=[
        {"content": "", "tool_calls": [{"name": "calculate", "arguments": {"expression": "2+2"}}]},
        {"content": "4", "tool_calls": []},
    ])
    run(agent.start(AgentStart(goal="2+2", mode="native_tools", required_tools=["calculate"])))
    assert models.offered[0] == ["calculate"]
    assert set(models.offered[1]) == {"search_knowledge", "calculate", "create_follow_up"}


def test_native_unknown_tool_is_an_invalid_action():
    agent, _, _ = runtime(tool_replies=[
        {"content": "", "tool_calls": [{"name": "delete_everything", "arguments": {}}]},
        {"content": "done", "tool_calls": []},
    ])
    result = run(agent.start(AgentStart(goal="x", mode="native_tools")))
    assert result["steps"][0]["status"] == "invalid_action" and result["status"] == "completed"


def test_token_budget_stops_before_calling_the_model():
    agent, _, models = runtime()
    result = run(agent.start(AgentStart(goal="x", token_budget=1000)))
    assert result["status"] == "budget_exceeded" and models.prompts == []


def test_prompt_uses_compacted_observations():
    replies = [{"tool": "calculate", "arguments": {"expression": f"{i}+1"}} for i in range(6)]
    agent, _, models = runtime(replies + [{"tool": "finish", "answer": "done"}])
    run(agent.start(AgentStart(goal="count", max_steps=7)))
    assert '"summary_of"' in models.prompts[-1]


def test_structured_prompt_keeps_the_explicit_finish_instruction():
    """Regression: a looser "finish with the answer" made llama3 loop on calculate
    until max_steps. The live agent suite caught it; this pins the wording."""
    agent, _, models = runtime([{"tool": "finish", "answer": "done"}])
    run(agent.start(AgentStart(goal="x")))
    assert "return tool=finish with the answer now" in models.prompts[0]
