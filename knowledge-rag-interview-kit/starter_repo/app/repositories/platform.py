"""Small PostgreSQL JSON registry, shared by the learning labs (not a queue)."""
import json


class PlatformRepository:
    def __init__(self, pool):
        self.pool = pool

    async def initialize(self):
        await self.pool.execute("""
            CREATE TABLE IF NOT EXISTS platform_records (
                namespace TEXT NOT NULL, id TEXT NOT NULL, body JSONB NOT NULL,
                PRIMARY KEY (namespace, id)
            )
        """)

    async def get(self, namespace, identifier):
        value = await self.pool.fetchval(
            "SELECT body::text FROM platform_records WHERE namespace=$1 AND id=$2",
            namespace, identifier)
        return json.loads(value) if value else None

    async def put(self, namespace, identifier, body):
        await self.pool.execute("""
            INSERT INTO platform_records VALUES ($1,$2,$3::jsonb)
            ON CONFLICT (namespace,id) DO UPDATE SET body=EXCLUDED.body
        """, namespace, identifier, json.dumps(body, ensure_ascii=False))
        return body

    async def create_once(self, namespace, identifier, body):
        # The unique key is the write tool's durable idempotency boundary.
        await self.pool.execute("""
            INSERT INTO platform_records VALUES ($1,$2,$3::jsonb)
            ON CONFLICT (namespace,id) DO NOTHING
        """, namespace, identifier, json.dumps(body, ensure_ascii=False))
        return await self.get(namespace, identifier)

    async def list(self, namespace):
        rows = await self.pool.fetch(
            "SELECT body::text FROM platform_records WHERE namespace=$1 ORDER BY id",
            namespace)
        return [json.loads(row[0]) for row in rows]
