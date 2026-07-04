# -*- coding: utf-8 -*-
"""Structured audit logger for platform account operations."""

from __future__ import annotations

import re
from typing import Any, Dict, Optional


SECRET_KEY_MARKERS = {
    "apikey",
    "authorization",
    "password",
    "secret",
    "token",
}
SECRET_VALUE_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9._-]{6,}\b"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._-]{8,}\b", re.IGNORECASE),
)


def _normalize_key(key: str) -> str:
    return "".join(ch for ch in key if ch.isalnum()).lower()


def _is_secret_key(key: str) -> bool:
    normalized = _normalize_key(key)
    if normalized in SECRET_KEY_MARKERS:
        return True
    return (
        normalized.endswith("apikey")
        or normalized.endswith("token")
        or "secret" in normalized
        or "password" in normalized
    )


def _redact_string(value: str) -> str:
    redacted = value
    for pattern in SECRET_VALUE_PATTERNS:
        redacted = pattern.sub("[REDACTED]", redacted)
    return redacted


def _redact_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "[REDACTED]" if _is_secret_key(str(key)) else _redact_value(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    if isinstance(value, tuple):
        return [_redact_value(item) for item in value]
    if isinstance(value, str):
        return _redact_string(value)
    return value


def redact_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
    return _redact_value(metadata or {})


class PlatformAuditLogger:
    def record(
        self,
        *,
        user_id: Optional[int],
        action: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        from src.storage import DatabaseManager

        DatabaseManager.get_instance().add_platform_audit_event(
            user_id=user_id,
            action=action,
            metadata=redact_metadata(metadata or {}),
        )

    def list_events(self, *, user_id: Optional[int] = None, limit: int = 100) -> list[dict]:
        from src.storage import DatabaseManager

        return DatabaseManager.get_instance().list_platform_audit_events(user_id=user_id, limit=limit)
