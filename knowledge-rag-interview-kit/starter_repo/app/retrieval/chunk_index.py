"""BM25 over chunks, using only free-tier Elasticsearch.

Week 2 indexes whole documents, which is the right unit for `/search` but the
wrong unit for RAG: the lexical candidate set has to line up with the dense one
so that fusion has a shared key, and citations need the page a chunk came from.

Deliberately absent: `semantic_text`, `inference_id`, and the `retriever` block
with `rrf`/`text_similarity_reranker`. Those are licensed Elastic features. This
index is a plain `text` field with BM25 similarity, which every tier includes;
fusion and reranking happen in the application layer instead.
"""
from __future__ import annotations

from typing import Any, Iterable

from elasticsearch import AsyncElasticsearch

from app.domain.retrieval import ChunkRecord, RetrievalFilters
from app.retrieval.elasticsearch_index import flattened_value


class ElasticsearchChunkIndex:
    """Chunk-level lexical candidate generator."""

    def __init__(self, url: str, index_name: str = "knowledge-chunks") -> None:
        self.url = url
        self.index_name = index_name
        self.client: AsyncElasticsearch | None = None

    async def connect(self) -> None:
        self.client = AsyncElasticsearch(self.url)
        await self._client().info()

    async def ensure_index(self) -> None:
        client = self._client()
        if await client.indices.exists(index=self.index_name):
            return
        await client.indices.create(
            index=self.index_name,
            settings={
                "analysis": {
                    "analyzer": {
                        # Keep stopwords: exact policy phrases and IDs matter more
                        # here than recall on common words.
                        "knowledge_text": {"type": "standard", "stopwords": "_none_"}
                    }
                },
                "similarity": {"default": {"type": "BM25", "k1": 1.2, "b": 0.75}},
            },
            mappings={
                "properties": {
                    "chunk_id": {"type": "keyword"},
                    "document_id": {"type": "keyword"},
                    "title": {"type": "text", "analyzer": "knowledge_text"},
                    "text": {"type": "text", "analyzer": "knowledge_text"},
                    "source": {"type": "keyword"},
                    "tags": {"type": "keyword"},
                    "metadata": {"type": "flattened"},
                    "page": {"type": "integer"},
                    "position": {"type": "integer"},
                    "created_at": {"type": "date"},
                }
            },
        )

    async def replace(self, document_id: str, records: Iterable[ChunkRecord]) -> int:
        """Delete this document's chunks, then write the new ones.

        Same ordering as the vector store: remove first, then insert, so a retry
        of a failed index request repairs a partial write instead of doubling it.
        """
        await self.remove(document_id)
        operations: list[dict[str, Any]] = []
        count = 0
        for record in records:
            operations.append({"index": {"_index": self.index_name, "_id": record.id}})
            operations.append(record.as_payload())
            count += 1
        if not operations:
            return 0
        response = await self._client().bulk(operations=operations, refresh="wait_for")
        if response.get("errors"):
            first = next(
                (item["index"]["error"] for item in response["items"]
                 if item.get("index", {}).get("error")),
                "unknown error",
            )
            raise RuntimeError(f"chunk index write failed: {first}")
        return count

    async def remove(self, document_id: str) -> None:
        try:
            await self._client().delete_by_query(
                index=self.index_name,
                query={"term": {"document_id": document_id}},
                refresh=True,
                conflicts="proceed",
            )
        except Exception as exc:
            if getattr(exc, "status_code", None) != 404:
                raise

    async def search(
        self,
        query: str,
        filters: RetrievalFilters,
        limit: int,
    ) -> list[dict[str, Any]]:
        """Return BM25 candidates as payload dicts with a `_score`."""
        try:
            response = await self._client().search(
                index=self.index_name,
                size=limit,
                query={
                    "bool": {
                        "must": [
                            {
                                "multi_match": {
                                    "query": query,
                                    # The chunk's own text carries the evidence;
                                    # the title only disambiguates between documents.
                                    "fields": ["text", "title^0.5"],
                                }
                            }
                        ],
                        "filter": build_filters(filters),
                    }
                },
            )
        except Exception as exc:
            # An index that was never created is an empty candidate set, not an
            # outage: documents indexed before Week 4 simply have no chunks here.
            if getattr(exc, "status_code", None) == 404:
                return []
            raise
        hits = []
        for hit in response["hits"]["hits"]:
            payload = dict(hit["_source"])
            payload["chunk_id"] = payload.get("chunk_id") or hit["_id"]
            payload["_score"] = float(hit.get("_score") or 0.0)
            hits.append(payload)
        return hits

    async def count(self) -> int:
        try:
            response = await self._client().count(index=self.index_name)
        except Exception as exc:
            if getattr(exc, "status_code", None) == 404:
                return 0
            raise
        return int(response["count"])

    async def health(self) -> bool:
        return bool((await self._client().info()).meta.status == 200)

    async def close(self) -> None:
        if self.client is not None:
            await self.client.close()
            self.client = None

    def _client(self) -> AsyncElasticsearch:
        if self.client is None:
            raise RuntimeError("Elasticsearch chunk index is not connected")
        return self.client


def build_filters(filters: RetrievalFilters) -> list[dict[str, Any]]:
    """Translate shared filters into Elasticsearch filter clauses."""
    clauses: list[dict[str, Any]] = []
    if filters.source:
        clauses.append({"term": {"source": filters.source}})
    # One clause per tag: all requested tags must be present.
    clauses.extend({"term": {"tags": tag}} for tag in filters.tags)
    for key, value in filters.metadata.items():
        clauses.append({"term": {f"metadata.{key}": flattened_value(value)}})
    return clauses
