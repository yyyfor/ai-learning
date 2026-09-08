from fastapi import APIRouter, Depends

from app.api.dependencies import get_knowledge_service
from app.services.knowledge import KnowledgeService

router = APIRouter()


@router.get("/health")
async def health(service: KnowledgeService = Depends(get_knowledge_service)) -> dict:
    return await service.health()
