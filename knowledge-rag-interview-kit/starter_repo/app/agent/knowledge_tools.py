"""How agents reach knowledge: always through the governed retrieval path.

DirectKnowledge runs the same ACL-aware hybrid retrieval as /rag/hybrid,
in-process, under the caller's identity. McpKnowledge calls the MCP server in
app/mcp_server.py, which calls the HTTP Knowledge API. Neither talks to
Qdrant or Elasticsearch directly, so ACL, governance and audit stay in one place.
"""
from app.dto.rag import HybridQueryRequest


class KnowledgeUnavailable(RuntimeError):
    """The knowledge tool answered with an error (not a transport failure)."""


class DirectKnowledge:
    name = "direct"

    def __init__(self, rag):
        self.rag = rag

    async def search(self, query, top_k=3):
        result = await self.rag.retrieve(HybridQueryRequest(query=query, top_k=top_k))
        return [{"document_id": h.document_id, "title": h.title, "text": h.text[:800]}
                for h in result.hits]


class McpKnowledge:
    """`server` is a Streamable HTTP URL, StdioServerParameters, or (in tests) an MCPServer."""

    name = "mcp"

    def __init__(self, server):
        self.server = server

    async def search(self, query, top_k=3):
        from mcp import Client  # Optional dependency: pip install -e '.[agent]'

        # One connection per call keeps the lab simple; a long-lived client
        # (and its session) would be reused in production.
        async with Client(self.server) as client:
            result = await client.call_tool("search_knowledge", {"query": query, "top_k": top_k})
        if result.is_error:
            text = " ".join(getattr(part, "text", "") for part in result.content)
            raise KnowledgeUnavailable(text or "search_knowledge failed")
        return list((result.structured_content or {}).get("hits", []))
