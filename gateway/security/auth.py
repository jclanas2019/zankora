from __future__ import annotations
import secrets
from gateway.config import Settings

def constant_time_equals(a: str, b: str) -> bool:
    return secrets.compare_digest(a.encode("utf-8"), b.encode("utf-8"))

def verify_client_key(settings: Settings, provided: str | None) -> bool:
    if not settings.require_client_auth:
        return True
    if not provided:
        return False
    for k in settings.client_api_keys:
        if constant_time_equals(k, provided):
            return True
    return False
