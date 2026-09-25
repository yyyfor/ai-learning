from datetime import datetime, timezone
from fastapi import APIRouter, Request
from app.observability import summary, traces
from app.security import require_role

router = APIRouter(prefix="/observability", tags=["Lab 10 Observability"])


@router.get("/metrics")
async def metrics(request: Request):
    require_role("admin")
    result = summary()
    store = request.app.state.platform_store
    indexed = {row["document_id"]: row for row in await store.list("indexing") if row.get("status") == "indexed"}
    now = datetime.now(timezone.utc)
    lag = [(now-datetime.fromisoformat(doc.created_at)).total_seconds()
           for doc in await request.app.state.knowledge_service.repository.all() if doc.id not in indexed]
    result["unindexed_documents"] = len(lag)
    result["max_index_lag_seconds"] = round(max(lag, default=0))
    result["slo"]["index_lag_under_10min"] = max(lag, default=0) < 600
    result["freshness"] = await request.app.state.governance.freshness()
    return result


@router.get("/traces")
async def recent_traces():
    require_role("admin")
    return list(traces)[-50:]
