from dataclasses import dataclass


@dataclass(frozen=True)
class Chunk:
    text: str
    page: int
    position: int
