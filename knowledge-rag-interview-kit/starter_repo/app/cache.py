import json
import hashlib
from typing import Any

from redis.asyncio import Redis


class RedisSearchCache:
    """Redis cache for search responses with a short TTL."""

    PREFIX = "knowledge:search:"

    def __init__(self, url: str, ttl_seconds: int = 30) -> None:
        self.url = url
        self.ttl_seconds = ttl_seconds
        self.client: Redis | None = None

    async def connect(self) -> None:
        self.client = Redis.from_url(self.url, decode_responses=True)
        await self._client().ping()

    @classmethod
    def key_for(cls, value: str) -> str:
        digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
        return f"{cls.PREFIX}{digest}"

    async def get(self, key: str) -> dict[str, Any] | None:
        value = await self._client().get(self.key_for(key))
        return json.loads(value) if value else None

    async def set(self, key: str, value: dict[str, Any]) -> None:
        await self._client().setex(
            self.key_for(key),
            self.ttl_seconds,
            json.dumps(value, ensure_ascii=False),
        )

    async def clear(self) -> None:
        keys = [
            key async for key in self._client().scan_iter(match=f"{self.PREFIX}*")
        ]
        if keys:
            await self._client().delete(*keys)

    async def inspect(self, cursor: int = 0) -> dict[str, Any]:
        """One SCAN batch, with bounded previews and no writes or TTL refresh."""
        client = self._client()
        next_cursor, keys = await client.scan(
            cursor=cursor, match=f"{self.PREFIX}*", count=30, _type="string"
        )
        entries = []
        for key in dict.fromkeys(keys):
            # GETRANGE caps response size even if a cached document is large.
            raw = await client.execute_command(
                "GETRANGE", key, 0, 65535, NEVER_DECODE=True
            )
            # A byte-limited preview may end in the middle of a UTF-8 character.
            preview = raw.decode("utf-8", errors="replace")
            size = await client.strlen(key)
            ttl = await client.ttl(key)
            if ttl == -2:
                continue  # The short-lived key expired during inspection.
            truncated = size > 65536
            try:
                value = json.loads(preview) if not truncated else preview
            except json.JSONDecodeError:
                value = preview
            entries.append({
                "key": key, "ttl_seconds": ttl, "size_bytes": size,
                "value": value, "truncated": truncated,
            })
        return {"entries": entries, "next_cursor": next_cursor, "prefix": self.PREFIX}

    async def health(self) -> bool:
        return bool(await self._client().ping())

    async def close(self) -> None:
        if self.client is not None:
            await self.client.aclose()
            self.client = None

    def _client(self) -> Redis:
        if self.client is None:
            raise RuntimeError("Redis cache is not connected")
        return self.client
