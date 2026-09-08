import math
import re
from collections.abc import Awaitable, Callable

from app.domain.chunks import Chunk
from app.dto.rag import ChunkOptions


def recursive_split(text: str, size: int, level: int = 0) -> list[str]:
    """Split paragraphs, then lines, then sentences/words, then characters."""
    if len(text) <= size:
        return [text] if text.strip() else []
    separators = ("\n\n", "\n", ". ", "。", " ")
    for depth in range(level, len(separators)):
        separator = separators[depth]
        if separator in text:
            parts = text.split(separator)
            pieces = []
            for index, part in enumerate(parts):
                pieces.extend(recursive_split(
                    part + (separator if index < len(parts) - 1 else ""), size, depth + 1
                ))
            # A separator at the end can otherwise recur without making progress.
            if all(len(piece) <= size for piece in pieces):
                return pieces
    return [text[i:i + size] for i in range(0, len(text), size)]


def cosine(left: list[float], right: list[float]) -> float:
    denominator = math.sqrt(sum(x*x for x in left) * sum(x*x for x in right))
    return sum(a*b for a, b in zip(left, right)) / denominator if denominator else 0


async def chunk_pages(
    pages: list[tuple[int, str]],
    options: ChunkOptions,
    embed: Callable[[list[str]], Awaitable[list[list[float]]]],
) -> list[Chunk]:
    chunks = []
    for page, text in pages:
        # Reserve room for overlap so every chunk respects chunk_size.
        size = options.chunk_size - options.overlap
        if options.strategy == "semantic":
            sentences = re.split(r"(?<=[.!?。！？])\s*|\n\n+", text.strip())
            units = [piece for sentence in sentences
                     for piece in recursive_split(sentence, size) if piece.strip()]
            vectors = await embed(units) if units else []
        else:
            units = recursive_split(text, size)
            vectors = []
        groups, current = [], ""
        for index, unit in enumerate(units):
            boundary = bool(vectors and index and cosine(vectors[index-1], vectors[index])
                            < options.similarity_threshold)
            if current and (boundary or len(current) + len(unit) + 1 > size):
                groups.append(current.strip())
                current = ""
            current += (" " if current else "") + unit
        if current.strip():
            groups.append(current.strip())
        previous = ""
        for group in groups:
            prefix = previous[-options.overlap:] if options.overlap else ""
            # Prefix only within the same source page.
            content = (prefix + group).strip()
            chunks.append(Chunk(content, page, len(chunks)))
            previous = group
    return chunks
