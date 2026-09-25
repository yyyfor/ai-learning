"""Immutable governance snapshots; documents remain immutable source evidence."""
from datetime import date, datetime, timezone

from fastapi import HTTPException

from app.security import can_read, enabled, principal, require_role


def now():
    return datetime.now(timezone.utc).isoformat()


class GovernanceService:
    def __init__(self, store, documents):
        self.store, self.documents = store, documents

    async def document(self, identifier):
        doc = await self.documents.get(identifier)
        asset = await self.store.get("assets", identifier)
        if doc is None or not can_read(doc, asset):
            raise HTTPException(404, "Document not found")
        return doc

    async def save_draft(self, identifier, metadata):
        require_role("admin", "editor")
        await self.document(identifier)
        old = await self.store.get("assets", identifier)
        return await self._save(identifier, old, metadata.model_dump(mode="json"),
                                "draft", "edit", "Create/revise governance metadata")

    async def _save(self, identifier, old, fields, status, action, reason):
        history = (old or {}).get("history", [])
        version = (old or {}).get("version", 0) + 1
        snapshot = {**fields, "knowledge_id": identifier, "version": version,
                    "parent_version": version - 1 or None, "status": status,
                    "updated_at": now()}
        event = {"version": version, "action": action, "reason": reason,
                 "actor": principal.get().user, "at": now()}
        asset = {**snapshot, "history": [*history, snapshot],
                 "provenance_chain": [*(old or {}).get("provenance_chain", []), event]}
        return await self.store.put("assets", identifier, asset)

    async def get(self, identifier):
        await self.document(identifier)
        asset = await self.store.get("assets", identifier)
        if asset is None:
            raise HTTPException(404, "Register governance metadata first")
        return asset

    async def transition(self, identifier, request):
        require_role("admin", "approver" if request.action in {"approve", "publish"} else "editor")
        asset = await self.get(identifier)
        transitions = {"validate": ("draft", "validated"),
                       "approve": ("validated", "approved"),
                       "publish": ("approved", "published"),
                       "deprecate": ("published", "deprecated")}
        before, after = transitions[request.action]
        if asset["status"] != before:
            raise HTTPException(409, f"{request.action} requires {before} status")
        if request.action == "publish" and asset.get("expiry_date") and asset["expiry_date"] < date.today().isoformat():
            raise HTTPException(409, "Cannot publish expired knowledge")
        fields = {k: v for k, v in asset.items() if k not in {"history", "provenance_chain"}}
        return await self._save(identifier, asset, fields, after, request.action, request.reason)

    async def rollback(self, identifier, request):
        require_role("admin", "editor")
        asset = await self.get(identifier)
        snapshot = next((v for v in asset["history"] if v["version"] == request.version), None)
        if snapshot is None:
            raise HTTPException(404, "Version not found")
        # Never silently reactivate previously approved/expired content.
        return await self._save(identifier, asset, snapshot, "draft", "rollback", request.reason)

    @staticmethod
    def usable(asset):
        today = date.today().isoformat()
        return bool(asset and asset["status"] == "published"
                    and asset["effective_date"] <= today
                    and (not asset.get("expiry_date") or asset["expiry_date"] >= today))

    async def allowed_ids(self, published=True):
        assets = {a["knowledge_id"]: a for a in await self.store.list("assets")}
        return [d.id for d in await self.documents.all()
                if can_read(d, assets.get(d.id)) and
                (not published or not enabled("GOVERNANCE_ENABLED") or self.usable(assets.get(d.id)))]

    async def freshness(self):
        allowed = set(await self.allowed_ids(published=False))
        result = []
        for asset in await self.store.list("assets"):
            if asset["knowledge_id"] not in allowed:
                continue
            age = (datetime.now(timezone.utc) - datetime.fromisoformat(asset["updated_at"])).total_seconds()
            result.append({"knowledge_id": asset["knowledge_id"], "version": asset["version"],
                           "usable": self.usable(asset), "freshness_lag_seconds": round(age),
                           "freshness_score": round(max(0, 1 - age / (30 * 86400)), 3)})
        return result

    async def citation(self, request):
        doc = await self.document(request.document_id)
        asset = await self.store.get("assets", request.document_id)
        reasons = []
        # Chunking can normalize whitespace and add overlap across unit boundaries.
        if "".join(request.text.split()) not in "".join(doc.content.split()):
            reasons.append("quote_not_in_source")
        if request.version is not None and (not asset or asset["version"] != request.version):
            reasons.append("version_mismatch")
        if enabled("GOVERNANCE_ENABLED") and not self.usable(asset):
            reasons.append("not_currently_published")
        return {"valid": not reasons, "reasons": reasons, "document_id": doc.id,
                "version": asset["version"] if asset else None}
