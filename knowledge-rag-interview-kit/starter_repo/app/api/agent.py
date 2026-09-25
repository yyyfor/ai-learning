from fastapi import APIRouter, HTTPException, Request
from app.dto.agent_lab import AgentApproval, AgentStart
from app.agent.runtime import TOOLS
from app.security import principal

router = APIRouter(prefix="/agent", tags=["Lab 11 Agent"])


def service(request):
    value = getattr(request.app.state, "agent", None)
    if value is None:
        raise HTTPException(503, "Agent requires RAG_ENABLED=true and Ollama")
    return value


@router.get("/tools")
async def tools():
    return [{"name": name, "schema": model.model_json_schema(),
             "risk": "internal_write" if name == "create_follow_up" else "read_only"}
            for name, model in TOOLS.items()]


@router.post("/runs")
async def start(payload: AgentStart, request: Request):
    return await service(request).start(payload)


@router.get("/runs/{run_id}")
async def get_run(run_id: str, request: Request):
    return await service(request).get(run_id)


@router.post("/runs/{run_id}/approval")
async def approve(run_id: str, payload: AgentApproval, request: Request):
    return await service(request).approve(run_id, payload)


@router.get("/followups")
async def followups(request: Request):
    who = principal.get()
    return [r for r in await request.app.state.platform_store.list("followups")
            if r["tenant"] == who.tenant and r["owner"] == who.user]
