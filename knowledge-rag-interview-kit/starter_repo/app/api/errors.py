from fastapi import Request, status
from fastapi.responses import JSONResponse

from app.services.knowledge import DocumentNotFoundError


async def document_not_found_handler(
    request: Request, exc: DocumentNotFoundError
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"detail": f"document not found: {exc}"},
    )
