import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter
from fastapi.responses import FileResponse

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
router = APIRouter()


@router.get("/", include_in_schema=False)
async def workspace_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@router.get("/ui/config")
async def workspace_config() -> dict[str, Any]:
    semantic = os.getenv("ELASTICSEARCH_SEMANTIC_ENABLED", "false").strip().lower() in {
        "true", "1", "yes", "on"
    }
    return {
        "semantic_enabled": semantic,
        "index_name": os.getenv("ELASTICSEARCH_INDEX") or (
            "knowledge-documents-hybrid" if semantic else "knowledge-documents"
        ),
    }
