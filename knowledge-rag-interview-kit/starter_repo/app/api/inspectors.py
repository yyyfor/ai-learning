import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.dependencies import get_knowledge_service
from app.services.knowledge import KnowledgeService

router = APIRouter()
logger = logging.getLogger("knowledge_api")


@router.get("/inspector/redis")
async def inspect_redis(
    cursor: int = Query(default=0, ge=0),
    service: KnowledgeService = Depends(get_knowledge_service),
) -> dict[str, Any]:
    """Read this application's search cache only; never expose arbitrary keys."""
    try:
        return await service.cache.inspect(cursor)
    except Exception as exc:
        logger.exception("cache_inspection_failed")
        raise HTTPException(status_code=503, detail="Redis cache unavailable") from exc


@router.get("/inspector/elasticsearch")
async def inspect_elasticsearch(
    page: int = Query(default=1, ge=1, le=500),
    page_size: int = Query(default=20, ge=1, le=20),
    service: KnowledgeService = Depends(get_knowledge_service),
) -> dict[str, Any]:
    try:
        return await service.search_index.inspect(page, page_size)
    except Exception as exc:
        logger.exception("index_inspection_failed")
        raise HTTPException(status_code=503, detail="Elasticsearch index unavailable") from exc
