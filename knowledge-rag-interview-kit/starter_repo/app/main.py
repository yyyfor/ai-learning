import json
import logging
import os
import time
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer
from fastapi.staticfiles import StaticFiles

from app.api import router
from app.api.errors import document_not_found_handler
from app.api.workspace import STATIC_DIR
from app.cache import RedisSearchCache
from app.repositories.documents import PostgresDocumentRepository
from app.retrieval.chunk_index import ElasticsearchChunkIndex
from app.retrieval.elasticsearch_index import ElasticsearchSearchIndex
from app.retrieval.query_rewrite import OllamaQueryRewriter
from app.retrieval.rerank import build_reranker
from app.services.hybrid import HybridRetrievalService
from app.services.knowledge import DocumentNotFoundError, KnowledgeService
from app.services.rag import RagService
from app.retrieval.local_models import OllamaModels
from app.retrieval.qdrant_index import QdrantIndex
from app.repositories.platform import PlatformRepository
from app.services.governance import GovernanceService
from app.security import authenticate, enabled, principal, require_role
from app.observability import current_trace, new_trace, traces
from app.agent.runtime import AgentRuntime


class JsonFormatter(logging.Formatter):
    """Write one small JSON object per log line."""

    def format(self, record: logging.LogRecord) -> str:
        return json.dumps(
            {
                "level": record.levelname,
                "message": record.getMessage(),
                "logger": record.name,
            },
            ensure_ascii=False,
        )


def configure_logging() -> None:
    # Uvicorn's default access log includes the raw query string. Our middleware
    # logs route templates + trace IDs instead, keeping search text out of logs.
    logging.getLogger("uvicorn.access").disabled = True
    logger = logging.getLogger("knowledge_api")
    if logger.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


