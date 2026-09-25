from fastapi import APIRouter, HTTPException, Request
from app.api.rag import run_rag
from app.dto.graph import GraphExtraction, GraphQuery, RELATIONS

router = APIRouter(prefix="/graph", tags=["Lab 6 GraphRAG"])


async def run_graph(operation):
    try:
        return await run_rag(operation)
    except Exception as exc:
        # The driver is optional: do not import it when graph support is off.
        if type(exc).__module__.startswith("neo4j"):
            raise HTTPException(503, "Neo4j unavailable; check the graph container and credentials") from exc
        raise


def service(request):
    value = getattr(request.app.state, "graph", None)
    if value is None:
        raise HTTPException(503, "Set GRAPH_ENABLED=true and RAG_ENABLED=true; install .[graph] and start Neo4j")
    return value


@router.get("/schema")
async def schema():
    return {"version": 1, "relations": RELATIONS, "extraction_schema": GraphExtraction.model_json_schema()}


@router.post("/documents/{document_id}/extract")
async def extract(document_id: str, request: Request):
    return await run_graph(service(request).extract(document_id))


@router.put("/documents/{document_id}")
async def build(document_id: str, payload: GraphExtraction, request: Request):
    return await run_graph(service(request).build(document_id, payload))


@router.post("/query")
async def query(payload: GraphQuery, request: Request):
    return await run_graph(service(request).query(payload))


@router.post("/compare")
async def compare(payload: GraphQuery, request: Request):
    return await run_graph(service(request).compare(payload))
