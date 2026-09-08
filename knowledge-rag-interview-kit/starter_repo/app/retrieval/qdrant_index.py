import hashlib

import httpx


class QdrantIndex:
    def __init__(self, url: str, embedding_model: str):
        self.client = httpx.AsyncClient(base_url=url, timeout=60)
        # Prevent accidentally mixing vectors from different embedding models.
        suffix = hashlib.sha256(embedding_model.encode()).hexdigest()[:12]
        self.path = f"/collections/knowledge_chunks_{suffix}"

    async def ensure(self, dimensions: int):
        response = await self.client.get(self.path)
        if response.status_code == 404:
            response = await self.client.put(self.path, json={
                "vectors": {"size": dimensions, "distance": "Cosine"},
            })
        else:
            response.raise_for_status()
            if response.json()["result"]["config"]["params"]["vectors"]["size"] != dimensions:
                raise ValueError("Embedding dimensions changed; use a new model tag")
        response.raise_for_status()

    async def replace(self, document_id: str, points: list[dict]):
        # Small demo: embed first, then replace; retries repair a partial write.
        await self.remove(document_id)
        for start in range(0, len(points), 64):
            response = await self.client.put(self.path + "/points", params={"wait": "true"},
                                            json={"points": points[start:start + 64]})
            response.raise_for_status()

    async def remove(self, document_id: str):
        response = await self.client.post(self.path + "/points/delete",
            params={"wait": "true"}, json={"filter": {"must": [
                {"key": "document_id", "match": {"value": document_id}},
            ]}})
        if response.status_code != 404:
            response.raise_for_status()

    async def query(self, vector, top_k, source, tags, score_threshold):
        conditions = [{"key": "tags", "match": {"value": tag}} for tag in tags]
        if source is not None:
            conditions.append({"key": "source", "match": {"value": source}})
        response = await self.client.post(self.path + "/points/query", json={
            "query": vector, "limit": top_k, "with_payload": True,
            "filter": {"must": conditions}, "score_threshold": score_threshold,
        })
        if response.status_code == 404:
            return []
        response.raise_for_status()
        return response.json()["result"]["points"]

    async def close(self):
        await self.client.aclose()
