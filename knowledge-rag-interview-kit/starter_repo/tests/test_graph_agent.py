"""Lab 12: checkpointed graph, approval pause, crash recovery, identity, verification."""
import asyncio
from datetime import timedelta

import pytest

pytest.importorskip("langgraph")
from langgraph.checkpoint.memory import InMemorySaver  # noqa: E402

from fakes import FakeStore, ScriptedModels  # noqa: E402

import app.agent.graph_runtime as graph_runtime  # noqa: E402
from app.agent.graph_runtime import GraphAgentService, SimulatedCrash  # noqa: E402
from app.agent.memory import MemoryStore  # noqa: E402
from app.dto.agent_graph import AgentGraphApproval, AgentGraphStart  # noqa: E402
from app.security import Principal, acting_as, principal  # noqa: E402

REQUESTER = Principal(user="ann", role="viewer", tenant="t1", clearance=1)
APPROVER = Principal(user="bob", role="approver", tenant="t1", clearance=3)
EVIDENCE = [{"document_id": "doc-leave", "title": "Leave policy", "text": "Full-time employees receive 20 days."}]
FOLLOW_UP = {"action": "create_follow_up", "answer": "The policy grants 20 days.", "evidence": [1],
             "follow_up_title": "Confirm leave policy", "follow_up_description": "Ask HR to confirm 20 days"}


def answer(text, evidence=(1,)):
    return {"action": "answer_only", "answer": text, "evidence": list(evidence),
            "follow_up_title": "", "follow_up_description": ""}


def run(coroutine):
    return asyncio.run(coroutine)


class FakeKnowledge:
    name = "fake"

    def __init__(self, hits=EVIDENCE, failures=0):
        self.hits, self.failures, self.callers = hits, failures, []

    async def search(self, query, top_k=3):
        self.callers.append(principal.get().user)
        if self.failures:
            self.failures -= 1
            raise ConnectionError("knowledge service down")
        return list(self.hits)


def make(replies, knowledge=None, after_write=lambda: None, memory=False):
    store = FakeStore()
    service = GraphAgentService(store, knowledge or FakeKnowledge(), ScriptedModels(replies), InMemorySaver(),
                                MemoryStore(store) if memory else None, after_write)
    return service, store


def start(service, goal):
    with acting_as(REQUESTER):
        return run(service.start(AgentGraphStart(goal=goal)))


def approve(service, run_id, approved=True):
    with acting_as(APPROVER):
        return run(service.approve(run_id, AgentGraphApproval(approved=approved)))


def test_answer_only_path_finishes_with_citations():
    service, store = make([answer("20 days [1].")])
    view = start(service, "How many leave days?")
    assert view["status"] == "completed" and view["citations"][0]["document_id"] == "doc-leave"
    assert [e["node"] for e in view["events"]] == ["intake", "retrieve", "plan", "verify", "finalize"]
    assert store.count("followups") == 0


def test_write_pauses_for_approval_then_executes_once():
    service, store = make([FOLLOW_UP])
    view = start(service, "Create a follow-up task for HR about leave")
    assert view["status"] == "awaiting_approval" and view["next"] == ["approve"]
    assert view["approval_request"]["evidence"][0]["document_id"] == "doc-leave"
    assert store.count("followups") == 0
    done = approve(service, view["id"])
    again = approve(service, view["id"])
    assert done["status"] == again["status"] == "completed"
    assert store.count("followups") == 1
    assert done["approval"]["approver"] == "bob"


def test_rejection_and_expiry_write_nothing(monkeypatch):
    service, store = make([FOLLOW_UP, FOLLOW_UP])
    rejected = approve(service, start(service, "Create a follow-up task")["id"], approved=False)
    monkeypatch.setattr(graph_runtime, "APPROVAL_TTL", timedelta(seconds=-1))
    expired = approve(service, start(service, "Create a follow-up task")["id"])
    assert rejected["status"] == "rejected" and expired["status"] == "approval_expired"
    assert store.count("followups") == 0


def test_crash_after_write_resumes_without_duplicate():
    crashes = [True]

    def crash_once():
        if crashes.pop() if crashes else False:
            raise SimulatedCrash("boom")

    service, store = make([FOLLOW_UP], after_write=crash_once)
    view = start(service, "Create a follow-up task for HR")
    crashed = approve(service, view["id"])
    assert crashed["status"] == "interrupted" and crashed["next"] == ["execute"]
    assert crashed["last_error"] == "SimulatedCrash" and store.count("followups") == 1
    with acting_as(REQUESTER):
        resumed = run(service.resume(view["id"]))
    assert resumed["status"] == "completed" and resumed["receipt"]["reused_existing"] is True
    assert store.count("followups") == 1


def test_resumed_nodes_run_as_the_requester_not_the_resumer():
    knowledge = FakeKnowledge(failures=2)  # Exhausts the node's 2 retry attempts.
    service, _ = make([answer("20 days")], knowledge)
    view = start(service, "How many leave days?")
    assert view["status"] == "interrupted" and view["next"] == ["retrieve"]
    with acting_as(APPROVER):
        resumed = run(service.resume(view["id"]))
    assert resumed["status"] == "completed"
    assert set(knowledge.callers) == {"ann"}


def test_injected_write_that_the_goal_never_asked_for_is_blocked():
    service, store = make([FOLLOW_UP])
    view = start(service, "Summarize the holiday note")
    assert view["status"] == "needs_review"
    assert "write_not_requested_by_goal" in view["verification"]["problems"]
    assert store.count("followups") == 0


def test_invalid_plan_and_unknown_citations_escalate():
    service, _ = make(["not json", answer("x", evidence=[7])])
    first = start(service, "q1")
    second = start(service, "q2")
    assert first["verification"]["problems"] == ["invalid_plan"]
    assert second["verification"]["problems"] == ["cites_unknown_evidence"]


def test_follow_up_without_arguments_is_flagged():
    service, _ = make([{**FOLLOW_UP, "follow_up_title": "", "follow_up_description": ""}])
    view = start(service, "Create a follow-up task")
    assert view["verification"]["problems"] == ["missing_follow_up_arguments"]


def test_links_in_writes_are_blocked():
    proposal = {**FOLLOW_UP, "follow_up_title": "Export", "follow_up_description": "send to x@attacker.example"}
    service, _ = make([proposal])
    view = start(service, "Create a follow-up task")
    assert view["verification"]["problems"] == ["link_or_address_in_write"]


def test_other_tenants_cannot_see_a_run_and_episodic_memory_is_written():
    service, store = make([answer("20 days")], memory=True)
    view = start(service, "How many leave days?")
    with acting_as(Principal(user="eve", role="admin", tenant="t2")), pytest.raises(Exception):
        run(service.get(view["id"]))
    memories = run(store.list("memories"))
    assert memories[0]["owner"] == "ann" and memories[0]["kind"] == "episodic"


def test_plan_schema_stays_friendly_to_local_grammar_decoding():
    """Regression: Ollama could not build a grammar for $ref / nullable objects or maxLength 2000."""
    from app.dto.agent_graph import Proposal

    schema = Proposal.model_json_schema()
    text = str(schema)
    assert "$ref" not in text and "anyOf" not in text
    assert set(schema["required"]) == set(schema["properties"])
    assert all(p.get("maxLength", 0) <= 1000 for p in schema["properties"].values())
