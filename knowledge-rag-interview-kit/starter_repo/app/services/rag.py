from dataclasses import asdict
from uuid import NAMESPACE_URL, uuid5

from app.dto.rag import ChunkOptions, RagQueryRequest
from app.ingestion.chunking import chunk_pages


class RagService:
    def __init__(self, knowledge, models, index):
        self.knowledge = knowledge
        self.models = models
        self.index = index

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
        vectors = await self.models.embed([chunk.text for chunk in chunks])
        await self.index.ensure(len(vectors[0]))
        points = [{
            "id": str(uuid5(NAMESPACE_URL, f"{document.id}:{chunk.position}")),
            "vector": vector,
            "payload": {
                **asdict(chunk), "document_id": document.id,
                "title": document.title, "source": document.source,
                "tags": document.tags,
            },
        } for chunk, vector in zip(chunks, vectors)]
        await self.index.replace(document.id, points)
        return {"document": document.as_dict(), "chunks": len(chunks)}

    async def query(self, request: RagQueryRequest):
        vector = (await self.models.embed([request.query]))[0]
        hits = await self.index.query(vector, request.top_k, request.source,
                                      request.tags, request.score_threshold)
        citations, parts = [], []
        remaining = 6000  # Characters, not tokens: simple visible context budget.
        for hit in hits:
            data = hit["payload"]
            # PostgreSQL is authoritative: never answer from deleted documents.
            if await self.knowledge.repository.get(data["document_id"]) is None:
                continue
            number = len(citations) + 1
            header = f"[{number}] {data['title']} (page {data['page']})\n"
            room = remaining - len(header) - 2
            if room <= 0:
                break
            text = data["text"][:room]
            part = header + text
            remaining -= len(part) + 2
            parts.append(part)
            citations.append({
                "number": number, "document_id": data["document_id"],
                "chunk_id": str(hit["id"]), "title": data["title"],
                "source": data["source"], "page": data["page"],
                "text": text, "score": hit["score"],
            })
        context = "\n\n".join(parts)
        answer = (await self.models.answer(request.query, context) if citations
                  else "I could not find supporting evidence in the indexed documents.")
        return {"query": request.query, "answer": answer, "context": context,
                "citations": citations, "model": self.models.chat_model}
