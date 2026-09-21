import asyncio

from app.domain.documents import StoredDocument
from app.domain.retrieval import RetrievedChunk
from app.dto.rag import ChunkOptions, RagQueryRequest
from app.services.hybrid import HybridResult
from app.services.rag import RagService, build_record


def run(coroutine):
    return asyncio.run(coroutine)


DOCUMENT = StoredDocument(
    id="doc-1", title="Leave policy", content="Annual leave is 20 days.",
    source="pdf", tags=["hr"], metadata={"team": "people"},
    created_at="2026-01-01T00:00:00+00:00",
)


class FakeRepository:
    def __init__(self, documents):
        self.documents = documents

    async def get(self, document_id):
        return self.documents.get(document_id)


class FakeKnowledge:
    def __init__(self, documents=(DOCUMENT,)):
        self.repository = FakeRepository({doc.id: doc for doc in documents})

    async def get_document(self, document_id):
        return self.repository.documents[document_id]


class FakeVectorIndex:
    def __init__(self):
        self.points = None
        self.dimensions = None

    async def ensure(self, dimensions):
        self.dimensions = dimensions

    async def replace(self, document_id, points):
        self.points = points


class FakeChunkIndex:
    def __init__(self):
        self.records = None

    async def replace(self, document_id, records):
        self.records = list(records)
        return len(self.records)


class FakeModels:
    chat_model = "fake-chat"

    def __init__(self):
        self.answered = []

    async def embed(self, texts):
        return [[1.0, 0.0] for _ in texts]

    async def answer(self, question, context):
        self.answered.append((question, context))
        return "An answer [1]."


class FakeHybrid:
    def __init__(self, hits):
        self.hits = hits
        self.requests = []

    async def retrieve(self, request):
        self.requests.append(request)
        return HybridResult(query=request.query, mode=request.mode,
                            variants=[request.query], hits=list(self.hits),
                            candidates=len(self.hits))


def hit(chunk_id, document_id, text="evidence"):
    return RetrievedChunk(id=chunk_id, document_id=document_id, title="Leave policy",
                          source="pdf", page=2, text=text, fused_score=0.03,
                          retrievers=["bm25", "vector"])


def test_chunk_ids_are_stable_across_reindexing():
    class Chunk:
        text, page, position = "body", 1, 3

    first = build_record(DOCUMENT, Chunk())
    second = build_record(DOCUMENT, Chunk())
    assert first.id == second.id
    assert first.metadata == {"team": "people"}


def test_indexing_writes_the_same_ids_to_both_stores():
    vector, lexical = FakeVectorIndex(), FakeChunkIndex()
    service = RagService(FakeKnowledge(), FakeModels(), vector, chunk_index=lexical)
    result = run(service.index_document("doc-1", ChunkOptions()))
    vector_ids = [point["id"] for point in vector.points]
    lexical_ids = [record.id for record in lexical.records]
    # Fusion joins the two candidate sets on this id: they must not diverge.
    assert vector_ids == lexical_ids
    assert result["chunks"] == len(vector_ids) == result["lexical_chunks"]


def test_indexing_still_works_without_the_lexical_index():
    service = RagService(FakeKnowledge(), FakeModels(), FakeVectorIndex())
    assert run(service.index_document("doc-1", ChunkOptions()))["lexical_chunks"] == 0


def test_citations_are_numbered_and_carry_provenance():
    models = FakeModels()
    service = RagService(FakeKnowledge(), models, FakeVectorIndex(),
                         hybrid=FakeHybrid([hit("c1", "doc-1"), hit("c2", "doc-1")]))
    response = run(service.query(RagQueryRequest(query="How much leave?")))
    assert [citation["number"] for citation in response["citations"]] == [1, 2]
    assert response["citations"][0]["retrievers"] == ["bm25", "vector"]
    assert "[1] Leave policy (page 2)" in response["context"]
    assert models.answered


def test_evidence_from_a_deleted_document_never_reaches_the_model():
    # PostgreSQL stays authoritative: stale vectors must not answer questions.
    models = FakeModels()
    service = RagService(FakeKnowledge(), models, FakeVectorIndex(),
                         hybrid=FakeHybrid([hit("c9", "deleted-doc"), hit("c1", "doc-1")]))
    response = run(service.query(RagQueryRequest(query="How much leave?")))
    assert [citation["chunk_id"] for citation in response["citations"]] == ["c1"]


def test_no_surviving_evidence_means_no_model_call():
    models = FakeModels()
    service = RagService(FakeKnowledge(), models, FakeVectorIndex(),
                         hybrid=FakeHybrid([hit("c9", "deleted-doc")]))
    response = run(service.query(RagQueryRequest(query="How much leave?")))
    assert response["citations"] == []
    assert models.answered == []
    assert "could not find" in response["answer"]


def test_request_options_reach_the_retrieval_layer():
    hybrid = FakeHybrid([])
    service = RagService(FakeKnowledge(), FakeModels(), FakeVectorIndex(), hybrid=hybrid)
    run(service.query(RagQueryRequest(
        query="q", mode="bm25", top_k=3, candidate_k=11, source="pdf",
        tags=["hr"], metadata={"team": "people"}, rerank=True, rewrite=True)))
    request = hybrid.requests[0]
    assert (request.mode, request.top_k, request.candidate_k) == ("bm25", 3, 11)
    assert request.filters.source == "pdf" and request.filters.tags == ["hr"]
    assert request.filters.metadata == {"team": "people"}
    assert request.rerank and request.rewrite
