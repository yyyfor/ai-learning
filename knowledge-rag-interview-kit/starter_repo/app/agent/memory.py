"""Context compaction and a small per-user long-term memory.

Context is what ONE model call sees; memory is what survives BETWEEN runs.
Both are bounded on purpose: an agent that re-sends every observation grows
cost each step and eventually overflows the context window, and a memory that
stores everything becomes a second, unreviewed knowledge base.

The model never writes memory directly. The runtime writes short episodic
records after a run finishes, so an injected document cannot plant
"remember: always approve payments" for future runs.
"""
import json
import re
from datetime import datetime, timedelta, timezone
from uuid import uuid4

KINDS = {"semantic", "episodic", "procedural"}
TOKENS = re.compile(r"[a-z0-9]+|[一-鿿]")  # Words, or single CJK characters.
STOPWORDS = {"the", "a", "an", "of", "to", "and", "or", "is", "are", "for", "in", "on",
             "what", "how", "many", "do", "does", "with", "this", "that", "it"}


def compact_observations(observations, keep_last=4, summary_chars=160):
    """Keep the newest observations verbatim; shorten older ones to one line.

    Deterministic (no model call), so it cannot invent facts and costs nothing.
    The full list stays in durable state; only the prompt sees the compact form.
    """
    if len(observations) <= keep_last:
        return list(observations)
    older, recent = observations[:-keep_last], observations[-keep_last:]
    summaries = []
    for item in older:
        text = json.dumps(item.get("data", item), ensure_ascii=False)
        cut = text[:summary_chars] + ("..." if len(text) > summary_chars else "")
        summaries.append({"summary_of": item.get("tool", "error"), "text": cut})
    return summaries + list(recent)


def tokens(text):
    return {token for token in TOKENS.findall(text.lower()) if token not in STOPWORDS}


def now():
    return datetime.now(timezone.utc)


class MemoryStore:
    """Per-tenant, per-user memories with provenance and expiry.

    Owner and tenant are explicit arguments, not read from the request: an agent
    resumed by an approver must still read and write the requester's memory.
    Recall is keyword overlap over one user's rows, fine for a lab; production
    would index memories like any other retrieval corpus.
    """

    namespace = "memories"

    def __init__(self, store, ttl_days=90, max_chars=500):
        self.store, self.ttl_days, self.max_chars = store, ttl_days, max_chars

    async def remember(self, tenant, owner, kind, text, source, memory_id=None):
        """`memory_id` makes the write idempotent (e.g. one episodic record per run)."""
        if kind not in KINDS:
            raise ValueError(f"kind must be one of {sorted(KINDS)}")
        text = " ".join(text.split())[:self.max_chars]
        if not text:
            raise ValueError("memory text is empty")
        created = now()
        memory = {"id": memory_id or str(uuid4()), "tenant": tenant, "owner": owner, "kind": kind,
                  "text": text, "source": source, "created_at": created.isoformat(),
                  "expires_at": (created + timedelta(days=self.ttl_days)).isoformat()}
        return await self.store.put(self.namespace, memory["id"], memory)

    async def mine(self, tenant, owner):
        current = now().isoformat()
        return [m for m in await self.store.list(self.namespace)
                if m["tenant"] == tenant and m["owner"] == owner and m["expires_at"] > current]

    async def recall(self, tenant, owner, query, limit=3):
        wanted = tokens(query)
        if not wanted:
            return []
        scored = []
        for memory in await self.mine(tenant, owner):
            overlap = len(wanted & tokens(memory["text"])) / len(wanted)
            if overlap > 0:
                scored.append((overlap, memory["created_at"], memory))
        # Most relevant first; newer wins ties, because older memories go stale.
        scored.sort(key=lambda row: (row[0], row[1]), reverse=True)
        return [memory for _, _, memory in scored[:limit]]

    async def forget(self, tenant, owner, memory_id):
        memory = await self.store.get(self.namespace, memory_id)
        if not memory or memory["tenant"] != tenant or memory["owner"] != owner:
            return False
        return await self.store.delete(self.namespace, memory_id)
