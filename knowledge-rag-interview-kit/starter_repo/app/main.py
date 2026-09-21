import json
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
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
    try:
        await repository.connect()
        await cache.connect()
        await search_index.connect()
        await search_index.ensure_index()

        service = KnowledgeService(repository, search_index, cache)
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
            service.vector_index = vector_index
            service.chunk_index = chunk_index
        logger.info("knowledge_api_started")
        yield
    finally:
        application.state.rag_service = None
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
    description="Week 1–3 Knowledge Platform API with optional local Vector RAG",
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.include_router(router)
app.add_exception_handler(DocumentNotFoundError, document_not_found_handler)


@app.middleware("http")
async def log_request(request: Request, call_next):
    response = await call_next(request)
    logger.info(
        "request_complete method=%s path=%s status=%s",
        request.method,
        request.url.path,
        response.status_code,
    )
    return response
