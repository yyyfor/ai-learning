"""Week 3 endpoints. Storage and model access stays in the service layer."""
import logging
import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from starlette.concurrency import run_in_threadpool

from app.api.dependencies import get_knowledge_service
from app.dto.documents import DocumentCreate, DocumentResponse
from app.dto.rag import (ChunkOptions, ChunkPreviewRequest, ChunkResponse,
                         IndexResponse, RagQueryRequest, RagQueryResponse)
from app.ingestion.parsing import parse_pdf
from app.services.knowledge import KnowledgeService
from app.services.rag import RagService

router = APIRouter(prefix="/rag", tags=["Week 3 RAG"])
logger = logging.getLogger("knowledge_api")


def get_rag_service(request: Request) -> RagService:
    service = getattr(request.app.state, "rag_service", None)
    if service is None:
        raise HTTPException(503, "RAG is disabled. Set RAG_ENABLED=true and start Ollama/Qdrant.")
    return service


async def run_rag(operation):
    try:
        return await operation
    except (httpx.HTTPError, KeyError) as exc:
        logger.warning("rag_dependency_failed type=%s", type(exc).__name__)
        raise HTTPException(503, "RAG dependency unavailable. Check Ollama models and Qdrant.") from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/status")
async def status(request: Request):
    service = getattr(request.app.state, "rag_service", None)
    return {"enabled": service is not None,
            "embedding_model": service.models.embedding_model if service else None,
            "chat_model": service.models.chat_model if service else None}


@router.post("/pdf", response_model=DocumentResponse, status_code=201)
async def upload_pdf(
    file: UploadFile = File(...),
    title: str = Form("PDF document", min_length=1, max_length=200),
    service: KnowledgeService = Depends(get_knowledge_service),
):
    # Parsing works without RAG enabled; indexing is an explicit second request.
    try:
        data = await file.read(10 * 1024 * 1024 + 1)
    finally:
        await file.close()
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(413, "PDF must be at most 10 MiB")
    try:
        pages = await run_in_threadpool(parse_pdf, data)
        payload = DocumentCreate(title=title, content="\f".join(text for _, text in pages),
                                 source="pdf", metadata={"page_count": len(pages)})
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    # Do not strip leading/trailing form feeds: empty pages still count.
    payload.content = "\f".join(text for _, text in pages)
    try:
        return (await service.create_document(payload)).as_dict()
    except Exception as exc:
        logger.warning("pdf_storage_failed type=%s", type(exc).__name__)
        raise HTTPException(503, "PDF could not be stored") from exc


@router.post("/chunks/preview", response_model=list[ChunkResponse])
async def preview(payload: ChunkPreviewRequest,
                  service: RagService = Depends(get_rag_service)):
    return await run_rag(service.preview(payload.text, payload))


@router.post("/documents/{document_id}/index", response_model=IndexResponse)
async def index_document(document_id: str, payload: ChunkOptions,
                         service: RagService = Depends(get_rag_service)):
    return await run_rag(service.index_document(document_id, payload))


@router.post("/query", response_model=RagQueryResponse)
async def query(payload: RagQueryRequest,
                service: RagService = Depends(get_rag_service)):
    return await run_rag(service.query(payload))
