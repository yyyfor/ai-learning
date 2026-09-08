from dataclasses import dataclass
from typing import Any

from app.domain.documents import StoredDocument


@dataclass(frozen=True)
class SearchHit:
    document: StoredDocument
    score: float


@dataclass(frozen=True)
class SearchPage:
    query: str
    results: list[SearchHit]
    total: int
    page: int
    page_size: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "results": [
                {
                    "document": hit.document.as_dict(),
                    "score": round(hit.score, 6),
                }
                for hit in self.results
            ],
            "total": self.total,
            "page": self.page,
            "page_size": self.page_size,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "SearchPage":
        return cls(
            query=value["query"],
            results=[
                SearchHit(
                    document=StoredDocument(**result["document"]),
                    score=float(result["score"]),
                )
                for result in value["results"]
            ],
            total=int(value["total"]),
            page=int(value["page"]),
            page_size=int(value["page_size"]),
        )
