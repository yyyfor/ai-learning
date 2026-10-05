import asyncio

from fakes import FakeStore

from app.agent.memory import MemoryStore, compact_observations


def run(coroutine):
    return asyncio.run(coroutine)


def test_compaction_keeps_recent_observations_verbatim():
    observations = [{"tool": "calculate", "data": {"value": i}} for i in range(6)]
    compact = compact_observations(observations, keep_last=2)
    assert compact[-2:] == observations[-2:]
    assert compact[0] == {"summary_of": "calculate", "text": '{"value": 0}'}
    assert len(compact) == 6


def test_compaction_truncates_long_old_observations():
    observations = [{"tool": "search_knowledge", "data": {"text": "x" * 500}}, {"tool": "calculate", "data": {}}]
    compact = compact_observations(observations, keep_last=1, summary_chars=20)
    assert compact[0]["text"].endswith("...") and len(compact[0]["text"]) == 23


def test_recall_is_scoped_to_one_user_and_ranked_by_overlap():
    memory = MemoryStore(FakeStore())
    run(memory.remember("t1", "ann", "semantic", "Ann prefers follow-ups assigned to HR", "user"))
    run(memory.remember("t1", "ann", "episodic", "Asked about annual leave policy", "run:1"))
    run(memory.remember("t1", "bob", "semantic", "Bob asked about annual leave too", "user"))
    found = run(memory.recall("t1", "ann", "annual leave policy"))
    assert [m["text"] for m in found][0] == "Asked about annual leave policy"
    assert all(m["owner"] == "ann" for m in found)


def test_recall_matches_chinese_characters():
    memory = MemoryStore(FakeStore())
    run(memory.remember("t1", "ann", "semantic", "年假政策是二十天", "user"))
    assert run(memory.recall("t1", "ann", "年假"))


def test_fixed_memory_id_makes_writes_idempotent_and_forget_checks_owner():
    store = FakeStore()
    memory = MemoryStore(store)
    run(memory.remember("t1", "ann", "episodic", "first", "run:1", memory_id="episodic:1"))
    run(memory.remember("t1", "ann", "episodic", "second", "run:1", memory_id="episodic:1"))
    assert store.count("memories") == 1
    assert not run(memory.forget("t1", "bob", "episodic:1"))
    assert run(memory.forget("t1", "ann", "episodic:1"))
    assert store.count("memories") == 0
