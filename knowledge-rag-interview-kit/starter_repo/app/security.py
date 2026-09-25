"""Opt-in local bearer identities. Never trust identity headers or LLM roles."""
import json
import os
from contextvars import ContextVar
from dataclasses import dataclass

from fastapi import HTTPException


def enabled(name):
    return os.getenv(name, "false").lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Principal:
    user: str = "local"
    role: str = "admin"
    tenant: str = "local"
    clearance: int = 3


principal = ContextVar("principal", default=Principal())


def authenticate(header):
    if not enabled("SECURITY_ENABLED"):
        return Principal()
    identities = json.loads(os.getenv("API_IDENTITIES", "{}"))
    token = header.removeprefix("Bearer ") if header.startswith("Bearer ") else ""
    identity = identities.get(token)
    if not identity:
        raise HTTPException(401, "A configured bearer token is required")
    return Principal(**identity)


def require_role(*roles):
    if principal.get().role not in roles:
        raise HTTPException(403, "Your role cannot perform this operation")


def can_read(document, asset=None):
    if not enabled("SECURITY_ENABLED"):
        return True
    who = principal.get()
    metadata = document.metadata
    if metadata.get("tenant", "local") != who.tenant:
        return False
    if who.role == "admin":
        return True
    acl = metadata.get("acl", [])
    level = (asset or {}).get("security_level", metadata.get("security_level", 0))
    return (isinstance(level, int) and level <= who.clearance
            and isinstance(acl, list) and (not acl or who.user in acl))
