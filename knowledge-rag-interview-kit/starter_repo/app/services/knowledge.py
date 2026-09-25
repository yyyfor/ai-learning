import json
from typing import Any, Protocol
from uuid import uuid4

from app.cache import RedisSearchCache
from app.repositories.documents import (
    DocumentRepository,
    now_utc_iso,
)
from app.domain.documents import StoredDocument
from app.domain.search import SearchHit, SearchPage
from app.dto.documents import DocumentCreate
from app.security import enabled, principal


class DocumentNotFoundError(Exception):
    pass


class SearchIndex(Protocol):
    async def inspect(self, page: int, page_size: int) -> dict[str, Any]: ...

    async def add(self, document: StoredDocument) -> None: ...

    async def remove(self, document_id: str) -> None: ...

    async def rebuild(self, documents: list[StoredDocument]) -> None: ...

    async def search(
        self,
        query: str,
        source: str | None,
        tags: list[str],
        metadata: dict[str, Any],
        limit: int,
        offset: int,
    ) -> tuple[list[dict[str, Any]], int]: ...

    async def health(self) -> bool: ...


class KnowledgeService:
    """Coordinates PostgreSQL, Elasticsearch and Redis."""

    def __init__(
        self,
        repository: DocumentRepository,
        search_index: SearchIndex,
        cache: RedisSearchCache,
    ) -> None:
        self.repository = repository
        self.search_index = search_index
        self.cache = cache
        self.vector_index = None
        self.chunk_index = None
        self.governance = None

    async def initialize(self) -> None:
        # This makes an existing PostgreSQL dataset searchable after a fresh
        # Elasticsearch index is created or cleared.
        await self.search_index.rebuild(await self.repository.all())

    async def create_document(self, payload: DocumentCreate) -> StoredDocument:
        if enabled("SECURITY_ENABLED"):
            payload.metadata["tenant"] = principal.get().tenant
        document = StoredDocument(
            id=str(uuid4()),
            title=payload.title,
            content=payload.content,
            source=payload.source,
            tags=payload.tags,
            metadata=payload.metadata,
            created_at=now_utc_iso(),
        )
        await self.repository.create(document)
        try:
            await self.search_index.add(document)
        except Exception:
            # Keep metadata and search index aligned for this simple demo.
            await self.repository.delete(document.id)
            raise
        await self.cache.clear()
        return document

    async def list_documents(self, page: int, page_size: int) -> list[StoredDocument]:
        if self.governance is not None and enabled("SECURITY_ENABLED"):
            allowed = set(await self.governance.allowed_ids(published=False))
            docs = [d for d in reversed(await self.repository.all()) if d.id in allowed]
            return docs[(page-1)*page_size:page*page_size]
        return await self.repository.list(
            limit=page_size,
            offset=(page - 1) * page_size,
        )

    async def get_document(self, document_id: str) -> StoredDocument:
        if self.governance is not None and enabled("SECURITY_ENABLED"):
            return await self.governance.document(document_id)
        document = await self.repository.get(document_id)
        if document is None:
            raise DocumentNotFoundError(document_id)
        return document

    async def delete_document(self, document_id: str) -> None:
        await self.get_document(document_id)
        if self.vector_index is not None:
            await self.vector_index.remove(document_id)
        if self.chunk_index is not None:
            await self.chunk_index.remove(document_id)
        if not await self.repository.delete(document_id):
            raise DocumentNotFoundError(document_id)
        await self.search_index.remove(document_id)
        await self.cache.clear()

    async def search_documents(
        self,
        query: str,
        source: str | None,
        tags: list[str],
        metadata: dict[str, Any],
        page: int,
        page_size: int,
    ) -> SearchPage:
        allowed = None
        if self.governance is not None and (enabled("SECURITY_ENABLED") or enabled("GOVERNANCE_ENABLED")):
            allowed = await self.governance.allowed_ids()
        cache_key = json.dumps(
            {
                "query": query,
                "source": source,
                "tags": sorted(tags),
                "metadata": metadata,
                "page": page,
                "page_size": page_size,
                "allowed_ids": sorted(allowed) if allowed is not None else None,
            },
            sort_keys=True,
            ensure_ascii=False,
        )
        cached = await self.cache.get(cache_key)
        if cached is not None:
            return SearchPage.from_dict(cached)

        access = {"document_ids": allowed} if allowed is not None else {}
        raw_results, total = await self.search_index.search(
            query=query,
            source=source,
            tags=tags,
            metadata=metadata,
            limit=page_size,
            offset=(page - 1) * page_size,
            **access,
        )
        page_result = SearchPage(
            query=query,
            results=[
                SearchHit(
                    document=result["document"],
                    score=float(result["score"]),
                )
                for result in raw_results
            ],
            total=total,
            page=page,
            page_size=page_size,
        )
        await self.cache.set(cache_key, page_result.as_dict())
        return page_result

    async def query_documents(
        self,
        query: str,
        source: str | None,
        tags: list[str],
        metadata: dict[str, Any],
        page: int,
        page_size: int,
    ) -> dict[str, Any]:
        page_result = await self.search_documents(
            query=query,
            source=source,
            tags=tags,
            metadata=metadata,
            page=page,
            page_size=page_size,
        )
        context_parts = []
        citations = []
        for number, hit in enumerate(page_result.results, start=1):
            context_parts.append(f"[{number}] {hit.document.title}\n{hit.document.content}")
            citations.append(
                {
                    "document_id": hit.document.id,
                    "title": hit.document.title,
                    "source": hit.document.source,
                }
            )
        return {
            **page_result.as_dict(),
            "context": "\n\n".join(context_parts),
            "citations": citations,
        }

    async def health(self) -> dict[str, str]:
        storage_ok = await self._safe_health_check(self.repository.health)
        search_ok = await self._safe_health_check(self.search_index.health)
        cache_ok = await self._safe_health_check(self.cache.health)
        all_ok = storage_ok and search_ok and cache_ok
        return {
            "status": "ok" if all_ok else "degraded",
            "storage": "ok" if storage_ok else "error",
            "search": "ok" if search_ok else "error",
            "cache": "ok" if cache_ok else "error",
        }

    @staticmethod
    async def _safe_health_check(check) -> bool:
        try:
            return bool(await check())
        except Exception:
            return False
