import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dependencies import get_knowledge_service
from app.dto.documents import DocumentCreate, DocumentResponse
from app.services.knowledge import DocumentNotFoundError, KnowledgeService

router = APIRouter()
logger = logging.getLogger("knowledge_api")


@router.post(
    "/documents",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_document(
    payload: DocumentCreate,
    service: KnowledgeService = Depends(get_knowledge_service),
) -> dict[str, Any]:
    try:
        document = await service.create_document(payload)
    except Exception as exc:
        logger.exception("document_create_failed")
        raise HTTPException(
            status_code=503,
            detail="could not write document to PostgreSQL and Elasticsearch",
        ) from exc
    logger.info("document_created id=%s", document.id)
    return document.as_dict()


@router.get("/documents", response_model=list[DocumentResponse])
async def list_documents(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    service: KnowledgeService = Depends(get_knowledge_service),
) -> list[dict[str, Any]]:
    documents = await service.list_documents(page=page, page_size=page_size)
    return [document.as_dict() for document in documents]


@router.get("/documents/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: str,
    service: KnowledgeService = Depends(get_knowledge_service),
) -> dict[str, Any]:
    document = await service.get_document(document_id)
    return document.as_dict()


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: str,
    service: KnowledgeService = Depends(get_knowledge_service),
) -> None:
    try:
        await service.delete_document(document_id)
    except DocumentNotFoundError:
        raise
    except Exception as exc:
        logger.exception("document_delete_failed")
        raise HTTPException(
            status_code=503,
            detail="could not delete document from PostgreSQL and Elasticsearch",
        ) from exc
    logger.info("document_deleted id=%s", document_id)
