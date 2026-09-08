from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Protocol

import asyncpg

from app.domain.documents import StoredDocument


class DocumentRepository(Protocol):
    async def create(self, document: StoredDocument) -> StoredDocument: ...

    async def get(self, document_id: str) -> StoredDocument | None: ...

    async def list(self, limit: int, offset: int) -> list[StoredDocument]: ...

    async def all(self) -> list[StoredDocument]: ...

    async def delete(self, document_id: str) -> bool: ...

    async def health(self) -> bool: ...


class PostgresDocumentRepository:
    """PostgreSQL metadata store used by the API."""

    def __init__(self, dsn: str) -> None:
        self.dsn = dsn
        self.pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        self.pool = await asyncpg.create_pool(
            self.dsn,
            min_size=1,
            max_size=5,
        )
        async with self.pool.acquire() as connection:
            await connection.execute(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    source TEXT NOT NULL,
                    tags TEXT[] NOT NULL DEFAULT '{}',
                    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
                    created_at TIMESTAMPTZ NOT NULL
                )
                """
            )

    async def create(self, document: StoredDocument) -> StoredDocument:
        pool = self._pool()
        await pool.execute(
            """
            INSERT INTO documents
                (id, title, content, source, tags, metadata, created_at)
            VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7::timestamptz)
            """,
            document.id,
            document.title,
            document.content,
            document.source,
            document.tags,
            json.dumps(document.metadata, ensure_ascii=False),
            datetime.fromisoformat(document.created_at),
        )
        return document

    async def get(self, document_id: str) -> StoredDocument | None:
        row = await self._pool().fetchrow(
            self._select_sql("WHERE id = $1"), document_id
        )
        return self._from_row(row) if row else None

    async def list(self, limit: int, offset: int) -> list[StoredDocument]:
        rows = await self._pool().fetch(
            self._select_sql("ORDER BY created_at DESC LIMIT $1 OFFSET $2"),
            limit,
            offset,
        )
        return [self._from_row(row) for row in rows]

    async def all(self) -> list[StoredDocument]:
        rows = await self._pool().fetch(self._select_sql("ORDER BY created_at ASC"))
        return [self._from_row(row) for row in rows]

    async def delete(self, document_id: str) -> bool:
        result = await self._pool().execute(
            "DELETE FROM documents WHERE id = $1", document_id
        )
        return result.endswith("1")

    async def health(self) -> bool:
        await self._pool().fetchval("SELECT 1")
        return True

    async def close(self) -> None:
        if self.pool is not None:
            await self.pool.close()
            self.pool = None

    def _pool(self) -> asyncpg.Pool:
        if self.pool is None:
            raise RuntimeError("PostgreSQL repository is not connected")
        return self.pool

    @staticmethod
    def _select_sql(suffix: str) -> str:
        return f"""
            SELECT id, title, content, source, tags,
                   metadata::text AS metadata_json, created_at
            FROM documents
            {suffix}
        """

    @staticmethod
    def _from_row(row: asyncpg.Record) -> StoredDocument:
        return StoredDocument(
            id=row["id"],
            title=row["title"],
            content=row["content"],
            source=row["source"],
            tags=list(row["tags"]),
            metadata=json.loads(row["metadata_json"]),
            created_at=row["created_at"].isoformat(),
        )


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
