from app.dto.search import SearchRequest, SearchResponse


class QueryRequest(SearchRequest):
    """Legacy document retrieval; use /rag/query for vector RAG answers."""


class QueryResponse(SearchResponse):
    context: str
    citations: list[dict[str, str]]
