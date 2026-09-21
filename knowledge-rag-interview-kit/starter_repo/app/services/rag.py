from dataclasses import asdict
from uuid import NAMESPACE_URL, uuid5

from app.domain.retrieval import ChunkRecord, RetrievalFilters
from app.dto.rag import ChunkOptions, RagQueryRequest
from app.ingestion.chunking import chunk_pages
from app.services.hybrid import HybridRequest, HybridResult

CONTEXT_BUDGET_CHARACTERS = 6000


class RagService:
    def __init__(self, knowledge, models, index, hybrid=None, chunk_index=None):
        self.knowledge = knowledge
        self.models = models
        self.index = index
        self.hybrid = hybrid
        self.chunk_index = chunk_index

    async def preview(self, text: str, options: ChunkOptions):
        return [asdict(chunk) for chunk in await chunk_pages(
            [(1, text)], options, self.models.embed)]

    async def index_document(self, document_id: str, options: ChunkOptions):
        document = await self.knowledge.get_document(document_id)
        # Form feeds retain original PDF page numbering, including empty pages.
        pages = list(enumerate(document.content.split("\f"), 1))
        chunks = await chunk_pages(pages, options, self.models.embed)
        if not chunks:
            raise ValueError("Document has no text to index")
        records = [build_record(document, chunk) for chunk in chunks]
        vectors = await self.models.embed([record.text for record in records])
        await self.index.ensure(len(vectors[0]))
        points = [
            {"id": record.id, "vector": vector, "payload": record.as_payload()}
            for record, vector in zip(records, vectors)
        ]
        await self.index.replace(document.id, points)
        lexical = 0
        if self.chunk_index is not None:
            # The same chunk ids go to both stores: fusion needs one shared key.
            # Written after the vectors so a failure here leaves the Week 3 path
            # working, and a retry repairs the lexical side.
            lexical = await self.chunk_index.replace(document.id, records)
        return {
            "document": document.as_dict(),
            "chunks": len(records),
            "lexical_chunks": lexical,
        }

    async def retrieve(self, request) -> HybridResult:
        """Retrieval only: the same pipeline /rag/query answers from."""
        result = await self.hybrid.retrieve(HybridRequest(
            query=request.query,
            mode=request.mode,
            top_k=request.top_k,
            candidate_k=request.candidate_k,
            filters=RetrievalFilters(
                source=request.source,
                tags=list(request.tags),
                metadata=dict(request.metadata),
            ),
            score_threshold=request.score_threshold,
            rerank=request.rerank,
            rewrite=request.rewrite,
        ))
        result.hits = await self._live_hits(result.hits)
        return result

    async def query(self, request: RagQueryRequest):
        result = await self.retrieve(request)
        citations, parts = [], []
        remaining = CONTEXT_BUDGET_CHARACTERS  # Characters, not tokens.
        for hit in result.hits:
            number = len(citations) + 1
            header = f"[{number}] {hit.title} (page {hit.page})\n"
            room = remaining - len(header) - 2
            if room <= 0:
                break
            text = hit.text[:room]
            part = header + text
            remaining -= len(part) + 2
            parts.append(part)
            citation = hit.as_dict(result.mode)
            citation["number"] = number
            citation["text"] = text
            citations.append(citation)
        context = "\n\n".join(parts)
        answer = (await self.models.answer(request.query, context) if citations
                  else "I could not find supporting evidence in the indexed documents.")
        return {
            "query": request.query, "answer": answer, "context": context,
            "citations": citations, "model": self.models.chat_model,
            "mode": result.mode, "variants": result.variants,
            "reranked": result.reranked, "warnings": result.warnings,
            "timings_ms": {k: round(v, 1) for k, v in result.timings_ms.items()},
        }

    async def _live_hits(self, hits):
        """PostgreSQL is authoritative: never answer from deleted documents."""
        live = []
        for hit in hits:
            if await self.knowledge.repository.get(hit.document_id) is None:
                continue
            live.append(hit)
        return live


def build_record(document, chunk) -> ChunkRecord:
    """Stable chunk identity, shared by the vector store and the BM25 index."""
    return ChunkRecord(
        id=str(uuid5(NAMESPACE_URL, f"{document.id}:{chunk.position}")),
        document_id=document.id,
        title=document.title,
        source=document.source,
        tags=list(document.tags),
        metadata=dict(document.metadata),
        text=chunk.text,
        page=chunk.page,
        position=chunk.position,
        created_at=document.created_at,
    )
