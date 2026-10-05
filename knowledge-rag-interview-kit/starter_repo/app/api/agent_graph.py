from fastapi import APIRouter, HTTPException, Request

from app.dto.agent_graph import AgentGraphApproval, AgentGraphStart

router = APIRouter(prefix="/agent/v2", tags=["Lab 12 Durable agent"])


def service(request):
    value = getattr(request.app.state, "agent_graph", None)
    if value is None:
        raise HTTPException(503, "Lab 12 agent needs RAG_ENABLED=true, Ollama and pip install -e '.[agent]'")
    return value


@router.post("/runs")
async def start(payload: AgentGraphStart, request: Request):
    return await service(request).start(payload)


@router.get("/runs/{run_id}")
async def get_run(run_id: str, request: Request):
    return await service(request).get(run_id)


@router.post("/runs/{run_id}/approval")
async def approve(run_id: str, payload: AgentGraphApproval, request: Request):
    return await service(request).approve(run_id, payload)


@router.post("/runs/{run_id}/resume")
async def resume(run_id: str, request: Request):
    return await service(request).resume(run_id)
