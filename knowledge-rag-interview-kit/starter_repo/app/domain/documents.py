from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class StoredDocument:
    id: str
    title: str
    content: str
    source: str
    tags: list[str]
    metadata: dict[str, Any]
    created_at: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)
