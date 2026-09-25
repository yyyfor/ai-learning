from fastapi import APIRouter, Request
from app.dto.governance import AssetMetadata, CitationCheck, Rollback, Transition

router = APIRouter(prefix="/governance", tags=["Lab 8 Governance"])


@router.put("/documents/{document_id}")
async def draft(document_id: str, payload: AssetMetadata, request: Request):
    return await request.app.state.governance.save_draft(document_id, payload)


@router.get("/documents/{document_id}")
async def get_asset(document_id: str, request: Request):
    return await request.app.state.governance.get(document_id)


@router.post("/documents/{document_id}/transition")
async def transition(document_id: str, payload: Transition, request: Request):
    return await request.app.state.governance.transition(document_id, payload)


@router.post("/documents/{document_id}/rollback")
async def rollback(document_id: str, payload: Rollback, request: Request):
    return await request.app.state.governance.rollback(document_id, payload)


@router.get("/freshness")
async def freshness(request: Request):
    return await request.app.state.governance.freshness()


@router.post("/citations/validate")
async def citation(payload: CitationCheck, request: Request):
    return await request.app.state.governance.citation(payload)
