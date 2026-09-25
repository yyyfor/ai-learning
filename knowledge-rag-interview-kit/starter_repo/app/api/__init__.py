"""HTTP endpoints and shared API dependencies."""

from fastapi import APIRouter

from app.api import documents, health, inspectors, search, workspace, rag
from app.api import agent, evaluation, governance, graph, observability

router = APIRouter()
router.include_router(workspace.router)
router.include_router(health.router)
router.include_router(documents.router)
router.include_router(search.router)
router.include_router(inspectors.router)
router.include_router(rag.router)
router.include_router(governance.router)
router.include_router(graph.router)
router.include_router(evaluation.router)
router.include_router(observability.router)
router.include_router(agent.router)
