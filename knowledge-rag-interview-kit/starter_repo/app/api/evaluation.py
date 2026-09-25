from fastapi import APIRouter, Request
from app.api.rag import get_rag_service
from app.dto.evaluation import EvaluationRequest
from app.services.evaluation import EvaluationService

router = APIRouter(prefix="/evaluation", tags=["Lab 9 Evaluation"])


@router.post("/run")
async def run(payload: EvaluationRequest, request: Request):
    service = EvaluationService(get_rag_service(request), request.app.state.governance,
                                request.app.state.platform_store)
    return await service.run(payload)