configure_logging()
logger = logging.getLogger("knowledge_api")


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Connect to the three Docker services once when the API starts."""

    repository = PostgresDocumentRepository(
        os.getenv(
            "DATABASE_URL",
            "postgresql://rag:rag@localhost:5432/knowledge",
        )
    )
    search_index = ElasticsearchSearchIndex(
        url=os.getenv("ELASTICSEARCH_URL", "http://localhost:9200"),
        index_name=os.getenv("ELASTICSEARCH_INDEX"),
        semantic_enabled=os.getenv(
            "ELASTICSEARCH_SEMANTIC_ENABLED", "false"
        ).strip().lower() in {"true", "1", "yes", "on"},
        inference_id=os.getenv(
            "ELASTICSEARCH_SEMANTIC_INFERENCE_ID",
            ".elser-2-elasticsearch",
        ),
    )
    cache = RedisSearchCache(
        url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        ttl_seconds=30,
    )

    models = None
    vector_index = None
    chunk_index = None
    graph_service = None
    try:
        await repository.connect()
        await cache.connect()
        await search_index.connect()
        await search_index.ensure_index()

        service = KnowledgeService(repository, search_index, cache)
        store = PlatformRepository(repository._pool())
        await store.initialize()
        governance_service = GovernanceService(store, repository)
        service.governance = governance_service
        application.state.platform_store = store
        application.state.governance = governance_service
        await service.initialize()
        await cache.clear()
        application.state.knowledge_service = service
        if os.getenv("RAG_ENABLED", "false").strip().lower() in {"true", "1", "yes", "on"}:
            models = OllamaModels(
                os.getenv("OLLAMA_URL", "http://localhost:11434"),
                os.getenv("OLLAMA_EMBEDDING_MODEL", "embeddinggemma"),
                os.getenv("OLLAMA_CHAT_MODEL", "llama3:latest"),
            )
            vector_index = QdrantIndex(
                os.getenv("QDRANT_URL", "http://localhost:6333"), models.embedding_model
            )
            # Week 4: lexical candidates over chunks, in the free Elasticsearch
            # tier. No semantic_text, no inference, no licensed retriever; the
            # fusion and reranking happen in app/services/hybrid.py.
            chunk_index = ElasticsearchChunkIndex(
                os.getenv("ELASTICSEARCH_URL", "http://localhost:9200"),
                os.getenv("ELASTICSEARCH_CHUNK_INDEX", "knowledge-chunks"),
            )
            await chunk_index.connect()
            await chunk_index.ensure_index()
            hybrid = HybridRetrievalService(
                chunk_index,
                vector_index,
                models,
                reranker=build_reranker(os.getenv("RERANKER", "ollama"), models),
                rewriter=OllamaQueryRewriter(models),
                rrf_k=int(os.getenv("RRF_K", "60")),
            )
            application.state.rag_service = RagService(
                service, models, vector_index, hybrid, chunk_index
            )
            application.state.rag_service.governance = governance_service
            application.state.agent = AgentRuntime(store, application.state.rag_service)
            if enabled("GRAPH_ENABLED"):
                from app.services.graph import GraphService
                graph_service = GraphService(governance_service, application.state.rag_service)
                application.state.graph = graph_service
            service.vector_index = vector_index
            service.chunk_index = chunk_index
        logger.info("knowledge_api_started")
        yield
    finally:
        application.state.rag_service = None
        application.state.agent = None
        application.state.graph = None
        if graph_service is not None:
            await graph_service.close()
        if models is not None:
            await models.close()
        if vector_index is not None:
            await vector_index.close()
        if chunk_index is not None:
            await chunk_index.close()
        await cache.close()
        await search_index.close()
        await repository.close()
        logger.info("knowledge_api_stopped")


app = FastAPI(
    title="Enterprise Knowledge & RAG Studio",
    version="0.1.0",
    description="Knowledge API, hybrid/graph RAG, governance, evaluation and local agents",
    lifespan=lifespan,
    dependencies=[Depends(HTTPBearer(auto_error=False))],
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.include_router(router)
app.add_exception_handler(DocumentNotFoundError, document_not_found_handler)


@app.middleware("http")
async def log_request(request: Request, call_next):
    started = time.perf_counter()
    trace = new_trace()
    trace_token = current_trace.set(trace)
    identity_token = None
    status = 500
    try:
        path = request.url.path
        public = path in {"/", "/docs", "/openapi.json", "/redoc", "/health"} or path.startswith("/static/")
        if not public:
            identity_token = principal.set(authenticate(request.headers.get("authorization", "")))
            if path.startswith(("/inspector/", "/observability/")):
                require_role("admin")
            if enabled("SECURITY_ENABLED") and path.startswith("/inspector/"):
                raise HTTPException(403, "Raw inspectors are disabled in security mode; use ACL-filtered document APIs")
            readonly_posts = {"/search", "/query", "/rag/query", "/rag/hybrid", "/rag/chunks/preview",
                              "/graph/query", "/graph/compare", "/governance/citations/validate",
                              "/agent/runs", "/evaluation/run"}
            if request.method not in {"GET", "HEAD", "OPTIONS"} and path not in readonly_posts:
                require_role("admin", "editor", "approver")
                if path.startswith(("/documents", "/rag/pdf", "/rag/documents", "/graph/documents")):
                    require_role("admin", "editor")
        response = await call_next(request)
        status = response.status_code
        response.headers["X-Trace-ID"] = trace["id"]
        return response
    except HTTPException as exc:
        status = exc.status_code
        return JSONResponse({"detail": exc.detail}, status_code=status, headers={"X-Trace-ID": trace["id"]})
    finally:
        route = request.scope.get("route")
        trace.update({"route": getattr(route, "path", "unmatched"), "method": request.method,
                      "status": status, "latency_ms": round((time.perf_counter()-started)*1000, 2)})
        if not request.url.path.startswith(("/static/", "/observability/")):
            traces.append(trace)
        logger.info("request_complete trace=%s route=%s status=%s", trace["id"], trace["route"], status)
        current_trace.reset(trace_token)
        if identity_token is not None:
            principal.reset(identity_token)
