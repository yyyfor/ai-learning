"""The MCP server is read-only, validates input, and reports upstream refusals as tool errors."""
import asyncio
import json

import httpx
import pytest

pytest.importorskip("mcp")
from mcp import Client  # noqa: E402

from app.agent.knowledge_tools import KnowledgeUnavailable, McpKnowledge  # noqa: E402
from app.mcp_server import build_server  # noqa: E402


def run(coroutine):
    return asyncio.run(coroutine)


def api(status=200):
    seen = []

    def handler(request):
        seen.append(json.loads(request.content))
        if status != 200:
            return httpx.Response(status, json={"detail": "no"})
        return httpx.Response(200, json={"hits": [
            {"document_id": "doc-1", "title": "Leave", "text": "20 days " * 200}]})

    return httpx.AsyncClient(base_url="http://api", transport=httpx.MockTransport(handler)), seen


def test_tool_is_discoverable_and_marked_read_only():
    client, _ = api()

    async def scenario():
        async with Client(build_server(client)) as session:
            return (await session.list_tools()).tools

    tools = run(scenario())
    assert [t.name for t in tools] == ["search_knowledge"]
    assert tools[0].annotations.read_only_hint is True
    assert tools[0].input_schema["properties"]["top_k"]["maximum"] == 5


def test_search_calls_the_governed_api_and_truncates_text():
    client, seen = api()
    hits = run(McpKnowledge(build_server(client)).search("leave", top_k=2))
    assert seen == [{"query": "leave", "top_k": 2}]
    assert hits[0]["document_id"] == "doc-1" and len(hits[0]["text"]) == 800


def test_upstream_refusal_and_bad_arguments_are_tool_errors():
    client, _ = api(status=403)
    with pytest.raises(KnowledgeUnavailable, match="refused"):
        run(McpKnowledge(build_server(client)).search("leave"))
    ok_client, seen = api()
    with pytest.raises(KnowledgeUnavailable):
        run(McpKnowledge(build_server(ok_client)).search("leave", top_k=50))
    assert seen == []  # Invalid input never reaches the API.
