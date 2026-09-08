from fastapi import HTTPException, Request

from app.services.knowledge import KnowledgeService


def get_knowledge_service(request: Request) -> KnowledgeService:
    """Dependency injection point for the service layer."""

    service = getattr(request.app.state, "knowledge_service", None)
    if service is None:
        raise HTTPException(status_code=503, detail="service is not ready")
    return service
