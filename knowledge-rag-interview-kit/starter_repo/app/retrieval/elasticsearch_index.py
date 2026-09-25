from typing import Any, Iterable

from elasticsearch import AsyncElasticsearch

from app.domain.documents import StoredDocument


class ElasticsearchSearchIndex:
    """BM25 search with optional semantic_text hybrid search."""

    semantic_field = "semantic_text"

    def __init__(
        self,
        url: str,
        index_name: str | None = None,
        inference_id: str = ".elser-2-elasticsearch",
        semantic_enabled: bool = False,
    ) -> None:
        self.url = url
        self.semantic_enabled = semantic_enabled
        self.index_name = index_name or (
            "knowledge-documents-hybrid" if semantic_enabled else "knowledge-documents"
        )
        self.inference_id = inference_id
        self.client: AsyncElasticsearch | None = None

    async def connect(self) -> None:
        self.client = AsyncElasticsearch(self.url)
        await self._client().info()

    async def ensure_index(self) -> None:
        client = self._client()
        if await client.indices.exists(index=self.index_name):
            mapping = await client.indices.get_mapping(index=self.index_name)
            properties = mapping[self.index_name]["mappings"].get("properties", {})
            semantic_mapping = properties.get(self.semantic_field, {})
            has_semantic = semantic_mapping.get("type") == "semantic_text"
            if has_semantic != self.semantic_enabled:
                raise RuntimeError(
                    f"Elasticsearch index {self.index_name!r} does not match "
                    f"semantic_enabled={self.semantic_enabled}; unset "
                    "ELASTICSEARCH_INDEX to use the mode's default index, "
                    "or set it to a new index name"
                )
            return
        properties: dict[str, Any] = {
            "title": {"type": "text", "analyzer": "knowledge_text"},
            "content": {"type": "text", "analyzer": "knowledge_text"},
            "source": {"type": "keyword"},
            "tags": {"type": "keyword"},
            # User-defined metadata keys stay in one field.
            "metadata": {"type": "flattened"},
            "created_at": {"type": "date"},
        }
        if self.semantic_enabled:
            properties["content"]["copy_to"] = self.semantic_field
            properties[self.semantic_field] = {
                "type": "semantic_text",
                "inference_id": self.inference_id,
            }
        await client.indices.create(
            index=self.index_name,
            settings={
                "analysis": {
                    "analyzer": {
                        "knowledge_text": {
                            "type": "standard",
                            "stopwords": "_none_",
                        }
                    }
                },
                "similarity": {
                    "default": {"type": "BM25", "k1": 1.2, "b": 0.75}
                }
            },
            mappings={"properties": properties},
        )

    async def add(self, document: StoredDocument) -> None:
        await self._client().index(
            index=self.index_name,
            id=document.id,
            document=document.as_dict(),
            refresh="wait_for",
        )

    async def remove(self, document_id: str) -> None:
        try:
            await self._client().delete(
                index=self.index_name,
                id=document_id,
                refresh="wait_for",
            )
        except Exception as exc:
            # Deleting a document that is already absent is harmless.
            if getattr(exc, "status_code", None) != 404:
                raise

    async def rebuild(self, documents: Iterable[StoredDocument]) -> None:
        client = self._client()
        await client.delete_by_query(
            index=self.index_name,
            query={"match_all": {}},
            refresh=True,
            conflicts="proceed",
        )
        for document in documents:
            await self.add(document)

    async def search(
        self,
        query: str,
        source: str | None,
        tags: list[str],
        metadata: dict[str, Any],
        limit: int,
        offset: int,
        document_ids: list[str] | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        filters: list[dict[str, Any]] = []
        if document_ids is not None:
            filters.append({"ids": {"values": document_ids}})
        if source:
            filters.append({"term": {"source": source}})
        if tags:
            # One filter per tag means all requested tags must be present.
            filters.extend({"term": {"tags": tag}} for tag in tags)
        for key, value in metadata.items():
            # flattened stores metadata values as keyword-like strings.
            filters.append(
                {"term": {f"metadata.{key}": flattened_value(value)}}
            )

        lexical_query = {
            "multi_match": {
                "query": query,
                "fields": ["title^2", "content"],
            }
        }
        queries = [lexical_query]
        if self.semantic_enabled:
            queries.append({"match": {self.semantic_field: query}})

        response = await self._client().search(
            index=self.index_name,
            from_=offset,
            size=limit,
            track_total_hits=True,
            query={
                "bool": {
                    "should": queries,
                    "minimum_should_match": 1,
                    "filter": filters,
                }
            },
        )
        total = response["hits"]["total"]["value"]
        results = []
        for hit in response["hits"]["hits"]:
            source_data = dict(hit["_source"])
            source_data["id"] = hit["_id"]
            results.append(
                {
                    "document": StoredDocument(**source_data),
                    "score": float(hit.get("_score") or 0),
                }
            )
        return results, int(total)

    async def inspect(self, page: int, page_size: int) -> dict[str, Any]:
        """Inspect only the configured application index, without inference."""
        client = self._client()
        response = await client.search(
            index=self.index_name,
            query={"match_all": {}},
            sort=[{"created_at": "desc"}],
            from_=(page - 1) * page_size,
            size=page_size,
            track_total_hits=True,
        )
        mappings = await client.indices.get_mapping(index=self.index_name)
        return {
            "index_name": self.index_name,
            "semantic_enabled": self.semantic_enabled,
            "total": response["hits"]["total"]["value"],
            "page": page,
            "page_size": page_size,
            "documents": [
                {"id": hit["_id"], "source": hit["_source"]}
                for hit in response["hits"]["hits"]
            ],
            "mappings": dict(mappings),
        }

    async def health(self) -> bool:
        return bool((await self._client().info()).meta.status == 200)

    async def close(self) -> None:
        if self.client is not None:
            await self.client.close()
            self.client = None

    def _client(self) -> AsyncElasticsearch:
        if self.client is None:
            raise RuntimeError("Elasticsearch index is not connected")
        return self.client


def flattened_value(value: Any) -> str:
    """Turn simple JSON metadata values into flattened field values."""

    if isinstance(value, bool):
        return str(value).lower()
    return str(value)
