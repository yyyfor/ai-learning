"""HTTP endpoints and shared API dependencies."""

from fastapi import APIRouter

from app.api import documents, health, inspectors, search, workspace, rag

router = APIRouter()
router.include_router(workspace.router)
router.include_router(health.router)
router.include_router(documents.router)
router.include_router(search.router)
router.include_router(inspectors.router)
router.include_router(rag.router)
