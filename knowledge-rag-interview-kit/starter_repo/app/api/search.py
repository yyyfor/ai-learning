import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.dependencies import get_knowledge_service
from app.dto.query import QueryRequest, QueryResponse
from app.dto.search import SearchRequest, SearchResponse
from app.services.knowledge import KnowledgeService

router = APIRouter()
logger = logging.getLogger("knowledge_api")


@router.post("/search", response_model=SearchResponse)
async def search_documents(
    payload: SearchRequest,
    service: KnowledgeService = Depends(get_knowledge_service),
) -> dict[str, Any]:
    try:
        page = await service.search_documents(**payload.model_dump())
    except Exception as exc:
        logger.exception("search_failed")
        raise HTTPException(status_code=503, detail="search service unavailable") from exc
    return page.as_dict()


@router.get("/search", response_model=SearchResponse)
async def search_documents_get(
    q: str = Query(..., min_length=1, description="Keyword query"),
    source: str | None = None,
    tag: list[str] = Query(default=[]),
    metadata: str | None = Query(
        default=None,
        description='JSON object for exact filters, for example {"team":"risk"}',
    ),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=50),
    service: KnowledgeService = Depends(get_knowledge_service),
) -> dict[str, Any]:
    filters = parse_metadata(metadata)
    try:
        page_result = await service.search_documents(
            query=q,
            source=source,
            tags=tag,
            metadata=filters,
            page=page,
            page_size=page_size,
        )
    except Exception as exc:
        logger.exception("search_failed")
        raise HTTPException(status_code=503, detail="search service unavailable") from exc
    return page_result.as_dict()


@router.post("/query", response_model=QueryResponse)
async def query_documents(
    payload: QueryRequest,
    service: KnowledgeService = Depends(get_knowledge_service),
) -> dict[str, Any]:
    # Keep the original retrieval response compatible with the frontend.
    # Week 3 vector retrieval and answer generation live at /rag/query.
    try:
        return await service.query_documents(**payload.model_dump())
    except Exception as exc:
        logger.exception("query_failed")
        raise HTTPException(status_code=503, detail="query service unavailable") from exc


def parse_metadata(raw_metadata: str | None) -> dict[str, Any]:
    if raw_metadata is None:
        return {}
    try:
        parsed = json.loads(raw_metadata)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="metadata must be valid JSON") from exc
    if not isinstance(parsed, dict):
        raise HTTPException(status_code=400, detail="metadata must be a JSON object")
    return parsed
