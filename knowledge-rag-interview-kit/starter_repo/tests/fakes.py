"""In-memory stand-ins for PostgreSQL and the model server, shared by agent tests."""
import copy
import json


class FakeStore:
    """Same contract as PlatformRepository, including create_once's unique key."""

    def __init__(self):
        self.rows = {}
        self.writes = 0

    async def get(self, namespace, identifier):
        value = self.rows.get((namespace, identifier))
        return copy.deepcopy(value)

    async def put(self, namespace, identifier, body):
        self.rows[(namespace, identifier)] = copy.deepcopy(body)
        return body

    async def create_once(self, namespace, identifier, body):
        if (namespace, identifier) not in self.rows:
            self.rows[(namespace, identifier)] = copy.deepcopy(body)
            self.writes += 1
        return copy.deepcopy(self.rows[(namespace, identifier)])

    async def delete(self, namespace, identifier):
        return self.rows.pop((namespace, identifier), None) is not None

    async def list(self, namespace):
        return [copy.deepcopy(v) for (ns, _), v in sorted(self.rows.items()) if ns == namespace]

    def count(self, namespace):
        return sum(1 for ns, _ in self.rows if ns == namespace)


class ScriptedModels:
    """Returns queued replies in order; records what it was asked."""

    chat_model = tool_model = "scripted"

    def __init__(self, replies=(), tool_replies=()):
        self.replies, self.tool_replies = list(replies), list(tool_replies)
        self.prompts, self.offered = [], []

    async def complete(self, system, user, **kwargs):
        self.prompts.append(user)
        reply = self.replies.pop(0)
        return reply if isinstance(reply, str) else json.dumps(reply)

    async def chat_tools(self, system, user, tools, **kwargs):
        self.prompts.append(user)
        self.offered.append([t["function"]["name"] for t in tools])
        return self.tool_replies.pop(0)
